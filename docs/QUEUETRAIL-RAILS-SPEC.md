# QueueTrail-Rails spec

Static contract for an opt-in trail around ActiveSupport parallel testing. This file was written from `inputs/rea-brief-rails-parallel/observations.json` before `tools/queuetrail/rails.rb` and `tools/queuetrail/rails_replay.py`. It does not copy Rails or Minitest.

The trail shape is the QueueTrail spec v2 shape (`docs/QUEUETRAIL-SPEC.md`, sha256 `27804a9600434f2e52b36feaa17934938962ec58d7302b782b8f2df32366f7d3`) so `python3 tools/queuetrail/cli.py manifest` can read it without changes to `cli.py`. Suite `name` values are `Klass#method`. Suite `status` values are `pass`, `fail`, `error`, or `skip`.

Every requirement below has one `Cites:` line. That line is the observation citation. A claim this file marks UNPROVEN is not a Phase 1 result.

## RR1. Opt-in hook

Cites: R-Q3.

The hook is the new file `tools/queuetrail/rails.rb`. A test helper loads it with `require` after `require "rails/test_help"`. A process that does not load this file creates no directory and writes no file.

Loading the file does not create the trail directory. If `ActiveSupport::TestCase` does not respond to `parallelize_setup`, or `ActiveSupport::Testing::Parallelization::Worker` is not defined, loading the file raises nothing and installs nothing.

When both exist, loading the file:

- calls `parallelize_setup` with a block of one argument, the worker number
- prepends one module onto `Worker` that wraps `perform_job`, once

`parallelize_setup` is the after-fork hook. Rails documents that this hook is not available with `with: :threads`. This hook does not install a threaded trail. The worker number is the integer passed into that block (`@number` from `@worker_count.times`, 0-based).

The `perform_job` wrapper calls the original method. It does not run the test a second time. It observes the result object the original method passes to `@queue.record`.

## RR2. Trail record

Cites: R-Q1, R-Q2, R-Q5.

Rails 8.1.4 keeps the job queue in memory and does not write a per-worker order. QueueTrail writes a different record and does not delete it.

- Directory: `ENV["QUEUETRAIL_DIR"]` when set, otherwise `./queuetrail`, expanded with `File.expand_path`.
- If that path is `/tmp` or a path under `/tmp`, the hook raises and writes nothing.
- The directory is created only when a worker start block opens its file.
- One file per worker: `worker-<k>.jsonl`.
- `run_id` is `ENV["QUEUETRAIL_RUN_ID"]` when that variable is non-empty. Otherwise the hook assigns `SecureRandom.hex(8)` to `ENV["QUEUETRAIL_RUN_ID"]` at load time.

The first line is a JSON object from `JSON.generate` (no extra whitespace) plus a newline:

| key | value |
|---|---|
| type | `"worker"` |
| run_id | string |
| worker_num | integer k |
| pid | `Process.pid` |
| host | `Socket.gethostname` |
| srand_seed | S_k from RR3 |
| minitest_seed | `Minitest.seed` when that method exists, otherwise JSON null |
| master_seed | M from RR3 |
| ruby_version | `RUBY_VERSION` |
| rspec_seed | JSON null |
| test_queue_version | `ENV["QUEUETRAIL_TEST_QUEUE_VERSION"]` when set and non-empty, otherwise JSON null |

Each later line is one test, appended in `perform_job` order:

| key | value |
|---|---|
| type | `"suite"` |
| index | 0-based integer, increasing by 1 |
| name | `"#{klass}##{method}"` using job[0] and job[1], the same interpolation as the process title |
| path | `""` |
| start_monotonic | `Process.clock_gettime(Process::CLOCK_MONOTONIC)` before the original `perform_job` |
| end_monotonic | the same clock after the original `perform_job` returns |
| status | the result status below |

Status is read from the result object passed to `@queue.record(reporter, result)`. It is not read from the method name, the process title, or an exception message.

1. When the result responds to `skipped?` and `skipped?` is true, status is `"skip"`.
2. Otherwise, when the result responds to `error?` and `error?` is true, status is `"error"`.
3. Otherwise, when the result responds to `passed?` and `passed?` is true, status is `"pass"`.
4. Otherwise status is `"fail"`.

