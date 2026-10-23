# CURSOR TASK: flakecert-attempt-to-fix (internal)

Inputs: `inputs/flakecert-attempt-to-fix/` on `hark-inputs-2026-10-18`. Base: flakecert main b9f2c9e.

## Goal
Add `make rspec-attempt-to-fix` (module `flakecert.runners.rspec_attempt_to_fix`, reusing `flakecert/runners/rspec.py`). It writes `audit/rspec-attempt-to-fix.json` in the shape in the gate's docstring.

## Steps
For each variant in prefix, wrong_fix and real_fix:
1. **Copy and patch.** Copy `inputs/flakecert-rspec-runner/sample/` to a temp dir and replace `spec/models/cart_spec.rb` with `inputs/flakecert-attempt-to-fix/fixes/cart_spec.<variant>.rb`. Record `cart_spec_sha256`, plus `sample_other_sha256` for the 7 other files, keyed as in `sample.sha256`.
2. **Same image.** Run in the same pinned image, `FROM ruby@sha256:2e32876d…`, with the committed `envs/rspec/Gemfile.lock` and `--network none`. Mount the variant's sample, or build one image per variant whose only difference is that file. `image_digest` and `lock_sha256` must equal `audit/rspec-cert.json`.
3. **plain_retry.** Run `bundle exec rspec --format json --out …` 20 times: defined order, no `--order`, no srand. Record the victim `./spec/models/cart_spec.rb[1:1]` status per run.
4. **cert_replay.** Run the certificate's `replay` command 3 times at `{order_seed: 0, srand_seed: 0}`, and record:
   - victim and polluter status;
   - for a failure: `exc`, the `message`, and `sig` (the `_failure_of` signature).
5. **sweep** (wrong_fix and real_fix only). Run `--order rand:S --require /flakecert/srand.rb` with FLAKECERT_SRAND=0 for S in 0..99, once each. Record victim and polluter status.

Do not change the sample, the fixes, the gate, or `audit/rspec-cert.json`.

## Acceptance
A1–A6 in `inputs/flakecert-attempt-to-fix/README.md`. A3 must print `GATE PASS`, with the INFO line certified={prefix: NOT_FIXED, wrong_fix: NOT_FIXED, real_fix: FIXED}.

**If any prediction fails, stop and report the raw JSON. Don't edit expectations.** Predictions that could fail:
- wrong_fix sweep ≠ the 39 prefix seeds;
- real_fix sweep has a victim failure;
- the prefix sig differs from the cert.

## Out of scope
The Datadog upload, any rate claim from 3 replays, other runners, and the exponential speedup.
