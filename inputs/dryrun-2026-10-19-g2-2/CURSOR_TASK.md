# CURSOR TASK: FlakeCert G2.2, residual seeds + cause sets (second polluter) on teamshares/axn#235
Rules:
- REA clean-room. Execute axn only in Docker ruby:3.3 with the G2 image digest. No pytest-randomly, no macOS.
- Evidence rule: no count goes in a log or PR unless the file, log or command output behind it is there.
- No victim, polluter, seed or mechanism names in tools/ or the invocation.
- Don't touch inputs/ and don't score the holdout. No merge.
1. `cd inputs/dryrun-2026-10-19-g2-2 && sha256sum -c SHA256SUMS` must be all OK. Re-run `bash reverse/recon-g2-2.sh` in an empty dir; its two sha256 lines must equal recon-g2-2.log lines 2-3.
2. Branch feat/certify-rspec-g2-2 from main 611e80f. Implement S6-S10 per SPEC-G2-2.md, stdlib Python only, reusing the G2.1 ordering hook, order guard and ddmin. Unit tests per acceptance 4.
3. Run on base 8daba1dcb4e1f44e2a26c87e2d602c10fc04eca9 / head 6c62d568e27844bf7500be0a54425b7c9c65a8cc.
   Check the tarball sha256 against inputs/dryrun-2026-10-19-g2/reverse/recon-axn.log, and take the s0 inputs from evidence/certify-rspec-g2/s0 unchanged.
4. Save to evidence/certify-rspec-g2-2/: run.log (commands, wall times, image digest), s6/residual-seeds.json, s7-s8 probe logs (every probe), s9 arm logs, updated certs with cause_set, replay-*.sh, replay-check.log (two runs), check-summary.md, summary.json, SHA256SUMS.
5. g2-2.log must end with these lines:
   RESIDUAL_SEEDS per victim
   per seed: SEED s ROUND k SET ids PROBES n STATUS
   NEW_POLLUTERS ids with labels
   G2_LABELS_UNCHANGED, EXIT_OK
   ACCEPTANCE_1..4, GO
   the acceptance-1 grep output
6. Draft PR. Report head sha + CI. If a step loops more than twice, stop and report what you have.
