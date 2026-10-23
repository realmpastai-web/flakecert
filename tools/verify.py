#!/usr/bin/env python3.11
"""make verify: gates from committed logs, plus live certificate replays.

--replay-skip does not run live replay. The certificates check is SKIP with
pass null: not a 3/3 pass, and not an N/3 mismatch. Plain make verify still
replays every certificate.
"""

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakecert.cert import check_bound, load_cert, schedule_dict
from flakecert.effective import committed_effective_text, effective_text, evidence_path, load_swaps
from flakecert.effective import derive, load_frozen
from flakecert.ingest import PINNED_SAMPLE_SHA
from flakecert.logs import method_runs, parse_runs
from flakecert.paths import (
    BASELINE_LOGS,
    CERTS,
    COMPARATOR_CSV,
    EVIDENCE,
    FLAKECERT_LOGS,
    FROZEN_CSV,
    FROZEN_SHA256,
    HASHES,
    README,
    RESULTS,
    ROOT,
    SHA256SUMS,
    SUMMARY,
    SUMMARY_BUILD,
    SWAPS,
    VERIFY_LOG,
    VERIFY_REPORT,
)
from flakecert.preflight import compare_deps, compare_resolve, run_deps, run_resolve
from flakecert.runner import Session, pip_freeze, python_version, run_schedule
from flakecert.summary import build_summary, numeric_tokens
from flakecert.util import freeze_sha, log, sha256_file

REAL = {"passed", "failed", "error", "skipped"}


def _gate(ok: bool, actual, expected=None) -> dict:
    item = {"pass": bool(ok), "actual": actual}
    if expected is not None:
        item["expected"] = expected
    return item


def _completed_replay(runs: list[dict]) -> bool:
    return len(runs) == 3 and all("outcome" in item for item in runs)


def _replay_record_from_runs(runs: list[dict]) -> dict:
    """An N/3 record exists only after three pytest outcomes were recorded."""
    if _completed_replay(runs):
        good = sum(1 for item in runs if item.get("ok"))
        return {"matched": f"{good}/3", "runs": runs}
    detail = "replay did not finish"
    if runs and runs[0].get("detail"):
        detail = str(runs[0]["detail"])
    return {"status": "unavailable", "pass": None, "detail": detail, "runs": runs}


def _replay_unavailable(detail: str) -> dict:
    return {"status": "unavailable", "pass": None, "detail": detail}


def _replay_skip_record() -> dict:
    return {"status": "skip", "pass": None, "detail": "SKIP live replay not run"}


def _replay_say(cert_id: str, record: dict) -> str:
    if record.get("status") == "skip":
        return f"replay {cert_id} SKIP"
    if "matched" in record:
        return f"replay {cert_id} {record['matched']}"
    return f"replay {cert_id} NOT_RUN {record.get('detail', 'replay did not finish')}"


def _certificates_gate(
    replay_skip: bool,
    certified_ok: list,
    bound_bad: list,
    cert_paths: list,
    replay_actual: dict,
) -> dict:
    if replay_skip:
        return {
            "pass": None,
            "status": "skip",
            "actual": "SKIP live replay not run",
            "expected": ">= 10/20 each 3/3",
        }
    unavailable = [
        path.stem
        for path in cert_paths
        if replay_actual.get(path.stem, {}).get("status") == "unavailable"
    ]
    ok = (
        len(certified_ok) >= 10
        and len(bound_bad) == 0
        and all(replay_actual.get(path.stem, {}).get("matched") == "3/3" for path in cert_paths)
    )
    actual = f"{len(certified_ok)}/20"
    if unavailable:
        actual += "; NOT_RUN " + ",".join(unavailable)
    return _gate(ok, actual, ">= 10/20 each 3/3")


_CHECK_ALREADY_IN_GATES = {
    "a_frozen_hash",
    "b_effective_set",
    "c_swaps_logged",
    "e_cert_replay",
    "f_bounds",
    "j_readme_ingest",
}


def _failures(gates: dict, checks: dict) -> list[str]:
    failed = []
    for name, gate in gates.items():
        # A skipped gate is not a pass. pass true on a skip is a broken report.
        if gate.get("status") == "skip":
            if gate.get("pass") is True:
                failed.append(name)
            continue
        if not gate["pass"]:
            failed.append(name)
    for name, check in checks.items():
        if check.get("status") == "skip":
            if check.get("pass") is True:
                failed.append(name)
            continue
        if not check.get("pass"):
            if name not in _CHECK_ALREADY_IN_GATES:
                failed.append(name)
    return failed


