# QueueTrail spec v2

Static contract for an opt-in trail around test-queue 0.12.0. This file was revised from `inputs/rea-brief-test-queue/observations.json` before the v2 hook and CLI changes. It does not copy the gem.

This is spec v2. Spec v1 (sha256 `a914be1e148eb73671e2ba4d465298a8938f39e30b3aca4e51c570f13c31b6cd`) named a suite from `.name` and treated `failure_count > 0` as a failure. O6 and O7 show those choices do not match test-queue 0.12.0, so the suite name, the status, and the replay command below replace the v1 text. The digest of this file is the `docs/QUEUETRAIL-SPEC.md` line in `inputs/rea-brief-test-queue/SHA256SUMS`.

Every requirement below cites an observations id. A claim this file marks UNPROVEN is not a Part A result.

## What the reversed gem does

These sentences are the observations, not new behaviour.

- Q1. In the forked worker, `TestQueue::Runner#after_fork_internal` calls bare `srand` (`lib/test_queue/runner.rb:370`). The return value is not stored. The startup line prints pid and hostname, not the seed (`runner.rb:380`).
- Q2. A worker's ordered suite list is the in-memory `@suite_stats` array (`iterator.rb:12`, appended at `iterator.rb:68`), dumped with `Marshal` to `/tmp/test_queue_worker_<pid>_suites` (`iterator.rb:79-80`). The master loads that file and deletes it (`runner.rb:443-445`). `runner.rb:440` deletes the sibling output file.
- Q3. `.test_queue_stats` (override: `TEST_QUEUE_STATS`, `runner.rb:218`) stores `name`, `path`, `duration`, and `last_seen_at` (`stats.rb:6`, `stats.rb:27`) in a hash keyed by suite name (`stats.rb:52-56`). It has no worker id and no pid.
- Q4. `TestQueue::Iterator#each` yields each suite (`iterator.rb:24`, `iterator.rb:66`). After the yield, a suite may expose `failure_count` (`iterator.rb:69`). The worker number is `num = i + 1` (`runner.rb:283`), passed into `after_fork_internal(num, iterator)` (`runner.rb:289`, `runner.rb:369`), which calls `after_fork(num)` after the bare `srand` (`runner.rb:383`, `runner.rb:397`).
- Q5. `QueueRunner` is constructed from `ARGV` (`rspec_ext.rb:24-26`). `run_worker` calls `run_each` (`rspec.rb:26-27`, `rspec_ext.rb:52`). Neither method assigns `configuration.seed`. The master prints `configuration.seed` (`rspec.rb:20`). A forked worker inherits that configuration.
- C1. parallel_tests 5.8.0 builds static groups and reprints a failing group through `command_with_seed`, which appends `--seed` (`lib/parallel_tests/rspec/runner.rb:53-55`, `lib/parallel_tests/cli.rb:161` and `:169`). The control gem has no `srand` call.
- O6. An RSpec suite name is `example_or_group.id` when that method exists (`lib/test_queue/runner/rspec.rb:70-71`), otherwise `full_description` (`rspec.rb:72-73`), otherwise `metadata[:full_description]` (`rspec.rb:74-75`), otherwise `metadata[:example_group][:full_description]` (`rspec.rb:76-77`). `split_groups` returns top-level groups, or each group's `descendant_filtered_examples` when `TEST_QUEUE_SPLIT_GROUPS=true` (`rspec.rb:85-100`). A group with `metadata[:no_split]` stays whole.
- O7. `RSpec::Core::ExampleGroup.failure_count` is `examples.map { |e| e.execution_result.status == 'failed' }.length` (`lib/test_queue/runner/rspec_ext.rb:4-6`). `map` yields a boolean per direct example and `length` counts those booleans, so the integer is the number of direct examples, failed or not. `Iterator#each` adds that integer to `@failures` (`iterator.rb:69`). The same `@failures` is compared with `@early_failure_limit` (`iterator.rb:33`). O7 records those lines only. The inference that `early_failure_limit` misfires on a real run is UNPROVEN until Part B.

## R1. Deterministic worker RNG (Q1)

Stock `srand` takes no argument and does not save the seed (Q1). When this hook is loaded, `TestQueue::Runner#after_fork(num)` runs after that bare call (Q4, `runner.rb:383`) and replaces the worker RNG:

```
M = integer value of ENV["QUEUETRAIL_MASTER_SEED"], or 0 when unset
k = the integer passed to after_fork
S_k = ((M + 1) * 1000003 + k * 9176) mod 2147483648
srand(S_k)
```

`2147483648` is `2**31`. `M` and `k` are non-negative integers. A missing or non-decimal master seed, or a negative worker number, aborts the worker before it writes a trail.

`S_k` is written on the worker header as `srand_seed`. The header also stores `master_seed` (the value of `M`).

Worked values:

| M | k | S_k |
|---|---|-----|
| 0 | 1 | 1009179 |
| 42 | 3 | 43027657 |

## R2. Durable per-worker trail (Q2, Q3, O6, O7)

Stock state is a Marshal file under `/tmp` that the master deletes (Q2), or a stats file with no worker id and no pid (Q3). QueueTrail writes a different record and does not delete it.

- Directory: `ENV["QUEUETRAIL_DIR"]` when set, otherwise `./queuetrail`, expanded with `File.expand_path`.
- If that path is `/tmp` or a path under `/tmp`, the hook raises and writes nothing.
- One file per worker: `worker-<k>.jsonl`, where `<k>` is the `after_fork` argument.
- The hook creates the directory only when a worker opens its file. Loading the hook does not create it.
- The hook never unlinks a trail file and never writes a trail under `/tmp`.
- `run_id` is `ENV["QUEUETRAIL_RUN_ID"]` when that variable is non-empty. Otherwise the hook assigns `SecureRandom.hex(8)` to `ENV["QUEUETRAIL_RUN_ID"]` at load time, so workers forked later share it.

The first line is a JSON object, one line, no extra whitespace:

| key | value |
|---|---|
| type | `"worker"` |
| run_id | string |
| worker_num | integer k |
| pid | `Process.pid` |
| host | `Socket.gethostname` |
| srand_seed | S_k |
| rspec_seed | `RSpec.configuration.seed` when that method exists, otherwise JSON null (Q5) |
| master_seed | M |
| ruby_version | `RUBY_VERSION` |
| test_queue_version | `ENV["QUEUETRAIL_TEST_QUEUE_VERSION"]` when set and non-empty, otherwise JSON null |

`TestQueue::VERSION` is not read. It is not a method cited in observations.json.

Each later line is one suite, in yield order (Q4):

| key | value |
|---|---|
| type | `"suite"` |
| index | 0-based integer, increasing by 1 for each yield |
| name | the suite id from O6, as specified under "Suite name" below |
| path | `suite.path`, else `suite.file_path`, else `suite.metadata[:file_path]` when `metadata` responds to `[]`, else `""`. Path is recorded separately from the name. |
| start_monotonic | `Process.clock_gettime(Process::CLOCK_MONOTONIC)` before the yield |
| end_monotonic | the same clock after the yield returns or raises |
| status | the suite status from O7, as specified under "Suite status" below |

A raised exception is recorded as `"failed"` and then re-raised. Suite lines are written only after the worker header exists.

### Suite name (O6)

`name` is the first non-empty string from these sources, in this order, matching `rspec.rb:70-77`:

1. `suite.id` when the object responds to `id`.
2. `suite.full_description` when the object responds to `full_description`.
3. `suite.metadata[:full_description]` when `metadata` responds to `key?` and `key?(:full_description)` is true.
4. `suite.metadata[:example_group][:full_description]` when that value is reached through `metadata`.

A nil or empty string is not a name, and the next source is used. `suite.name` is not a source. On an RSpec example group that method is the Ruby constant name, and test-queue does not use it (O6). When none of the four sources yields a non-empty string, `name` is `suite.to_s`.

The yielded object is a top-level example group, or a single example when `TEST_QUEUE_SPLIT_GROUPS=true` (O6, `rspec.rb:85-100`).

### Suite status (O7)

Status is not read from `failure_count`. That method's return value is the number of direct examples (O7, `rspec_ext.rb:4-6`).

After a yield that returns:

1. Collect `execution_result.status` from each object in `suite.descendant_filtered_examples` when the suite responds to that method and the list is not nil.
2. Also collect `execution_result.status` from the suite itself when the suite responds to `execution_result`. That is the split-example case (O6): the yielded object is the example.
3. When the collected list is empty, or any collected status is nil, status is `"unknown"`.
4. When any collected status equals `"failed"`, status is `"failed"`.
5. Otherwise status is `"passed"`.

