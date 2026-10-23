#!/usr/bin/env python3
"""Writes controls/*.json: a synthetic results file that matches the predictions (gate-logic fixture, NOT Ruby output)
and four mutants that must each fail. Deterministic: python3 -B make_controls.py && sha256sum -c SHA256SUMS"""
import copy, json
from pathlib import Path
H = Path(__file__).resolve().parent; R = H.parent
cert = json.loads((H / "pins/rspec-cert-b9f2c9e.json").read_text())
fails = set(json.loads((R / "flakecert-rspec-runner/expected/predicted-cart-order.json").read_text())["victim_fails"])
other = {l.split("  ")[1]: l.split("  ")[0] for l in (R / "flakecert-rspec-runner/sample.sha256").read_text().splitlines() if not l.endswith("spec/models/cart_spec.rb")}
spec = {"prefix": "8496e9a8e342ff4884b7613362cb5dcb80ab98246df32511a0bf98cb39cf02a3",
        "wrong_fix": "ed722088487412a8a8c32151e0ed55784a97d75104e533d6eab3d070faf65757",
        "real_fix": "7e5cb3c8b09f32d2d6761554e378208e7208a649172dbc5415b5e723b76ece84"}
MSG = "\nexpected: 100\n     got: 90\n\n(compared using ==)\n"
def fail(sig): return {"victim": "failed", "polluter": "passed", "exc": cert["expected_failure"]["exc"], "message": MSG, "sig": sig}
ok = {"victim": "passed", "polluter": "passed", "exc": None, "message": None, "sig": None}
good = {"rspec_core": "3.13.6", "image_digest": cert["image_digest"], "lock_sha256": cert["lock_sha256"], "schedule": cert["schedule"], "variants": {
    "prefix": {"cart_spec_sha256": spec["prefix"], "sample_other_sha256": other, "plain_retry": ["passed"] * 20, "cert_replay": [fail(cert["expected_failure"]["sig"])] * 3},
    "wrong_fix": {"cart_spec_sha256": spec["wrong_fix"], "sample_other_sha256": other, "plain_retry": ["passed"] * 20, "cert_replay": [fail("synthetic-wrong-fix-sig")] * 3,
                  "sweep": {str(s): {"victim": "failed" if s in fails else "passed", "polluter": "passed"} for s in range(100)}},
    "real_fix": {"cart_spec_sha256": spec["real_fix"], "sample_other_sha256": other, "plain_retry": ["passed"] * 20, "cert_replay": [ok] * 3,
                 "sweep": {str(s): {"victim": "passed", "polluter": "passed"} for s in range(100)}}}}
out = {"synthetic-good-results.json": good}
m = copy.deepcopy(good); m["variants"]["wrong_fix"]["cert_replay"] = [ok] * 3; out["mutant-wrong-fix-accepted.json"] = m
m = copy.deepcopy(good)
for v in m["variants"].values(): v["cert_replay"] = []
out["mutant-plain-retry-only.json"] = m
m = copy.deepcopy(good); m["schedule"] = {"order_seed": 1, "srand_seed": 0}; out["mutant-schedule-drift.json"] = m
m = copy.deepcopy(good); m["variants"]["real_fix"]["sample_other_sha256"] = dict(other, **{"app/models/cart.rb": "0" * 64}); out["mutant-real-fix-edits-model.json"] = m
(H / "controls").mkdir(exist_ok=True)
for n, d in out.items():
    (H / "controls" / n).write_text(json.dumps(d, indent=1, sort_keys=True) + "\n")
print("wrote", ", ".join(out))