def _offline_ok(test_id: str, hashes: str) -> bool:
    path = BASELINE_LOGS / f"{test_id}.log"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    if not any(line.startswith(f"image {test_id} ") for line in hashes.splitlines()):
        return False
    if "ip link set lo up" not in text or "lo_set=0" not in text:
        return False
    if "network: none" not in text and "--network none" not in text:
        return False
    runs = method_runs(parse_runs(text), "baseline")
    return any(run["outcome"] in REAL for run in runs)


def _baseline_complete(test_id: str) -> int:
    path = BASELINE_LOGS / f"{test_id}.log"
    if not path.exists():
        return 0
    return len(method_runs(parse_runs(path.read_text(encoding="utf-8", errors="replace")), "baseline"))


def _replay(cert: dict) -> list[dict]:
    # Replay identity is python version, pip freeze, node id, and schedule.
    # image_digest stays on the certificate and is not a gate: a local
    # `docker image inspect` id changes on every rebuild.
    live_freeze = freeze_sha(pip_freeze(cert["image_tag"]))
    if live_freeze != cert["pip_freeze_sha"]:
        return [{"ok": False, "detail": "pip_freeze_mismatch", "sig": "-"}]
    live_python = python_version(cert["image_tag"])
    if live_python != cert.get("python"):
        return [{"ok": False, "detail": "python_mismatch", "sig": "-"}]
    schedule = schedule_dict(cert)
    args = list(cert.get("pytest_args") or ["-v", "--tb=short", "-p", "no:cacheprovider"])
    out = []
    with Session(cert["id"], cert["image_tag"]) as session:
        for _ in range(3):
            result = run_schedule(session, cert["node_id"], schedule, args, 300)
            ok = result.outcome in {"failed", "error"} and result.sig == cert["expected_failure"]["sig"]
            out.append({"ok": ok, "sig": result.sig, "outcome": result.outcome, "exc": result.exc})
    return out


def _swaps_ok() -> tuple[bool, str]:
    swaps = load_swaps()
    bad = []
    for swap in swaps:
        name = (swap.get("evidence_file") or "").strip()
        expected = (swap.get("evidence_sha256") or "").strip()
        if not name or not expected:
            bad.append(swap.get("swap_id", "?") + " missing evidence columns")
            continue
        path = evidence_path(name)
        if not path.is_file():
            bad.append(f"{swap['swap_id']} missing {name}")
            continue
        got = sha256_file(path)
        if got != expected:
            bad.append(f"{swap['swap_id']} sha {got} != {expected}")
    rows = load_frozen()
    mains, reserves = derive(rows, swaps)
    removed = {(swap.get("removed_id") or "").strip() for swap in swaps}
    frozen_ids = {row["id"] for row in rows}
    present = set(mains) | set(reserves)
    dropped = frozen_ids - present
    unlogged = sorted(item for item in dropped if item not in removed)
    if unlogged:
        bad.append("unlogged " + ",".join(unlogged))
    if bad:
        return False, "; ".join(bad)
    return True, f"0 unlogged; {len(swaps)} rows matched"


def _ledger_rows_ok() -> tuple[bool, str]:
    if not RESULTS.exists():
        return False, "results.csv missing"
    missing = []
    with RESULTS.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            path = Path(row["log"])
            if not path.is_file():
                path = Path(__file__).resolve().parents[1] / row["log"]
            if not path.is_file():
                missing.append(row["log"])
    if missing:
        return False, f"missing logs {len(set(missing))}"
    return True, "every results row log exists"


def _comparator_rows() -> list[dict]:
    if not COMPARATOR_CSV.exists():
        return []
    with COMPARATOR_CSV.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _summary_ok() -> tuple[bool, str]:
    summary, build_log = build_summary()
    if not SUMMARY.exists() or SUMMARY.read_text(encoding="utf-8") != summary:
        return False, "SUMMARY.md does not match logs"
    if not SUMMARY_BUILD.exists() or SUMMARY_BUILD.read_text(encoding="utf-8") != build_log:
        return False, "summary-build.log does not match logs"
    haystack = build_log
    if BASELINE_LOGS.exists():
        for path in BASELINE_LOGS.glob("*.log"):
            haystack += path.read_text(encoding="utf-8", errors="replace")
    if FLAKECERT_LOGS.exists():
        for path in FLAKECERT_LOGS.glob("*.log"):
            haystack += path.read_text(encoding="utf-8", errors="replace")
    missing = [token for token in numeric_tokens(summary) if token not in haystack]
    if missing:
        return False, "numbers missing from logs " + ",".join(missing[:8])
    return True, "summary regenerated from logs"


