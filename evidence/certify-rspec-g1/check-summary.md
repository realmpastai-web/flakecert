# PR check

One line per order-dependent id. Verdicts are arm A. Plain-retry is arm B.

| victim | base | head | plain-retry base | plain-retry head | polluter ids | label |
| --- | --- | --- | --- | --- | --- | --- |
| ./spaceship/spec/connect_api/models/build_beta_detail_spec.rb:5 | NOT_FIXED | FIXED | FIXED | FIXED | ./spaceship/spec/connect_api/models/webhook_spec.rb[1:1:1:1] | CERTIFIED |
| ./spaceship/spec/connect_api/models/beta_build_metric_spec.rb:5 | NOT_FIXED | FIXED | FIXED | FIXED | ./spaceship/spec/connect_api/models/webhook_spec.rb[1:1:1:1] | CERTIFIED |
| ./spaceship/spec/connect_api/models/app_store_version_release_request_spec.rb:5 | NOT_FIXED | FIXED | FIXED | FIXED | ./spaceship/spec/connect_api/models/capabilities_spec.rb[1:1:1] | CERTIFIED |
| ./spaceship/spec/connect_api/models/build_delivery_spec.rb:5 | POLLUTER_FAILED | FIXED | FIXED | FIXED | ./spaceship/spec/connect_api/provisioning/provisioning_client_spec.rb[1:1:2:1:2] | REJECTED |
| ./spaceship/spec/portal/certificate_spec.rb:111 | NOT_FIXED | FIXED | FIXED | FIXED | ./spaceship/spec/provisioning_profile_spec.rb[1:12:3:1] | CERTIFIED |
| ./spaceship/spec/two_step_or_factor_client_spec.rb:76 | NOT_FIXED | NOT_FIXED | FIXED | FIXED | ./spaceship/spec/two_step_or_factor_client_spec.rb[1:2:3:1] | CONTROL |

## Skeptic pass

Read against `inputs/dryrun-2026-10-19-g1/SKEPTIC-G1.md` after this run.

- Each certificate names one sufficient polluter id returned by `rspec --bisect`. The certificate is the per-victim verdict and the replay.
- `s1.doc.log` lines 8-9 print `[Coveralls] Set up the SimpleCov formatter` and `Using SimpleCov's default settings`. Line 10 prints `Changing stdout to /tmp/fastlane_tests`. `FASTLANE_SKIP_UPDATE_CHECK` was unset, so Coveralls runs. A coveralls POST is network. The verdicts are the rspec example statuses.
- `docker run --rm` drops container `/tmp` between reps. `coverage/` on the mounted tree stays. Base `coverage/` was created at 14:12 by a hashcash smoke before S1 and then shared by later base runs. Head `coverage/` was created during S4. Arm A/B/C signatures used for the verdicts were stable across reps on exit code, counts, error class, failed ids, and order.
- cert-4 base arm A is `WebMock::NetConnectNotAllowedError` on all three reps, and the first message line differs on each rep (the SRP `a` field). cert-5 base arm A is the same class, and the certificate-request body differs across reps. `replay.sh` compares exit code, counts, error class, failed ids, and order. It leaves the message line out. All six `replay.sh` runs exited 0 (`replay-check.log`).
- This run's `bundle_check_exit=0` (`run.log`). It did not reinstall. `vendor/bundle` was completed earlier from rubygems.org (`/tmp/flakecert-g1-1019/work/bundle-base-resume.log` and `bundle-head-resume.log`, `Bundle complete! 29 Gemfile dependencies, 174 gems`). Native extensions were compiled in image `sha256:1f3248c0b71fb38ce02d05bc3cee8da5257792360158a660b83518c8cb827e63`. Docker server `26.1.5+dfsg1`.
- The longest bisect argument vector is `rspec_argv_len=41883` on `two_step_or_factor_client_spec.rb:76`. That run's `docker_exit=0`.
- One repo and one pull request. The run is this image, these two tarballs, seed 48174.

## Rejudge

Rejudged from the recorded S4 runs. Each run's log sha256 matches the file under s4/. No rspec rerun.

NOT_FIXED requires a stable arm failure whose failed_ids equal [victim_id] on every rep, so the polluter ids passed. If any rep's failed_ids include a polluter id, that arm's verdict is POLLUTER_FAILED and the certificate label is REJECTED. The first error message line stays out of the signature.

What else could move a verdict:
- Adding the message line to the signature would split reps whose message text changes while the error class and failed ids stay the same.
- Reading the documentation Failed examples file:line instead of the JSON example id would not equal victim_id.
- A failure list of the victim plus any other id is not NOT_FIXED. A polluter id in that list is POLLUTER_FAILED.
- A polluter failure on a single rep is enough for POLLUTER_FAILED.
- Arm C has no verdict field. A polluter failure only on C still sets the label to REJECTED.
- FIXED still means the arm's exit code and failure count say pass. The id check applies to failures.
