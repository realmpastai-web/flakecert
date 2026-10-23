#!/usr/bin/env python3
"""Write controls/: a synthetic-good gate-logic fixture (NOT pytest output), 7 results mutants, and a tampered-sdist dir."""
import copy, hashlib, io, json, tarfile
from pathlib import Path
H = Path(__file__).resolve().parent; C = H / "controls"; C.mkdir(exist_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
pred = json.loads((H / "expected/predicted-sweep.json").read_text())
V, P, FAILS = pred["victim"], pred["polluter"], set(pred["victim_fails"])
other = {l.split("  ", 1)[1][len("sample/"):]: l.split("  ")[0] for l in (H / "sample.sha256").read_text().splitlines() if not l.endswith("tests/test_cart.py")}
lock = [l.split()[0] for l in (H / "pins/requirements.lock").read_text().splitlines() if l and not l.startswith("#")]
IMG, SIG, MSG = "sha256:" + "1" * 64, "a" * 64, "assert 90 == 100\n +  where 90 = total()"
good = {"pytest": "8.4.2", "python": "3.11.14", "base_image": "python@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89",
        "image_digest": IMG, "pip_freeze": lock, "_note": "synthetic gate-logic fixture, not pytest output",
        "cert": {"node_id": V, "image_digest": IMG, "pip_freeze_sha": "2" * 64, "python": "3.11.14",
                 "schedule": [{"source": "order", "value": [P, V]}, {"source": "seed", "value": ""}, {"source": "pythonhashseed", "value": ""}],
                 "expected_failure": {"exc": "AssertionError", "sig": SIG}}, "variants": {}}
fail = {"victim": "failed", "polluter": "passed", "exc": "AssertionError", "message": MSG, "sig": SIG}
ok = {"victim": "passed", "polluter": "passed", "exc": None, "message": None, "sig": None}
for v in ("prefix", "wrong_fix", "real_fix"):
    good["variants"][v] = {"test_cart_sha256": sha(H / f"fixes/test_cart.{v}.py"), "sample_other_sha256": dict(other),
        "plain_retry": ["passed"] * 20, "cert_replay": [dict(ok if v == "real_fix" else fail) for _ in range(3)],
        "sweep": {str(s): {"victim": "failed" if (s in FAILS and v != "real_fix") else "passed", "polluter": "passed"} for s in range(100)}}
def w(name, d): (C / f"{name}.json").write_text(json.dumps(d, indent=1, sort_keys=True) + "\n")
w("synthetic-good-results", good)
m = copy.deepcopy(good); m["variants"]["wrong_fix"]["cert_replay"] = [dict(ok) for _ in range(3)]; w("mutant-wrong-fix-accepted", m)
m = copy.deepcopy(good); m["cert"] = {}; [x.pop("cert_replay") for x in m["variants"].values()]; w("mutant-plain-retry-only", m)
m = copy.deepcopy(good); m["cert"]["schedule"][0]["value"] = [V, P]; w("mutant-schedule-drift", m)
m = copy.deepcopy(good); m["variants"]["real_fix"]["sample_other_sha256"]["app/cart.py"] = "0" * 64; w("mutant-real-fix-edits-app", m)
m = copy.deepcopy(good); [m["cert"].pop(k) for k in ("pip_freeze_sha", "python")]; m["cert"]["schedule"] = m["cert"]["schedule"][:1]; w("mutant-omitted-env-and-seed", m)
m = copy.deepcopy(good); m["pip_freeze"] = lock + ["pytest-rerunfailures==16.7"]; w("mutant-rerun-plugin-installed", m)
m = copy.deepcopy(good); m["variants"]["prefix"]["cert_replay"] = [dict(fail, sig="b" * 64) for _ in range(3)]; w("mutant-fabricated-sig", m)
# tampered sdist: rerunfailures source gains a seed line; same filename, different bytes
T = C / "rea-tampered"; T.mkdir(exist_ok=True)
(T / "pytest_randomly-5.0.0.tar.gz").write_bytes((H / "rea/pytest_randomly-5.0.0.tar.gz").read_bytes())
src = tarfile.open(H / "rea/pytest_rerunfailures-16.7.tar.gz", "r:gz"); buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.PAX_FORMAT) as out:
    for mem in src.getmembers():
        data = src.extractfile(mem).read() if mem.isfile() else None
        if mem.name.endswith("src/pytest_rerunfailures.py"):
            data = data.replace(b"def pytest_addoption(parser):", b"REPLAY_SEED = 0  # tampered\n\n\ndef pytest_addoption(parser):", 1); mem.size = len(data)
        mem.mtime = 0; out.addfile(mem, io.BytesIO(data) if data is not None else None)
(T / "pytest_rerunfailures-16.7.tar.gz").write_bytes(buf.getvalue())
print("wrote", sorted(p.name for p in C.glob("*.json")), "and rea-tampered/")
