# Spec G1: certify-the-fix PR check for RSpec (flakecert certify-rspec), validated on fastlane#30184

Product claim under test: given a base commit, a PR head and the seed of a failing CI run, FlakeCert finds each order-dependent
failure, NAMES its polluter by itself, and issues a replayable certificate that says whether the PR fixes it, where plain retry
says "fixed" wrongly. Not claimed: polluter search itself (rspec-core already ships --bisect, B1).
Evidence: reverse/recon-bisect.log (regenerate: reverse/recon-bisect.sh), reverse/breaker-sets.log, and F6 inputs
inputs/dryrun-2026-10-19-f6/reverse/recon.log (cited as F6-M*). Static only; Hark executed nothing from fastlane.

## What rspec --bisect does (rspec-core 3.12.2 .gem sha256 155b5448...2551, recon-bisect.log)
- B1: `--seed N` == `--order rand:N`; `--bisect[=verbose]` swaps in the Bisect invocation.
- B3: candidates = all example ids minus the original failures. A subset "reproduces" iff ALL original failures fail
  (example_minimizer.rb:150). So on the full suite it returns ONE union polluter set for all 31 failures, with no
  polluter->victim attribution. Deterministic failures are carried along harmlessly (they fail anyway).
- B3: halving tries ignoring the EARLIER half first (example_minimizer.rb:57-61), so among several sufficient culprits it keeps
  the latest one in run order. Aborts if the subset order differs from the original (example_minimizer.rb:158-165).
- B4: the repro command keeps all original non-location args (incl. --seed) and drops --bisect.
- B5/B6: default runner is fork; the parent boots once, including `--require` files; each subset runs in a fork.
- B7: random order is a per-sibling sort_by jenkins(seed+id), so a subset keeps the original relative order.
- B8: fastlane .rspec at 76eeb3f has `--require ./spec_helper`, so under fork spec_helper's top-level code runs once.

## Gap FlakeCert fills (what it adds)
Per-victim attribution plus a cross-commit verdict plus a replayable certificate. Plain retry of a victim alone passes at the
prefix (F4), so a retry-based "fixed" is wrong for every order-dependent id.

## Algorithm (tool input: repo tarball URLs for base+head, suite path, seed; NO victim or polluter names)
S1 discover: at base, `rspec <suite> --seed N --format json --out s1.json` (+ doc log). Failing ids + full run order.
S2 classify: each failing id alone, 3 reps. ORDER-DEPENDENT iff it failed in S1 and passes alone 3/3.
S3 attribute, per OD victim v: `rspec --bisect=verbose --seed N <every non-failing S1 id that ran before v, in S1 order> <v>`.
   Record the "minimal reproduction command"; polluter set P(v) = its ids minus v. If bisect reports no failure or an ordering
   abort, record that and mark v UNATTRIBUTED (no certificate).
S4 certify, per attributed v, at base and head, 3 reps each:
   A = `rspec --seed N P(v) v` (polluter-then-victim), B = victim alone (plain-retry arm), C = `rspec --order defined <v file:id> <P files:ids>`
   (swapped). Verdict at a commit: NOT_FIXED iff A fails 3/3 with one first error class; FIXED iff A passes 3/3. CERTIFIED iff
   base NOT_FIXED, head FIXED, C passes 3/3 at both, no rep disagreement (pass/fail, error class, order, failed ids).
   CONTROL = an attributed v whose verdict is NOT_FIXED at both (a PR that does not fix it).
S5 emit certificate JSON per v + replay.sh + PR-check summary markdown (one line per v: verdict at base/head, plain-retry verdict,
   polluter ids). Exit 0 iff every OD victim is CERTIFIED or explicitly listed as NOT_FIXED.

## Certificate fields (each cert-<n>.json)
tool version+git sha; repo; base/head commit + codeload tarball sha256; image id; ruby -v; bundle -v; rspec-core version;
Gemfile.lock sha256; seed; victim id; polluter ids; exact commands A/B/C; per run: exit code, example/failure counts, first error
class + message line, log sha256; verdicts; plain-retry verdict. replay.sh reruns A/B/C from the JSON and exits 0 iff outcomes match.

## Breaker-set expectation (reverse/breaker-sets.log; the tool must not see this)
B(build_beta_detail:5)={bundle_id, webhook}; B(beta_build_metric:5)={bundle_id, webhook};
B(app_store_version_release_request:5)={bundle_id, webhook, capabilities}; B(build_delivery:5) adds bundle_id_capability, profile,
provisioning_client; control two_step:76 <- :94. With B3's latest-culprit preference the expected picks are in the sealed holdout.

## Acceptance (fastlane base 76eeb3f9352a657fd979ae00e89e49a388729e30, head 148c1c9b4c041b1659ea633f2632dd47eef8cb04, seed 48174)
1. Tool source and invocation contain no polluter or victim names (grep for webhook|capabilities|profile_spec|two_step|:94 in
   tools/ and the command line = no hits outside test fixtures).
2. CERTIFIED for the victims at build_beta_detail_spec.rb:5, beta_build_metric_spec.rb:5 and app_store_version_release_request_spec.rb:5,
   each with |P(v)| >= 1 and the M4 TypeError at base.
3. two_step_or_factor_client_spec.rb:76 attributed, NOT_FIXED at both commits (the control).
4. Every cert's replay.sh exits 0 on a second invocation.
GO iff 1-4 hold. Holdout predictions-G1.json sealed in HOLDOUT-G1.sha256, scored once.
