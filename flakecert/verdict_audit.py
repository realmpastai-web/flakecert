"""Exact one-sided bound for an Attempt-to-Fix verdict.

Stdlib only. Comparisons use decimal.Decimal (precision >= 50) and
fractions.Fraction. This module does not call flakecert.stats.wilson.
"""

import csv
import io
import json
from decimal import ROUND_CEILING, Decimal, localcontext
from fractions import Fraction

ALPHA = Fraction(1, 20)
DEFAULT_TARGETS = ("0.01", "0.001")
STEP = Fraction(1, 10**6)
_PREC = 60
_QUANT = Decimal("0.000001")


class VerdictAuditError(RuntimeError):
    """The decimal result failed the Fraction check."""


class CsvVerdictError(ValueError):
    """A pup CSV export cannot be turned into an audit document."""


_CSV_PREFIX = "attributes.attributes."
_CSV_REQUIRED = ("start", "test.suite", "test.name", "test.status")


def _csv_cell(row: dict, column: str) -> str:
    value = row.get(column)
    if value is None:
        return ""
    return value


def document_from_csv(text: str) -> dict:
    """Build the event document audit() reads from a pup CSV export.

    csv.DictReader parses the file. Each dd-trace tag is the column name
    with the attributes.attributes. prefix removed. An empty cell omits that
    tag. Rows are sorted by start ascending so the newest attempt is last.
    """
    reader = csv.DictReader(io.StringIO(text, newline=""))
    fields = [name for name in (reader.fieldnames or []) if name]
    columns = {}
    for name in fields:
        if name.startswith(_CSV_PREFIX):
            tag = name[len(_CSV_PREFIX) :]
            if tag:
                columns[tag] = name
    missing = [name for name in _CSV_REQUIRED if name not in columns]
    if missing:
        raise CsvVerdictError("missing required column: " + ", ".join(missing))
    parsed = []
    seen = set()
    for row in reader:
        empty = [name for name in _CSV_REQUIRED if _csv_cell(row, columns[name]) == ""]
        if empty:
            raise CsvVerdictError("missing required column: " + ", ".join(empty))
        raw_start = _csv_cell(row, columns["start"])
        try:
            start = int(raw_start)
        except ValueError as exc:
            raise CsvVerdictError(f"start is not an integer: {raw_start}") from exc
        if start in seen:
            raise CsvVerdictError(f"duplicate start: {start}")
        seen.add(start)
        meta = {}
        for tag, column in columns.items():
            if tag == "start":
                continue
            value = _csv_cell(row, column)
            if value != "":
                meta[tag] = value
        parsed.append((start, meta))
    parsed.sort(key=lambda item: item[0])
    events = [{"type": "test", "content": {"meta": meta}} for _, meta in parsed]
    return {"events": events}


def _test_key(meta: dict) -> str:
    key = meta["test.suite"] + "::" + meta["test.name"]
    parameters = meta.get("test.parameters")
    if parameters:
        key += "[" + parameters + "]"
    return key


def _upper_ok(u_str: str, n: int) -> bool:
    u = Fraction(u_str)
    return (1 - u) ** n <= ALPHA and (1 - (u - STEP)) ** n > ALPHA


def upper_bound_95(n: int) -> str:
    """1 - alpha^(1/n), rounded up to 6 decimal places, then Fraction-checked."""
    if n < 1:
        raise VerdictAuditError(f"atf run count must be positive, got {n}")
    with localcontext() as ctx:
        ctx.prec = _PREC
        raw = Decimal(1) - (Decimal(1) / Decimal(20)) ** (Decimal(1) / Decimal(n))
        rounded = raw.quantize(_QUANT, rounding=ROUND_CEILING)
    text = str(rounded)
    if not _upper_ok(text, n):
        raise VerdictAuditError(f"upper bound failed Fraction verification: n={n} u={text}")
    return text


def _required_ok(n: int, p: Fraction) -> bool:
    if n < 1:
        return False
    fits = (1 - p) ** n <= ALPHA
    previous = n == 1 or (1 - p) ** (n - 1) > ALPHA
    return fits and previous


def clean_seeded_runs_required(p_str: str) -> int:
    """Smallest n with (1 - p*)^n <= alpha. p* is parsed as a Fraction."""
    p = Fraction(p_str)
    if not (Fraction(0) < p < Fraction(1)):
        raise VerdictAuditError(f"target out of range: {p_str}")
    lo = 1
    hi = 1
    while (1 - p) ** hi > ALPHA:
        hi *= 2
    while lo < hi:
        mid = (lo + hi) // 2
        if (1 - p) ** mid <= ALPHA:
            hi = mid
        else:
            lo = mid + 1
    if not _required_ok(lo, p):
        raise VerdictAuditError(f"required n failed Fraction verification: p*={p_str} n={lo}")
    return lo


def audit(doc, targets=DEFAULT_TARGETS) -> dict:
    """Group attempt-to-fix events and bound every verdict marked fixed."""
    groups: dict[str, list] = {}
    for event in doc["events"]:
        if event.get("type") != "test":
            continue
        meta = event["content"]["meta"]
        if meta.get("test.test_management.is_attempt_to_fix") != "true":
            continue
        groups.setdefault(_test_key(meta), []).append(meta)
    rows = []
    for key in sorted(groups):
        metas = groups[key]
        n = len(metas)
        k = sum(1 for meta in metas if meta.get("test.status") == "fail")
        tag = metas[-1].get("test.test_management.attempt_to_fix_passed")
        if tag == "true" and k == 0:
            rows.append(
                {
                    "test": key,
                    "verdict": "fixed",
                    "atf_runs": n,
                    "atf_failures": 0,
                    "upper_bound_95": upper_bound_95(n),
                    "clean_seeded_runs_required": {
                        target: clean_seeded_runs_required(target) for target in targets
                    },
                }
            )
        elif tag == "true":
            rows.append(
                {
                    "test": key,
                    "verdict": "inconsistent",
                    "atf_runs": n,
                    "atf_failures": k,
                }
            )
        else:
            rows.append(
                {
                    "test": key,
                    "verdict": "not_fixed",
                    "atf_runs": n,
                    "atf_failures": k,
                }
            )
    return {
        "alpha": "0.05",
        "method": "exact one-sided binomial (Clopper-Pearson), 0 failures",
        "tests": rows,
    }


def dumps_audit(report: dict) -> str:
    """Canonical audit JSON: indent 1, sorted keys, trailing newline."""
    return json.dumps(report, indent=1, sort_keys=True) + "\n"
