"""S2 classification and the S3 candidate filter.

An id is order-dependent when it failed in the seeded suite run and then
passed alone on every one of three repetitions. S3's candidate list is the
non-failing ids that ran before that victim, in that same run order.
"""

from __future__ import annotations

ORDER_DEPENDENT = "ORDER-DEPENDENT"
BRITTLE = "BRITTLE"
OTHER = "OTHER"


def classify_s2(failed_in_s1: bool, alone_passed: list[bool]) -> str:
    if failed_in_s1 and len(alone_passed) == 3 and all(alone_passed):
        return ORDER_DEPENDENT
    return OTHER


def classify_discovered(alone_passed_flags: list[bool], defined_order_passed: bool) -> str:
    """Classify one id from the seed-search union.

    ORDER-DEPENDENT: passes alone 3/3.
    BRITTLE: fails alone 3/3 and passed in the base defined-order run.
    OTHER: everything else.
    """
    if len(alone_passed_flags) == 3 and all(alone_passed_flags):
        return ORDER_DEPENDENT
    failed_all = len(alone_passed_flags) == 3 and not any(alone_passed_flags)
    if failed_all and defined_order_passed:
        return BRITTLE
    return OTHER


def alone_passed(outcome: dict) -> bool:
    """One isolated example passed. Zero examples is not a pass."""
    return (
        outcome.get("exit_code") == 0
        and outcome.get("failure_count") == 0
        and outcome.get("example_count") == 1
    )


def predecessors(examples: list[dict], victim_id: str) -> list[str]:
    """Non-failing example ids that ran strictly before victim_id."""
    index = None
    for i, example in enumerate(examples):
        if example.get("id") == victim_id:
            index = i
            break
    if index is None:
        raise KeyError(victim_id)
    chosen = []
    for example in examples[:index]:
        if example.get("status") != "failed":
            ident = example.get("id")
            if ident:
                chosen.append(ident)
    return chosen
