# Spec G2: certify-rspec on teamshares/axn#235 (seed discovery + BRITTLE/enabler class)
Evidence: reverse/recon-axn.log (regenerate: reverse/recon-axn.sh). Static only; Hark executed nothing from axn.
Prior: G1 spec inputs/dryrun-2026-10-19-g1/ and recon-bisect.log (B1-B9), merged tool on flakecert main 9b9cfec.

## Target (recon-axn.log ## sha256, A1-A5)
- teamshares/axn, MIT. PR #235 merged 2026-08-15. base 8daba1dcb4e1f44e2a26c87e2d602c10fc04eca9 (tgz 63119f8a...823c),
  merge 6c62d568e27844bf7500be0a54425b7c9c65a8cc (tgz 6b21ebd8...46e0). A1: the trees differ in the 9 spec files only, so head = base + PR.
- A2: rspec-core 3.13.2, rspec-mocks 3.13.2, Bundler 2.5.6. A3: CI Ruby 3.2/3.3/3.4, `bundle exec rake spec` (RakeTask, no --order).
- A4: .rspec has no --order/--seed and spec_helper has none, so CI runs DEFINED order. That is why base was green and no seed is named.
- A5: the global before calls Axn::Testing.reset! + Tools::Registry.reset_adapters! only. It does not reset @on_exception, registries or constants.

## Mechanisms the PR names, with static evidence (do not give these to the tool)
- M1 registry :custom leak: Registry#register raises the duplicate error on an existing key (internal/registry.rb:34-41). The shared
  '.clear!' example (registry_behavior.rb:100) registers :custom WITHOUT clearing first, while :26/:32/:38/:46 and strategies_spec.rb:35 leave
  :custom registered. Used by Axn::Strategies and Axn::Async::Adapters (separate registries).
- M2 lazy constant: ErrorHandlerMiddleware is const_set only when error_handler is configured (client.rb:108-112). client_spec :169/:175
  reference the constant directly, so they raise NameError UNLESS :163 ran first. This is not polluter-then-victim. The victim needs an ENABLER.
- M3 real-require fixtures in tools/registry_spec keep constants that exact-membership asserts (contain_exactly / eq) then see.
- M4 lazy `let(:original_handler)` read first in `after` restores the handler the example installed (5 files, recon M4), so it leaks a
  handler process-wide.

## rspec-core 3.13.2 --bisect (B10-B12)
- bisect/ differs from 3.12.2 only at example_minimizer.rb:139: `ids_to_run = all_example_ids & (ids + failed_example_ids)`, so subsets are
  re-sorted into the original order. The reproduce rule is unchanged (:150): a subset counts only if the original failures FAIL.
- Consequence (gap): --bisect cannot find an ENABLER (a test whose prior run makes the victim pass). M2 is exactly that class.

## Tool changes for G2 (on top of main 9b9cfec)
S-1 exit rule (G1 open note): exit 0 iff every classified id is CERTIFIED, CONTROL, BRITTLE_CERTIFIED or explicitly REJECTED/UNATTRIBUTED
    with a reason. summary.json exit_ok must follow it. Re-run on G1 evidence via `rejudge`, so exit_ok=True there.
S0 seed discovery (no seed given): run `rspec spec --order defined` once and `rspec spec --seed s` for s in 1..30, at base and head
    (62 runs). Save s0/seeds.json: per seed, failing ids at base and head. Primary seed = the seed with the most base failures that all
    pass at head (ties: smallest). Union U = every id failing at base in any seed, with the seeds it failed in.
S1/S2 classify each id in U at base, 3 reps alone:
    ORDER-DEPENDENT = passes alone 3/3. BRITTLE = fails alone 3/3 at base AND passes in the base defined-order run.
    OTHER = everything else.
S3 attribute: OD as in G1 (rspec --bisect at base on the first seed in which v failed, ids that ran before v). BRITTLE: enabler search
    by the tool's own ddmin over the ids that ran before v in the base defined-order run. Candidate set E reproduces iff
    `rspec --order defined E v` passes v. Minimise to 1-minimal. Record every probe.
S4 certify: OD as G1.1 (victim must be the only failed id). BRITTLE_CERTIFIED iff at base v alone fails 3/3 with one error class and
    `E v` (defined) passes 3/3, and at head v alone passes 3/3.
S5 certs + replay.sh + check-summary as G1, with seed provenance (which seed, the s0 line) in each cert.

## Acceptance (base 8daba1dc / head 6c62d568, Docker ruby:3.3 + bundle from base Gemfile.lock, record image digest)
1. No mechanism names in tools/ or the invocation: grep -RInE 'custom|ErrorHandlerMiddleware|on_exception|RegistryFixtures|clear!' on
   tools/certify_rspec and invocation.txt exits 1.
2. >=3 CERTIFIED or BRITTLE_CERTIFIED certificates covering >=2 of the PR's spec files.
3. Every replay.sh exits 0 on a second run. G1 rejudge gives exit_ok True with G1 labels unchanged (CERTIFIED 4, REJECTED 1, CONTROL 1).
4. Root `python3 -m pytest -q` green. New unit tests: seed pick rule, BRITTLE rule, ddmin on a canned fixture, exit rule.
GO iff 1-4. Holdout predictions-G2.json sealed in HOLDOUT-G2.sha256, scored once after the run.
