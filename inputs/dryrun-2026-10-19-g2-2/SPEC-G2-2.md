# Spec G2.2: residual seeds and cause sets (second polluter) on teamshares/axn#235
Evidence: reverse/recon-g2-2.log (regenerate: reverse/recon-g2-2.sh). Static only: it reads merged evidence JSON and axn base source; Hark ran nothing from axn.
Prior: flakecert main 611e80f (PR #11 merged; evidence/certify-rspec-g2 checks with 0 bad, R1). G2 spec inputs/dryrun-2026-10-19-g2/, score inputs/dryrun-2026-10-19-g2-reveal/ (6/8).

## Gap (R2, R3, R7)
- strategies_spec[1:1:5:1] (registry_behavior.rb:100) failed at base with the same DuplicateStrategyError in seeds 16, 24, 26 and 27,
  while running BEFORE its certified polluter strategies_spec[1:1:2:3]. So that polluter is sufficient but not the whole cause set.
- R7 over 30 base seeds: the victim failed in all 4 seeds where the named polluter was absent from the prefix and strategies_spec[1:3:1] was present.
  This is correlation only. Not a result.
## Static candidates (R4-R6, R8-R9; never given to the tool)
- strategies_spec.rb:35 ([1:3:1]) calls clear! then registers :custom, with no cleanup at base.
- use_strategy_spec.rb:14-17 has a before hook that clears and registers :custom, and the file has no after hooks.
- Seeds 16 and 26 also have 10 use_strategy_spec examples before the victim. Seeds 24 and 27 have none.
- Clearers in the suite (vernier, client, factory, slack_sender, use_strategy) can mask a leak. That may explain the R7 rows where the victim passed.

## Tool changes (on main 611e80f)
S6 residual seeds: for each CERTIFIED ORDER-DEPENDENT victim, take every base seed in s0 where the victim failed and ran before EVERY known polluter.
   Use existing s0 JSON only and write s6/residual-seeds.json. No new suite runs.
S7 residual attribution: per residual seed, candidates = ids that ran before the victim in that seed's base order.
   Reproduce test: run candidates + victim with the G2.1 ordering hook in that exact seed order. The order guard must pass.
   The victim fails with the same first error class as in s0.
   - Probe 0 is the full prefix. If it doesn't reproduce, label the seed UNREPRODUCED and stop.
   - Run the existing ddmin to a 1-minimal set and log every probe.
S8 cause set: after round k finds a set Pk, drop Pk from the candidates and re-run S7. Stop when probe 0 no longer reproduces, or after 3 rounds (CAP_REACHED).
   A seed is EXPLAINED when its round-1 set reproduces 3/3.
S9 certify every new polluter set with the S4 arms (A, B, C via the ordering hook with the order guard; head as base). Same victim-only rule.
   The victim cert holds a cause_set list: each polluter set with its own verdicts, seed provenance and replay script.
S10 no regressions: rejudge G2 evidence, so the 8 labels stay unchanged and exit_ok stays true.

## Acceptance (Docker ruby:3.3, same image digest as G2 run.log)
1. grep -RInE 'custom|ErrorHandlerMiddleware|on_exception|RegistryFixtures|clear!|use_strategy|strategies_spec' over tools/certify_rspec and invocation.txt exits 1.
2. At least 1 new polluter set CERTIFIED for strategies_spec[1:1:5:1], with residual-seed provenance.
3. Every residual seed is EXPLAINED, or labeled UNREPRODUCED / CAP_REACHED with its probe log.
4. All replays exit 0 on two runs. G2 rejudge unchanged. Root pytest green, with new tests for the S6 selection rule, S8 stop rules and the cause_set schema.
GO iff 1-4. Holdout predictions-G2-2.json is sealed in HOLDOUT-G2-2.sha256 and scored once by Hark after the run.
