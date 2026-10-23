#!/usr/bin/env python3
"""Gate for the FlakeCert RSpec runner (frozen by Hark 2026-10-18).

  python3 gate_rspec_runner.py                     # self-check of frozen target facts + sample + prediction
  python3 gate_rspec_runner.py --results R.json    # judge a runner's results file

Results file shape (written by the runner, see CURSOR_TASK):
  {"rspec_core": "3.13.6", "image_digest": "sha256:<64hex>", "lock_sha256": "<64hex>",
   "schedules": [{"order_seed": int, "srand_seed": int, "examples": {"<rspec id>": "passed|failed|pending"}}]}
"""
import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path
H = Path(__file__).resolve().parent
T = H / "target"; X = T / "src-excerpts"
IMAGE = "sha256:2e32876dfe84913ec84eb4a59617f72dab7c0989d38f8219487491e384543975"  # ruby:3.3-slim-bookworm index digest, 2026-10-18 10:49 UTC
V, P = "./spec/models/cart_spec.rb[1:1]", "./spec/models/cart_spec.rb[1:2]"
DRAW = "./spec/models/coupon_spec.rb[1:2]"
STABLE = ["./spec/models/coupon_spec.rb[1:1]", "./spec/models/stable_spec.rb[1:1]", "./spec/models/stable_spec.rb[1:2]"]
fails = []
def chk(tag, ok, note=""):
    print(("PASS" if ok else "FAIL") + f"\t{tag}\t{note}"); ok or fails.append(tag)
