# F4/F5 summary (fastlane spaceship, 2026-10-19)

Pins: F4 at `76eeb3f9352a657fd979ae00e89e49a388729e30`, F5 at `148c1c9b4c041b1659ea633f2632dd47eef8cb04`. Image `flakecert-dryrun-fastlane:ruby31` (`sha256:1a9f5251d78b846341bad2d4b1992d89f71e97d3d7416146b45d2dbecbd75481`, `q4.log` line 7). `q4.log` lines 32, 34, and 39: `ruby 3.1.7p261 (2025-03-26 revision 0a3704f218) [x86_64-linux]`, `Bundler version 2.6.9`, `RSpec 3.12` (rspec-core 3.12.2, rspec-expectations 3.12.3, rspec-mocks 3.12.6, rspec-support 3.12.1).

F1 evidence check (`q4.log` lines 25-29): the 31 ids in `inputs/dryrun-2026-10-19-f4/f1-failing-ids.txt` are the failed-example list, same order, in `evidence/dryrun-2026-10-19/rspec/F1-76eeb3f-r1.log`, `r2`, and `r3`. `f1_all_31_failed_3_of_3=True`.

F4: each id alone, 3 reps, `bundle exec rspec <id>` at 76eeb3f. 93 logs, `rspec/F4-<n>-r<k>.log`, `n` = 1-based line in `f1-failing-ids.txt`. `q4.log` line 65476: `F4 files: 93`. Line 65477: 18 logs contain `1 example, 0 failures`. Line 65478: 75 logs contain `1 example, 1 failure`. Lines 65479-65480: 18 `RSPEC_EXIT:0` and 75 `RSPEC_EXIT:1`. Line 65520: `rep_or_class_disagreements 0` (the three reps of each id share the summary and the error class).

An id is ORDER-DEPENDENT when it failed 3/3 in F1 and passed 3/3 alone. **6 ids are ORDER-DEPENDENT** (`q4.log` line 65521: `ORDER_DEPENDENT_COUNT 6`).

F5: one `bundle exec rspec spaceship/spec --seed 48174` at 148c1c9. `rspec/F5.log` line 9 `Randomized with seed 48174`, line 1611 `913 examples, 1 failure`, line 1615 the only failed example `./spaceship/spec/two_step_or_factor_client_spec.rb:76`, line 1604 `RuntimeError`. Same lines are in `q4.log` at 65460 and 65464. An id's F5 outcome is `fail` only when that line is the failed example; every other id is `pass` because the suite reported 913 examples and 1 failure (same example count as F1).

**5 ORDER-DEPENDENT ids pass in F5** (`q4.log` line 65522: `OD_AND_F5_PASS_COUNT 5`). **Pass condition holds** (`q4.log` line 65523: `PASS_CONDITION True`). The rule is at least one ORDER-DEPENDENT id that passes in F5.

`two_step_or_factor_client_spec.rb:76` is ORDER-DEPENDENT (passes alone 3/3) and is the F5 failure.

## Table

`n` is the F4 log index. First error class is the class line in the first failure. Passes have none. For `spaceauth_spec.rb:49` and `:59`, RSpec printed no class line; the failure text is `expected: 0` / `got: 1` (`rspec/F4-3-r1.log` lines 24-25, `rspec/F4-4-r1.log` lines 24-25). Installed `rspec-core-3.12.2` `exception_presenter.rb` line 188 skips the class line when the class name matches `/RSpec/`.

