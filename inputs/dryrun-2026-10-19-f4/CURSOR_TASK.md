# CURSOR TASK: fastlane#30184 F4/F5 (order-dependence split)
Verify `cd inputs/dryrun-2026-10-19-f4 && sha256sum -c SHA256SUMS`. Run F4 and F5 exactly as in SPEC-fastlane-F4.md
(93 isolated runs + 1 seeded suite run). Deliver q4.log (commands + outputs), rspec/F4-<n>-r<k>.log, rspec/F5.log, a table
id | alone r1-r3 | first error class | ORDER-DEPENDENT y/n | F5 outcome, and SHA256SUMS, under evidence/dryrun-2026-10-19-f4/
on feat/dryrun-2026-10-19 (PR #8). No pytest and no pytest-randomly in this task. If a step loops more than twice, stop and report.
