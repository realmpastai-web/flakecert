# REA brief: QueueTrail (FlakeCert for dynamic-queue Ruby test runners) - 2026-10-20, Hark
Method: static only. Gems fetched from rubygems.org, sha256 equal to the API "sha" field; unpacked with tar, never installed or run.
REA CLI cannot open .gem (known since 6.5.0), so plain tar + grep (recon.log). Clean-room: no code copied; observations only.

## Targets
- test-queue 0.12.0  sha256 78632f446a06657a5f11c0606d8de25b7738ed49912c9c1b2c5c6c0b0ee82343  (4,320,060 downloads; rubygems-api-2026-10-20.json)
- parallel_tests 5.8.0 sha256 181898cbee2ffb1c796274ce31d27f792a421324609bfc7e9b5531d929d91eda (control)
Why: a public 2025 engineering write-up: moving to test-queue failed >100 specs that pass alone; polluters hunted by hand with rspec --bisect.

## Observations (file:line)
O1 runner.rb:370 after_fork_internal calls bare `srand`: each worker's Ruby RNG gets a fresh random seed that is never printed or saved.
O2 iterator.rb:12,68,80 each worker keeps an ordered list of the suites it ran and dumps it to /tmp/test_queue_worker_<pid>_suites.
O3 runner.rb:440,445 the master reads then deletes that file (and the worker output file).
O4 stats.rb:52-56 record_suites stores suites in a Hash keyed by suite name; Suite has only name, path, duration, last_seen_at (stats.rb:6). Worker identity and per-worker sequence are not persisted in .test_queue_stats (runner.rb:218).
O5 The queue is pulled dynamically, so which suites share a worker, and in what order, depends on timing.
Control C1 parallel_tests rspec/runner.rb:53-55 + cli.rb:161-171: static groups and a printed per-group rerun command with --seed (verbose). Order seed only, no srand (consistent with the rspec-core 3.13.6 reverse).

## Inference
I1 A test-queue failure caused by an earlier suite on the same worker cannot be replayed from what the run saves: the sequence is deleted and the RNG seed was never recorded. This is consistent with that write-up's manual bisect. INFERENCE, not run.
## Unknowns (UNPROVEN)
U1 Whether last_seen_at timestamps alone allow rebuilding one worker's sequence (likely not with interleaved workers).
U2 knapsack_pro queue mode behaviour (paid vendor = competitor; not reversed).

## Gate for any CURSOR TASK
G1 Replay O1-O4 from these exact sha256s on a fresh unpack (grep lines match recon.log).
G2 On fastlane at 76eeb3f (known certified pair webhook_spec -> build_beta_detail:5), stock rspec-queue with 4 workers must fail AND the stock artifacts must be shown insufficient to rerun it; QueueTrail must recover the same pair and FlakeCert must re-certify NOT_FIXED@76eeb3f, FIXED@148c1c9.
Fail -> written no-go.
