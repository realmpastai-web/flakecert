# QueueTrail skeptic pass (Part A.1)

Mutants M1-M6 were applied to the working tree, the matching test was run, and the file was restored from a copy taken before the edit. After all six restores:

```
nice -n 19 ruby tools/queuetrail/test/hook_test.rb
OK
HOOK_EXIT:0

nice -n 19 python3 -m pytest tests/test_queuetrail.py -q
....................                                                     [100%]
20 passed in 1.24s
PYTEST_EXIT:0

nice -n 19 python3 tools/queuetrail/reverse_check.py --gem inputs/rea-brief-test-queue/test-queue-0.12.0.gem --control inputs/rea-brief-test-queue/parallel_tests-5.8.0.gem --expect inputs/rea-brief-test-queue/observations.json
Q1 PASS
Q2 PASS
Q3 PASS
Q4 PASS
Q5 PASS
C1 PASS
O6 PASS
O7 PASS
CHECK_EXIT:0
```

Spec v2 sha256 after the restores: `27804a9600434f2e52b36feaa17934938962ec58d7302b782b8f2df32366f7d3`.

v1 was `a914be1e148eb73671e2ba4d465298a8938f39e30b3aca4e51c570f13c31b6cd`. The digest changed because O6 and O7 replaced the v1 suite name (`.name` first) and the v1 status (`failure_count > 0`). Replay now passes the recorded ids through `ordering.rb` instead of `--order defined`.

## M1 hook stops writing srand_seed

The `"srand_seed"` header key was removed from `tools/queuetrail/queuetrail.rb`. `hook_test.rb` exited 1:

```
srand_seed field
M1_EXIT:1
```

Restored.

## M2 trail lines written in reverse order

Suite lines were inserted immediately after the header, so each new suite landed in front of the previous one. `hook_test.rb` exited 1:

```
R2 suite order
M2_EXIT:1
```

Restored.

## M3 replay drops the ordering.rb require

v1 M3 removed `--order defined`. Spec v2 does not pass `--order`. The order source is `tools/certify_rspec/ordering.rb`, required read-only. This mutant removed that `--require`. pytest exited 1:

```
E   AssertionError: assert ['rspec', '--...lpha', 'beta'] == ['rspec', '--...spec_shim.rb']
FAILED tests/test_queuetrail.py::test_replay_prints_ids_ordering_require_and_recorded_seed
FAILED tests/test_queuetrail.py::test_replay_upto_keeps_inclusive_prefix
FAILED tests/test_queuetrail.py::test_replay_upto_zero_is_the_first_suite
FAILED tests/test_queuetrail.py::test_replay_empty_path_uses_suite_name
FAILED tests/test_queuetrail.py::test_replay_uses_recorded_ids_not_paths
M3_EXIT:1
```

Restored. `ordering.rb` was not edited.

## M4 manifest omits one trail sha256

`build_manifest` popped the first trail entry after hashing. pytest exited 1:

```
E   KeyError: 'worker-1.jsonl'
FAILED tests/test_queuetrail.py::test_manifest_records_every_trail_sha256
M4_EXIT:1
```

Restored.

## M5 reverse_check accepts a wrong sha256

The early `return 1` after `SHA FAIL` was removed, so a forged `target_sha256` still exited 0. pytest exited 1:

```
E   AssertionError: assert 0 != 0
E    +  where 0 = CompletedProcess(..., returncode=0, stdout='SHA FAIL target\nQ1 PASS\nQ2 PASS\nQ3 PASS\nQ4 PASS\nQ5 PASS\nC1 PASS\nO6 PASS\nO7 PASS\n', stderr='').returncode
FAILED tests/test_queuetrail.py::test_reverse_check_rejects_wrong_gem_sha256
M5_EXIT:1
```

Restored.

## M6 status reads failure_count

`IteratorHook` was changed to set status from `suite.failure_count` (positive integer means `"failed"`). The hook test's group stub uses the gem expression `examples.map { |e| e.execution_result.status == "failed" }.length`, which is 2 for two passing examples. `hook_test.rb` exited 1:

```
gem semantics: status ignores failure_count
M6_EXIT:1
```

Restored.

## What O6 and O7 change for a sealed prediction

The holdout file was not opened, not edited, and not re-sealed. Part B scores it once.

O6 changes the recorded suite name. v1 used `.name` first, which on an RSpec example group is the Ruby constant. v2 uses `id`, then `full_description`, then metadata `full_description` (`lib/test_queue/runner/rspec.rb:70-77`). Replay and `to-flakecert` use that recorded id when it is non-empty, and do not substitute the path. A sealed prediction that keyed a suite by the constant name or by the file path is about a different identifier than this trail records.

O7 changes status. v1 treated `failure_count > 0` as `"failed"`. The gem method is `examples.map { |e| e.execution_result.status == 'failed' }.length` (`rspec_ext.rb:4-6`), so the integer is the number of direct examples. v2 reads `execution_result.status` from descendant examples and from the example itself when the suite is a split example. A sealed prediction that treated a positive `failure_count` as a failed suite is about the v1 rule.

`iterator.rb:69` adds that integer to `@failures`, and `iterator.rb:33` compares `@failures` with `@early_failure_limit`. That the limit misfires on a real run is UNPROVEN until Part B. Nothing was filed upstream.

## UNPROVEN until Part B

Part A does not execute test-queue or parallel_tests. These spec claims stay UNPROVEN:

- R4 reproduces a real victim failure. The printed command's order source is `ordering.rb:10-14` and `:30`, which is specified. A live `rspec` process is not run here.
- R5 adapter fit: `to-flakecert` writes JSON, `ids_file` is the RSpec ids from O6, and `adapter_gap` is `UNPROVEN` because no certify_rspec CLI accepts an external candidate file.
- Whether `early_failure_limit` misfires (O7).
- P1, P2, P3, P4, and P5 in the sealed holdout. The holdout file was not scored.
- Byte-identical trail files across two runs. R2 records `pid` and monotonic times, which differ by construction. `srand_seed` and suite order are what R1 makes deterministic.

`BRIEF.md` was not edited in this pass. Its digest is `1431333d650ba9bd5cc1450fbba4c0f44c8945f7f9cde648364f88c4bc083396`.