def line(f, n): return (X / f).read_text().splitlines()[n - 1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def self_check():
    api = json.loads((T / "api-rspec-core.json").read_text())
    pins = (T / "gem.sha256").read_text()
    chk("gem.version", api["version"] == "3.13.6")
    chk("gem.license_mit", api["licenses"] == ["MIT"])
    chk("gem.sha256_matches_rubygems_api", f"{api['sha']}  rspec-core-3.13.6.gem" in pins, api["sha"][:16])
    cs = (T / "checksums.yaml").read_text()
    d = re.search(r"([0-9a-f]{64})\s+gem/data.tar.gz", pins).group(1)
    chk("gem.data_tar_matches_signed_checksums", f"data.tar.gz: {d}" in cs, d[:16])
    for h, f in (l.split("  ") for l in (T / "src-excerpts.sha256").read_text().splitlines()):
        chk(f"excerpt.sha {f}", sha(X / f) == h)
    chk("rea.unsupported_recorded", all(json.loads((T / n).read_text()).get("details", {}).get("reason") == "unsupported binary format"
                                        for n in ["rea-extract-gem.json", "rea-extract-data-tar.json"]))
    # where seed and order are set
    chk("cli.seed_is_order_rand", "parser.on('--seed SEED', Integer, 'Equivalent of --order rand:SEED.')" in line("option_parser.rb", 68)
        and 'options[:order] = "rand:#{seed}"' in line("option_parser.rb", 69))
    chk("cli.order_type_seed", "parser.on('--order TYPE[:SEED]'" in line("option_parser.rb", 59))
    chk("order.sort_by_jenkins", "items.sort_by { |item| jenkins_hash_digest(seed + item.id) }" in line("ordering.rb", 29))
    chk("order.default_seed_rand_0xFFFF", "@seed = rand(0xFFFF)" in line("ordering.rb", 149))
    chk("example_group.orders_examples", "ordering_strategy.order(filtered_examples)" in line("example_group.rb", 649))
    chk("example_group.orders_children", "ordering_strategy.order(children)" in line("example_group.rb", 615))
    chk("id.rerun_path_scoped_id", '"#{metadata[:rerun_file_path]}[#{metadata[:scoped_id]}]"' in line("metadata.rb", 106))
    # srand: only in the generated template, inside =begin/=end
    g = (T / "grep-srand.txt").read_text().strip().splitlines()
    chk("srand.only_in_template", g == ["src/lib/rspec/core/project_initializer/spec/spec_helper.rb:96:  Kernel.srand config.seed"], str(len(g)))
    tl = (X / "project_initializer/spec/spec_helper.rb").read_text().splitlines()
    b = max(i for i, l in enumerate(tl[:95]) if l.startswith("=begin")); e = min(i for i, l in enumerate(tl) if l.startswith("=end") and i > 95)
    chk("srand.template_commented_out", b < 95 < e, f"=begin@{b+1} =end@{e+1}")
    # what run output records
    jf = (X / "formatters/json_formatter.rb").read_text()
    keys = re.findall(r":(\w+)\s*=>", jf[jf.index("def format_example"):])
    chk("json.example_keys", keys == ["id", "description", "full_description", "status", "file_path", "line_number", "run_time", "pending_message"], ",".join(keys))
    chk("json.seed_only_if_used", "return unless notification.seed_used?" in jf and "@output_hash[:seed] = notification.seed" in jf)
    chk("json.version_key", ":version => RSpec::Core::Version::STRING" in jf)
    chk("text.prints_seed", 'Randomized with seed #{seed}' in line("notifications.rb", 283))
    sp = (X / "example_status_persister.rb").read_text()
    chk("persister.keys", all(k in sp for k in [":example_id => ex.id", ":status     =>", ":run_time   =>"]))
    chk("gap.no_env_fields", (T / "grep-json-env.txt").read_text().strip() == "(no matches)", "RUBY_VERSION|Gemfile.lock|digest absent")
    # sample + prediction
    for h, f in (l.split("  ") for l in (H / "sample.sha256").read_text().splitlines()):
        chk(f"sample.sha {f}", sha(H / "sample" / f) == h)
    out = subprocess.run([sys.executable, str(H / "predict_order.py")], capture_output=True, text=True).stdout
    chk("predict.reproduces_frozen", out == (H / "expected/predicted-cart-order.json").read_text())
    pr = json.loads(out); chk("predict.split_39_61", (len(pr["victim_fails"]), len(pr["victim_passes"])) == (39, 61))

def judge(r):
    pr = json.loads((H / "expected/predicted-cart-order.json").read_text())
    chk("res.rspec_core", r.get("rspec_core") == "3.13.6")
    chk("res.image_digest", r.get("image_digest") == IMAGE)
    chk("res.lock_sha256", bool(re.fullmatch(r"[0-9a-f]{64}", r.get("lock_sha256", ""))))
    sch = r.get("schedules", [])
    by = {}
    for s in sch: by.setdefault((s["order_seed"], s["srand_seed"]), []).append(s["examples"])
    order_sweep = [(o, 0) for o in range(100)]
    chk("res.order_sweep_present", all(k in by for k in order_sweep))
    bad = [o for o, _ in order_sweep if k_ok(by, (o, 0)) and (by[(o, 0)][0].get(V) == "failed") != (o in pr["victim_fails"])]
    chk("res.victim_matches_jenkins_prediction", all(k_ok(by, k) for k in order_sweep) and not bad, f"mismatched order seeds {bad[:8]}")
    allx = [e for runs in by.values() for e in runs]
    chk("res.polluter_always_passes", bool(allx) and all(e.get(P) == "passed" for e in allx))
    chk("res.stable_always_pass", bool(allx) and all(e.get(t) == "passed" for e in allx for t in STABLE))
    rep = [k for k, v in by.items() if len(v) >= 2]
    chk("res.every_schedule_replayed", len(rep) == len(by) and len(by) > 0, f"{len(rep)}/{len(by)}")
    chk("res.replay_identical", all(all(x == v[0] for x in v) for v in by.values()))
    draw = {k[1]: v[0].get(DRAW) for k, v in by.items() if k[0] == 0}
    chk("res.srand_sweep_0_99", all(s in draw for s in range(100)))
    chk("res.srand_controls_draw", {"passed", "failed"} <= set(draw.values()), f"{sorted(set(draw.values()))}")
def k_ok(by, k): return k in by and len(by[k]) > 0

ap = argparse.ArgumentParser(); ap.add_argument("--results"); a = ap.parse_args()
if a.results: judge(json.loads(Path(a.results).read_text()))
else: self_check()
print("GATE " + ("PASS" if not fails else f"FAIL {fails}")); sys.exit(1 if fails else 0)
