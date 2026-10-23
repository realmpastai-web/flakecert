# Rails parallel polluter / victim

This fixture is not executed in Phase 1. There is no `Gemfile.lock`.

## Pair

Polluter: `LocalePolluterTest#test_sets_french_and_leaves_it` in `test/locale_polluter_test.rb`. It sets `I18n.locale = :fr` and has no teardown that restores `:en`.

Victim: `LocaleVictimTest#test_expects_english_greeting` in `test/locale_victim_test.rb`. It asserts `I18n.locale == :en` and `I18n.t("greeting") == "Hello"`. The English string is `config/locales/en.yml` (`greeting: Hello`). The French string is `config/locales/fr.yml` (`greeting: Bonjour`).

i18n 1.14.8, the exact version pinned in the Gemfile, stores `I18n.config` on the current thread (`lib/i18n.rb:58-59` and `:64`, `thread_variable_get` / `thread_variable_set` of `:i18n_config`). `Config#locale=` (`lib/i18n/config.rb:14-16`) calls `enforce_available_locales!` and then assigns `@locale` on that config. Enforcement defaults to true (`config.rb:140`). `enforce_available_locales!` (`lib/i18n.rb:381-383`) raises `I18n::InvalidLocale` when the locale is not available. ActiveSupport's railtie (`lib/active_support/i18n_railtie.rb:43-45`) turns enforcement off while it copies `config.i18n`, then restores it (`:66`). `config.i18n` itself is defined at `i18n_railtie.rb:11`. `config/application.rb` requires `active_support/railtie` and sets `config.i18n.available_locales = [:en, :fr]`, so `:fr` is a declared locale when enforcement is back on.

This fixture uses the default `with: :processes`. A forked worker is one process, and the tests that run there share that thread's config, so a polluter that runs first leaves `:fr` for a later victim in the same worker. `with: :threads` gives each thread its own `I18n.config`, so this pair does not cross threads.

If both methods run in one worker process and the polluter runs first, the victim fails. A worker that does not run the polluter before the victim keeps the default `:en` locale and the victim passes. The other test methods do not assign `I18n.locale`.

## Why `threshold: 1`

`test/test_helper.rb` calls `parallelize(workers: 4, threshold: 1)`.

ActiveSupport 8.1.4 sets the default threshold to 50:

```
lib/active_support.rb:105:  cattr_accessor :test_parallelization_threshold, default: 50
```

Parallel workers start only when `PARALLEL_WORKERS` is set or the test count is above the threshold, and the worker count is greater than 1:

```
lib/active_support/testing/parallelize_executor.rb:56:        def should_parallelize?
lib/active_support/testing/parallelize_executor.rb:57:          (ENV["PARALLEL_WORKERS"] || tests_count > threshold) && many_workers?
lib/active_support/testing/parallelize_executor.rb:60:        def many_workers?
lib/active_support/testing/parallelize_executor.rb:61:          size > 1
```

`ENV["PARALLEL_WORKERS"]` also replaces the worker count (`test_case.rb:115-116`). This suite is 40 tests, under 50, so the default threshold would keep them in one process. `threshold: 1` is what makes `workers: 4` take effect when `PARALLEL_WORKERS` is unset.

## Hook

`QUEUETRAIL_RAILS=1` makes `test_helper.rb` require `tools/queuetrail/rails.rb` after `require "rails/test_help"`. When that variable is unset, the hook file is not loaded.

## Tests

Eight files, forty tests:

| file | class | tests |
|---|---|---|
| test/alpha_test.rb | AlphaTest | 6 |
| test/beta_test.rb | BetaTest | 6 |
| test/gamma_test.rb | GammaTest | 6 |
| test/delta_test.rb | DeltaTest | 6 |
| test/epsilon_test.rb | EpsilonTest | 6 |
| test/zeta_test.rb | ZetaTest | 6 |
| test/locale_polluter_test.rb | LocalePolluterTest | 2 |
| test/locale_victim_test.rb | LocaleVictimTest | 2 |
