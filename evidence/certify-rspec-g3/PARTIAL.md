# G3 partial close-out

This file records the resume that already finished. It does not start a new run. Every count below is copied from the file named on that line.

## Stop

`evidence/certify-rspec-g3/summary.json` has `exit_ok` false, `reason` `ENV_SETUP`, and `wall_clock_s` 10736.3. `evidence/certify-rspec-g3/g3.log` has `WALL_CLOCK=10736.3`, `setup_failures=2`, `exit_ok=false`, `reason=ENV_SETUP`. The last line of `evidence/certify-rspec-g3/resume.log` and line 496 of `evidence/certify-rspec-g3/run.log` are `2026-10-20T07:51:02Z exit_ok=False reason=ENV_SETUP wall=10736.3`.

The stop is the two environment setup failures in `run.log`:

- line 474: `2026-10-20T07:50:04Z ENV_SETUP_FAILURE count=1`
- line 477: `2026-10-20T07:50:10Z ENV_SETUP_FAILURE count=2`

Both are `./spec/lib/gitlab/background_migration/update_jira_tracker_data_deployment_type_based_on_url_spec.rb` (`summary.json` verdict `INCOMPLETE`, `arm_f_trials` 0). The preserved logs are `arm-f/00a05162a528756d/seed-01.setup-1.log` and `arm-f/00a05162a528756d/seed-01.setup-2.log`. Each has this excerpt:

```
LoadError:
  cannot load such file -- /gitlab/spec/lib/gitlab/background_migration/update_jira_tracker_data_deployment_type_based_on_url_spec.rb
```

and ends `0 examples, 0 failures, 1 error occurred outside of examples`. That path is missing from GitLab's own spec tree at the pinned commit. It is not a FlakeCert gate failure.

## Sample verdicts

`summary.json` `s20` (20 paths): `BOUNDED_CLEAN` 5, `INCOMPLETE` 2, `NOT_RUN` 13.

`BOUNDED_CLEAN`, 0 failures in 30 trials, arm G pass:

- `./spec/models/board_spec.rb`
- `./spec/models/concerns/from_intersect_spec.rb`
- `./spec/lib/gitlab/git/blame_spec.rb`
- `./spec/lib/gitlab/pagination/keyset/page_spec.rb`
- `./spec/lib/gitlab/database/postgresql_adapter/dump_schema_versions_mixin_spec.rb`

`INCOMPLETE`:

- `./spec/lib/gitlab/throttle_spec.rb` (0 failures in 1 trial, arm G pass)
- `./spec/lib/gitlab/background_migration/update_jira_tracker_data_deployment_type_based_on_url_spec.rb` (0 trials, arm G fail)

`NOT_RUN` (13), each with 0 trials in `summary.json`:

- `./spec/models/concerns/limitable_spec.rb`
- `./spec/lib/gitlab/auth/atlassian/user_spec.rb`
- `./spec/lib/gitlab/memory/reports/jemalloc_stats_spec.rb`
- `./spec/lib/gitlab/github_import_spec.rb`
- `./spec/lib/gitlab/api_authentication/token_resolver_spec.rb`
- `./spec/models/review_spec.rb`
- `./spec/lib/gitlab/markdown_cache/redis/store_spec.rb`
- `./spec/lib/gitlab/ci/matching/build_matcher_spec.rb`
- `./spec/lib/gitlab/ci/reports/terraform_reports_spec.rb`
- `./spec/models/integrations/chat_message/issue_message_spec.rb`
- `./spec/lib/gitlab/database/schema_cache_with_renamed_table_spec.rb`
- `./spec/lib/gitlab/ci/build/artifacts/metadata/entry_spec.rb`
- `./spec/lib/gitlab/diff/position_tracer/image_strategy_spec.rb`

Category A in `summary.json` (10 paths): `PASSES_ALONE` 8, `UNRESOLVED` 2. The unresolved files are `spec/mailers/devise_mailer_spec.rb` and `spec/requests/users_controller_spec.rb`.

B1 in `summary.json`: `spec/services/timelogs/delete_service_spec.rb` label `PASSES_ALONE`.

## What the certificates support

`NOT_RUN` and `INCOMPLETE` are not evidence of clean. The claims in this pack cover only the 5 `BOUNDED_CLEAN` certificates listed above.

`certificates/001a329edc1a9ae1.txt` (`./spec/lib/gitlab/git/blame_spec.rb`) moved from `INCOMPLETE` 0/3 to `BOUNDED_CLEAN` 0/30 after the seed-4 resume. At commit `e07a350` the certificate's first two lines were `0 failures in 3 seeded runs -> failure rate <= 63.16%` and `INCOMPLETE`. On disk now the first two lines are `0 failures in 30 seeded runs -> failure rate <= 9.50%` and `BOUNDED_CLEAN` (sha256 `3eac11a246071d4ef5b760133ee028fdb31889cf4db08f4f7376cb67eb9f4cee`). `summary.json` records `arm_f_failures` 0 and `arm_f_trials` 30 for that path. `run.log` line 266 is `END rc=124 elapsed_s=159.4` for `seed-04.log` (the unfinished seed). Lines 283 and 286 are `RESUME continue from_seed=4` and `RESUME rerun unfinished seed=4`. Line 288 is `END rc=0 elapsed_s=98.0` for the same seed log.

The three older certificates are byte-identical to the digests `run.log` lines 280-282 recorded as `skip_verified`:

```
25d805477519ccb38e632b962efa3823c4ae1f10c6c484ade3e9821210706c89  certificates/00031d8665bd69bb.txt
cf48a804bdd4c54eb923ad30718bb3996b4dde7a3367a584aa6af94634ed4ba6  certificates/000823af86f945f3.txt
e36af5400046ea3448e8e5b4dd0378feee85c8d56e0a598abf9be2e041deaee1  certificates/001b5959e258723a.txt
```

## make verify

`/tmp/g3-make-verify.log` line 98 is `make: *** [Makefile:36: verify] Error 1`. Line 96 is:

```
GATES {"frozen_hash": true, "effective_set": true, "swaps_logged": true, "offline_run": true, "certificates": false, "blind_comparator": true, "bounds": true, "baseline_denominator": true, "summary_traceable": true, "readme_ingest": true}
```

`certificates` is false. The same log says `replay F04 NOT_RUN Unable to find image 'flakecert:F04' locally`, and the same for `flakecert:F06` and `flakecert:F14`. `replay F15 NOT_RUN pip_freeze_mismatch`. The other gates in that JSON are true. CI run 39391541035 on `7899122` completed with conclusion success (`gh run list --branch feat/certify-rspec-g3 -L 1`). The certificate gate was not changed to pass.
