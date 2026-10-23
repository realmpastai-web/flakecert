# QueueTrail-Rails skeptic pass (Phase 1)

Mutants K1-K6 were applied one at a time, the matching test was run, and the file was restored from a copy taken before the edit. Phase 2 was not started. No Rails, activesupport, railties, or minitest code was installed or executed. The fixture under `fixtures/rails-parallel-pair/` was not run.

Spec sha256 after the restores: `79ebca667281b1a3d26a2323f787da69762a8fd6ee8dbd7a754837bc727f775b`.

## K1 hook drops srand_seed

The `"srand_seed"` header key was removed from `tools/queuetrail/rails.rb`. `rails_hook_test.rb` exited 1:

```
srand_seed field
K1_EXIT:1
```

Restored.

## K2 trail order reversed

`write_line` was changed so each suite line is inserted immediately after the header. `rails_hook_test.rb` exited 1:

```
RR2 suite order
K2_EXIT:1
```

Restored.

## K3 status inferred from the method name

The suite `"status"` field was set from `method` (`fail` / `pass` / `skip` substrings) instead of `status_of(result)`. `rails_hook_test.rb` exited 1:

```
RR2 status is read from the result, got ["fail", "pass", "skip", "fail", "fail"]
K3_EXIT:1
```

Restored.

## K4 replay uses more than one worker

A first replacement of the earliest `PARALLEL_WORKERS=1` hit the handoff reason string and left the printed command unchanged. Those two tests still passed (`2 passed`, exit 0). That edit was restored and is not the K4 result.

The printed command in `replay_line` was then changed to `PARALLEL_WORKERS=4`. Both replay tests failed, exit 1:

```
E       AssertionError: assert 'PARALLEL_WORKERS=4' == 'PARALLEL_WORKERS=1'
E       AssertionError: assert <re.Match object; span=(25, 43), match='PARALLEL_WORKERS=4'> is None
FAILED tests/test_queuetrail_rails.py::test_rails_replay_prints_single_process_command
FAILED tests/test_queuetrail_rails.py::test_rails_replay_refuses_parallel_workers_above_one
2 failed in 0.18s
K4_EXIT:1
```

Restored.

## K5 reverse_check accepts a wrong sha256

The target digest mismatch was changed to `return 0` with no `SHA FAIL` line. `test_rails_reverse_check_rejects_wrong_sha256` failed, exit 1:

```
E       AssertionError: assert 0 != 0
E        +  where 0 = CompletedProcess(... returncode=0, stdout='', stderr='').returncode
FAILED tests/test_queuetrail_rails.py::test_rails_reverse_check_rejects_wrong_sha256
1 failed in 0.07s
K5_EXIT:1
```

Restored.

## K6 spec citation removed

The `Cites: R-Q3.` line was deleted from `docs/QUEUETRAIL-RAILS-SPEC.md`. The citation test failed, exit 1:

```
E           AssertionError: RR1 has no observation citation
FAILED tests/test_queuetrail_rails.py::test_spec_every_rr_cites_an_observation
1 failed in 0.02s
K6_EXIT:1
```

Restored. `sha256sum docs/QUEUETRAIL-RAILS-SPEC.md` again printed `79ebca667281b1a3d26a2323f787da69762a8fd6ee8dbd7a754837bc727f775b`.

## Step 6 after the restores

