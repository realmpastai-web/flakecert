#!/usr/bin/env python3
"""Gate for the FlakeCert verdict audit (frozen by Hark 2026-10-18).

  python3 gate_verdict_audit.py                    # self-check: sources + sample + expected
  python3 gate_verdict_audit.py --report OUT.json  # judge an implementation's output

Math (alpha = 0.05, one-sided, exact binomial / Clopper-Pearson with 0 failures):
  upper(n)      = 1 - alpha**(1/n). Reported rounded UP to 6 decimals, u.
                  Valid:  (1-u)**n <= alpha        Tight: (1-(u-1e-6))**n > alpha   (both exact, Fraction)
  required(p*)  = min n with (1-p*)**n <= alpha    (exact, Fraction; checked n and n-1)
A verdict is "fixed" when the test's attempt-to-fix executions all pass and the last one carries
test.test_management.attempt_to_fix_passed = "true" (Datadog flaky_management docs).
"""
import json, sys, argparse, hashlib
from decimal import Decimal, getcontext, ROUND_CEILING
from fractions import Fraction
from pathlib import Path
H = Path(__file__).resolve().parent
ALPHA = Fraction(1, 20)
TARGETS = ["0.01", "0.001"]
STEP = Fraction(1, 10**6)
fails = []
def chk(tag, ok, note=""):
    print(("PASS" if ok else "FAIL") + f"\t{tag}\t{note}"); ok or fails.append(tag)

def upper6(n):
    getcontext().prec = 60
    u = 1 - (Decimal(1) / Decimal(20)) ** (Decimal(1) / Decimal(n))
    return u.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)

def upper_ok(u_str, n):
    u = Fraction(u_str)
    return (1 - u) ** n <= ALPHA and (1 - (u - STEP)) ** n > ALPHA

def required(p_str):
    p = Fraction(p_str); n = 1
    lo, hi = 1, 1
    while (1 - p) ** hi > ALPHA: hi *= 2
    while lo < hi:
        mid = (lo + hi) // 2
        if (1 - p) ** mid <= ALPHA: hi = mid
        else: lo = mid + 1
    return lo

def required_ok(n, p_str):
    p = Fraction(p_str)
    return (1 - p) ** n <= ALPHA and (1 - p) ** (n - 1) > ALPHA

def audit(doc):
    groups = {}
    for e in doc["events"]:
        if e.get("type") != "test": continue
        m = e["content"]["meta"]
        key = m["test.suite"] + "::" + m["test.name"] + (("[" + m["test.parameters"] + "]") if m.get("test.parameters") else "")
        if m.get("test.test_management.is_attempt_to_fix") == "true":
            groups.setdefault(key, []).append(m)
    rows = []
    for key in sorted(groups):
        ms = groups[key]; n = len(ms); k = sum(1 for m in ms if m["test.status"] == "fail")
        tag = ms[-1].get("test.test_management.attempt_to_fix_passed")
        if tag == "true" and k == 0:
            rows.append({"test": key, "verdict": "fixed", "atf_runs": n, "atf_failures": 0,
                         "upper_bound_95": str(upper6(n)),
                         "clean_seeded_runs_required": {t: required(t) for t in TARGETS}})
        elif tag == "true":
            rows.append({"test": key, "verdict": "inconsistent", "atf_runs": n, "atf_failures": k})
        else:
            rows.append({"test": key, "verdict": "not_fixed", "atf_runs": n, "atf_failures": k})
    return {"alpha": "0.05", "method": "exact one-sided binomial (Clopper-Pearson), 0 failures", "tests": rows}

def judge(report, expected):
    chk("report.alpha", report.get("alpha") == "0.05")
    got = {r["test"]: r for r in report.get("tests", [])}
    exp = {r["test"]: r for r in expected["tests"]}
    chk("report.test_set", sorted(got) == sorted(exp), f"{sorted(got)}")
    for key, e in exp.items():
        r = got.get(key, {})
        chk(f"verdict {key}", r.get("verdict") == e["verdict"] and r.get("atf_runs") == e["atf_runs"]
            and r.get("atf_failures") == e["atf_failures"], f"{r.get('verdict')} n={r.get('atf_runs')} k={r.get('atf_failures')}")
        if e["verdict"] != "fixed": continue
        u = r.get("upper_bound_95", "")
        chk(f"upper_exact {key}", isinstance(u, str) and len(u.split(".")[-1]) == 6 and upper_ok(u, e["atf_runs"]), u)
        req = r.get("clean_seeded_runs_required", {})
        for t in TARGETS:
            chk(f"required_min {key} p*={t}", isinstance(req.get(t), int) and required_ok(req[t], t), str(req.get(t)))

ap = argparse.ArgumentParser(); ap.add_argument("--report"); a = ap.parse_args()
sample = json.loads((H / "sample/dd-test-run.json").read_text())
expected = json.loads((H / "expected-audit.json").read_text())
if a.report:
    judge(json.loads(Path(a.report).read_text()), expected)
else:
    src = (H / "sources")
    chk("src.pin", "fa6d74a613af044ed1c93a3b6b00aaf9038db0135eee110acc2c150458ceac65" in (src / "PIN.txt").read_text())
    jf = (src / "dd-trace-jest-plugin-finish.js.txt").read_text()
    chk("src.atf_passed_true_false", "span.setTag(TEST_MANAGEMENT_ATTEMPT_TO_FIX_PASSED, 'true')" in jf and "span.setTag(TEST_MANAGEMENT_ATTEMPT_TO_FIX_PASSED, 'false')" in jf)
    chk("src.retry_reason_atf", "atf: 'attempt_to_fix'" in (src / "dd-trace-retry-reasons.js.txt").read_text())
    chk("src.event_shape", "content: normalizeSpan(truncateSpanTestOpt(span))" in (src / "dd-trace-encoder-event.js.txt").read_text())
    fm = (src / "tests_flaky_management.txt").read_text()
    chk("docs.atf_20_and_passed_tag", "Retries any tests you’re attempting to fix 20 times" in fm and "Tags the last test retry with @test.test_management.attempt_to_fix_passed:true" in fm)
    chk("docs.merge_moves_to_fixed", "When the associated pull request merges, the test automatically moves to Fixed" in fm)
    chk("sample.events_92", len(sample["events"]) == 92)
    chk("oracle.matches_expected", audit(sample) == expected)
    chk("math.upper_20", str(upper6(20)) == "0.139109" and upper_ok("0.139109", 20))
    chk("math.required_1pct", required("0.01") == 299 and required_ok(299, "0.01"))
    chk("math.required_0.1pct", required("0.001") == 2995 and required_ok(2995, "0.001"))
    judge(expected, expected)
print("GATE " + ("PASS" if not fails else f"FAIL {fails}")); sys.exit(1 if fails else 0)
