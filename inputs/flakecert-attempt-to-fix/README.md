# flakecert-attempt-to-fix: certified Attempt-to-Fix gate (Hark, 2026-10-18, internal)

**Claim under test.** On the pinned failing schedule from the RSpec certificate (main b9f2c9e `audit/rspec-cert.json`: order_seed 0, srand_seed 0, image `ruby@sha256:2e32876d…`, lock `91102ec2…`):
- **Before the fix:** the certificate replay fails 3/3.
- **Wrong fix** (`before(:all)` reset): the replay still fails 3/3, so it's NOT FIXED.
- **Real fix** (`after` reset): the replay passes 3/3, so it's FIXED. An order sweep over seeds 0–99 shows 0 victim failures.
- **The 20/20 plain-retry control** passes for all three, so it can't tell the wrong fix from the real one.

**Status.** UNPROVEN until the Ruby run. The predictions rest on two things: the committed Ruby run at b9f2c9e, where the pinned schedule fails every replay and the plain rerun fails the victim 0/100, and the Jenkins port (at seed 0 the polluter sorts before the victim).

**Not claimed.**
- **No rate bound from 3 runs.** The 3/3 is a determinism check of a schedule already shown to replay identically.
- **No claim about Datadog's Ruby integration.** The plain-retry arm uses Datadog's documented count of 20 retries (`rea-datadog-test-optimization`, docs.attempt_to_fix_20).
- **20/20 plain passes still allow a failure rate up to 13.9%** (exact one-sided 95% upper bound, 1 - 0.05^(1/20)). That bound is about the plain retries, not about FlakeCert. The two-sided Wilson figure is not used.

## Commands
```
A1 cd inputs/flakecert-attempt-to-fix && sha256sum -c SHA256SUMS && python3 -B gate_attempt_to_fix.py | diff - gate-output.txt && bash run_controls.sh | diff - controls-output.txt && cd -
A2 make rspec-attempt-to-fix                       # Cursor builds it; writes audit/rspec-attempt-to-fix.json (Ruby run, team box)
A3 python3 -B inputs/flakecert-attempt-to-fix/gate_attempt_to_fix.py --results audit/rspec-attempt-to-fix.json   # GATE PASS, exit 0
A4 jq -e '([range(20)|"passed"]) as $p | .variants.wrong_fix.plain_retry==$p and .variants.real_fix.plain_retry==$p' audit/rspec-attempt-to-fix.json
A5 for m in mutant-wrong-fix-accepted mutant-plain-retry-only mutant-schedule-drift mutant-real-fix-edits-model; do ! python3 -B inputs/flakecert-attempt-to-fix/gate_attempt_to_fix.py --results inputs/flakecert-attempt-to-fix/controls/$m.json || exit 1; done
A6 make unit && make verify OFFLINE=1
```
A1 also needs `inputs/rea-datadog-test-optimization/` (it pins the 20-retry doc line), so copy it in with this folder.

**Expected A3 tail:**
```
INFO	certified={'prefix': 'NOT_FIXED', 'wrong_fix': 'NOT_FIXED', 'real_fix': 'FIXED'} plain_retry={'prefix': 'FIXED', 'wrong_fix': 'FIXED', 'real_fix': 'FIXED'}
GATE PASS
```

## Files
- **`gate_attempt_to_fix.py`:** run with no arguments for the self-check (21 checks, output in `gate-output.txt`), or with `--results` to judge the runner's file.
- **`fixes/`:** `cart_spec.{prefix,wrong_fix,real_fix}.rb` plus the two `.patch` diffs. Only `spec/models/cart_spec.rb` changes, by one hook line and a blank line.
- **`pins/`:** the b9f2c9e cert and the results from that Ruby run, sha-pinned in the gate.
- **`make_controls.py`:** writes `controls/` (a synthetic-good gate-logic fixture, NOT Ruby output, plus 4 mutants).
- **`run_controls.sh` and `controls-output.txt`:** S0 = 0, G1 = 0, all 4 mutants = 1, CONTROLS OK.
- **`CURSOR_TASK.md`:** the build task.
