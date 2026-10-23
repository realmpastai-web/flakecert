# Spec F6: first real-world RSpec FlakeCert certificate (fastlane#30184), polluters named

Method: REA clean-room. Static reverse only (nothing from fastlane executed by Hark). Every claim below cites reverse/recon.log
(regenerate with reverse/recon.sh from an empty dir) or reverse/f1-order.log (read from flakecert main a75858b).

## Pinned artifacts (reverse/recon.log lines 1-7)
- fastlane prefix 76eeb3f9352a657fd979ae00e89e49a388729e30, codeload tar.gz sha256 078c5e59b1765b88d829d9878b29deffb66e85122301a1f65d90b714bc81abaa
- fastlane fix 148c1c9b4c041b1659ea633f2632dd47eef8cb04 (PR #30192), codeload tar.gz sha256 db53c7bc72519a447c11961956516a240472457042b28a6ea12f7138968390d5
- rspec-core 3.12.2 (Gemfile.lock pin) .gem sha256 155b54480f28e2b2813185077fe435c2d663031616360ed3b179a9d6a55d2551 (= rubygems.org API sha)
- Whole-tree diff prefix..fix = 6 spec/helper files; spaceship/lib unchanged (M9). So any change in outcome is the spec harness, not the product.

## Mechanism A (4 victims): stale ConnectAPI @client
- M2: `Spaceship::ConnectAPI.client` returns `@client` if set, before building an implicit client from Tunes/Portal sessions.
- M1/M3: webhook_spec's `after` does `ConnectAPI.token = nil` -> `@client = Client.new(token: nil)`; Client.new wires test_flight/tunes
  request clients only `if cookie || token || tunes_client` -> none wired. M5: 5 specs log in portal-only (use_tunes: false) -> same.
- M7: the victims only `include_examples "common spaceship login"`, which at the prefix does `Spaceship::Tunes.login` and never resets
  ConnectAPI @client. M4: TestFlight/Tunes API raise `TypeError: You need to instantiate this module with ..._request_client`.
- M6: the only spec writers of ConnectAPI @client are listed; no lib code writes it.
- F1 order at seed 48174 (f1-order.log): Webhook(148) -> BuildBetaDetail(163) -> BetaBuildMetric(183) -> Capabilities(210) ->
  AppStoreVersionReleaseRequest(252) ... Profile(339) -> Provisioning::Client(350) -> BuildDelivery(380). No other M6 writer sits between
  each named polluter and its victim. F1 r1 failure messages match (#15,#16,#18 test_flight; #17 tunes).
- M8 the fix: shared example now sets `Spaceship::ConnectAPI.client = nil` and `Spaceship::Portal.login`.
- Named polluter hypotheses (static, UNPROVEN until F6 runs): webhook_spec -> build_beta_detail:5 and beta_build_metric:5;
  capabilities_spec -> app_store_version_release_request:5; provisioning_client_spec -> build_delivery:5.
- portal/certificate_spec.rb:111 (WebMock in F1) polluter NOT named; out of F6 scope.

## Mechanism B (NOT_FIXED control): ENV leak in two_step spec
- N1: 'when running interactive' example (:94) sets ENV SPACESHIP_ONLY_ALLOW_INTERACTIVE_2FA="true" and never deletes it; :76 then hits
  lib raise "2FA can only be performed in interactive mode". Spec and lib identical at both commits. F1 r1 and F2 r1 both run
  'when running interactive' (1411) right before 'when running non-interactive' (1413).

## Ordering primitives (rspec-core 3.12.2, R1/R2)
- Explicit file args keep command-line order (get_files_to_run: no sort; only directory globs are sorted) -> `--order defined` with
  polluter file first gives polluter-then-victim.
- Random order = `sort_by jenkins(seed + id)` per sibling set, so `--seed 48174` on `:76:94` keeps the F1 relative order.

## Runs (Cursor team box; same env as F4: ruby:3.1, 3.1.7p261, Bundler 2.6.9, RSpec 3.12). Each at BOTH commits, 3 reps = 60 runs.
Common flags: `bundle exec rspec --format documentation --no-color`. Paths relative to repo root, prefix `./spaceship/spec/`.
| id | args |
|---|---|
| C1 | --order defined connect_api/models/webhook_spec.rb connect_api/models/build_beta_detail_spec.rb:5 |
| C2 | --order defined connect_api/models/webhook_spec.rb connect_api/models/beta_build_metric_spec.rb:5 |
| C3 | --order defined connect_api/models/capabilities_spec.rb connect_api/models/app_store_version_release_request_spec.rb:5 |
| C4 | --order defined connect_api/provisioning/provisioning_client_spec.rb connect_api/models/build_delivery_spec.rb:5 |
| R1-R4 | same as C1-C4 with the two file args swapped (victim first) |
| N1 | --seed 48174 two_step_or_factor_client_spec.rb:76:94 |
| NR1 | --order defined two_step_or_factor_client_spec.rb:76:94 |
Plain-retry arm = F4 (victims alone, 3/3 pass at 76eeb3f; f1-order.log tail), not rerun.

## Certificate verdicts
- Pair Ci is CERTIFIED iff: doc output shows the polluter group before the victim; Ci fails 3/3 at 76eeb3f with the M4 message;
  Ci passes 3/3 at 148c1c9; Ri passes 3/3 at both. Verdict: prefix NOT_FIXED, fix FIXED. Plain retry (F4): FIXED at prefix (wrong).
- Control valid iff N1 fails 3/3 at both and NR1 passes 3/3 at both: NOT_FIXED at both.
- GO: >= 1 certified pair AND valid control. Holdout predictions-F6.json sealed in HOLDOUT-F6.sha256, scored once.
