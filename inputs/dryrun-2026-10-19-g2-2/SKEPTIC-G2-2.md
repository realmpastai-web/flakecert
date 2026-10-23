# Skeptic pass (before any run)
1. R7 is a 30-seed contingency drawn from the same data that S6 selects from. Predictions built on it are expected to score well, so a high holdout score is weak evidence.
   The real test is S9 arm C (victim-first) and head FIXED.
2. ddmin returns one 1-minimal set. When independent leakers exist (many use_strategy examples each leak), which one it returns depends on the split.
   Report "a sufficient set", never "the cause".
3. Three rounds bound nothing. CAP_REACHED means the cause set is at least k, not exactly k.
4. Masking (a clearer between the polluter and the victim) is not modeled. Seeds where the victim passed despite a polluter running earlier stay unexplained by design.
5. Ruby 3.3 only, and seeds 1..30 only.
6. Product angle: "all polluters per flaky test" is the claim. It is UNPROVEN until it beats rspec --bisect (one set) on more than one repo.