def _readme_claim_text(text: str) -> str:
    """Drop the ingest transcript before the ledger-number scan.

    Those digits belong to make ingest, not SUMMARY.md. The readme_ingest
    gate checks the dropped block against a fresh run.
    """
    return re.sub(
        r"<!-- INGEST:BEGIN -->.*?<!-- INGEST:END -->",
        "",
        text,
        flags=re.DOTALL,
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _render_readme_ingest_block(transcript: str) -> str:
    """Wrap make-ingest stdout the way the README block was written.

    Heading, the pinned make command, then a text fence around that stdout.
    The stdout is not edited. Nothing in it is a timestamp, and the command
    lines use repo-relative paths.
    """
    return (
        "<!-- INGEST:BEGIN -->\n"
        "## Feeding FlakeCert from Buildkite/CircleCI/GitLab\n"
        "\n"
        f"`make ingest SHA={PINNED_SAMPLE_SHA}`\n"
        "\n"
        "```text\n"
        + transcript.rstrip("\n")
        + "\n```\n"
        "<!-- INGEST:END -->\n"
    )


def _extract_readme_ingest_block(text: str) -> str | None:
    matches = re.findall(
        r"<!-- INGEST:BEGIN -->.*?<!-- INGEST:END -->\n?",
        text,
        flags=re.DOTALL,
    )
    if len(matches) != 1:
        return None
    return matches[0]


def _pinned_ingest_stdout() -> tuple[int, str, str]:
    """Run top-level `make ingest` on docs/inputs/flakecert-ingest/samples.

    make verify leaves MAKELEVEL=1 in the environment. A nested make then
    prints Entering/Leaving directory lines that contain the absolute
    checkout path. Those lines are not ingest output, so they are not
    stripped afterwards: MAKELEVEL, MAKEFLAGS, and MFLAGS are removed and
    make is started as a top-level command, matching the README capture.

    PYTHON is removed so the echoed recipe stays the Makefile default
    (python3.11). An ambient PYTHON= would change the command line only.
    """
    env = os.environ.copy()
    for key in ("MAKELEVEL", "MAKEFLAGS", "MFLAGS", "PYTHON"):
        env.pop(key, None)
    try:
        proc = subprocess.run(
            ["make", "ingest", f"SHA={PINNED_SAMPLE_SHA}"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        return 127, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr


def _readme_ingest_ok(text: str | None = None) -> tuple[bool, str]:
    if text is None:
        if not README.exists():
            return False, "README missing"
        text = README.read_text(encoding="utf-8")
    found = _extract_readme_ingest_block(text)
    if found is None:
        return False, "README ingest block missing or duplicated"
    code, stdout, stderr = _pinned_ingest_stdout()
    if code != 0:
        detail = (stderr or stdout or "no output").strip()
        return False, "make ingest failed: " + detail
    fresh = _render_readme_ingest_block(stdout)
    if found != fresh:
        return (
            False,
            "README ingest block differs from make ingest "
            f"readme={_sha256_text(found)} fresh={_sha256_text(fresh)}",
        )
    return True, "README ingest block matches make ingest sha256=" + _sha256_text(found)


def _fresh_verdict_text() -> str:
    """Re-run the audit on the pinned sample. Same bytes as `make audit`."""
    from flakecert.verdict_audit import audit, dumps_audit

    sample_path = README.parent / "inputs/flakecert-verdict-audit/sample/dd-test-run.json"
    doc = json.loads(sample_path.read_text(encoding="utf-8"))
    return dumps_audit(audit(doc))


def _verdict_quote(text: str) -> tuple[str, str] | None:
    """Split out the make-audit quote. Ledger numbers are scanned on the rest.

    The quote is accepted only when it is byte-identical to a fresh audit of
    the pinned sample. Those counts are not ledger counts.
    """
    begin = "<!-- AUDIT:BEGIN -->"
    end = "<!-- AUDIT:END -->"
    start = text.find(begin)
    stop = text.find(end)
    if start < 0 or stop < start:
        return None
    raw = text[start + len(begin) : stop].strip("\n")
    lines = raw.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    quote = "\n".join(lines)
    if quote and not quote.endswith("\n"):
        quote += "\n"
    scanned = text[:start] + text[stop + len(end) :]
    return quote, scanned


def _readme_numbers_ok(text: str, summary: str) -> tuple[bool, str]:
    if summary.strip() not in text:
        return False, "README does not contain SUMMARY.md"
    quoted = _verdict_quote(text)
    if quoted is None:
        return False, "README missing verdict audit quote"
    quote, scanned = quoted
    if quote != _fresh_verdict_text():
        return False, "README verdict audit quote does not match fresh make audit output"
    summary_tokens = set(numeric_tokens(summary))
    # Ingest digits are checked by the readme_ingest gate, not against SUMMARY.
    extra = [token for token in numeric_tokens(_readme_claim_text(scanned)) if token not in summary_tokens]
    if extra:
        return False, "README numbers outside SUMMARY " + ",".join(extra[:8])
    return True, "README numbers are a subset of SUMMARY.md"


def _readme_ok(summary: str) -> tuple[bool, str]:
    if not README.exists():
        return False, "README missing"
    text = README.read_text(encoding="utf-8")
    return _readme_numbers_ok(text, summary)


def _committed_preflight_is_online(path: Path | None = None) -> bool:
    """True when the committed report recorded a matching online preflight."""
    path = VERIFY_REPORT if path is None else path
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    pre = data.get("checks", {}).get("d_resolve_preflight")
    if not isinstance(pre, dict):
        return False
    return pre.get("status") == "match" and pre.get("pass") is True


def _evidence_write_paths(offline: bool) -> tuple[Path, Path, bool]:
    """Return (log, report, protected).

    An --offline run must not replace a committed online verify report.
    It still writes copies under evidence/offline/ (gitignored).
    """
    if offline and _committed_preflight_is_online():
        dest = VERIFY_LOG.parent / "offline"
        dest.mkdir(parents=True, exist_ok=True)
        return dest / "verify.log", dest / "verify-report.json", True
    VERIFY_LOG.parent.mkdir(parents=True, exist_ok=True)
    return VERIFY_LOG, VERIFY_REPORT, False


def _write_sums() -> None:
    paths = [
        HASHES,
        SWAPS,
        RESULTS,
        SUMMARY,
        SUMMARY_BUILD,
        COMPARATOR_CSV,
        EVIDENCE / "resolve-check.log",
        EVIDENCE / "deps-preflight.log",
        EVIDENCE / "effective-set.txt",
        VERIFY_LOG,
        VERIFY_REPORT,
    ]
    if BASELINE_LOGS.exists():
        paths.extend(sorted(BASELINE_LOGS.glob("*.log")))
    if FLAKECERT_LOGS.exists():
        paths.extend(sorted(FLAKECERT_LOGS.glob("*.log")))
    if CERTS.exists():
        paths.extend(sorted(CERTS.glob("*.json")))
    lines = []
    for path in paths:
        if not path.exists():
            continue
        # Paths are relative to evidence/ so `cd evidence && sha256sum -c SHA256SUMS` resolves them.
        rel = Path(os.path.relpath(path.resolve(), SHA256SUMS.parent.resolve())).as_posix()
        lines.append(f"{sha256_file(path)}  {rel}")
    SHA256SUMS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    offline = "--offline" in sys.argv
    replay_skip = "--replay-skip" in sys.argv
    lines = []

    def say(msg: str) -> None:
        lines.append(msg)
        log(msg)

    frozen = sha256_file(FROZEN_CSV)
    mains, _reserves = derive(load_frozen(), load_swaps())
    derived = effective_text()
    committed = committed_effective_text()
    swaps_ok, swaps_actual = _swaps_ok()
    hashes = HASHES.read_text(encoding="utf-8") if HASHES.exists() else ""

    if offline:
        preflight = {"status": "skip", "pass": False, "actual": "SKIP --offline"}
        say("SKIP resolve-check offline")
        say("SKIP deps-preflight offline")
    else:
        try:
            resolve_text = run_resolve()
            deps_text = run_deps()
            ok_r, msg_r = compare_resolve(resolve_text)
            ok_d, msg_d = compare_deps(deps_text)
            preflight = {
                "status": "match" if ok_r and ok_d else "fail",
                "pass": bool(ok_r and ok_d),
                "actual": f"{msg_r}; {msg_d}",
            }
            say(preflight["actual"])
        except Exception as exc:
            preflight = {"status": "fail", "pass": False, "actual": f"preflight error {exc}"}
            say(preflight["actual"])

    offline_ids = [test_id for test_id in mains if _offline_ok(test_id, hashes)]
    baseline_counts = {test_id: _baseline_complete(test_id) for test_id in mains}

    cert_paths = sorted(CERTS.glob("*.json")) if CERTS.exists() else []
    replay_actual = {}
    certified_ok = []
    bound_bad = []
    if replay_skip:
        say("SKIP live certificate replay; pass is null")
    for path in cert_paths:
        cert = load_cert(path)
        ok_bound, bound_msg = check_bound(cert)
        if not ok_bound:
            bound_bad.append(f"{cert['id']} {bound_msg}")
        say(f"replay {cert['id']}")
        if replay_skip:
            record = _replay_skip_record()
        else:
            try:
                runs = _replay(cert)
            except Exception as exc:
                record = _replay_unavailable(str(exc))
            else:
                record = _replay_record_from_runs(runs)
        replay_actual[cert["id"]] = record
        say(_replay_say(cert["id"], record))
        if record.get("matched") == "3/3" and ok_bound:
            certified_ok.append(cert["id"])

    comp_rows = _comparator_rows()
    comp_ids = {row["id"] for row in comp_rows}
    comp_pass = [row["id"] for row in comp_rows if row.get("result") == "pass"]
    missing_comp = [path.stem for path in cert_paths if path.stem not in comp_ids]

    summary_ok, summary_msg = _summary_ok()
    summary_text = SUMMARY.read_text(encoding="utf-8") if SUMMARY.exists() else ""
    readme_ok, readme_msg = _readme_ok(summary_text if summary_ok else build_summary()[0])
    readme_ingest_ok, readme_ingest_msg = _readme_ingest_ok()
    ledger_ok, ledger_msg = _ledger_rows_ok()

    by_id = {row["id"]: row for row in load_frozen()}
    categories = {}
    for name in ("NOD", "OD-Vic", "NIO"):
        ids = [test_id for test_id in mains if by_id[test_id]["category"] == name]
        categories[name] = {
            "tests": len(ids),
            "ids": ids,
            "offline": [test_id for test_id in ids if test_id in offline_ids],
            "certified_replay_3_of_3": [test_id for test_id in ids if test_id in certified_ok],
        }

    gates = {
        "frozen_hash": _gate(frozen == FROZEN_SHA256, frozen, FROZEN_SHA256),
        "effective_set": _gate(derived == committed, "derived == committed" if derived == committed else "mismatch"),
        "swaps_logged": _gate(swaps_ok, swaps_actual),
        "offline_run": _gate(len(offline_ids) >= 15, f"{len(offline_ids)}/20", ">= 15/20"),
        "certificates": _certificates_gate(
            replay_skip, certified_ok, bound_bad, cert_paths, replay_actual
        ),
        "blind_comparator": _gate(len(comp_pass) >= 8 and not missing_comp, f"{len(comp_pass)}/{len(cert_paths)}", ">= 8"),
        "bounds": _gate(
            not bound_bad,
            f"{len(cert_paths) - len(bound_bad)}/{len(cert_paths)}",
            "100%",
        ),
        "baseline_denominator": _gate(
            all(count == 100 for count in baseline_counts.values()) and len(baseline_counts) == 20,
            {test_id: count for test_id, count in baseline_counts.items() if count != 100} or "100/100 x20",
            "100 reruns for every main test",
        ),
        "summary_traceable": _gate(summary_ok, summary_msg),
        "readme_ingest": _gate(readme_ingest_ok, readme_ingest_msg),
    }
    checks = {
        "a_frozen_hash": gates["frozen_hash"],
        "b_effective_set": gates["effective_set"],
        "c_swaps_logged": gates["swaps_logged"],
        "d_resolve_preflight": preflight,
        "e_cert_replay": (
            {"pass": None, "status": "skip", "actual": replay_actual}
            if replay_skip
            else {"pass": gates["certificates"]["pass"], "actual": replay_actual}
        ),
        "f_bounds": {"pass": gates["bounds"]["pass"], "actual": bound_bad or "100%"},
        "g_ledger_logs": _gate(ledger_ok, ledger_msg),
        "h_comparator": _gate(not missing_comp, "present" if not missing_comp else ",".join(missing_comp)),
        "i_readme_numbers": _gate(readme_ok, readme_msg),
        "j_readme_ingest": gates["readme_ingest"],
    }
    report = {
        "gates": gates,
        "checks": checks,
        "categories": categories,
        "offline_ids": offline_ids,
        "certified_ids": certified_ok,
    }
    if replay_skip:
        report["live_replay"] = {"status": "skip", "pass": None}
    # A skip is not a pass. Preflight --offline and --replay-skip both use status skip.
    failed = _failures(gates, checks)
    say("GATES " + json.dumps({key: value["pass"] for key, value in gates.items()}))
    log_path, report_path, protected = _evidence_write_paths(offline)
    text = json.dumps(report, indent=2) + "\n"
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report_path.write_text(text, encoding="utf-8")
    if not protected:
        _write_sums()
    say(f"wrote {report_path}")
    if protected:
        say("kept committed online evidence; --offline wrote evidence/offline/")
    # The lines after the file was written are not in verify.log. Rewrite so the
    # file matches what this process printed, then refresh the sums entry.
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not protected:
        _write_sums()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
