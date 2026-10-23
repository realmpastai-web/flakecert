# Spec: fastlane/fastlane#30184 (RSpec, module singleton leak). Clean-room, static only, nothing executed.

## Target (evidence: evidence/fastlane-30184/)
- Issue #30184, open, 2 comments (issue-30184.json, comments-30184.json). Issue text: `bundle exec rspec spaceship/spec --order random`
  -> 915 examples, 17 failures; `#<Double "portal_client"> ... has leaked into another example`, at
  `spaceship/lib/spaceship/connect_api/spaceship.rb:28:in 'Spaceship::ConnectAPI.client'`.
- Maintainer comment 2026-09-09: CI measured "at the pinned seed 48174"; baseline 48 failures (full run, not spaceship-only).
- Real fix: PR #30192 "Stop spaceship specs sharing clients and cached state", merged 2026-09-12 02:25 IST,
  squash commit `148c1c9b4c041b1659ea633f2632dd47eef8cb04`, single parent `76eeb3f9352a657fd979ae00e89e49a388729e30`
  (= #30190 merge). 6 files, all specs/spec helpers (pr-30192-files.json). PR #30192's 6 files contain no `spaceship/lib/` file, so the fix
  is test-isolation only, not app code. `spaceship.rb` copies at 3a4fc36 (master at issue time, 2026-09-07) and 148c1c9 diff empty.

## Pair for FlakeCert
- prefix = 76eeb3f, real_fix = 148c1c9. A wrong_fix is not frozen yet (to be written after the pytest pair scores).

## Exact runs (forced order via RSpec's own seed; no plugin)
- F1 `bundle exec rspec spaceship/spec --seed 48174` at 76eeb3f, 3 reps.
- F2 same at 148c1c9, 3 reps.
- F3 victim-only control: the first failing example id from F1 run alone, 3 reps (expect pass).
Ruby/bundler versions are pinned by the repo's Gemfile.lock at each commit; record `ruby -v` and `bundle -v` in the log.

## Holdout
H5-H7 sealed in HOLDOUT.sha256. If F1 shows 0 leak failures at 48174, that is scored as a miss; no seed search before scoring.
