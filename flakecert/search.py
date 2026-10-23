"""Controlled search, ablation, and certificate emission."""

import json
import re
import time

from flakecert.cert import build_certificate, dump_cert
from flakecert.logs import header_lines, run_line
from flakecert.paths import BUDGET, CERTS, FLAKECERT_LOGS, SEED
from flakecert.runner import Session, run_schedule
from flakecert.scheduler import build_plan, observed_k
from flakecert.sources import SOURCE_SEED, active_sources
from flakecert.util import log

# Hypothesis prints the seed that reproduces a failure. Replaying with that
# seed is the random-seed knob, not a second copy of the same unseeded run.
_HYPOTHESIS_SEED = re.compile(r"--hypothesis-seed=(\d+)|@seed\((\d+)\)")

FAILURES = {"failed", "error"}


def _same(result, sig: str) -> bool:
    return result.outcome in FAILURES and result.sig == sig and sig not in ("", "-")


def hypothesis_seed(result) -> str:
    text = (getattr(result, "traceback", "") or "") + "\n" + (getattr(result, "stdout", "") or "")
    match = _HYPOTHESIS_SEED.search(text)
    if not match:
        return ""
    return match.group(1) or match.group(2) or ""


def _lock_hypothesis_seed(schedule, result, sources, run_one):
    """Rerun once with the seed Hypothesis names, when that seed is not already set.

    Returns the schedule/result to certify, plus a passing schedule if the
    seeded rerun passed instead.
    """
    if SOURCE_SEED not in sources:
        return schedule, result, None
    seed = hypothesis_seed(result)
    if not seed or str(schedule.get(SOURCE_SEED, "") or "") == seed:
        return schedule, result, None
    trial = dict(schedule)
    trial[SOURCE_SEED] = seed
    reproduced = run_one(trial, "flakecert")
    passed = trial if reproduced.outcome == "passed" else None
    if reproduced.outcome in FAILURES and reproduced.sig not in ("", "-"):
        return trial, reproduced, passed
    return schedule, result, passed


