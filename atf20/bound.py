"""One-sided exact upper bound for 0 failures in N executions.

Bisection on (1 - p) ** N = 0.05. The 1% search is the smallest N whose
bound is at most 0.01.
"""

from __future__ import annotations


def upper_bound(n: int, alpha: float = 0.05) -> float:
    if n < 1:
        raise ValueError("n must be >= 1")
    lo = 0.0
    hi = 1.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if (1.0 - mid) ** n > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def min_n_for(limit: float = 0.01, alpha: float = 0.05) -> int:
    n = 1
    while upper_bound(n, alpha) > limit:
        n += 1
    return n


def main() -> None:
    value = upper_bound(20)
    smallest = min_n_for(0.01)
    print(f"upper_0_of_20={value:.6f}")
    print(f"min_n_for_1pct={smallest}")
    if abs(value - 0.139108) >= 1e-6:
        raise SystemExit(1)
    if smallest != 299:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
