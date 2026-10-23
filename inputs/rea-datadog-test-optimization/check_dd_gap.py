#!/usr/bin/env python3
"""FlakeCert vs Datadog Test Optimization (flaky tests): what its records lack.
Frozen by Hark 2026-10-18. Usage: python3 check_dd_gap.py <flakecert checkout at 7d22e2d>"""
import json, re, sys
from pathlib import Path
H = Path(__file__).resolve().parent; S = H / "sources"; FC = Path(sys.argv[1]).resolve(); fails = []
rd = lambda p: (S / p).read_text(encoding="utf-8", errors="replace")
def chk(tag, ok, note=""):
    print(("PASS" if ok else "FAIL") + f"\t{tag}\t{note}"); ok or fails.append(tag)
dd = "dd-trace-6.21.0/"
# Shipped artifact pin
chk("pin.tarball", "fa6d74a613af044ed1c93a3b6b00aaf9038db0135eee110acc2c150458ceac65" in rd(dd + "PIN.txt"))
# REA: the copied files are the ones REA inventoried in the shipped tarball
import hashlib
rea = json.loads((H / "rea-summary.json").read_text())
chk("rea.no_integrity_contradictions", rea["integrity_contradictions"] == [], rea["evidence_id"][:19])
for rel, v in rea["files"].items():
    got = hashlib.sha256((S / dd / Path(rel).name).read_bytes()).hexdigest()
    chk("rea.node_matches " + Path(rel).name, v["rea_node_sha256"] == got)
# 1. The test-event tag vocabulary (test.js) has no reproduction fields
test_js = rd(dd + "test.js")
tags = re.findall(r"^const [A-Z0-9_]+ = '([a-z0-9_.@]+)'", test_js, re.M)
chk("tags.count_80", len(tags) == 80, f"{len(tags)} string tag constants")
bad = [t for t in tags if re.search(r"seed|shuffle|random|order|hashseed|digest|image|lockfile|freeze|schedule|interval|confidence|bound", t)]
chk("tags.no_repro_fields", bad == [], "0 tags for seed/order/image digest/dependency lock/schedule/bound")
for t in ("test.is_retry", "test.is_new", "test.retry_reason", "test.has_failed_all_retries",
          "test.test_management.is_quarantined", "test.test_management.is_attempt_to_fix",
          "test.test_management.attempt_to_fix_passed"):
    chk("tags.has " + t, t in tags)
env_js = rd(dd + "env.js")
chk("env.records_os_runtime_only", sorted(set(re.findall(r"'((?:os|runtime)\.[a-z_.]+)'", env_js))) ==
    ["os.architecture", "os.platform", "os.version", "runtime.name", "runtime.version"])
# 2. Jest integration strips the seed out of the test name
jest_js = rd(dd + "jest.js")
chk("jest.seed_stripped", "const SEED_SUFFIX_RE = / ?\\(with seed=-?\\d+\\) ?$/i" in jest_js and
    "return testName.replace(SEED_SUFFIX_RE, '')" in jest_js)
# 3. Docs: how Datadog decides flaky / fixed
fm = rd("tests_flaky_management.txt")
chk("docs.attempt_to_fix_20", "Retries any tests you’re attempting to fix 20 times" in fm)
chk("docs.all_pass_marks_fix", "If all retries pass, marks the fix as in progress" in fm)
chk("docs.policy_7d_rate", "if its failure rate over the last 7 days is greater or equal to the specified threshold" in fm)
chk("docs.fixed_after_30d", "If a flaky test no longer flakes for 30 days, it is automatically move" in fm)
efd = rd("tests_flaky_test_management_early_flake_detection.txt")
chk("docs.efd_new_tests", "New tests have the @test.is_new tag set to true , and retries for this test have the @test.is_retry tag set to true" in efd)
# 4. What 20/20 passes proves: exact one-sided bound, no FlakeCert import needed
hi = 1 - 0.05 ** (1 / 20)  # exact one-sided 95% upper bound for 0/20 (two-sided Wilson 0.1611 banned since 2026-10-18)
chk("stats.20_of_20_upper", round(hi, 4) == 0.1391, f"exact one-sided 95% upper={hi:.4f}")
# 5. FlakeCert ledger: tests that pass plain reruns yet certify under control
led = (FC / "ledger/SUMMARY.md").read_text()
cert_ids = re.search(r"certified_ids=(\S+)", led).group(1).split(",")
zero = [s.split()[0] for s in re.split(r"\n### ", led)[1:] if s.split()[0] in cert_ids and "- baseline_failures=0\n" in s]
chk("fc.certified_zero_baseline_9", len(zero) == 9, ",".join(zero))
runs = {s.split()[0]: int(re.search(r"- baseline_runs=(\d+)", s).group(1)) for s in re.split(r"\n### ", led)[1:] if s.split()[0] in zero}
chk("fc.zero_baseline_runs_ge_100", min(runs.values()) >= 100, str(sorted(set(runs.values()))))
c = json.loads((FC / "certs/F01.json").read_text())
chk("fc.cert_has_repro_fields", all(k in c for k in ("sha", "image_digest", "pip_freeze_sha", "schedule", "d")))
chk("fc.speedup_unproven", "exponential_speedup=UNPROVEN" in led)
print("CHECK " + ("PASS" if not fails else f"FAIL {fails}")); sys.exit(1 if fails else 0)