Those three predicates are the Minitest::Reportable methods: `skipped?` is `Skip === failure`, `error?` is `failures.any? UnexpectedError`, and `passed?` is `not failure`. A skip is a failure object, so `passed?` is false for a skip; the skip check comes first.

If `perform_job` runs before the worker-start block has opened the file, the hook raises and does not append a suite line.

`python3 tools/queuetrail/cli.py manifest` reads this file unchanged. `cli.py` is not modified.

## RR3. Deterministic worker RNG

Cites: R-Q4.

Stock Rails never calls `srand`. Ruby 3.3.8's `Kernel#fork` child calls `rb_reset_random_seed`, which clears the default MT and sets its seed to 0 so the next default-rand draw is a new seed. The worker-start block runs after that fork, inside the `parallelize_setup` hook, and replaces the worker RNG:

```
M = integer value of ENV["QUEUETRAIL_MASTER_SEED"], or 0 when unset
k = the integer passed to the parallelize_setup block
S_k = ((M + 1) * 1000003 + k * 9176) mod 2147483648
srand(S_k)
```

`2147483648` is `2**31`. This is the QueueTrail R1 formula. `k` may be 0 because Rails worker numbers start at 0. A missing or non-decimal master seed, or a negative worker number, raises `ArgumentError` before the hook writes a trail.

`S_k` is the header `srand_seed`. The header `master_seed` is `M`.

Worked values:

| M | k | S_k |
|---|---|-----|
| 0 | 0 | 1000003 |
| 0 | 1 | 1009179 |
| 42 | 3 | 43027657 |

## RR4. Replay command

Cites: R-Q5.

`python3 tools/queuetrail/rails_replay.py replay --manifest M --worker K` reads `worker-<K>.jsonl` beside the manifest. It checks that file's sha256 against `manifest["trails"]` and exits 1 when the trail is missing or the sha256 differs. It does not execute the command. It prints one line:

```
QUEUETRAIL_SRAND=<srand_seed> PARALLEL_WORKERS=1 ids=<shell-quoted ids> ruby -r <rails_order_shim.rb>
```

- `<srand_seed>` is the integer on the worker header.
- `PARALLEL_WORKERS=1` is that exact assignment. The command has no other `PARALLEL_WORKERS` value. Rails reads that variable and sets the worker count from it; a count of 1 fails `many_workers?` (`size > 1`), so the process executor does not fork.
- `<ids>` is the suite `name` values in ascending `index` order, joined by one space. Empty names are omitted. `shlex.quote` keeps the string one shell word.
- `<rails_order_shim.rb>` is the absolute path of the new file `tools/queuetrail/rails_order_shim.rb`.

The shim reads `ENV["ids"]` when that value is non-empty. Otherwise it reads `ENV["ids_file"]` when that path is non-empty. It splits the text on whitespace. When `Minitest` is defined, it prepends `Minitest.run_all_suites` and does not call the original method. The replacement calls `srand(Integer(ENV["QUEUETRAIL_SRAND"]))` when that variable is set and non-empty, then for each id `Klass#method` runs `klass.new(method).run` and, when the reporter responds, `prerecord` and `record`. It does not call `Runnable.runnables.shuffle` or `methods.sort.shuffle`. Those are the Minitest steps that turn `--seed` into enqueue order.

Whether this command reproduces a real failure, or preserves order on a real Rails process, is UNPROVEN until Phase 2.

## RR5. Hand-off

Cites: R-Q1, R-Q5.

`python3 tools/queuetrail/rails_replay.py handoff --manifest M --worker K --victim NAME [--out PATH]` uses the same sha256 check as replay. The victim is the first suite line whose `name` equals `NAME`. Suites with a smaller `index` are the ordered prefix. The command exits 1 when the name is absent or the sha256 does not match.

It writes JSON, indented by two spaces and ending in a newline, to `--out` or to stdout:

| key | value |
|---|---|
| kind | `"queuetrail-rails-candidate"` |
| adapter_gap | `"UNPROVEN"` |
| reason | the paragraph below |
| worker_num | K |
| victim | NAME |
| candidate_ids | prefix `name` values in index order |
| ids_file | those names, then the victim, joined by newlines, with a trailing newline |

`reason` is this text, exactly:

```
UNPROVEN. certify_rspec is RSpec-only: tools/certify_rspec/ordering.rb registers an RSpec global ordering and QueueTrail replay invokes rspec. A minitest certify path would need its own runner that reads this ids file of Class#method lines and executes that ordered prefix plus the victim in one process with PARALLEL_WORKERS=1. That runner is not built here.
```

