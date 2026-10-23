"""Process exit for a finished classification.

Exit 0 iff every classified id is CERTIFIED, CONTROL, or BRITTLE_CERTIFIED,
or is explicitly REJECTED or UNATTRIBUTED and carries a reason. summary.json
exit_ok follows the same rule.
"""

from __future__ import annotations

SETTLED = frozenset({"CERTIFIED", "CONTROL", "BRITTLE_CERTIFIED"})
EXPLAINED = frozenset({"REJECTED", "UNATTRIBUTED"})


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def rejection_reason(row: dict) -> str:
    """Why a REJECTED or UNATTRIBUTED row is explicit. Empty means it is not."""
    named = _text(row.get("reason"))
    if named:
        return named
    if row.get("label") != "REJECTED":
        return ""
    for key in ("base", "head"):
        if row.get(key) == "POLLUTER_FAILED":
            return "POLLUTER_FAILED"
    verdicts = row.get("verdicts")
    if isinstance(verdicts, dict):
        for key in ("base", "head"):
            if verdicts.get(key) == "POLLUTER_FAILED":
                return "POLLUTER_FAILED"
    return ""


def classification_exit_ok(rows: list[dict]) -> bool:
    """True when every row is a settled label or an explained rejection."""
    for row in rows:
        label = row.get("label")
        if label in SETTLED:
            continue
        if label in EXPLAINED and rejection_reason(row):
            continue
        return False
    return True
