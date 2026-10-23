#!/usr/bin/env python3
"""pytest Attempt-to-Fix gate for FlakeCert, reverse-first (frozen by Hark 2026-10-18, internal).

  python3 -B gate_pytest_attempt_to_fix.py                     # self-check: REA static read of the two sdists, pins, fixes, predictions
  python3 -B gate_pytest_attempt_to_fix.py --rea-dir DIR       # same self-check against another sdist dir (controls only)
  python3 -B gate_pytest_attempt_to_fix.py --results R.json    # judge the runner's results file

Never executes, imports or installs the reversed packages: the sdists are read as bytes with tarfile.
"Not found in the pinned sdist" is the strongest absence claim this gate makes; it says nothing about
other versions, forks, plugins layered on top, or vendor products.

Sample (sample/, pytest 8.4.2, python@sha256:0a310eee... 3.11-slim-bookworm):
  victim   V = tests/test_cart.py::test_total_without_discount   (expects 100)
  polluter P = tests/test_cart.py::test_total_with_discount      (sets cart.DEFAULT_DISCOUNT = 10, never resets)
  noise      tests/test_coupon.py::test_coupon_draw (RNG only), tests/test_stable.py::test_stable
Variants of tests/test_cart.py, everything else byte-identical:
  prefix     frozen sample
  wrong_fix  + module-level reset at import (collection precedes every test, so P still leaks; predicted NOT FIXED)
  real_fix   + autouse fixture resetting after each test (predicted FIXED)
Arms per variant:
  plain_retry  20 x `python -m pytest` in defined file order (V before P), unseeded. Datadog's Attempt-to-Fix count is 20;
               this is a plain rerun control, not Datadog's or pytest-rerunfailures' implementation.
  cert_replay  3 x FlakeCert's replay of the certificate it produced for V on prefix
  sweep        seeds 0..99: node ids in order random.Random(seed).shuffle(sorted(ids)), passed explicitly on the command line

Results file shape:
{"pytest": "8.4.2", "python": "3.11.<n>", "base_image": "python@sha256:<64>", "image_digest": "sha256:<64>",
 "pip_freeze": ["iniconfig==2.1.0", ...],
 "cert": {FlakeCert certificate for V on prefix: node_id, image_digest, pip_freeze_sha, python, schedule[{source,value}], expected_failure{exc,sig}, ...},
 "variants": {"<prefix|wrong_fix|real_fix>": {
    "test_cart_sha256": "<64>", "sample_other_sha256": {"<relpath under sample/>": "<64>", ...},
    "plain_retry": ["passed", ... x20],
    "cert_replay": [{"victim": "failed|passed", "polluter": "passed", "exc": str|null, "message": str|null, "sig": str|null} x3],
    "sweep": {"0": {"victim": "...", "polluter": "..."}, ... "99": {...}} }}}
"""
import argparse, difflib, hashlib, io, json, random, re, sys, tarfile
from pathlib import Path

H = Path(__file__).resolve().parent
R = H.parent  # inputs/
V = "tests/test_cart.py::test_total_without_discount"
P = "tests/test_cart.py::test_total_with_discount"
BASE = "python@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89"
SDIST = {"pytest_rerunfailures-16.7.tar.gz": "6956ddfb65ca1d07e7e3d99e2c5359d82300f4cb062e6049563bd2c106f72d5c",
         "pytest_randomly-5.0.0.tar.gz": "e9c575a5873ef168ddbe340ed9e97ce9edb4492ccc821e4b2ac6bb1f0ed515d2"}
PIN = {"pins/requirements.lock": "3e92ee06a3243bc172d78d65f6ec83da289a1165a72e032f6cb53bdc229eff58",
       "pins/Dockerfile": "ebc28c1bc5aa9903b57d7c5614b3c78508a2a9941b4f962bb21769bf83711cfa",
       "expected/predicted-sweep.json": "e08709e94843d1760f1a2d7479bb376e891270e130c9d203888b4322681a83fe"}
SPEC = {"prefix": "871e2e4b2792376d419594f7a50eacb0c9fada4a8d5e0936a580727116dd671b",
        "wrong_fix": "89a1f5dc0e3b8ee6613943377a204300669093f9d0a41c4cf6ba9c64d6d5e8c1",
        "real_fix": "469147e64fdbe2f865d6cb10a9671122516c948d73ec630e691887a86378eee3"}
LOCK = sorted(l.split()[0] for l in (H / "pins/requirements.lock").read_text().splitlines() if l and not l.startswith("#"))
OTHER = {}
for l in (H / "sample.sha256").read_text().splitlines():
    h, f = l.split("  ", 1)
    if f != "sample/tests/test_cart.py":
        OTHER[f[len("sample/"):]] = h
