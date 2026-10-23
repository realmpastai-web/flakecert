"""Intended-order check for an arm, and the rank rule used to request that order.

An arm run whose JSON example ids are not the intended list is INVALID_ORDER.
That result is not a pass and not a fail. A verdict must not use it.
"""

from __future__ import annotations

from tools.certify_rspec.parse_rspec import norm_id

INVALID_ORDER = "INVALID_ORDER"
ORDER_OK = "OK"


def rank_of(item: dict, ids: list[str]) -> int:
    """Rank one example or group.

    An example's rank is its index in ``ids``. A group (a dict that has
    ``descendants``) ranks as the minimum rank of those descendants. An id
    that is not listed ranks after every listed id.
    """
    positions = {ident: index for index, ident in enumerate(ids)}
    fallback = len(positions)

    def walk(node: dict) -> int:
        if "descendants" in node:
            children = node["descendants"]
            if not children:
                return fallback
            return min(walk(child) for child in children)
        return positions.get(node.get("id"), fallback)

    return walk(item)


def order_by_rank(items: list[dict], ids: list[str]) -> list[dict]:
    """Sort items by rank_of, keeping the original order when ranks tie."""
    ranked = sorted(enumerate(items), key=lambda pair: (rank_of(pair[1], ids), pair[0]))
    return [item for _, item in ranked]


def order_guard(examples: list[dict], intended: list[str]) -> str:
    """Return ORDER_OK when the JSON example ids equal the intended list."""
    actual = []
    for example in examples:
        ident = example.get("id")
        if ident:
            actual.append(norm_id(str(ident)))
    wanted = [norm_id(item) for item in intended]
    if actual != wanted:
        return INVALID_ORDER
    return ORDER_OK