No file under `tools/certify_rspec/` is added or edited.

## RR6. What 8.2 already does

Cites: R-Q6.

On commit `926edf5` (parent `8082369`), `Server#pop(worker_id)` calls `@distributor.take(worker_id:)`. `work_stealing: false` selects `RoundRobinDistributor`, which assigns each arriving test to `@next_worker` and then increments that index. Arrival order is the Minitest seed shuffle from RR4's citation of enqueue order. `work_stealing: true` selects `RoundRobinWorkStealingDistributor`. Its `next_job` is `pop_now(worker_id) || steal(worker_id)`, and `steal` pops another worker's queue. A worker that finishes first takes tests that round-robin had given to someone else, so the assignment depends on test duration.

Those files contain no `File.write`, `File.open`, `Tempfile`, or `Marshal.dump`. 8.2 does not persist a per-worker trail. The word `seed` in those files is only in comments.

`test_case.rb` says that the same seed and worker count run the same sequence on each worker, and that this is not a guarantee of deterministic test execution. Seeded round-robin is what 8.2 already gives. It is not, on Rails' own words, a guarantee. QueueTrail adds the persisted trail 8.2 does not write, and it is the record that still exists when `work_stealing` is on. Whether stock 8.2 without `work_stealing` is enough in a real run is holdout H4, UNPROVEN until Phase 2. This spec does not say that stock 8.2 replay is sufficient.

## Fixture locale pair

Cites: R-Q7.

`fixtures/rails-parallel-pair/` is hand-written and is not executed in Phase 1. i18n 1.14.8 is the exact version in the Rails v8.1.4 lock, and the Gemfile pins that version. `Config#locale=` calls `enforce_available_locales!` before it assigns `@locale`. Enforcement defaults to true, and the ActiveSupport railtie turns it off only while it copies `config.i18n`, then restores it. A locale that is not available raises `I18n::InvalidLocale` after that restore.

The fixture therefore declares both locales. `config/locales/en.yml` contains `en:` and `greeting: Hello`. `config/locales/fr.yml` contains `fr:` and `greeting: Bonjour`. Those greeting strings differ. `config/application.rb` sets `config.i18n.available_locales = [:en, :fr]` and requires `active_support/railtie`, which loads the i18n railtie that defines `config.i18n`. `LocalePolluterTest` assigns `I18n.locale = :fr`, and `:fr` is the locale declared in `fr.yml`.

`I18n.config` is stored with `Thread.current.thread_variable_get` and `thread_variable_set` of `:i18n_config`. The locale is the `@locale` of that per-thread config. This fixture uses the default `with: :processes`, so a worker process shares that thread-local config between tests that run in the process. `with: :threads` gives each thread its own config, so this pair does not cross threads. The hook does not install a trail for that path.

## Static checker

`python3 tools/queuetrail/reverse_check_rails.py --gem GEM --expect observations.json` reads gem archives and cited files named in the expect file. It does not install or execute them, and it does not open the codeload tarballs. `GEM` is the activesupport gem. Its sha256 must equal `target_sha256`. Every gem archive `sha256` must equal that gem's bytes. Every cited-file `sha256` must equal that cited file's bytes. A mismatch prints `SHA FAIL` and exits non-zero before any `R-Q` line.

For R-Q1 through R-Q7, every cited `file` / `line` / `text` must match those bytes, and every `scans` entry must match the listed hits. Success prints `R-Q1 PASS` through `R-Q7 PASS` and exits 0.

Tarball sha256 values and their codeload URLs live in `inputs/rea-brief-rails-parallel/SHA256SUMS.remote`. The Ruby and Rails 8.2 line checks read the cited copies.

## Phase 1 does not score these

UNPROVEN until Phase 2, which needs Santhosh's written yes in `inputs/rea-brief-rails-parallel/PHASE2-APPROVAL.txt` before any Rails, activesupport, railties, or minitest code is executed:

- RR4 order fidelity and reproduction of a real victim failure.
- RR5's ids file as a certify input. The gap is the missing minitest runner.
- Holdout predictions H1, H2, H3, H4, and H5. The holdout stays sealed.

R-Q4 is cited from the pinned Ruby tag. It is not in this list.