```
===== ruby rails_hook_test =====
OK
RUBY_EXIT:0
===== pytest =====
...................................                                      [100%]
35 passed in 3.60s
PYTEST_EXIT:0
===== reverse_check_rails =====
R-Q1 PASS
R-Q2 PASS
R-Q3 PASS
R-Q4 PASS
R-Q5 PASS
R-Q6 PASS
CHECK_EXIT:0
===== wrong sha =====
SHA FAIL target

WRONG_SHA_EXIT:1
===== sha256sum -c =====
BASE.txt: OK
BRIEF.md: OK
activesupport-8.1.4.gem: OK
minitest-6.0.6.gem: OK
observations.json: OK
railties-8.1.4.gem: OK
rails-8082369.tar.gz: OK
rails-926edf5.tar.gz: OK
rea-attempt.log: OK
recon.log: OK
ruby-v3_3_8.tar.gz: OK
../../docs/QUEUETRAIL-RAILS-SPEC.md: OK
cited/activesupport-8.1.4/lib/active_support.rb: OK
cited/activesupport-8.1.4/lib/active_support/test_case.rb: OK
cited/activesupport-8.1.4/lib/active_support/testing/parallelization.rb: OK
cited/activesupport-8.1.4/lib/active_support/testing/parallelization/server.rb: OK
cited/activesupport-8.1.4/lib/active_support/testing/parallelization/worker.rb: OK
cited/activesupport-8.1.4/lib/active_support/testing/parallelize_executor.rb: OK
cited/minitest-6.0.6/History.rdoc: OK
cited/minitest-6.0.6/lib/minitest.rb: OK
cited/minitest-6.0.6/lib/minitest/parallel.rb: OK
cited/minitest-6.0.6/lib/minitest/test.rb: OK
cited/rails-8082369/lib/active_support/test_case.rb: OK
cited/rails-8082369/lib/active_support/testing/parallelization.rb: OK
cited/rails-8082369/lib/active_support/testing/parallelization/server.rb: OK
cited/rails-8082369/lib/active_support/testing/parallelization/worker.rb: OK
cited/rails-8082369/lib/active_support/testing/parallelize_executor.rb: OK
cited/rails-926edf5/lib/active_support/test_case.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelization.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelization/server.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelization/test_distributor.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelization/thread_pool_executor.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelization/worker.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelize_executor.rb: OK
cited/railties-8.1.4/lib/rails/generators/rails/app/templates/test/test_helper.rb.tt: OK
cited/railties-8.1.4/lib/rails/test_help.rb: OK
cited/ruby-v3_3_8/internal/random.h: OK
cited/ruby-v3_3_8/process.c: OK
cited/ruby-v3_3_8/random.c: OK
cited/ruby-v3_3_8/thread.c: OK
cited/ruby-v3_3_8/thread_pthread.c: OK
HOLDOUT-QTR.sha256: OK
SUMS_EXIT:0
===== make queuetrail-test =====
nice -n 19 ruby tools/queuetrail/test/hook_test.rb
OK
nice -n 19 python3 -m pytest tests/test_queuetrail.py -q
....................                                                     [100%]
20 passed in 1.17s
nice -n 19 python3 tools/queuetrail/reverse_check.py --gem inputs/rea-brief-test-queue/test-queue-0.12.0.gem --control inputs/rea-brief-test-queue/parallel_tests-5.8.0.gem --expect inputs/rea-brief-test-queue/observations.json
Q1 PASS
Q2 PASS
Q3 PASS
Q4 PASS
Q5 PASS
C1 PASS
O6 PASS
O7 PASS
MAKE_QT_EXIT:0
```

`make queuetrail-test` is the existing target. Its output is the same shape as before this branch: hook OK, 20 passed, Q1 through O7 PASS.

The existing `reverse_check.py` still requires `--control` and cannot take this observations file. The step-6 checker is the new file `tools/queuetrail/reverse_check_rails.py`.

## UNPROVEN

- RR4 order fidelity, and whether replay reproduces a real victim failure. The shim is specified and unit-tested against stubs. It has not been run on Rails or Minitest.
- RR5 adapter fit. `certify_rspec` is RSpec-only. The handoff writes an ids file and records that a minitest certify runner is not built here.
- H1, H2, H3, H4, H5. Predictions are sealed. They are not scored in Phase 1.

R-Q4 is cited from Ruby 3.3.8 (`v3_3_8`, commit `b200bad6cd40d08e9f33b93e1a85c270b337867c`) in `observations.json`. It is not in this list.

## Codeload re-run

Pushed head `28b6f9df18fd43ad30db73a1cad97aaff54b8ed8`. `git ls-remote` returned that same sha for `refs/heads/feat/queuetrail-rails`. Fresh tarball:

```
curl -fsSL -o /tmp/qtr-head.tar.gz https://codeload.github.com/realmpastai-web/flakecert/tar.gz/28b6f9df18fd43ad30db73a1cad97aaff54b8ed8
fc9d7c4034fb5e38f6d5d4b6450947e10ffed483ba18ee005110e92e85c549b7  /tmp/qtr-head.tar.gz
```

Extracted to `/tmp/qtr-codeload/flakecert-28b6f9df18fd43ad30db73a1cad97aaff54b8ed8`. Step 6 from that tree:

```
===== ruby rails_hook_test =====
OK
RUBY_EXIT:0
===== pytest =====
...................................                                      [100%]
35 passed in 3.86s
PYTEST_EXIT:0
===== reverse_check_rails =====
R-Q1 PASS
R-Q2 PASS
R-Q3 PASS
R-Q4 PASS
R-Q5 PASS
R-Q6 PASS
CHECK_EXIT:0
===== wrong sha =====
SHA FAIL target

WRONG_SHA_EXIT:1
===== sha256sum -c =====
BASE.txt: OK
BRIEF.md: OK
activesupport-8.1.4.gem: OK
minitest-6.0.6.gem: OK
observations.json: OK
railties-8.1.4.gem: OK
rails-8082369.tar.gz: OK
rails-926edf5.tar.gz: OK
rea-attempt.log: OK
recon.log: OK
ruby-v3_3_8.tar.gz: OK
../../docs/QUEUETRAIL-RAILS-SPEC.md: OK
cited/activesupport-8.1.4/lib/active_support.rb: OK
cited/activesupport-8.1.4/lib/active_support/test_case.rb: OK
cited/activesupport-8.1.4/lib/active_support/testing/parallelization.rb: OK
cited/activesupport-8.1.4/lib/active_support/testing/parallelization/server.rb: OK
cited/activesupport-8.1.4/lib/active_support/testing/parallelization/worker.rb: OK
cited/activesupport-8.1.4/lib/active_support/testing/parallelize_executor.rb: OK
cited/minitest-6.0.6/History.rdoc: OK
cited/minitest-6.0.6/lib/minitest.rb: OK
cited/minitest-6.0.6/lib/minitest/parallel.rb: OK
cited/minitest-6.0.6/lib/minitest/test.rb: OK
cited/rails-8082369/lib/active_support/test_case.rb: OK
cited/rails-8082369/lib/active_support/testing/parallelization.rb: OK
cited/rails-8082369/lib/active_support/testing/parallelization/server.rb: OK
cited/rails-8082369/lib/active_support/testing/parallelization/worker.rb: OK
cited/rails-8082369/lib/active_support/testing/parallelize_executor.rb: OK
cited/rails-926edf5/lib/active_support/test_case.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelization.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelization/server.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelization/test_distributor.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelization/thread_pool_executor.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelization/worker.rb: OK
cited/rails-926edf5/lib/active_support/testing/parallelize_executor.rb: OK
cited/railties-8.1.4/lib/rails/generators/rails/app/templates/test/test_helper.rb.tt: OK
cited/railties-8.1.4/lib/rails/test_help.rb: OK
cited/ruby-v3_3_8/internal/random.h: OK
cited/ruby-v3_3_8/process.c: OK
cited/ruby-v3_3_8/random.c: OK
cited/ruby-v3_3_8/thread.c: OK
cited/ruby-v3_3_8/thread_pthread.c: OK
HOLDOUT-QTR.sha256: OK
SKEPTIC-QTR.md: OK
SUMS_EXIT:0
===== make queuetrail-test =====
nice -n 19 ruby tools/queuetrail/test/hook_test.rb
OK
nice -n 19 python3 -m pytest tests/test_queuetrail.py -q
....................                                                     [100%]
20 passed in 1.20s
nice -n 19 python3 tools/queuetrail/reverse_check.py --gem inputs/rea-brief-test-queue/test-queue-0.12.0.gem --control inputs/rea-brief-test-queue/parallel_tests-5.8.0.gem --expect inputs/rea-brief-test-queue/observations.json
Q1 PASS
Q2 PASS
Q3 PASS
Q4 PASS
Q5 PASS
C1 PASS
O6 PASS
O7 PASS
MAKE_QT_EXIT:0
```

## Fix round A.1, after the holdout was sealed

`HOLDOUT-QTR.txt` was not opened or rewritten. `HOLDOUT-QTR.sha256` is still `ebedebf332994ca606ace12c750e32bcbd772da96c591bb71d70ecc38064f083`.

Hark's review of `f58290d` said the planted pair cannot fire. The fixture loaded only `en.yml`, and i18n 1.14.8 `Config#locale=` calls `enforce_available_locales!` before assigning `@locale` (`lib/i18n/config.rb:14-16`). Enforcement defaults to true (`config.rb:140`) and the ActiveSupport railtie restores it after init (`i18n_railtie.rb:45`, `:66`). `I18n.locale = :fr` would raise `I18n::InvalidLocale` (`lib/i18n.rb:381-383`), the locale would stay `:en`, and the victim would always pass. H2 and H3 would miss because of the fixture. The fixture was corrected after sealing for that reason. It was still not executed.

`git diff` of the fixture files that already existed:

```
diff --git a/fixtures/rails-parallel-pair/Gemfile b/fixtures/rails-parallel-pair/Gemfile
index 4265d86..9c12d63 100644
--- a/fixtures/rails-parallel-pair/Gemfile
+++ b/fixtures/rails-parallel-pair/Gemfile
@@ -2,3 +2,4 @@ source "https://rubygems.org"
 
 gem "rails", "8.1.4"
 gem "minitest", "6.0.6"
+gem "i18n", "1.14.8"
diff --git a/fixtures/rails-parallel-pair/PAIR.md b/fixtures/rails-parallel-pair/PAIR.md
index ef5f2a2..cc681b0 100644
--- a/fixtures/rails-parallel-pair/PAIR.md
+++ b/fixtures/rails-parallel-pair/PAIR.md
@@ -4,11 +4,15 @@ This fixture is not executed in Phase 1. There is no `Gemfile.lock`.
 
 ## Pair
 
-Polluter: `LocalePolluterTest#test_sets_french_and_leaves_it` in `test/locale_polluter_test.rb`. It sets `I18n.locale = :fr` and has no teardown that restores `:en`. `I18n.locale` is process-global.
+Polluter: `LocalePolluterTest#test_sets_french_and_leaves_it` in `test/locale_polluter_test.rb`. It sets `I18n.locale = :fr` and has no teardown that restores `:en`.
 
