"""1-minimal subset search.

``test(subset)`` is true when that subset reproduces. Relative order of the
input list is kept. The result is 1-minimal: the full result reproduces, and
dropping any one element does not.
"""

from __future__ import annotations


class DdminError(ValueError):
    pass


def _ddmin(circumstances: list, test) -> list:
    current = list(circumstances)
    if not test(current):
        raise DdminError("full set does not reproduce")
    n = 2
    while len(current) >= 2:
        subset_length = len(current) // n
        if subset_length < 1:
            break
        start = 0
        reduced = False
        while start < len(current):
            subset = current[start : start + subset_length]
            if test(subset):
                current = subset
                n = max(n - 1, 2)
                reduced = True
                break
            complement = current[:start] + current[start + subset_length :]
            if test(complement):
                current = complement
                n = max(n - 1, 2)
                reduced = True
                break
            start += subset_length
        if reduced:
            continue
        if n >= len(current):
            break
        n = min(n * 2, len(current))
    return current


def one_minimal(circumstances: list, test) -> list:
    """ddmin, then drop any element whose removal still reproduces."""
    current = _ddmin(circumstances, test)
    changed = True
    while changed:
        changed = False
        for index in range(len(current)):
            trial = current[:index] + current[index + 1 :]
            if test(trial):
                current = trial
                changed = True
                break
    return current
