# G2.2 residual seeds and cause sets

Prior evidence: `evidence/certify-rspec-g2`.
S6 list: `s6/residual-seeds.json`.
Probe logs: `s7/` and `s8/`. Arm logs: `s9/`.
Prior rejudge: `s10/rejudge.log`.

| victim | seed | status | rounds |
| --- | --- | --- | --- |
| ./spec/axn/strategies_spec.rb[1:1:5:1] | 16 | CAP_REACHED | r1:./spec/axn/core/use_strategy_spec.rb[1:1:3]; r2:./spec/axn/core/use_strategy_spec.rb[1:1:1]; r3:./spec/axn/core/use_strategy_spec.rb[1:1:2] |
| ./spec/axn/strategies_spec.rb[1:1:5:1] | 24 | EXPLAINED | r1:./spec/axn/strategies_spec.rb[1:3:1]; r2:- |
| ./spec/axn/strategies_spec.rb[1:1:5:1] | 26 | CAP_REACHED | r1:./spec/axn/core/use_strategy_spec.rb[1:1:2]; r2:./spec/axn/core/use_strategy_spec.rb[1:1:1]; r3:./spec/axn/core/use_strategy_spec.rb[1:1:3] |
| ./spec/axn/strategies_spec.rb[1:1:5:1] | 27 | EXPLAINED | r1:./spec/axn/strategies_spec.rb[1:3:1]; r2:- |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 3 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:12:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 7 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:7:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 8 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:8:2]; r2:./spec/axn/tools/registry_spec.rb[1:8:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 13 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:12:1]; r2:./spec/axn/tools/registry_spec.rb[1:7:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 14 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:./spec/axn/tools/registry_spec.rb[1:12:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 15 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:./spec/axn/tools/registry_spec.rb[1:13:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 20 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:13:1]; r2:- |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 24 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:- |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 25 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:13:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:1]; r3:./spec/axn/tools/registry_spec.rb[1:8:2] |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 26 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:13:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 29 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:7:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:7] | 30 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 3 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:12:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 7 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:7:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 8 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:8:2]; r2:./spec/axn/tools/registry_spec.rb[1:8:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 13 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:12:1]; r2:./spec/axn/tools/registry_spec.rb[1:7:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 14 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:./spec/axn/tools/registry_spec.rb[1:12:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 15 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:./spec/axn/tools/registry_spec.rb[1:13:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 20 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:13:1]; r2:- |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 24 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:- |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 25 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:13:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:1]; r3:./spec/axn/tools/registry_spec.rb[1:8:2] |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 26 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:13:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 29 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:7:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:6] | 30 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 3 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:12:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 7 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:7:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 8 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:8:2]; r2:./spec/axn/tools/registry_spec.rb[1:8:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 13 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:12:1]; r2:./spec/axn/tools/registry_spec.rb[1:7:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 14 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:./spec/axn/tools/registry_spec.rb[1:12:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 15 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:./spec/axn/tools/registry_spec.rb[1:13:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 20 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:13:1]; r2:- |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 24 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:- |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 25 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:13:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:1]; r3:./spec/axn/tools/registry_spec.rb[1:8:2] |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 26 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:13:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 29 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:7:1] |
| ./spec/axn/tools/registry_spec.rb[1:5:3] | 30 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:4:2] | 3 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:4:2] | 4 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:13:1]; r2:./spec/axn/tools/registry_spec.rb[1:7:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:4:2] | 7 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:4:2] | 14 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:- |
| ./spec/axn/tools/registry_spec.rb[1:4:2] | 16 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:13:1]; r2:- |
| ./spec/axn/tools/registry_spec.rb[1:4:2] | 18 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:8:2]; r2:./spec/axn/tools/registry_spec.rb[1:8:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:4:2] | 19 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:11:1]; r2:- |
| ./spec/axn/tools/registry_spec.rb[1:4:2] | 23 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:./spec/axn/tools/registry_spec.rb[1:8:1] |
| ./spec/axn/tools/registry_spec.rb[1:4:2] | 24 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:7:1]; r2:./spec/axn/tools/registry_spec.rb[1:11:1]; r3:- |
| ./spec/axn/tools/registry_spec.rb[1:4:2] | 28 | CAP_REACHED | r1:./spec/axn/tools/registry_spec.rb[1:11:1]; r2:./spec/axn/tools/registry_spec.rb[1:13:1]; r3:./spec/axn/tools/registry_spec.rb[1:8:1] |
| ./spec/axn/tools/registry_spec.rb[1:4:2] | 30 | EXPLAINED | r1:./spec/axn/tools/registry_spec.rb[1:8:1]; r2:./spec/axn/tools/registry_spec.rb[1:8:2]; r3:- |