-Victim: `LocaleVictimTest#test_expects_english_greeting` in `test/locale_victim_test.rb`. It asserts `I18n.locale == :en` and `I18n.t("greeting") == "Hello"`. The English string is `config/locales/en.yml`.
+Victim: `LocaleVictimTest#test_expects_english_greeting` in `test/locale_victim_test.rb`. It asserts `I18n.locale == :en` and `I18n.t("greeting") == "Hello"`. The English string is `config/locales/en.yml` (`greeting: Hello`). The French string is `config/locales/fr.yml` (`greeting: Bonjour`).
 
-If both methods run in one process and the polluter runs first, the victim fails. A worker that does not run the polluter before the victim keeps the default `:en` locale and the victim passes. The other test methods do not assign `I18n.locale`.
+i18n 1.14.8, the exact version pinned in the Gemfile, stores `I18n.config` on the current thread (`lib/i18n.rb:58-59` and `:64`, `thread_variable_get` / `thread_variable_set` of `:i18n_config`). `Config#locale=` (`lib/i18n/config.rb:14-16`) calls `enforce_available_locales!` and then assigns `@locale` on that config. Enforcement defaults to true (`config.rb:140`). `enforce_available_locales!` (`lib/i18n.rb:381-383`) raises `I18n::InvalidLocale` when the locale is not available. ActiveSupport's railtie (`lib/active_support/i18n_railtie.rb:43-45`) turns enforcement off while it copies `config.i18n`, then restores it (`:66`). `config.i18n` itself is defined at `i18n_railtie.rb:11`. `config/application.rb` requires `active_support/railtie` and sets `config.i18n.available_locales = [:en, :fr]`, so `:fr` is a declared locale when enforcement is back on.
+
+This fixture uses the default `with: :processes`. A forked worker is one process, and the tests that run there share that thread's config, so a polluter that runs first leaves `:fr` for a later victim in the same worker. `with: :threads` gives each thread its own `I18n.config`, so this pair does not cross threads.
+
+If both methods run in one worker process and the polluter runs first, the victim fails. A worker that does not run the polluter before the victim keeps the default `:en` locale and the victim passes. The other test methods do not assign `I18n.locale`.
diff --git a/fixtures/rails-parallel-pair/config/application.rb b/fixtures/rails-parallel-pair/config/application.rb
index b08ef18..634dd58 100644
--- a/fixtures/rails-parallel-pair/config/application.rb
+++ b/fixtures/rails-parallel-pair/config/application.rb
@@ -6,12 +6,14 @@ require "active_job/railtie"
 require "action_controller/railtie"
 require "action_view/railtie"
 require "rails/test_unit/railtie"
+require "active_support/railtie"
 
 Bundler.require(*Rails.groups)
 
 module ParallelPair
   class Application < Rails::Application
     config.load_defaults 8.1
+    config.i18n.available_locales = [:en, :fr]
     config.eager_load = false
     config.cache_classes = true
     config.secret_key_base = "fixture-only-secret-key-base-not-for-production-use-00"
```

New file `fixtures/rails-parallel-pair/config/locales/fr.yml`:

```
fr:
  greeting: Bonjour
```

`I18n.config` is per thread (`lib/i18n.rb:58-64`). `with: :processes` shares that config inside one worker. `with: :threads` gives each thread its own config, so this pair does not cross threads. PAIR.md no longer calls the locale process-global.

Mutants K1-K7 were applied, each matching test failed, and each file was restored:

```
K1_EXIT:1
srand_seed field
K2_EXIT:1
RR2 suite order
K3_EXIT:1
RR2 status is read from the result, got ["fail", "pass", "skip", "fail", "fail"]
K4_EXIT:1
AssertionError: assert 'PARALLEL_WORKERS=4' == 'PARALLEL_WORKERS=1'
K5_EXIT:1
AssertionError: assert 0 != 0
K6_EXIT:1
AssertionError: RR1 has no observation citation
K7_EXIT:1
FileNotFoundError: .../fixtures/rails-parallel-pair/config/locales/fr.yml
FAILED tests/test_queuetrail_rails.py::test_fixture_declares_en_and_fr_locales
```

Spec sha256 after those restores: `9f15f35ef4f14a6180592f5e062d9daa343f20d627486b39d48e167756eb2698`.