def _append(path, text: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")
        handle.flush()


def _record(path, method: str, index: int, schedule: dict, result) -> None:
    _append(path, "SCHEDULE run=%d %s" % (index, json.dumps(schedule, sort_keys=True)))
    _append(
        path,
        run_line(method, index, result.outcome, result.exc, result.sig, result.duration_s, result.node_id),
    )
    if result.traceback:
        _append(path, f"TRACEBACK run={index}")
        _append(path, result.traceback.rstrip("\n"))
        _append(path, f"ENDTRACEBACK run={index}")


def _json_equal(left, right) -> bool:
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def search_test(meta: dict, budget: int = BUDGET, no_failure_cap: int = 160) -> dict | None:
    test_id = meta["id"]
    node_id = meta["node_id"]
    sources = list(meta["sources"])
    plan, structured = build_plan(
        node_id,
        meta.get("file_nodes") or [node_id],
        meta.get("suite_nodes") or [],
        sources,
        budget,
        test_id,
    )
    log_path = FLAKECERT_LOGS / f"{test_id}.log"
    FLAKECERT_LOGS.mkdir(parents=True, exist_ok=True)
    lines = header_lines(meta, "flakecert")
    lines += [
        f"# seed: {SEED}",
        f"# sources: {','.join(sources)}",
        f"# budget: {budget}",
        f"# plan: {len(plan)}",
        f"# structured: {structured}",
        f"# order_scope: {meta.get('order_scope', '')}",
        "# network: none",
        "# netns_cmd: ip link set lo up",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    timeout_s = int(meta.get("timeout_s") or 180)
    base_args = list(meta.get("pytest_args") or ["-v", "--tb=short", "-p", "no:cacheprovider"])
    executed = []
    pass_schedule = None
    pending = None
    banned = set()
    seen_failure = False
    started = time.time()
    wall = int(meta.get("wall_s") or 2400)
    index = 0
    cert = None

    def _try_certify(session, run_one):
        nonlocal cert, pending
        if pending is None or pass_schedule is None or index < 2:
            return False
        fail_schedule, fail_result = pending
        if fail_result.sig in banned:
            pending = None
            return False
        made = _certify(
            session,
            meta,
            sources,
            base_args,
            timeout_s,
            log_path,
            executed,
            pass_schedule,
            fail_schedule,
            fail_result,
            run_one,
        )
        if made is not None:
            cert = made
            _append(log_path, f"SEARCH_STOP reason=certified index={index}")
            return True
        banned.add(fail_result.sig)
        pending = None
        _append(log_path, f"SEARCH_CONTINUE banned={fail_result.sig}")
        return False

    with Session(test_id, meta["image_tag"]) as session:
        plan_iter = iter(plan)

        def run_one(schedule, method):
            nonlocal index
            index += 1
            result = run_schedule(session, node_id, schedule, base_args, timeout_s)
            executed.append((schedule, result))
            _record(log_path, method, index, schedule, result)
            log(f"{test_id} {method} {index} {result.outcome} {result.exc}")
            return result

        while index < budget and cert is None:
            if time.time() - started > wall and index >= 8:
                _append(log_path, f"SEARCH_STOP reason=wall index={index}")
                break
            try:
                schedule = next(plan_iter)
            except StopIteration:
                _append(log_path, f"SEARCH_STOP reason=plan_exhausted index={index}")
                break
            result = run_one(schedule, "flakecert")
            if pass_schedule is None and result.outcome == "passed":
                pass_schedule = schedule
            if result.outcome in FAILURES and result.sig not in ("", "-") and result.sig not in banned:
                schedule, result, seeded_pass = _lock_hypothesis_seed(schedule, result, sources, run_one)
                if pass_schedule is None and seeded_pass is not None:
                    pass_schedule = seeded_pass
                seen_failure = True
                if result.sig not in banned:
                    pending = (schedule, result)
            if _try_certify(session, run_one):
                break
            past_structured = index >= structured
            past_cap = index >= no_failure_cap
            if past_cap and not seen_failure:
                _append(log_path, f"SEARCH_STOP reason=no_failure_cap index={index}")
                break
            if past_structured and (pass_schedule is None or pending is None):
                if not seen_failure:
                    reason = "no_failure"
                elif pass_schedule is None:
                    reason = "no_passing_schedule"
                else:
                    reason = "replay_or_ablation_failed"
                _append(log_path, f"SEARCH_STOP reason={reason} index={index}")
                break

        if cert is None:
            reason = "no_failure"
            if any(item[1].outcome in FAILURES for item in executed) and pass_schedule is None:
                reason = "no_passing_schedule"
            elif any(item[1].outcome in FAILURES for item in executed):
                reason = "replay_or_ablation_failed"
            _append(log_path, f"CERT id={test_id} certified=no reason={reason}")

        failures = sum(1 for _sched, item in executed if item.outcome in FAILURES)
        _append(log_path, "FLAKECERT_SUMMARY id=%s runs=%d failures=%d" % (test_id, len(executed), failures))
    return cert


def _certify(session, meta, sources, base_args, timeout_s, log_path, executed, pass_schedule, fail_schedule, fail_result, run_one):
    test_id = meta["id"]
    node_id = meta["node_id"]
    target_sig = fail_result.sig
    runs_to = None
    for offset, (_sched, result) in enumerate(executed, start=1):
        if _same(result, target_sig):
            runs_to = offset
            break
    minimized = dict(fail_schedule)
    necessary = []
    for source in sources:
        if _json_equal(fail_schedule.get(source), pass_schedule.get(source)):
            continue
        trial = dict(minimized)
        trial[source] = pass_schedule.get(source, "")
        result = run_one(trial, "flakecert")
        if _same(result, target_sig):
            minimized = trial
            _append(log_path, f"ABLATE source={source} necessary=no")
        else:
            necessary.append(source)
            _append(log_path, f"ABLATE source={source} necessary=yes")
    if not necessary:
        _append(log_path, f"CERT id={test_id} certified=no reason=d_unattributed sig={target_sig}")
        return None
    replays = []
    for _ in range(3):
        replays.append(run_one(minimized, "flakecert-replay"))
    matched = sum(1 for item in replays if _same(item, target_sig))
    _append(log_path, f"REPLAY id={test_id} matched={matched}/3 sig={target_sig}")
    if matched != 3:
        return None
    if not runs_to:
        return None
    k = max(1, observed_k([item[0] for item in executed], sources))
    cert = build_certificate(
        row={
            "id": test_id,
            "project_url": meta["project_url"],
            "sha": meta["sha"],
            "pytest_id": meta["pytest_id"],
        },
        node_id=node_id,
        image_digest=meta["image_digest"],
        image_tag=meta["image_tag"],
        pip_freeze_sha=meta["pip_freeze_sha"],
        python_version=meta.get("python", ""),
        sources=sources,
        k=k,
        d=len(necessary),
        schedule=minimized,
        order_scope=meta.get("order_scope", ""),
        exc=fail_result.exc,
        sig=target_sig,
        runs_to_failure=runs_to,
        pytest_args=base_args,
        tb=fail_result.traceback,
    )
    CERTS.mkdir(parents=True, exist_ok=True)
    (CERTS / f"{test_id}.json").write_text(dump_cert(cert), encoding="utf-8")
    _append(
        log_path,
        "CERT id=%s certified=yes d=%s m=%s k=%s per_run_lower=%s runs_to_failure=%s sig=%s"
        % (test_id, cert["d"], cert["m"], cert["k"], cert["bound"]["per_run_lower"], runs_to, target_sig),
    )
    return cert


def sources_for_text(thread_like: bool) -> list[str]:
    return active_sources(thread_like)
