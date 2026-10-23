"""S4 verdicts.

NOT_FIXED means every rep failed, the reps share one signature, and
failed_ids is exactly [victim_id] (the polluters passed). The signature is
pass/fail, first error class, example order, and failed ids. The error
message line is not part of it.
POLLUTER_FAILED means a polluter id is among failed_ids on any rep.
FIXED means every rep passed and the reps share one signature.
CERTIFIED means base is NOT_FIXED, head is FIXED, arm C passed 3/3 at
both commits, and no arm disagreed with itself.
CONTROL means A is NOT_FIXED at both commits.
REJECTED means a polluter failed.
"""

from __future__ import annotations

from tools.certify_rspec.order_guard import INVALID_ORDER
from tools.certify_rspec.parse_rspec import norm_id

FIXED = "FIXED"
NOT_FIXED = "NOT_FIXED"
DISAGREEMENT = "DISAGREEMENT"
POLLUTER_FAILED = "POLLUTER_FAILED"
CERTIFIED = "CERTIFIED"
CONTROL = "CONTROL"
UNRESOLVED = "UNRESOLVED"
REJECTED = "REJECTED"


def _failed(run: dict) -> bool:
    return run.get("exit_code") != 0 or (run.get("failure_count") or 0) > 0


def _order_blocked(runs: list[dict]) -> bool:
    return any(run.get("order_status") == INVALID_ORDER for run in runs)


def _norm_ids(ids) -> list[str]:
    return [norm_id(item) for item in ids]


def signature(run: dict) -> tuple:
    # Message text stays out. It can change while the class and ids do not.
    return (
        _failed(run),
        run.get("first_error_class"),
        tuple(run.get("order") or []),
        tuple(run.get("failed_ids") or []),
    )


def _polluter_failed(run: dict, polluter_ids: list[str]) -> bool:
    failed = set(_norm_ids(run.get("failed_ids") or []))
    return any(norm_id(item) in failed for item in polluter_ids)


def arm_stable(runs: list[dict]) -> tuple[bool, tuple | None]:
    if len(runs) != 3:
        return False, None
    sigs = [signature(run) for run in runs]
    if any(item != sigs[0] for item in sigs):
        return False, None
    return True, sigs[0]


def stable_outcome_verdict(runs: list[dict], victim_id: str, polluter_ids: list[str]) -> str:
    if _order_blocked(runs):
        return INVALID_ORDER
    if any(_polluter_failed(run, polluter_ids) for run in runs):
        return POLLUTER_FAILED
    stable, sig = arm_stable(runs)
    if not stable or sig is None:
        return DISAGREEMENT
    failed, error_class, _order, ids = sig
    if not failed:
        return FIXED
    victim_only = _norm_ids(ids) == [norm_id(victim_id)]
    polluters_passed = not any(norm_id(item) in set(_norm_ids(ids)) for item in polluter_ids)
    if victim_only and polluters_passed and error_class:
        return NOT_FIXED
    return DISAGREEMENT


def _c_passes(runs: list[dict]) -> bool:
    if _order_blocked(runs):
        return False
    stable, sig = arm_stable(runs)
    return bool(stable and sig is not None and sig[0] is False)


def _sides_stable(base_runs: dict, head_runs: dict) -> bool:
    for side in (base_runs, head_runs):
        for arm in ("A", "B", "C"):
            stable, _sig = arm_stable(side[arm])
            if not stable:
                return False
    return True


def _any_polluter_failed(base_runs: dict, head_runs: dict, polluter_ids: list[str]) -> bool:
    for side in (base_runs, head_runs):
        for arm in ("A", "B", "C"):
            for run in side[arm]:
                if run.get("order_status") == INVALID_ORDER:
                    continue
                if _polluter_failed(run, polluter_ids):
                    return True
    return False


def judge(base_runs: dict, head_runs: dict, victim_id: str, polluter_ids: list[str]) -> dict:
    base_verdict = stable_outcome_verdict(base_runs["A"], victim_id, polluter_ids)
    head_verdict = stable_outcome_verdict(head_runs["A"], victim_id, polluter_ids)
    plain = {
        "base": stable_outcome_verdict(base_runs["B"], victim_id, polluter_ids),
        "head": stable_outcome_verdict(head_runs["B"], victim_id, polluter_ids),
    }
    disagreement = not _sides_stable(base_runs, head_runs)
    c_ok = _c_passes(base_runs["C"]) and _c_passes(head_runs["C"])
    if _any_polluter_failed(base_runs, head_runs, polluter_ids):
        label = REJECTED
    elif base_verdict == NOT_FIXED and head_verdict == FIXED and c_ok and not disagreement:
        label = CERTIFIED
    elif base_verdict == NOT_FIXED and head_verdict == NOT_FIXED:
        label = CONTROL
    else:
        label = UNRESOLVED
    return {
        "verdicts": {"base": base_verdict, "head": head_verdict},
        "plain_retry_verdict": plain,
        "rep_disagreement": disagreement,
        "c_passes": c_ok,
        "label": label,
    }
