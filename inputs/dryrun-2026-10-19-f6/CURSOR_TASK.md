# CURSOR TASK: fastlane#30184 F6, polluter-named RSpec certificate
Goal: run the 60 runs in SPEC-fastlane-F6.md and record the certificate verdicts. RSpec only: no pytest, no pytest-randomly.
1. `cd inputs/dryrun-2026-10-19-f6 && sha256sum -c SHA256SUMS` must be all OK. Do not edit this folder.
2. In an empty dir run `bash reverse/recon.sh > recon-replay.log`; its sha256 lines must equal reverse/recon.log lines 2-4.
3. Use the fastlane checkouts at 76eeb3f9352a657fd979ae00e89e49a388729e30 and 148c1c9b4c041b1659ea633f2632dd47eef8cb04 in the F4 env
   (ruby:3.1, Bundler 2.6.9). Log `ruby -v`, `bundle -v`, `git rev-parse HEAD` per commit.
4. Run C1-C4, R1-R4, N1, NR1 at both commits, 3 reps each (60 runs), with the exact args in the spec table.
   Save each to rspec/<id>-<sha7>-r<k>.log (full doc output + exit code).
5. Write q6.log: all commands and outputs, then a table `id | sha7 | r1/r2/r3 | first error class + message line | polluter-before-victim y/n`,
   then per pair CERTIFIED y/n, CONTROL_VALID y/n, CERTIFIED_COUNT n, GO True/False, rep_disagreements n.
6. Add SHA256SUMS under evidence/dryrun-2026-10-19-f6/ on a new branch feat/dryrun-2026-10-19-f6 from flakecert main a75858b; open a
   draft PR. Acceptance: SHA256SUMS -c all OK, 60 run logs present, q6.log ends with the counts above.
If a step loops more than twice, stop and report what you have.
