# Skeptic pass (before any run)
1. GitLab is a proving ground for the method. GitLab builds its own tooling (scripts/rspec_check_order_dependence, rspec_order.rb) and runs AI agents on the backlog.
   Expect contributions to be accepted.
2. G-c rests on #601849's definition only. None of the 10 named Category A files cites a missing constant (T6). It may find 0 BRITTLE (Q3 predicts at most 1).
3. 153 FOSS removals in about 4.5 months (T1/T2), plus no issue update since 2026-06-17 (T4), could mean the effort stalled. It could also mean it moved elsewhere (MRs not linked here). Issue notes are UNKNOWN (401).
4. GDK is heavy (Postgres, Redis, Gitaly, Vite). Category A "Vite not running" failures may be harness noise in our run too.
5. A 30-seed bound (9.50%) is still weak. The headline must never round it to "not flaky".
6. S20 is limited to models/lib for cost, so it is not representative of request or feature specs.
7. This note records pain signals only. This run tests no commercial claim.
