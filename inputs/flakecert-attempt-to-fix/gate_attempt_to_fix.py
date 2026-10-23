#!/usr/bin/env python3
"""Certified Attempt-to-Fix gate for FlakeCert (frozen by Hark 2026-10-18).

  python3 -B gate_attempt_to_fix.py                   # self-check: pins, fixes, predictions (no Ruby)
  python3 -B gate_attempt_to_fix.py --results R.json  # judge the runner's attempt-to-fix results

Victim ./spec/models/cart_spec.rb[1:1]; pinned schedule = audit/rspec-cert.json at main b9f2c9e
(order_seed 0, srand_seed 0, image ruby@sha256:2e32876d..., lock_sha256 91102ec2...).
Three variants of spec/models/cart_spec.rb, everything else byte-identical:
  prefix     the frozen sample (polluter [1:2] never resets Cart.default_discount)
  wrong_fix  + before(:all) reset   (runs once per group, so the polluter still leaks; predicted NOT FIXED)
  real_fix   + after reset          (undoes the discount after every example; predicted FIXED)
Arms per variant:
  plain_retry  20 x `bundle exec rspec --format json` in defined order, no srand (Datadog's Attempt-to-Fix count is 20;
               this is a plain rerun control, not Datadog's Ruby implementation)
  cert_replay  3 x the certificate's replay command at the pinned schedule
  sweep        order seeds 0..99 at srand 0, 1 run each (wrong_fix and real_fix)

Results file shape:
{"rspec_core": "3.13.6", "image_digest": "sha256:<64>", "lock_sha256": "<64>", "schedule": {"order_seed": 0, "srand_seed": 0},
 "variants": {"<prefix|wrong_fix|real_fix>": {
    "cart_spec_sha256": "<64>", "sample_other_sha256": {"<relpath>": "<64>", ...},
    "plain_retry": ["passed", ... x20],                       # victim status per run
    "cert_replay": [{"victim": "failed|passed", "polluter": "passed", "exc": str|null, "message": str|null, "sig": str|null} x3],
    "sweep": {"0": {"victim": "...", "polluter": "..."}, ... "99": {...}}   # wrong_fix, real_fix only
 }}}
"""
import argparse, hashlib, json, math, re, sys
from pathlib import Path
H = Path(__file__).resolve().parent
R = H.parent  # inputs/
V, P = "./spec/models/cart_spec.rb[1:1]", "./spec/models/cart_spec.rb[1:2]"
CERT = json.loads((H / "pins/rspec-cert-b9f2c9e.json").read_text())
PIN = {"pins/rspec-cert-b9f2c9e.json": "bc87ebe6c1e619e55d7643eb33deb79d43138955b8297d49159bb7b6d7ce13fd",
       "pins/rspec-results-b9f2c9e.json": "811a6f0edfffb45879bf72a43d1b9984292e4d5d89ef3a96ef03996e710b27de"}
SPEC = {"prefix": "8496e9a8e342ff4884b7613362cb5dcb80ab98246df32511a0bf98cb39cf02a3",
        "wrong_fix": "ed722088487412a8a8c32151e0ed55784a97d75104e533d6eab3d070faf65757",
        "real_fix": "7e5cb3c8b09f32d2d6761554e378208e7208a649172dbc5415b5e723b76ece84"}
SAMPLE = R / "flakecert-rspec-runner/sample"
OTHER = {l.split("  ")[1]: l.split("  ")[0] for l in (R / "flakecert-rspec-runner/sample.sha256").read_text().splitlines() if not l.endswith("spec/models/cart_spec.rb")}
PRED = json.loads((R / "flakecert-rspec-runner/expected/predicted-cart-order.json").read_text())
FAILS = sorted(PRED["victim_fails"])
fails = []
def chk(tag, ok, note=""):
    print(("PASS" if ok else "FAIL") + f"\t{tag}\t{note}"); ok or fails.append(tag)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jenkins(s):
    h = 0
    for b in s.encode():
        h = (h + b) & 0xFFFFFFFF; h = (h + (h << 10)) & 0xFFFFFFFF; h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF; h ^= h >> 11; h = (h + (h << 15)) & 0xFFFFFFFF
    return h
