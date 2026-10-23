# Spec F4/F5: which fastlane#30184 F1 failures are order-dependent (RSpec only; nothing executed by Hark)

Source: evidence/dryrun-2026-10-19 @ 39e72e0 (PR #8). F1 at 76eeb3f, `--seed 48174`, 913 examples, 31 failures, the same 31 ids in all
3 reps (sorted id list sha256 b44fea03... for r1, r2, r3). F2 at 148c1c9: 1 failure, two_step_or_factor_client_spec.rb:76.
F3 showed spaceauth_spec.rb:7 fails ALONE 3/3 (WebMock::NetConnectNotAllowedError on signin/init), so a failure at seed 48174 is
not by itself an order dependency. F4 separates the two.

- F4: at 76eeb3f, for each id in f1-failing-ids.txt (31 lines): `bundle exec rspec <id>` alone, 3 reps. Record pass/fail and the
  first error class per run. An id is ORDER-DEPENDENT iff it fails 3/3 in F1 and passes 3/3 alone.
- F5: at 148c1c9, `bundle exec rspec spaceship/spec --seed 48174` once more, and report the outcome of every ORDER-DEPENDENT id.
- Same image as Part 2 (ruby:3.1, Bundler 2.6.9, RSpec 3.12). Log ruby -v, bundle -v. Do not edit this folder.
Holdout: predictions-F4.json sealed by sha256 in HOLDOUT-F4.sha256, scored once.
Pass condition for a FlakeCert RSpec real-world pair: >= 1 ORDER-DEPENDENT id that passes in F5.
