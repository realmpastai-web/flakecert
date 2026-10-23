# REA brief: QueueTrail-Rails (Rails parallel testing) - 2026-10-20

Method: static only. Phase 1 does not install, require, load, or run activesupport, railties, minitest, i18n, or Rails. Gems are read with tar and grep. The codeload tarballs are not in git; their sha256 values and URLs are in `SHA256SUMS.remote`, and the line checks read the cited copies. REA 6.7.0 has no Ruby command (`rea-attempt.log`: `analyze` inventoried the unpacked lib as a JavaScript application and parsed 0 files; `inspect-artifact` on `worker.rb` and on `i18n/config.rb` returned `unsupported binary format`, exit 1). Grep on the gem bytes is the fallback.

## Targets

- T1 activesupport 8.1.4. RubyGems API `sha` and the downloaded gem both equal `891dd3fe43c4fc8391934b237b1189bb1f661c932a84a840043db9d46a4e80df` (`recon.log`).
- T2 Rails commit `926edf5d51c5a0cd2698810fc6abd04525eb1a3b` (PR #56175, milestone 8.2.0, unreleased). Codeload tarball sha256 `e40f1a951c3ce7e76876248207cfcdbf77fcc3a781d325976a0642740aadf4d8`.
- T3 parent of T2, from the commits API: `8082369f155e30dee70c7bf4dfa078affb1b90c4`. Codeload tarball sha256 `fbae926556d89f853f2bb8d5170367db14a2e55815e1bb0f36089146d2c5f56b`.
- Minitest pin: Rails v8.1.4 `Gemfile.lock` has `minitest (6.0.6)`. Gem sha256 `153ea36d1d987a62942382b61075745042a2b3123b1cd48f4c3675af9cc7d6f1`, equal to the RubyGems API `sha`. activesupport's own gemspec requirement is `>= 5.1`.
- i18n pin: the same lockfile has `i18n (1.14.8)` at line 273. activesupport 8.1.4's gemspec requires `>= 1.6` and `< 2` (`metadata.gz` dependency `name: i18n`). Gem sha256 `285778639134865c5e0f6269e0b818256017e8cde89993fdfcbfb64d088824a5`, equal to the RubyGems API `sha` for 1.14.8.
- Ruby pin for the after-fork citation: tag `v3_3_8`, commit `b200bad6cd40d08e9f33b93e1a85c270b337867c` (the same revision `ruby -v` prints on this box: ruby 3.3.8). Tarball sha256 `62847a96f708f7bb34bb682570b902034416f7a3e6ec94fd4ab86af5d997fea0`.
- Baseline: `BASE.txt` is `git rev-parse origin/main` = `f8e201eaf7e8fc699c7f953a2f219ee933720bc3`.
- C1 control, already frozen: `inputs/rea-brief-test-queue/` test-queue 0.12.0. Cite BRIEF.md O2, O3, O4, and O5 there (ordered suite list dumped under `/tmp`, master deletes it, stats have no worker id, dynamic pull).

## Questions

Answers are the `notes` and the file:line groups in `observations.json`. `recon.log` holds every grep.

- R-Q1. 8.1.4 reaches workers through `Server` `@queue = Queue.new` (`server.rb:15`), `<<` / `pop` (`server.rb:32-38`), `while job = @queue.pop` (`worker.rb:37`), and `perform_job` (`worker.rb:42-57`) which runs `Minitest.run_one_method` or `klass.new(method).run`.
- R-Q2. Nothing in those files persists worker assignment or per-worker order. Hark's pattern `srand|seed|File.write|File.open|log` on the first three files has empty stdout and exit 1 (`recon.log`, argv form). `log` and `dump` do hit elsewhere: `tagged_logging` and `DRbUndumped`. Those are not a trail.
- R-Q3. User hooks are `parallelize_setup` / `parallelize_teardown`, the worker number passed to the after-fork hook, `set_process_title`, and `with: :threads`.
- R-Q4. Rails does not call `srand` (0 hits in the gem). Ruby 3.3.8's `Kernel#fork` child calls `rb_reset_random_seed`, which clears the default MT. Cited from `process.c`, `thread.c`, and `random.c` in the pinned tag. Not UNPROVEN.
- R-Q5. Minitest 6.0.6 `--seed` becomes `Minitest.seed`, `run_all_suites` shuffles suites, and `runnable_methods` does `srand Minitest.seed` then `methods.sort.shuffle` before the parallel executor is pushed.
- R-Q6. T2 versus T3: `pop(worker_id)` calls `@distributor.take(worker_id:)`. New `test_distributor.rb` round-robins by arrival order and can steal. `test_case.rb` says this is not a guarantee of deterministic test execution. 8.2 does not persist a per-worker trail. `work_stealing` pops another worker's queue when the local queue is empty, so who finishes first changes the assignment.
- R-Q7. i18n 1.14.8 `Config#locale=` (`config.rb:14-16`) enforces available locales before assigning `@locale`. `I18n.config` is a thread variable (`i18n.rb:58-59`, `:64`). The railtie restores enforcement after init (`i18n_railtie.rb:45`, `:66`). `:fr` is not available unless the app declares it.

## Gate

G1. `reverse_check_rails.py` replays every R-Q line and scan against these sha256s.
G2. Phase 2, only after `PHASE2-APPROVAL.txt` and after G3 has finished, scores sealed H1-H5 once.
A miss is a written no-go. Phase 2 is not started here.