def exact_hi_zero(n, alpha=0.05):
    """Exact one-sided (Clopper-Pearson) upper bound for 0 failures in n runs: 1 - alpha**(1/n)."""
    return 1 - alpha ** (1 / n)

def wilson_hi(f, n, z=1.959963984540054):  # unused since 2026-10-18 re-freeze (two-sided Wilson banned, 1371e26)
    p = f / n; d = 1 + z * z / n
    return min(1.0, ((p + z * z / (2 * n)) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d)

def self_check():
    for f, h in PIN.items():
        chk(f"pin.{f}", sha(H / f) == h, h[:16])
    for v, h in SPEC.items():
        chk(f"fix.sha {v}", sha(H / f"fixes/cart_spec.{v}.rb") == h, h[:16])
    chk("fix.prefix_is_frozen_sample", sha(SAMPLE / "spec/models/cart_spec.rb") == SPEC["prefix"])
    pre = (H / "fixes/cart_spec.prefix.rb").read_text().splitlines()
    for v, added in (("wrong_fix", "  before(:all) { Cart.default_discount = nil }"), ("real_fix", "  after { Cart.default_discount = nil }")):
        got = (H / f"fixes/cart_spec.{v}.rb").read_text().splitlines()
        ok = len(got) == len(pre) + 2 and got[:3] + got[5:] == pre and got[3].startswith(added) and got[4] == ""
        chk(f"fix.{v}_adds_one_hook_only", ok, got[3][:48] if len(got) > 3 else "")
    chk("fix.ids_unchanged", all(len(re.findall(r'^  it "', (H / f"fixes/cart_spec.{v}.rb").read_text(), re.M)) == 2 for v in SPEC), "2 examples, hooks get no scoped id")
    # the certificate
    chk("cert.schedule_0_0", CERT["schedule"] == {"order_seed": 0, "srand_seed": 0}, str(CERT["schedule"]))
    chk("cert.node_is_victim", CERT["node_id"] == V)
    chk("cert.replay_cmd", CERT["replay"].startswith("FLAKECERT_SRAND=0 bundle exec rspec --order rand:0 --require /flakecert/srand.rb"), CERT["replay"][:60])
    chk("cert.exc", CERT["expected_failure"]["exc"] == "RSpec::Expectations::ExpectationNotMetError")
    # committed Ruby run at b9f2c9e: the pinned schedule fails every replay; defined order never fails the victim
    res = json.loads((H / "pins/rspec-results-b9f2c9e.json").read_text())
    at = [s["examples"][V] for s in res["schedules"] if s["order_seed"] == 0 and s["srand_seed"] == 0]
    chk("ruby.prefix_schedule_0_0_fails_every_replay", len(at) >= 2 and set(at) == {"failed"}, f"{len(at)} runs {sorted(set(at))}")
    b = res["baseline"]
    chk("ruby.prefix_plain_rerun_never_fails_victim", b["runs"] == 100 and b["victim_failures"] == 0, f"{b['victim_failures']}/{b['runs']}")
    swept = {s["order_seed"]: s["examples"][V] for s in res["schedules"] if s["srand_seed"] == 0}
    chk("ruby.prefix_fail_seeds_equal_prediction", sorted(k for k, x in swept.items() if x == "failed") == FAILS, f"{len(FAILS)}/100")
    # prediction: at seed 0 the polluter sorts before the victim inside the Cart group, so a once-per-group reset cannot help
    chk("pred.seed0_polluter_before_victim", jenkins("0" + P) < jenkins("0" + V), f"{jenkins('0'+P)} < {jenkins('0'+V)}")
    chk("pred.wrong_fix_fail_seeds_equal_prefix", all((jenkins(f"{s}{P}") < jenkins(f"{s}{V}")) == (s in FAILS) for s in range(100)), "polluter-first seeds == prefix fail seeds")
    # why 20 plain retries are not a certificate
    hi = exact_hi_zero(20)
    chk("stats.20_of_20_exact_one_sided_upper_95", round(hi, 4) == 0.1391, f"{hi:.4f}")
    dd = (R / "rea-datadog-test-optimization/check-output.txt").read_text()
    chk("dd.attempt_to_fix_is_20_retries", "PASS\tdocs.attempt_to_fix_20" in dd)

def judge(path):
    r = json.loads(Path(path).read_text())
    chk("res.rspec_core", r.get("rspec_core") == "3.13.6")
    chk("res.image_digest_is_cert", r.get("image_digest") == CERT["image_digest"])
    chk("res.lock_is_cert", r.get("lock_sha256") == CERT["lock_sha256"])
    chk("res.schedule_is_cert", r.get("schedule") == CERT["schedule"], str(r.get("schedule")))
    vs = r.get("variants", {})
    chk("res.three_variants", sorted(vs) == sorted(SPEC), str(sorted(vs)))
    verdict = {}
    for v in SPEC:
        x = vs.get(v, {})
        chk(f"{v}.cart_spec_sha", x.get("cart_spec_sha256") == SPEC[v])
        chk(f"{v}.rest_of_sample_unchanged", x.get("sample_other_sha256") == OTHER, f"{len(x.get('sample_other_sha256') or {})}/{len(OTHER)} files")
        pr = x.get("plain_retry") or []
        chk(f"{v}.plain_retry_20_of_20_pass", len(pr) == 20 and set(pr) == {"passed"}, f"{pr.count('passed')}/{len(pr)}")
        cr = x.get("cert_replay") or []
        st = [c.get("victim") for c in cr]
        chk(f"{v}.cert_replay_3_runs", len(cr) == 3, str(st))
        chk(f"{v}.cert_replay_polluter_passes", len(cr) == 3 and all(c.get("polluter") == "passed" for c in cr))
        chk(f"{v}.cert_replay_identical", len(set(st)) == 1 and len(set(c.get("sig") for c in cr)) == 1)
        verdict[v] = "NOT_FIXED" if st == ["failed"] * 3 else "FIXED" if st == ["passed"] * 3 else "INCONSISTENT"
        if st == ["failed"] * 3:
            chk(f"{v}.failure_is_the_leak", all(c.get("exc") == CERT["expected_failure"]["exc"] and re.search(r"expected: 100\s+got: 90", c.get("message") or "") for c in cr), (cr[0].get("message") or "")[:60].replace("\n", " "))
        if v == "prefix" and cr:
            chk("prefix.sig_equals_cert", cr[0].get("sig") == CERT["expected_failure"]["sig"], (cr[0].get("sig") or "")[:16])
        if v != "prefix":
            sw = x.get("sweep") or {}
            ok = sorted(sw, key=int) == [str(i) for i in range(100)]
            got = sorted(int(k) for k, e in sw.items() if e.get("victim") == "failed")
            want = FAILS if v == "wrong_fix" else []
            chk(f"{v}.sweep_0_99_victim_fail_seeds", ok and got == want, f"{len(got)} failing, want {len(want)}")
            chk(f"{v}.sweep_polluter_always_passes", ok and all(e.get("polluter") == "passed" for e in sw.values()))
    want = {"prefix": "NOT_FIXED", "wrong_fix": "NOT_FIXED", "real_fix": "FIXED"}
    chk("verdict.certified", verdict == want, str(verdict))
    plain = {v: ("FIXED" if (vs.get(v, {}).get("plain_retry") or []) == ["passed"] * 20 else "NOT_FIXED") for v in SPEC}
    chk("verdict.plain_retry_cannot_tell_wrong_from_real", plain["wrong_fix"] == plain["real_fix"] == "FIXED", str(plain))
    print(f"INFO\tcertified={verdict} plain_retry={plain}")

ap = argparse.ArgumentParser(); ap.add_argument("--results")
a = ap.parse_args()
self_check() if not a.results else judge(a.results)
print("GATE PASS" if not fails else f"GATE FAIL {fails}"); sys.exit(1 if fails else 0)
