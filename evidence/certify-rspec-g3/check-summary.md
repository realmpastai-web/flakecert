# G3 check summary

Counts below are copied from the logs named on each line.

## Sample

- S20 paths: `s20.txt` (20 lines).
- Category paths: `cat_a.txt`.
- B1 path: `b1.txt`.

## Arm results

| path | arm G | arm F verdict | failures | certificate |
| --- | --- | --- | --- | --- |
| `./spec/models/board_spec.rb` | PASS `arm-g/00031d8665bd69bb.log` | BOUNDED_CLEAN | 0/30 | `certificates/00031d8665bd69bb.txt` |
| `./spec/models/concerns/from_intersect_spec.rb` | PASS `arm-g/000823af86f945f3.log` | BOUNDED_CLEAN | 0/30 | `certificates/000823af86f945f3.txt` |
| `./spec/lib/gitlab/git/blame_spec.rb` | PASS `arm-g/001a329edc1a9ae1.log` | BOUNDED_CLEAN | 0/30 | `certificates/001a329edc1a9ae1.txt` |
| `./spec/lib/gitlab/pagination/keyset/page_spec.rb` | PASS `arm-g/001b5959e258723a.log` | BOUNDED_CLEAN | 0/30 | `certificates/001b5959e258723a.txt` |
| `./spec/lib/gitlab/database/postgresql_adapter/dump_schema_versions_mixin_spec.rb` | PASS `arm-g/003e9fa2e3451681.log` | BOUNDED_CLEAN | 0/30 | `certificates/003e9fa2e3451681.txt` |
| `./spec/lib/gitlab/throttle_spec.rb` | PASS `arm-g/007aff8231bde71e.log` | INCOMPLETE | 0/1 | `certificates/007aff8231bde71e.txt` |
| `./spec/lib/gitlab/background_migration/update_jira_tracker_data_deployment_type_based_on_url_spec.rb` | FAIL `arm-g/00a05162a528756d.log` | INCOMPLETE | 0/0 | `` |
| `./spec/models/concerns/limitable_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/lib/gitlab/auth/atlassian/user_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/lib/gitlab/memory/reports/jemalloc_stats_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/lib/gitlab/github_import_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/lib/gitlab/api_authentication/token_resolver_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/models/review_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/lib/gitlab/markdown_cache/redis/store_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/lib/gitlab/ci/matching/build_matcher_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/lib/gitlab/ci/reports/terraform_reports_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/models/integrations/chat_message/issue_message_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/lib/gitlab/database/schema_cache_with_renamed_table_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/lib/gitlab/ci/build/artifacts/metadata/entry_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |
| `./spec/lib/gitlab/diff/position_tracer/image_strategy_spec.rb` | FAIL `` | NOT_RUN | 0/0 | `` |

Files that pass arm G and fail arm F: none. Source rows are the arm table above.

## Category labels

- `spec/mailers/devise_mailer_spec.rb` UNRESOLVED alone=`cat-a/4920aeb197e8c272-alone.log` siblings=`cat-a/4920aeb197e8c272-siblings.log`
- `spec/models/ci/build_trace_chunks/fog_spec.rb` PASSES_ALONE alone=`cat-a/3b8d4a2618e4d3b0-alone.log` siblings=`cat-a/3b8d4a2618e4d3b0-siblings.log`
- `spec/models/concerns/reactive_caching_spec.rb` PASSES_ALONE alone=`cat-a/44968f98661aa9b2-alone.log` siblings=`cat-a/44968f98661aa9b2-siblings.log`
- `spec/lib/gitlab/query_limiting/active_support_subscriber_spec.rb` PASSES_ALONE alone=`cat-a/0b26e1c3f997c549-alone.log` siblings=`cat-a/0b26e1c3f997c549-siblings.log`
- `spec/requests/api/graphql/mutations/ci/job_token_scope/remove_project_spec.rb` PASSES_ALONE alone=`cat-a/22a8c2cf06015b64-alone.log` siblings=`cat-a/22a8c2cf06015b64-siblings.log`
- `spec/requests/api/graphql/mutations/issues/set_escalation_status_spec.rb` PASSES_ALONE alone=`cat-a/ac7023540d80b3f3-alone.log` siblings=`cat-a/ac7023540d80b3f3-siblings.log`
- `spec/requests/api/graphql/project/error_tracking/sentry_errors_request_spec.rb` PASSES_ALONE alone=`cat-a/9ba4cff6870f3776-alone.log` siblings=`cat-a/9ba4cff6870f3776-siblings.log`
- `spec/requests/api/graphql/project/recent_issue_boards_query_spec.rb` PASSES_ALONE alone=`cat-a/9a4670a41e91cf6b-alone.log` siblings=`cat-a/9a4670a41e91cf6b-siblings.log`
- `spec/requests/users_controller_spec.rb` UNRESOLVED alone=`cat-a/fb59d6ac7d0fdc52-alone.log` siblings=`cat-a/fb59d6ac7d0fdc52-siblings.log`
- `spec/services/design_management/generate_image_versions_service_spec.rb` PASSES_ALONE alone=`cat-a/504c938610b95fb9-alone.log` siblings=`cat-a/504c938610b95fb9-siblings.log`

## B1

- path `spec/services/timelogs/delete_service_spec.rb` label `PASSES_ALONE`
- set `[]` same_file=False replay_twice=True
- logs `b1/defined.log` `b1/reverse.log` `b1/bisect.log` `b1/ddmin.log`

## Skeptic pass

The questions are the frozen `SKEPTIC-G3.md`. Answers use this run's logs.

```
# Skeptic pass (before any run)
1. GitLab is a proving ground for the method. GitLab builds its own tooling (scripts/rspec_check_order_dependence, rspec_order.rb) and runs AI agents on the backlog.
   Expect contributions to be accepted.
2. G-c rests on #601849's definition only. None of the 10 named Category A files cites a missing constant (T6). It may find 0 BRITTLE (Q3 predicts at most 1).
3. 153 FOSS removals in about 4.5 months (T1/T2), plus no issue update since 2026-06-17 (T4), could mean the effort stalled. It could also mean it moved elsewhere (MRs not linked here). Issue notes are UNKNOWN (401).
4. GDK is heavy (Postgres, Redis, Gitaly, Vite). Category A "Vite not running" failures may be harness noise in our run too.
5. A 30-seed bound (9.50%) is still weak. The headline must never round it to "not flaky".
6. S20 is limited to models/lib for cost, so it is not representative of request or feature specs.
7. This note records pain signals only. This run tests no commercial claim.
```

1. This subject is a proving ground for the method.
2. Enabler labels are the category list above. A zero enabler count is what `cat_a` logs support, not a prediction.
3. Removal totals stay in `inputs/dryrun-2026-10-19-g3/reverse/recon-gitlab.log` under T1 and T2. Notes were not read.
4. Setup noise is an `ENV_FAILURE` label only when the alone log matches the structural rule in that file's meta.
5. Each S20 certificate's first line is the Clopper-Pearson bound. `BOUNDED_CLEAN` means zero failures inside that bound, not the absence of flakes.
6. `s20.txt` is only the models/lib FOSS slice from the frozen spec. It does not represent request or feature specs.
7. This run is a method proof; it tests no commercial claim.

Holdout seal file `HOLDOUT-G3.sha256` was not opened as a predictions document. Its digest is recorded in `summary.json`. Q3 stays N/A under the amendment because the full-suite arm was dropped. The dated question stays for its own date.

