# CURSOR TASK: FlakeCert G2 (seed discovery + BRITTLE/enabler) on teamshares/axn#235
No pytest-randomly, no macOS. Execute axn only inside Docker ruby:3.3 (record image digest). Hark has not run axn.
1. `cd inputs/dryrun-2026-10-19-g2 && sha256sum -c SHA256SUMS` all OK; do not edit the folder. Replay `bash reverse/recon-axn.sh` in an
   empty dir; its four sha256 lines must equal recon-axn.log lines 2-5.
2. Branch feat/certify-rspec-g2 from flakecert main 9b9cfec. Step 1 = S-1 exit rule fix; `python -m tools.certify_rspec rejudge
   evidence/certify-rspec-g1` must give exit_ok True, labels unchanged. Commit that alone first.
3. Implement S0-S5 per SPEC-certify-rspec-G2.md, stdlib Python only, no victim, polluter or seed input. Unit tests as in acceptance 4.
4. Run on base 8daba1dcb4e1f44e2a26c87e2d602c10fc04eca9 / head 6c62d568e27844bf7500be0a54425b7c9c65a8cc
   (codeload tarballs; check sha256 vs recon-axn.log). Save under evidence/certify-rspec-g2/: run.log (commands, wall times, versions,
   image digest), s0/seeds.json + s0 logs, s1-s4 logs, enabler probes, cert-*.json, replay-*.sh, replay-check.log, check-summary.md,
   summary.json, SHA256SUMS.
5. g2.log must end with: SEEDS_SEARCHED, SEEDS_FAILING_BASE, SEEDS_FAILING_HEAD, PRIMARY_SEED, UNION n, OD n, BRITTLE n, CERTIFIED ids,
   BRITTLE_CERTIFIED ids, REJECTED ids, ACCEPTANCE_1..4, GO, and the acceptance-1 grep output.
6. Draft PR. If a step loops more than twice, stop and report what you have.
