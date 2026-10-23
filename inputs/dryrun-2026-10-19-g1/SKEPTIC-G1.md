# Skeptic pass (before any run)
1. Novelty: rspec --bisect already minimizes polluters (B1-B3). FlakeCert's claim is only the per-victim attribution, cross-commit
   verdict and replayable certificate; don't sell "finds the polluter".
2. Attribution is a minimal SUFFICIENT set, not THE cause in CI: several breakers exist (breaker-sets.log); bisect keeps the latest
   (B3). The cert says "this polluter reproduces it and the PR removes that effect", nothing more.
3. Bisect checks failure, not message (B3:150). A different error (e.g. an expired rspec double from connect_api/spaceship_spec, or
   WebMock) can satisfy it. S4 requires one stable first error class; acceptance 2 requires the M4 TypeError.
4. Fork runner boots spec_helper once (B6/B8). At the fix commit spec_helper's after(:suite) deletes SPACESHIP_COOKIE_DIR, so bisect
   under fork at head could misbehave. S3 runs bisect at base only; S4 uses plain rspec runs at both.
5. Victim-alone reps and A/B/C reps are 3: no rate bound. These paths have no RNG except the unstubbed SRP 'a' seen in F6 C4.
6. Coveralls is active (F6 notes): network present. Verdicts must not depend on it; record it.
7. Long argv in S3 (hundreds of ids) could hit shell limits; record argv length.
8. One repo, one PR. A user needs it on their suite; G1 proves the method, not market fit.
