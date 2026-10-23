# REA: Datadog Test Optimization (flaky tests) - what its records lack (DRAFT, internal, nothing sent)
Frozen by Hark 2026-10-18 against flakecert main 7d22e2d. Every line maps to a check in check_dd_gap.py (see check-output.txt). Control: controls/mutant-add-seed-tag.log (one added `test.seed` tag makes the check FAIL, exit 1).

## Target (legal, public, shipped)
npm dd-trace@6.21.0, sha256 fa6d74a6...ac65, registry sha512 integrity matched (sources/dd-trace-6.21.0/PIN.txt). Apache-2.0/BSD-3 (LICENSE files copied). Static only: nothing executed, no Datadog account.
REA: rea-agents@6.5.0 analyze-javascript-application, evidence ev_723213d0..., 3,767 nodes, 0 integrity contradictions; the three copied files match REA's node sha256 (rea-summary.json). The 131 MB raw output is not committed; its sha256 is in rea-summary.json.
Public docs: docs.datadoghq.com flaky_management, early_flake_detection, auto_test_retries (sources/*.txt).

## What Datadog records and decides (observed)
- Test events carry 80 tag constants (util/test.js), including is_retry, is_new, retry_reason, has_failed_all_retries, is_quarantined, is_attempt_to_fix, attempt_to_fix_passed. [tags.*]
- Environment tags are os.platform/version/architecture and runtime.name/version only. [env.records_os_runtime_only]
- Flaky policy: failure rate over the last 7 days >= a threshold. Attempt to Fix: retries the test 20 times on the fix commit; if all pass, the fix is marked in progress. Fixed: no flake for 30 days. Early Flake Detection retries new tests. [docs.*]

## What its records lack that a FlakeCert certificate proves
1. No seed, test order, hash seed, image digest, dependency lock or schedule tag: 0 of 80. [tags.no_repro_fields]
2. The Jest integration strips "(with seed=N)" from test names (SEED_SUFFIX_RE). [jest.seed_stripped]
3. No interval: 20/20 passing retries is still compatible with a 13.9% failure rate (exact one-sided 95% upper bound, 1 - 0.05^(1/20) = 0.1391; the two-sided Wilson 16.1% is no longer used). [stats.20_of_20_upper]
4. Plain reruns miss order/seed flakes: 9 of FlakeCert's 10 certified tests passed every one of 100-105 plain runs, then failed under a controlled schedule. [fc.certified_zero_baseline_9, fc.zero_baseline_runs_ge_100]
A FlakeCert certificate carries sha, image_digest, pip_freeze_sha, schedule and d, plus rates with CI95. [fc.cert_has_repro_fields]

## Do not claim
- That Datadog can't help debug: it ships Failed Test Replay (library capability tag present) - a variable snapshot, not a reproduction recipe.
- Anything about Datadog's backend or Python/Java tracers: this freeze reads the JS tracer only (UNPROVEN for dd-trace-py).
- The exponential speedup (ledger: UNPROVEN).

## Product consequence (for a later CURSOR TASK, not built here)
"Attempt-to-Fix, certified": take a FlakeCert certificate, replay its failing schedule on the fix commit, and report n_fail/n with Wilson CI95, instead of 20 plain retries. Gate idea: on F01-F16 certified tests, the certified replay must hit the failure on the pre-fix sha.
