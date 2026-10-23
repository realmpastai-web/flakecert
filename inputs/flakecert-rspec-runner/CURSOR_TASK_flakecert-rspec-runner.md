# CURSOR TASK: flakecert-rspec-runner (frozen by Hark 2026-10-18; internal)
**Evidence rule:** a claim counts only with the file, log or command output behind it. Inputs are frozen in `inputs/flakecert-rspec-runner/` (SHA256SUMS). Never edit them.

## Goal
Add a FlakeCert runner for RSpec that pins both nondeterminism sources rspec-core exposes, order and Ruby's global RNG, as a schedule. It records what rspec-core's own output lacks and replays any schedule bit-for-bit. Base the branch on main 7d22e2d. Keep the pytest path unchanged.

## What the reverse showed (rspec-core 3.13.6, MIT, gem sha256 a8823c64…828b2d = rubygems API; gate self-check 38/38)
- **Seed and order:**
  - `--seed N` is literally `--order rand:N` (option_parser.rb:68-69).
  - Random order is `items.sort_by { jenkins_hash_digest(seed.to_s + item.id) }` (ordering.rb:29). It's applied to child groups (example_group.rb:615) and to examples (example_group.rb:649).
  - The default seed is `rand(0xFFFF)` (ordering.rb:149).
- **The gap: `--seed` does not seed Ruby's RNG.**
  - The only `Kernel.srand` in the gem is in the generated spec_helper template (line 96). It sits inside a `=begin/=end` block, so it's off by default (grep-srand.txt; check `srand.template_commented_out`).
  - A suite that calls `rand` is not reproducible from the printed seed.
- **What the output records:**
  - JSON: `version`; `seed` only if random order was used; per example `id, description, full_description, status, file_path, line_number, run_time, pending_message`; plus summary.
  - `.rspec_status`: only `example_id, status, run_time`.
  - **Missing:** Ruby version, Gemfile.lock hash, image digest, RNG seed, schedule, any bound (grep-json-env.txt: no matches).
- **REA:** `rea-agents@6.5.0 extract-artifact` rejects both the .gem and data.tar.gz (`unsupported binary format`, target/rea-extract-*.json). The reverse is static `tar`/`grep -n`, and nothing was executed.

## Frozen sample (`sample/`, Rails layout: app/models + spec/models; the rails gem is deliberately left out)
- `Cart` keeps class-level state. `cart_spec.rb[1:2]` sets `Cart.default_discount = 10` and never resets it. The victim `[1:1]` fails only when `[1:2]` runs first. Defined order runs the victim first, so the plain baseline never fails it.
- `coupon_spec.rb[1:2]` passes only when `rand(2) == 1`, so it's RNG-dependent.
- 3 stable controls.
- **Prediction:** `predict_order.py` ports the Jenkins ordering to Python. For order seeds 0..99, the victim fails on exactly 39 (`expected/predicted-cart-order.json`). That's UNPROVEN until step A3 runs it in real Ruby. **If A3 mismatches, stop and report. Don't edit the prediction.**

## Build
1. `envs/rspec/Dockerfile`: `FROM ruby@sha256:2e32876dfe84913ec84eb4a59617f72dab7c0989d38f8219487491e384543975` (the ruby:3.3-slim-bookworm index, resolved 2026-10-18 10:49 UTC).
   - Copy the sample. Run `bundle lock` once and commit `envs/rspec/Gemfile.lock`. Don't edit the frozen sample.
   - Then `bundle install --frozen`. Log `ruby -v` and the lock sha256 to `envs/rspec/install.log`.
2. `flakecert/runners/rspec.py`. A schedule is `{order_seed:S, srand_seed:R}`, with d = 2.
   - Command: `bundle exec rspec --order rand:S --require /flakecert/srand.rb --format json --out /out/S-R.json`.
   - `srand.rb` is one line: `Kernel.srand(Integer(ENV.fetch("FLAKECERT_SRAND")))`, with FLAKECERT_SRAND=R.
   - Baseline is plain `bundle exec rspec --format json` (rspec defaults: defined order, no srand).
   - Parse rspec's JSON `examples[].id/status`. Fail if its `seed` ≠ S.
3. `make rspec-sample`, writing `audit/rspec-results.json` in the gate's shape: `rspec_core`, `image_digest`, `lock_sha256`, `schedules[]`.
   - Order sweep: S = 0..99 with R = 0.
   - srand sweep: S = 0 with R = 0..99.
   - Run every schedule twice (replay).
   - Add `baseline: {runs: 100, victim_failures, draw_failures}`.
4. Certificate for a failing schedule: the existing cert fields with `lock_sha256` in place of the pip-freeze hash, plus `schedule {order_seed, srand_seed}`, `d: 2`, and a replay command.
5. Tests:
   - parsing rspec JSON;
   - the seed mismatch abort;
   - the cert carries lock_sha256, image_digest and a schedule;
   - a port test that runs `predict_order.py`'s Jenkins against 3 hard-coded Ruby-computed values (record them in A3).

## Acceptance (fresh clone; any miss = non-zero exit)
```
A1 cd inputs/flakecert-rspec-runner && sha256sum -c SHA256SUMS && python3 gate_rspec_runner.py | diff - gate-output.txt && cd -
A2 make rspec-sample                     # builds image, writes audit/rspec-results.json + envs/rspec/install.log
A3 python3 inputs/flakecert-rspec-runner/gate_rspec_runner.py --results audit/rspec-results.json   # GATE PASS: victim = Jenkins prediction on all 100 order seeds, polluter+stable always pass, every schedule replayed identically, srand decides the draw
A4 jq -e '.baseline.runs==100 and .baseline.victim_failures==0' audit/rspec-results.json   # plain baseline never sees the order flake
A5 ! python3 inputs/flakecert-rspec-runner/gate_rspec_runner.py --results inputs/flakecert-rspec-runner/controls/mutant-ignore-order-seed.json
A6 make unit && make verify OFFLINE=1    # pytest path and the 9 gates unchanged
```
- **Mutant control:** `controls/mutant-ignore-order-seed.json` is a runner that drops `--order rand:S`. The gate fails it on `res.victim_matches_jenkins_prediction` (controls/mutant-ignore-order-seed.log, exit 1).
- `controls/synthetic-good-results.json` is a gate-logic fixture written by Hark, not Ruby output. It passes.

## Out of scope / do not
- No Lua or Mac/iOS runners. No rails/activerecord gems. No Datadog upload. No external copy.
- No claims about Ruby's hash seed or GC/thread nondeterminism. They're untested here: UNPROVEN.
- Don't touch ledger/, certs/ or evidence/ for the Python F-tests. Don't claim the exponential speedup (UNPROVEN).
