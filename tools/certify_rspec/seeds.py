"""S0 seed pick and the union of base failures. No suite is executed here."""

from __future__ import annotations


def primary_seed(records: list[dict]) -> int | None:
    """Seed with the most base failures that all pass at head.

    A seed qualifies only when it has at least one base failure and none of
    those ids fail at head. Ties go to the smallest seed.
    """
    best: tuple[int, int] | None = None
    for record in records:
        base = list(record.get("base_failing_ids") or [])
        head = set(record.get("head_failing_ids") or [])
        if not base or any(item in head for item in base):
            continue
        count = len(base)
        seed = int(record["seed"])
        if best is None or count > best[0] or (count == best[0] and seed < best[1]):
            best = (count, seed)
    if best is None:
        return None
    return best[1]


def union_failing(records: list[dict]) -> list[dict]:
    """Every id that fails at base in any seed, with those seeds, first-seen order."""
    found: dict[str, list[int]] = {}
    ordered = sorted(records, key=lambda record: int(record["seed"]))
    for record in ordered:
        seed = int(record["seed"])
        for ident in record.get("base_failing_ids") or []:
            found.setdefault(ident, []).append(seed)
    return [{"id": ident, "seeds": seeds} for ident, seeds in found.items()]
