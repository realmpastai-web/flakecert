# Skeptic pass (before any run)
1. Seed search spends CI minutes (62 full runs). The product claim needs that cost in run.log (wall time).
2. 30 seeds bound nothing: an id that never fails in 1..30 is not proven order-safe. Report the seeds searched, never "flake-free".
3. BRITTLE needs the defined-order run to pass v. If CI order changes, the enabler may differ. The cert states the order it used.
4. ddmin can return a sufficient enabler that is not the one CI used (as G1 skeptic #2). The cert claims sufficiency only.
5. Ruby 3.3 only; CI also runs 3.2/3.4. A pass on 3.3 says nothing about the other two.
6. M4 (handler leak) may cause no visible failure for any seed. Absence is not evidence that the PR was useless.
7. Novelty is real only for BRITTLE/enabler search and the cross-commit verdict. rspec --bisect can't find enablers (B11:150), but
   other tools might (e.g. hand ddmin scripts). No prior-art search done yet: UNPROVEN as a market claim.
8. axn has 3 stars: a method proof, not adoption pull.
