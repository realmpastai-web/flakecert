# CURSOR TASK: FlakeCert public dry run 2026-10-19 (arena-agent#206 first, then fastlane#30184)

Verify first: `cd inputs/dryrun-2026-10-19 && sha256sum -c SHA256SUMS` (all OK), then for each pinned arena commit download
the codeload tarball and check it against evidence/arena-agent-206/<sha7>/TARBALL.sha256.

Part 1, arena-agent#206 (pytest, Linux, python:3.11 image; install `requirements-ci.lock` with --require-hashes as pinned;
leave pytest-randomly installed and pass `-p no:randomly` on every command):
- Runs A0, A1, A2 x 3 reps at eb925fa and aec7800, and S1 x 20 at eb925fa, exactly as in SPEC-arena-agent-206.md, each with
  `-p no:randomly --no-cov --junitxml=<run>.xml`. Never pass --randomly-seed. Log `pip freeze`, `python -V`, `uname -a`.
- Record per run: victim outcome from junitxml, the assertion line if failed, and whether any e2e test errored at setup.
- If A1 does not reproduce on Linux, stop Part 1 there (do not tune). Optional only with Santhosh's yes: macos-latest py3.12.
Part 2, fastlane#30184: F1, F2, F3 as in SPEC-fastlane-30184.md. Log `ruby -v`, `bundle -v`, and the `has leaked into
another example` count per run (grep -c on the rspec output).
Deliver: logs q0..q3 under evidence/dryrun-2026-10-19/ on a branch with SHA256SUMS. Do not edit inputs/dryrun-2026-10-19.
Hark then reveals predictions.json (must hash to HOLDOUT.sha256) and scores H1-H7 once.
If any step loops more than twice, stop and report what blocked it.