PRED = json.loads((H / "expected/predicted-sweep.json").read_text())
FAILS = sorted(PRED["victim_fails"])
fails = []

def chk(tag, ok, note=""):
    print(("PASS" if ok else "FAIL") + f"\t{tag}\t{note}"); ok or fails.append(tag)

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
exact_hi_zero = lambda n, alpha=0.05: 1 - alpha ** (1 / n)  # exact one-sided (Clopper-Pearson) upper bound, 0 failures in n

def member(tgz, suffix):
    with tarfile.open(tgz, "r:gz") as t:
        m = [x for x in t.getmembers() if x.isfile() and x.name.endswith(suffix)]
        return t.extractfile(m[0]).read().decode() if len(m) == 1 else None

def rea(d):
    for f, h in SDIST.items():
        chk(f"rea.sha {f}", (d / f).is_file() and sha(d / f) == h, h[:16])
        meta = json.loads((H / f"rea/pypi-{f.split('-')[0].replace('_', '-')}-{f.split('-')[1][:-7]}.json").read_text())
        sd = [u for u in meta["urls"] if u["packagetype"] == "sdist"]
        chk(f"rea.pypi_json_sdist_digest {f}", len(sd) == 1 and sd[0]["filename"] == f and sd[0]["digests"]["sha256"] == h)
    rr = d / "pytest_rerunfailures-16.7.tar.gz"; ra = d / "pytest_randomly-5.0.0.tar.gz"
    pk = member(rr, "pytest_rerunfailures-16.7/PKG-INFO") or ""
    chk("rea.rerunfailures.pkg_info", "\nVersion: 16.7\n" in pk and "\nLicense: MPL-2.0\n" in pk)
    pk = member(ra, "pytest_randomly-5.0.0/PKG-INFO") or ""
    chk("rea.randomly.pkg_info", "\nVersion: 5.0.0\n" in pk and "\nLicense-Expression: MIT\n" in pk)
    s = member(rr, "pytest_rerunfailures-16.7/src/pytest_rerunfailures.py") or ""
    chk("rea.rerunfailures.rerun_condition", "item.execution_count <= reruns\n        and (any(_test_failed_statuses.values())" in s, "reruns only after a failed phase")
    loop = re.search(r"need_to_run = True\n    while need_to_run:\n        item\.execution_count \+= 1\n.*?reports = runtestprotocol\(item, nextitem=nextitem, log=False\)", s, re.S)
    chk("rea.rerunfailures.same_item_same_process_loop", bool(loop), "while loop re-runs runtestprotocol on the same item, same nextitem")
    chk("rea.rerunfailures.no_seed_random_shuffle", not re.search(r"seed|random|shuffle", s, re.I), f"{len(re.findall(r'seed|random|shuffle', s, re.I))} hits")
    chk("rea.rerunfailures.no_cert_replay_sha256", not re.search(r"certif|replay|sha256", s, re.I), f"{len(re.findall(r'certif|replay|sha256', s, re.I))} hits")
    hl = [l.strip() for l in s.splitlines() if "hashlib" in l]
    chk("rea.rerunfailures.hashlib_only_xdist_crash_key", hl == ["import hashlib", "self.hmap[crashitem] = hashlib.sha1(crashitem.encode()).hexdigest()[:10]  # noqa: S324"], f"{len(hl)} lines: import + StatusDB crash-item key")
    a = member(ra, "pytest_randomly-5.0.0/src/pytest_randomly/__init__.py") or ""
    chk("rea.randomly.reseed_random_seed", re.search(r"def _reseed\(config: Config, offset: int = 0\) -> int:\n(?:.*\n){1,4}?\s+random\.seed\(seed\)", a) is not None)
    chk("rea.randomly.per_phase_crc32_nodeid", all(x in a for x in ("_reseed(item.config, (_crc32(item.nodeid) - 1) % 2**32)", "_reseed(item.config, _crc32(item.nodeid))", "_reseed(item.config, (_crc32(item.nodeid) + 1) % 2**32)")), "setup/call/teardown offsets")
    chk("rea.randomly.order_key_crc32_seed_nodeid", 'return _crc32(f"{seed}::{item.nodeid}")' in a)
    chk("rea.randomly.header_seed_only", 'return f"Using --randomly-seed={seed}"' in a)
    chk("rea.randomly.session_seed_cached", 'config.cache.set("randomly_seed", seed)' in a, "one seed per session, cached for --randomly-seed=last")
    chk("rea.randomly.no_cert_replay_hash", not re.search(r"certif|replay|sha256|hashlib|signature", a, re.I), f"{len(re.findall(r'certif|replay|sha256|hashlib|signature', a, re.I))} hits")
    st = json.loads((H / "rea/pypistats-pytest-rerunfailures-recent.json").read_text())["data"]
    sa = json.loads((H / "rea/pypistats-pytest-randomly-recent.json").read_text())["data"]
    chk("rea.reach_snapshot_2026_10_18", st["last_month"] == 37633838 and sa["last_month"] == 14182476, "downloads, not user counts")

