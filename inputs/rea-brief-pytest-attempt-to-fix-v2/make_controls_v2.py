#!/usr/bin/env python3
"""Write controls/ for gate v2: a synthetic-good gate-logic fixture (NOT pytest output) whose replays carry tb_norm,
the 7 v1 results mutants rebuilt on it, 7 v2 mutants, and the real PR #7 results (3ec5eb8, no tb_norm) as a reject control."""
import copy, hashlib, json, shutil
from pathlib import Path
HERE = Path(__file__).resolve().parent; H = HERE.parent / "rea-brief-pytest-attempt-to-fix"; C = HERE / "controls"; C.mkdir(exist_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
hsh = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()
pred = json.loads((H / "expected/predicted-sweep.json").read_text())
V, P, FAILS = pred["victim"], pred["polluter"], set(pred["victim_fails"])
other = {l.split("  ", 1)[1][len("sample/"):]: l.split("  ")[0] for l in (H / "sample.sha256").read_text().splitlines() if not l.endswith("tests/test_cart.py")}
lock = [l.split()[0] for l in (H / "pins/requirements.lock").read_text().splitlines() if l and not l.startswith("#")]
IMG = "sha256:" + "1" * 64
MSG = "assert 90 == 100\n +  where 90 = total()\n +    where total = <app.cart.Cart object at 0x7f00deadbeef>.total"
def tb(line, e="E       assert 90 == 100\nE        +  where 90 = total()", tail="AssertionError", extra=""):
    return ("_________________________ test_total_without_discount __________________________\n\n"
            "    def test_total_without_discount():\n>       assert Cart([60, 40]).total() == 100\n"
            f"{e}\n\n{extra}tests/test_cart.py:{line}: {tail}\n")
TB6, TB7 = tb(6), tb(7)
good = {"pytest": "8.4.2", "python": "3.11.14", "base_image": "python@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89",
        "image_digest": IMG, "pip_freeze": lock, "_note": "synthetic gate-logic fixture, not pytest output",
        "cert": {"node_id": V, "image_digest": IMG, "pip_freeze_sha": "2" * 64, "python": "3.11.14",
                 "schedule": [{"source": "order", "value": [P, V]}, {"source": "seed", "value": ""}, {"source": "pythonhashseed", "value": ""}],
                 "expected_failure": {"exc": "AssertionError", "sig": hsh(TB6), "tb_norm": TB6}}, "variants": {}}
fail = lambda t, **kw: dict({"victim": "failed", "polluter": "passed", "exc": "AssertionError", "message": MSG, "sig": hsh(t), "tb_norm": t}, **kw)
ok = {"victim": "passed", "polluter": "passed", "exc": None, "message": None, "sig": None}
for v, t in (("prefix", TB6), ("wrong_fix", TB7), ("real_fix", None)):
    good["variants"][v] = {"test_cart_sha256": sha(H / f"fixes/test_cart.{v}.py"), "sample_other_sha256": dict(other),
        "plain_retry": ["passed"] * 20, "cert_replay": [dict(ok) if t is None else fail(t) for _ in range(3)],
        "sweep": {str(s): {"victim": "failed" if (s in FAILS and v != "real_fix") else "passed", "polluter": "passed"} for s in range(100)}}
def w(name, d): (C / f"{name}.json").write_text(json.dumps(d, indent=1, sort_keys=True) + "\n")
def wf(name, rows):
    m = copy.deepcopy(good); m["variants"]["wrong_fix"]["cert_replay"] = rows; w(name, m)
w("synthetic-good-results", good)
# v1 mutants, rebuilt on the v2 synthetic-good
m = copy.deepcopy(good); m["variants"]["wrong_fix"]["cert_replay"] = [dict(ok) for _ in range(3)]; w("mutant-wrong-fix-accepted", m)
m = copy.deepcopy(good); m["cert"] = {}; [x.pop("cert_replay") for x in m["variants"].values()]; w("mutant-plain-retry-only", m)
m = copy.deepcopy(good); m["cert"]["schedule"][0]["value"] = [V, P]; w("mutant-schedule-drift", m)
m = copy.deepcopy(good); m["variants"]["real_fix"]["sample_other_sha256"]["app/cart.py"] = "0" * 64; w("mutant-real-fix-edits-app", m)
m = copy.deepcopy(good); [m["cert"].pop(k) for k in ("pip_freeze_sha", "python")]; m["cert"]["schedule"] = m["cert"]["schedule"][:1]; w("mutant-omitted-env-and-seed", m)
m = copy.deepcopy(good); m["pip_freeze"] = lock + ["pytest-rerunfailures==16.7"]; w("mutant-rerun-plugin-installed", m)
m = copy.deepcopy(good); m["variants"]["prefix"]["cert_replay"] = [dict(fail(TB6), sig="b" * 64) for _ in range(3)]; w("mutant-fabricated-sig", m)
# v2 mutants (user's list 1-5, plus a wrong-size line shift)
wf("v2-m1-tb-norm-not-hashing-to-sig", [dict(fail(TB7), tb_norm=TB7.replace("90 == 100", "90 == 101")) for _ in range(3)])
wf("v2-m2-wrong-fix-copies-cert-sig", [fail(TB6) for _ in range(3)])
t = tb(7, e="E       TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'", tail="TypeError")
wf("v2-m3a-line-moved-different-exception", [fail(t, exc="TypeError", message="TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'") for _ in range(3)])
t = tb(7, e="E       assert 80 == 100\nE        +  where 80 = total()")
wf("v2-m3b-line-moved-different-message", [fail(t, message=MSG.replace("90", "80")) for _ in range(3)])
t = tb(7, tail="", extra="").replace("tests/test_cart.py:7: \n", "tests/test_cart.py:7: \n_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _\n\n    def total(self):\n>       return sum(self.items) - discount\n\napp/cart.py:9: AssertionError\n")
wf("v2-m4-non-test-frame-changed", [fail(t) for _ in range(3)])
m = copy.deepcopy(good); m["variants"]["real_fix"]["cert_replay"] = [fail(tb(9)) for _ in range(3)]; w("v2-m5-real-fix-still-fails", m)
wf("v2-m6-line-shift-wrong-size", [fail(tb(8)) for _ in range(3)])
shutil.copyfile("/tmp/pr7-results.json", C / "pr7-3ec5eb8-results-no-tb-norm.json")
print("wrote", sorted(p.name for p in C.glob("*.json")))
