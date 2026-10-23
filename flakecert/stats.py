"""Rates and Wilson score intervals. Pure functions of logged counts."""

import math
from fractions import Fraction

Z95 = 1.959963984540054


def wilson(failures: int, runs: int) -> tuple[float, float] | None:
    if runs <= 0:
        return None
    z2 = Z95 * Z95
    phat = failures / runs
    denom = 1.0 + z2 / runs
    centre = (phat + z2 / (2.0 * runs)) / denom
    margin = Z95 * math.sqrt((phat * (1.0 - phat) + z2 / (4.0 * runs)) / runs) / denom
    low = max(0.0, centre - margin)
    high = min(1.0, centre + margin)
    return low, high


def fmt_ci(interval: tuple[float, float] | None) -> str:
    if interval is None:
        return "none"
    return f"low={interval[0]:.6f} high={interval[1]:.6f}"


def rate_text(failures: int, runs: int) -> str:
    if runs <= 0:
        return "none"
    return f"{failures}/{runs}"


def ratio_text(controlled_failures: int, controlled_runs: int, baseline_failures: int, baseline_runs: int) -> str:
    if controlled_runs <= 0 or baseline_runs <= 0 or baseline_failures <= 0:
        return "undefined"
    return str(Fraction(controlled_failures * baseline_runs, controlled_runs * baseline_failures))