def fixes():
    for f, h in PIN.items():
        chk(f"pin.{f}", sha(H / f) == h, h[:16])
    for v, h in SPEC.items():
        chk(f"fix.sha {v}", sha(H / f"fixes/test_cart.{v}.py") == h, h[:16])
    chk("fix.prefix_is_frozen_sample", sha(H / "sample/tests/test_cart.py") == SPEC["prefix"])
    chk("sample.sha256", all(sha(H / "sample" / f) == h for f, h in OTHER.items()) and len(OTHER) == 5, f"{len(OTHER)} other files")
    pre = (H / "fixes/test_cart.prefix.py").read_text().splitlines()
    want = {"wrong_fix": ["cart.DEFAULT_DISCOUNT = None  # reset once, at import"],
            "real_fix": ["import pytest", "", "", "", "@pytest.fixture(autouse=True)", "def _reset_discount():", "    yield", "    cart.DEFAULT_DISCOUNT = None"]}
    for v, ins in want.items():
        got = (H / f"fixes/test_cart.{v}.py").read_text().splitlines()
        ops = difflib.SequenceMatcher(a=pre, b=got, autojunk=False).get_opcodes()
        added = [l for o, i1, i2, j1, j2 in ops if o == "insert" for l in got[j1:j2]]
        ok = all(o in ("equal", "insert") for o, *_ in ops) and added == ins
        chk(f"fix.{v}_insertions_only", ok, f"{len(added)} lines inserted")
    chk("fix.test_names_unchanged", all(re.findall(r"^def (test_\w+)", (H / f"fixes/test_cart.{v}.py").read_text(), re.M) == ["test_total_without_discount", "test_total_with_discount"] for v in SPEC))
    chk("fix.app_untouched_by_patches", all("app/cart.py" not in (H / f"fixes/{v}.patch").read_text() for v in ("wrong_fix", "real_fix")))
    chk("pin.lock_excludes_reversed_packages", LOCK == ["iniconfig==2.1.0", "packaging==25.0", "pluggy==1.6.0", "pygments==2.19.2", "pytest==8.4.2"], " ".join(LOCK))
    chk("pin.dockerfile_base", f"FROM {BASE}\n" in (H / "pins/Dockerfile").read_text())
    # predictions are recomputed here, from the stdlib only
    ids = sorted([V, P, "tests/test_coupon.py::test_coupon_draw", "tests/test_stable.py::test_stable"])
    rec = []
    for s in range(100):
        o = ids[:]; random.Random(s).shuffle(o)
        if PRED["orders"][str(s)] != o: rec = None; break
        o.index(P) < o.index(V) and rec.append(s)
    chk("pred.sweep_recomputed", rec == FAILS, f"{len(FAILS)}/100 polluter-first seeds")
    chk("pred.both_outcomes_present", 20 <= len(FAILS) <= 80)
    hi = exact_hi_zero(20)
    chk("stats.20_of_20_exact_one_sided_upper_95", round(hi, 4) == 0.1391, f"{hi:.4f}")
    dd = (R / "rea-datadog-test-optimization/check-output.txt").read_text()
    chk("dd.attempt_to_fix_is_20_retries", "PASS\tdocs.attempt_to_fix_20" in dd)
    brief = (H / "BRIEF.md").read_text()
    bad = re.findall(r"(?i)(?:randomly|rerunfailures|datadog|trunk)[^.\n]{0,60}\b(?:cannot|can't|unable to|never)\b", brief)
    chk("scope.no_capability_denials_in_brief", not bad, f"{len(bad)} hits")