| polluter ids | label | seeds | replay |
| --- | --- | --- | --- |
| ./spec/axn/core/use_strategy_spec.rb[1:1:1] | CERTIFIED | 16,26 | replay-1.sh |
| ./spec/axn/core/use_strategy_spec.rb[1:1:2] | CERTIFIED | 16,26 | replay-2.sh |
| ./spec/axn/core/use_strategy_spec.rb[1:1:3] | CERTIFIED | 16,26 | replay-3.sh |
| ./spec/axn/strategies_spec.rb[1:3:1] | CERTIFIED | 24,27 | replay-4.sh |
| ./spec/axn/tools/registry_spec.rb[1:12:1] | CERTIFIED | 3,13,14 | replay-5.sh |
| ./spec/axn/tools/registry_spec.rb[1:13:1] | CERTIFIED | 15,20,25,26 | replay-6.sh |
| ./spec/axn/tools/registry_spec.rb[1:7:1] | CERTIFIED | 7,13,14,15,24,29 | replay-7.sh |
| ./spec/axn/tools/registry_spec.rb[1:8:1] | CERTIFIED | 3,7,8,25,26,29,30 | replay-8.sh |
| ./spec/axn/tools/registry_spec.rb[1:8:2] | CERTIFIED | 3,7,8,25,26,29,30 | replay-9.sh |
| ./spec/axn/tools/registry_spec.rb[1:12:1] | CERTIFIED | 3,13,14 | replay-10.sh |
| ./spec/axn/tools/registry_spec.rb[1:13:1] | CERTIFIED | 15,20,25,26 | replay-11.sh |
| ./spec/axn/tools/registry_spec.rb[1:7:1] | CERTIFIED | 7,13,14,15,24,29 | replay-12.sh |
| ./spec/axn/tools/registry_spec.rb[1:8:1] | CERTIFIED | 3,7,8,25,26,29,30 | replay-13.sh |
| ./spec/axn/tools/registry_spec.rb[1:8:2] | CERTIFIED | 3,7,8,25,26,29,30 | replay-14.sh |
| ./spec/axn/tools/registry_spec.rb[1:12:1] | CERTIFIED | 3,13,14 | replay-15.sh |
| ./spec/axn/tools/registry_spec.rb[1:13:1] | CERTIFIED | 15,20,25,26 | replay-16.sh |
| ./spec/axn/tools/registry_spec.rb[1:7:1] | CERTIFIED | 7,13,14,15,24,29 | replay-17.sh |
| ./spec/axn/tools/registry_spec.rb[1:8:1] | CERTIFIED | 3,7,8,25,26,29,30 | replay-18.sh |
| ./spec/axn/tools/registry_spec.rb[1:8:2] | CERTIFIED | 3,7,8,25,26,29,30 | replay-19.sh |
| ./spec/axn/tools/registry_spec.rb[1:11:1] | CERTIFIED | 19,24,28 | replay-20.sh |
| ./spec/axn/tools/registry_spec.rb[1:13:1] | CERTIFIED | 4,16,28 | replay-21.sh |
| ./spec/axn/tools/registry_spec.rb[1:7:1] | CERTIFIED | 4,14,23,24 | replay-22.sh |
| ./spec/axn/tools/registry_spec.rb[1:8:1] | CERTIFIED | 3,7,18,23,28,30 | replay-23.sh |
| ./spec/axn/tools/registry_spec.rb[1:8:2] | CERTIFIED | 3,7,18,23,30 | replay-24.sh |

## Skeptic pass

1. R7 is a 30-seed contingency drawn from the same data that S6 selects from. Predictions built on it are expected to score well, so a high holdout score is weak evidence.
   The real test is S9 arm C (victim-first) and head FIXED.

Arm C and the head verdict are on each new polluter certificate. The sealed holdout file was not scored.

2. ddmin returns one 1-minimal set. When independent leakers exist (many use_strategy examples each leak), which one it returns depends on the split.
   Report "a sufficient set", never "the cause".

Each recorded set is one sufficient 1-minimal result. Which set the minimiser returns depends on the split. The certificate does not call that set the only cause.

3. Three rounds bound nothing. CAP_REACHED means the cause set is at least k, not exactly k.

The search stops after three rounds. CAP_REACHED means at least those rounds found a set, not that no further set exists.

4. Masking (a clearer between the polluter and the victim) is not modeled. Seeds where the victim passed despite a polluter running earlier stay unexplained by design.

Only a seed whose victim failed before every known polluter is searched. A pass after an earlier polluter is outside this search.

5. Ruby 3.3 only, and seeds 1..30 only.

The run records the Ruby image in run.log. Seeds are the base seeds present in the prior s0 directory.

6. Product angle: "all polluters per flaky test" is the claim. It is UNPROVEN until it beats rspec --bisect (one set) on more than one repo.

This run is one repository. It does not compare the method with bisect on any other repository.

## Rejudge

Labels were recomputed from the prior certificates and compared with the stored labels.
Log sha256 values were checked against the files named by those certificates.
The prior directory was not rewritten.

unchanged: True
exit_ok: True