A yield that raises records `"failed"` and re-raises. The hook does not call `failure_count` and does not change `iterator.rb`. Whether `@failures` reaching `@early_failure_limit` stops a real worker early (O7, `iterator.rb:33` and `:69`) is UNPROVEN until Part B.

## R3. Manifest (Q2, Q3)

`python3 tools/queuetrail/cli.py manifest --dir DIR [--out PATH] [--gemfile-lock PATH]` reads `worker-<digits>.jsonl` files that sit directly in `DIR`. It writes JSON, indented by two spaces and ending in a newline. The default output path is `DIR/manifest.json`. The task's default location is `queuetrail/manifest.json` when `DIR` is `queuetrail`.

| key | value |
|---|---|
| run_id | header `run_id`; every worker file must agree |
| flakecert_commit | `ENV["QUEUETRAIL_FLAKECERT_COMMIT"]` when set, else `git rev-parse HEAD`, else null |
| ruby_version | header `ruby_version` when the headers agree, else null |
| gemfile_lock_sha256 | sha256 of `--gemfile-lock`, or of `./Gemfile.lock` when that file exists, else null |
| test_queue_version | header `test_queue_version` when the headers agree on a string, else null |
| worker_count | number of worker files |
| master_seed | header `master_seed`; every worker file must agree |
| trails | object mapping each worker filename to the sha256 of that file's bytes |

Disagreeing `run_id` or `master_seed` values make the command exit 1 and write no manifest. `manifest.json` is not a trail file and is not an entry in `trails`.

## R4. Replay (Q4, Q5, O6)

`python3 tools/queuetrail/cli.py replay --manifest M --worker K [--upto INDEX] [--run]`

`M` is a manifest JSON file. The worker trail is `worker-<K>.jsonl` in the same directory. The command checks that file's sha256 against `trails` and exits 1 on a mismatch or a missing worker.

It prints one line and, only with `--run`, executes it:

```
QUEUETRAIL_SRAND=<srand_seed> ids=<shell-quoted ids> rspec --require <ordering.rb> --require <spec_shim.rb> <args>
```

- `<srand_seed>` is the integer on the worker header (R1, Q1).
- `<ordering.rb>` is the absolute path of `tools/certify_rspec/ordering.rb`. Replay requires that file and does not modify it.
- `<spec_shim.rb>` is the absolute path of `tools/queuetrail/spec_shim.rb`.
- The command does not pass `--order`. Argument order is not the example order. `ordering.rb` reads the id list itself:

```
tools/certify_rspec/ordering.rb:10:  raw = ENV.fetch("ids", "")
tools/certify_rspec/ordering.rb:12:  file_name = ENV.fetch("ids_file", "")
tools/certify_rspec/ordering.rb:13:  raw = File.read(file_name) if raw.empty? && !file_name.empty?
tools/certify_rspec/ordering.rb:14:  raw.split(/\s+/).each_with_index do |ident, index|
tools/certify_rspec/ordering.rb:30:  config.register_ordering(:global) do |items|
```

  `ENV["ids"]` wins when it is non-empty. Otherwise a non-empty `ENV["ids_file"]` is read. The text is split on whitespace. `:global` is the ordering RSpec applies to top-level groups and to groups that do not set their own `:order` metadata, so requiring this file is enough. No edit to `ordering.rb` is required.

- `<ids>` is the selected suites' recorded `name` values, in index order, joined by one space. Empty names are omitted. The shell quoting keeps that string one environment value. Those names are the RSpec ids from O6.
- `<args>` are those same non-empty names, in index order. When a suite's `name` is non-empty, its `path` is not an argument. When a suite's `name` is empty, the argument is its `path` if that path is non-empty, and that path is not added to `<ids>`.
- `--upto INDEX` keeps suites whose `index` is less than or equal to `INDEX`. `INDEX` is a non-negative integer. Omitted, every suite line is included.
- `--run` executes `rspec` with `QUEUETRAIL_SRAND` and `ids` set in the environment. Without `--run` the command is only printed.

`spec_shim.rb` calls `srand(Integer(ENV["QUEUETRAIL_SRAND"]))` when that variable is set and non-empty. When the variable is unset, the shim does not call `srand`.