def judge(path):
    r = json.loads(Path(path).read_text())
    chk("res.pytest", r.get("pytest") == "8.4.2")
    chk("res.python_3_11", re.fullmatch(r"3\.11\.\d+", str(r.get("python"))) is not None, str(r.get("python")))
    chk("res.base_image", r.get("base_image") == BASE)
    chk("res.image_digest", re.fullmatch(r"sha256:[0-9a-f]{64}", str(r.get("image_digest"))) is not None)
    pf = sorted(x.lower() for x in r.get("pip_freeze") or [])
    chk("res.pip_freeze_is_lock", pf == LOCK, f"{len(pf)} pkgs")
    chk("res.reversed_packages_not_installed", not any(x.startswith(("pytest-randomly", "pytest-rerunfailures", "pytest_randomly", "pytest_rerunfailures")) for x in pf))
    c = r.get("cert") or {}
    sched = {s.get("source"): s.get("value") for s in c.get("schedule") or []}
    order = sched.get("order") or []
    chk("cert.node_is_victim", c.get("node_id") == V)
    chk("cert.env_identity", c.get("image_digest") == r.get("image_digest") and re.fullmatch(r"[0-9a-f]{64}", str(c.get("pip_freeze_sha"))) is not None and c.get("python") == r.get("python"), "image_digest, pip_freeze_sha, python")
    chk("cert.seed_fields_recorded", all(k in sched for k in ("order", "seed", "pythonhashseed")), str(sorted(sched)))
    chk("cert.order_polluter_then_victim", P in order and order[-1:] == [V] and order.index(P) < len(order) - 1, " > ".join(o.split("::")[1] for o in order))
    ef = c.get("expected_failure") or {}
    chk("cert.exc", ef.get("exc") == "AssertionError")
    chk("cert.sig", re.fullmatch(r"[0-9a-f]{64}", str(ef.get("sig"))) is not None, str(ef.get("sig"))[:16])
    vs = r.get("variants", {})
    chk("res.three_variants", sorted(vs) == sorted(SPEC), str(sorted(vs)))
    verdict = {}
    for v in SPEC:
        x = vs.get(v, {})
        chk(f"{v}.test_cart_sha", x.get("test_cart_sha256") == SPEC[v])
        chk(f"{v}.rest_of_sample_unchanged", x.get("sample_other_sha256") == OTHER, f"{len(x.get('sample_other_sha256') or {})}/{len(OTHER)} files")
        pr = x.get("plain_retry") or []
        chk(f"{v}.plain_retry_20_of_20_pass", len(pr) == 20 and set(pr) == {"passed"}, f"{pr.count('passed')}/{len(pr)}")
        cr = x.get("cert_replay") or []
        st = [e.get("victim") for e in cr]
        chk(f"{v}.cert_replay_3_runs", len(cr) == 3, str(st))
        chk(f"{v}.cert_replay_polluter_passes", len(cr) == 3 and all(e.get("polluter") == "passed" for e in cr))
        chk(f"{v}.cert_replay_identical", len(cr) == 3 and len(set(st)) == 1 and len(set(e.get("sig") for e in cr)) == 1)
        verdict[v] = "NOT_FIXED" if st == ["failed"] * 3 else "FIXED" if st == ["passed"] * 3 else "INCONSISTENT"
        if st == ["failed"] * 3:
            chk(f"{v}.failure_is_the_leak", all(e.get("exc") == "AssertionError" and re.search(r"assert 90 == 100", e.get("message") or "") for e in cr), (cr[0].get("message") or "")[:60].replace("\n", " "))
            chk(f"{v}.sig_equals_cert", cr[0].get("sig") == ef.get("sig"), (cr[0].get("sig") or "")[:16])
        sw = x.get("sweep") or {}
        ok = sorted(sw, key=int) == [str(i) for i in range(100)]
        got = sorted(int(k) for k, e in sw.items() if e.get("victim") == "failed")
        want = [] if v == "real_fix" else FAILS
        chk(f"{v}.sweep_0_99_victim_fail_seeds", ok and got == want, f"{len(got)} failing, want {len(want)}")
        chk(f"{v}.sweep_polluter_always_passes", ok and all(e.get("polluter") == "passed" for e in sw.values()))
    want = {"prefix": "NOT_FIXED", "wrong_fix": "NOT_FIXED", "real_fix": "FIXED"}
    chk("verdict.certified", verdict == want, str(verdict))
    plain = {v: ("FIXED" if (vs.get(v, {}).get("plain_retry") or []) == ["passed"] * 20 else "NOT_FIXED") for v in SPEC}
    chk("verdict.plain_retry_cannot_tell_wrong_from_real", plain["wrong_fix"] == plain["real_fix"] == "FIXED", str(plain))
    print(f"INFO\tcertified={verdict} plain_retry={plain}")

ap = argparse.ArgumentParser(); ap.add_argument("--results"); ap.add_argument("--rea-dir")
a = ap.parse_args()
if a.results:
    judge(a.results)
else:
    rea(Path(a.rea_dir).resolve() if a.rea_dir else H / "rea"); fixes()
print("GATE PASS" if not fails else f"GATE FAIL {fails}"); sys.exit(1 if fails else 0)
