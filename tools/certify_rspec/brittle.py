"""BRITTLE certificate rule.

BRITTLE_CERTIFIED iff at base the victim alone fails 3/3 with one error
class, the enabler set then the victim in defined order passes the victim
3/3, and at head the victim alone passes 3/3.
"""

from __future__ import annotations

from tools.certify_rspec.classify import alone_passed
from tools.certify_rspec.order_guard import INVALID_ORDER
from tools.certify_rspec.parse_rspec import norm_id

BRITTLE_CERTIFIED = "BRITTLE_CERTIFIED"


def _failed(run: dict) -> bool:
    return run.get("exit_code") != 0 or (run.get("failure_count") or 0) > 0


def victim_passed(run: dict, victim_id: str) -> bool:
    status = run.get("victim_status")
    if status is not None:
        return status == "passed"
    target = norm_id(victim_id)
    failed = {norm_id(item) for item in run.get("failed_ids") or []}
    if target in failed:
        return False
    return not _failed(run)


def stable_alone_failure(runs: list[dict]) -> str | None:
    """Shared error class when every rep fails, else None."""
    if len(runs) != 3:
        return None
    classes = []
    for run in runs:
        if not _failed(run):
            return None
        klass = run.get("first_error_class")
        if not isinstance(klass, str) or not klass:
            return None
        classes.append(klass)
    if len(set(classes)) != 1:
        return None
    return classes[0]


def _order_blocked(runs: list[dict]) -> bool:
    return any(run.get("order_status") == INVALID_ORDER for run in runs)


def brittle_verdict(
    base_alone: list[dict],
    base_enabled: list[dict],
    head_alone: list[dict],
    victim_id: str,
) -> dict:
    if _order_blocked(base_alone) or _order_blocked(base_enabled) or _order_blocked(head_alone):
        return {"label": "REJECTED", "reason": "INVALID_ORDER", "error_class": None}
    error_class = stable_alone_failure(base_alone)
    enabled_ok = len(base_enabled) == 3 and all(victim_passed(run, victim_id) for run in base_enabled)
    head_ok = len(head_alone) == 3 and all(alone_passed(run) for run in head_alone)
    if error_class and enabled_ok and head_ok:
        return {"label": BRITTLE_CERTIFIED, "reason": "", "error_class": error_class}
    reasons = []
    if not error_class:
        reasons.append("base alone is not one stable failure")
    if not enabled_ok:
        reasons.append("enabled run does not pass the victim 3/3")
    if not head_ok:
        reasons.append("head alone does not pass 3/3")
    return {"label": "REJECTED", "reason": "; ".join(reasons), "error_class": error_class}