Whether this replay reproduces a real failure is UNPROVEN until Part B. The order source of the printed command is `ordering.rb`, cited above.

## R5. Hand-off (Q4, Q5, O6)

`python3 tools/queuetrail/cli.py to-flakecert --manifest M --worker K --victim NAME [--out PATH]`

The victim is the first suite line whose `name` equals `NAME`. Suites with a smaller `index` are the ordered prefix (Q4 yield order). The command exits 1 when the name is absent or the trail sha256 does not match the manifest. A non-empty `name` is the RSpec id (O6). The path is not substituted for that name.

It writes JSON, indented by two spaces and ending in a newline, to `--out` or to stdout:

| key | value |
|---|---|
| kind | `"queuetrail-candidate-polluters"` |
| adapter_gap | `"UNPROVEN"` |
| reason | the paragraph below |
| worker_num | K |
| victim | NAME |
| candidate_ids | prefix `name` values in index order |
| ids_file | those names, then the victim, joined by newlines, with a trailing newline |

`ids_file` is whitespace-separated RSpec ids. `ordering.rb:12-14` reads `ENV["ids_file"]` when `ENV["ids"]` is empty and splits that text on whitespace, so this field can be that file's bytes. `adapter_gap` stays `"UNPROVEN"` because no certify_rspec CLI accepts an external candidate file. `tools/certify_rspec` is not modified.

`reason` is this text, exactly:

```
UNPROVEN. ordering.rb reads whitespace-separated ids from ENV ids or ids_file (tools/certify_rspec/ordering.rb:10-14). Suite names are RSpec ids (O6), so ids_file feeds ordering.rb directly. No certify_rspec CLI accepts an external candidate file.
```

## R6. Opt-in hook (Q4)

The hook is `tools/queuetrail/queuetrail.rb`, loaded with `-r ./tools/queuetrail/queuetrail.rb`.

- It prepends `after_fork` on `TestQueue::Runner` and `each` on `TestQueue::Iterator` (Q4).
- If those classes already exist when the file loads, it prepends immediately.
- If they do not, it wraps `Kernel#require` and prepends on the require that first defines both classes. That is how `-r` runs before `rspec-queue` loads the gem.
- The wrapped `require` returns the value of the original `require` and stays a private instance method of `Kernel`. `install!` prepends each hook once.
- The hook calls `srand` only from `after_fork`, which is after the bare `srand` in `after_fork_internal` (Q1, Q4).
- It does not redefine `after_fork_internal`, `Iterator#each`'s socket protocol, stats, or anything under `tools/certify_rspec/`.
- When this file is not loaded, it creates no directory and writes no file.

## Static checker

`python3 tools/queuetrail/reverse_check.py --gem GEM --control CONTROL --expect observations.json` reads both `.gem` files as tar archives (`data.tar.gz` inside each gem). It does not install or execute them.

- It sha256-checks `GEM` against `target_sha256` and `CONTROL` against `control_sha256` in the expect file. A mismatch prints `SHA FAIL` and exits non-zero before the line checks.
- For each of Q1, Q2, Q3, Q4, Q5, C1, O6, and O7, every cited `file` / `line` / `text` must match the gem bytes. Line numbers are 1-based and `text` is the line without its trailing newline.
- C1 also requires that no `.rb` member of the control gem contains the word `srand` (`observations.C1.absent`).
- Success prints `Q1 PASS` through `Q5 PASS`, then `C1 PASS`, `O6 PASS`, and `O7 PASS`, then exits 0.

## Part A does not score these

UNPROVEN until Part B, which needs Santhosh's written yes before any test-queue or parallel_tests code is executed:

- R4 reproduces a real victim failure.
- R5's candidate list is a certify_rspec CLI input. The ids themselves match O6; the gap is the CLI.
- Whether `early_failure_limit` misfires because `failure_count` counts every direct example (O7).
- Holdout predictions P1, P2, P3, P4, and P5. The holdout stays sealed.
- Byte-identical trail files across two runs. `pid` and monotonic times differ by construction (R2). `srand_seed`, `master_seed`, and suite name/path/index order are deterministic when `QUEUETRAIL_RUN_ID`, `QUEUETRAIL_MASTER_SEED`, and the RSpec seed are the same (R1, Q5).