| n | id | alone r1-r3 | first error class | ORDER-DEPENDENT y/n | F5 outcome |
| --- | --- | --- | --- | --- | --- |
| 1 | ./spaceship/spec/spaceauth_spec.rb:7 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 2 | ./spaceship/spec/spaceauth_spec.rb:81 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 3 | ./spaceship/spec/spaceauth_spec.rb:59 | fail/fail/fail | omitted (/RSpec/); expected: 0 got: 1 | n | pass |
| 4 | ./spaceship/spec/spaceauth_spec.rb:49 | fail/fail/fail | omitted (/RSpec/); expected: 0 got: 1 | n | pass |
| 5 | ./spaceship/spec/spaceship_spec.rb:28 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 6 | ./spaceship/spec/spaceship_spec.rb:12 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 7 | ./spaceship/spec/spaceship_spec.rb:24 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 8 | ./spaceship/spec/spaceship_spec.rb:16 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 9 | ./spaceship/spec/spaceship_spec.rb:4 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 10 | ./spaceship/spec/spaceship_spec.rb:20 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 11 | ./spaceship/spec/spaceship_spec.rb:8 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 12 | ./spaceship/spec/spaceship_spec.rb:37 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 13 | ./spaceship/spec/spaceship_spec.rb:33 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 14 | ./spaceship/spec/spaceship_spec.rb:45 | fail/fail/fail | WebMock::NetConnectNotAllowedError | n | pass |
| 15 | ./spaceship/spec/connect_api/models/build_beta_detail_spec.rb:5 | pass/pass/pass | none | y | pass |
| 16 | ./spaceship/spec/connect_api/models/beta_build_metric_spec.rb:5 | pass/pass/pass | none | y | pass |
| 17 | ./spaceship/spec/connect_api/models/app_store_version_release_request_spec.rb:5 | pass/pass/pass | none | y | pass |
| 18 | ./spaceship/spec/connect_api/models/build_delivery_spec.rb:5 | pass/pass/pass | none | y | pass |
| 19 | ./spaceship/spec/portal/certificate_spec.rb:111 | pass/pass/pass | none | y | pass |
| 20 | ./spaceship/spec/connect_api/models/certificate_spec.rb:5 | fail/fail/fail | TypeError | n | pass |
| 21 | ./spaceship/spec/connect_api/models/certificate_spec.rb:37 | fail/fail/fail | TypeError | n | pass |
| 22 | ./spaceship/spec/connect_api/models/certificate_spec.rb:60 | fail/fail/fail | TypeError | n | pass |
| 23 | ./spaceship/spec/connect_api/models/device_spec.rb:62 | fail/fail/fail | TypeError | n | pass |
| 24 | ./spaceship/spec/connect_api/models/device_spec.rb:55 | fail/fail/fail | TypeError | n | pass |
| 25 | ./spaceship/spec/connect_api/models/device_spec.rb:36 | fail/fail/fail | TypeError | n | pass |
| 26 | ./spaceship/spec/connect_api/models/device_spec.rb:30 | fail/fail/fail | TypeError | n | pass |
| 27 | ./spaceship/spec/connect_api/models/device_spec.rb:42 | fail/fail/fail | TypeError | n | pass |
| 28 | ./spaceship/spec/connect_api/models/device_spec.rb:48 | fail/fail/fail | TypeError | n | pass |
| 29 | ./spaceship/spec/connect_api/models/device_spec.rb:5 | fail/fail/fail | TypeError | n | pass |
| 30 | ./spaceship/spec/connect_api/models/device_spec.rb:69 | fail/fail/fail | TypeError | n | pass |
| 31 | ./spaceship/spec/two_step_or_factor_client_spec.rb:76 | pass/pass/pass | none | y | fail |

## Skeptic pass

These can move a result without being order dependence in the specs:

- The fastlane tarballs were not re-downloaded. `q4.log` lines 11-13: their sha256 matches the hashes recorded in the earlier dry run `q0.log` (`078c5e59…` for 76eeb3f, `db53c7bc…` for 148c1c9), and `tarball_sha_match=yes`. `vendor/bundle` on those trees is the earlier `bundle install` against rubygems.org, not a fresh resolve in this task. `Gemfile.lock` is what that install used. A new install could still differ if a yanked gem or a native-extension rebuild differed; this run did not do that.
- The image layers (Debian apt packages, Ruby 3.1.7, Bundler 2.6.9) were built earlier the same day from `ruby:3.1`. `q4.log` line 36-37 lists `bundler (2.6.9, default: 2.3.27)` twice. `bundle -v` still printed `Bundler version 2.6.9`. Specs ran with `BUNDLE_APP_CONFIG=/src/.bundle`, which selects `vendor/bundle`. Dropping that variable is what made `rspec` missing in the earlier dry run.
- `spec_helper.rb` calls `Coveralls.wear!` unless `FASTLANE_SKIP_UPDATE_CHECK` is set. That variable was not set. Every log prints `[Coveralls] Set up the SimpleCov formatter`, and WebMock allows `coveralls.io`. A coveralls POST is network, not the example body. Each log prints the example summary and then `RSPEC_EXIT` equal to `docker_exit`, so a coveralls error did not replace the rspec status. `coverage/.resultset.json` on the mounted tree changed: `q4.log` line 20 vs line 65471 (76eeb3f) and line 21 vs line 65472 (148c1c9). That file is shared across runs. SimpleCov merging it should not change assertions; it is still host state from the previous dry run plus these runs.
- Each example used `timeout 420 docker run --rm`, so container `/tmp` (`rspec_failed_tests.txt` from `example_status_persistence_file_path`, and `fastlane_tests`) did not carry into the next rep. No log shows exit 124. The mounted source tree did carry `coverage/`.
- F4 commands had no `--seed`. Every F4 log says `1 example`, so there is no example-order inside the process. File hooks still run. That is the spec, and it is the same tree F1 used.
- F5 `pass` for the other 30 ids is the suite total (913 examples, 1 failure, one failed-example line), not a per-id pass line. A missing example would have changed 913. It matches F1's 913.
- The container is Linux, not macOS, same as Part 2. xcode-tagged examples skip here. These 31 each reported `1 example`, so they were not skipped.
- `FASTLANE_SPEC_SINGLETON_GUARD` was unset. At this commit `spec_helper.rb` defaults it to `reset` and clears listed tool singletons after each example. That code is in the 76eeb3f tree F1 already ran. It is source, not an extra variable from this driver. It can still change which failures look order-dependent compared with a tree that does not have the guard.
- A first driver start printed `ruby -v` and then died with `unexpected EOF while looking for matching` because the shell script was edited while bash was reading it. No example ran in that process. `q4.log` is only the completed second driver.
