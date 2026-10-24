# FlakeCert pack #2 closeout: posthog-python 7.75.4

Status: CLOSED. No certification issued.

## Final verdicts
- Day 6: intervention I2 NOT CERTIFIED for the victim test V. In full orders V is hit by setters other than test_call_identify_fails, so I2 is a pair-only fix.
- Day 7c: **HOLDOUT FAIL** (kept as committed, not rescored). The only failing clause is NEW 1: on X2, py312, seed 844117108, `posthog/test/tracing/test_client_traces.py::TestLifecycle::test_exit_does_not_wait_on_a_hung_span_request` (H) failed with `assert 54.329921923002985 < 1` (log line 6928). The X2s pair had a byte-identical order and passed in 0.20s. Seal score: 3/5, mean Brier 0.2415.
- Day 8 (attribution replay of that exact order, 10 reps per arm, interleaved): **ATTRIBUTION NOT_REPRODUCED**.
  - H failed 0/10 on X2 and 0/10 on X2s; H call time was 0.20s in all 20 reps.
  - V passed 10/10 in both arms. IN_TEST_WAIT 0, HANG 0, EXIT_HANG 0, ORDER_MISMATCH 0.
  - All 20 order.txt files match sha256 5779169fdb5147ee9929a41351c558de7c8c14a6d0edcd2cf4b143faeb7c658e.
  - One-sided 95% Clopper-Pearson upper bound on H's failure rate per arm: 0.2589 (k=0, n=10).
  - Seal score (archive commit 12ddaf74): 4 hits, 1 coin-flip, 1 miss, 1 void; mean Brier 0.1532 (n=6).

## Hypothesis (not proven)
A retro scan of Day 7c with the Day 8 in-test-wait detector flags 6 in-test stalls, not 1:
- H on X2/py312: 54.33s vs a 0.20s median.
- 5 other tests on X2/py313 (2 tests), X2s/py312 (2) and X2s/py313 (1), at 23x to 14930x their reference medians.

Stalls of this size occur in both arms and both Python versions. **Hypothesis:** the Day 7c NEW row is one instance of an environment-wide stall class (host or scheduler level), not an effect of X2. This is NOT proven: no run captured the stall cause, and Day 8 did not reproduce H at all. The Day 7c verdict stays HOLDOUT FAIL.

## Carry-forward for the next pack
- Pre-register IN_TEST_WAIT (call time >= 20x the reference median) as its own failure class and report it separately from NEW.
- Capture a faulthandler or py-spy dump on any IN_TEST_WAIT before declaring NEW.

## Evidence (replayable)
Repository: realmpastai-web/flakecert-archive, branch hark-inputs-posthog-2026-10-22.
- Day 7c replay: head f29bc2af. day7c/SHA256SUMS sha256 e779bbc5...3357; verdict-7c.py rerun is byte-identical.
- Day 8 results: commit 977af82f; audit bc1b5e41.
  - day8/SHA256SUMS sha256 f2890e2b6bcca163894b9334597a444a77520da07b09357ac75f403f62c33ed2: `sha256sum -c` gives 168 OK.
  - verdict-8.py rerun stdout sha256 3ef03b0b...4fb7, identical to verdict-8.txt.
  - Retro rows: inputs/flakecert-posthog-7.75.4-day8/retro-day7c-in-test-wait.tsv.
- Day 8 seal: SEAL-day8.txt names sha256 ceaf065c...71f3. Predictions revealed in a25578ca; score at 12ddaf74.
