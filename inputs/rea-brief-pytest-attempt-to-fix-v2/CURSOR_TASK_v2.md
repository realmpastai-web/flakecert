# CURSOR TASK: pytest Attempt-to-Fix rerun against gate v2 (PR #7 branch)

Goal: rerun the pytest Attempt-to-Fix runner on PR #7 (feat/pytest-attempt-to-fix, head 3ec5eb8) with one additive
change, tb_norm, and judge the results with gate v2. Nothing else changes.

Frozen inputs (do not edit; verify first):
- inputs/rea-brief-pytest-attempt-to-fix/ (v1 @ 2560b40): `cd inputs/rea-brief-pytest-attempt-to-fix && sha256sum -c SHA256SUMS` -> 41 OK
- inputs/rea-brief-pytest-attempt-to-fix-v2/ (this folder): `sha256sum -c SHA256SUMS` -> all OK
- `git diff --quiet 2560b40 HEAD -- inputs/rea-brief-pytest-attempt-to-fix` exit 0

Code change (additive only):
1. flakecert/cert.py build_certificate: expected_failure gains "tb_norm": normalize_traceback(tb) (the exact text
   failure_signature hashes). failure_signature, normalize_traceback and "sig" stay byte-identical.
2. flakecert/runners/pytest_attempt_to_fix.py: each failed cert_replay row gains "tb_norm": normalize_traceback(tb);
   passed rows get "tb_norm": null. The results "cert" block carries the certificate's expected_failure.tb_norm.
3. No other edits: no change to the gate, predictions, controls, sample, pins, schedule or replay count.

Acceptance:
- B1 existing test suite passes (`python3 -m pytest -q` exit 0); existing certificates' sig values are unchanged.
- B2 controls: `inputs/rea-brief-pytest-attempt-to-fix-v2/run_controls_v2.sh` from / prints CONTROLS OK, exit 0, and
  its output diff against controls-output-v2.txt is empty.
- B3 rerun in the pinned Python 3.11 image, then
  `python3 -B inputs/rea-brief-pytest-attempt-to-fix-v2/gate_pytest_attempt_to_fix_v2.py --results audit/pytest-attempt-to-fix.json`
  must end with:
    INFO certified={'prefix': 'NOT_FIXED', 'wrong_fix': 'NOT_FIXED', 'real_fix': 'FIXED'} plain_retry={'prefix': 'FIXED', 'wrong_fix': 'FIXED', 'real_fix': 'FIXED'}
    GATE PASS
  and show `PASS wrong_fix.same_failure_modulo_line shift=1 lines [6]->[7]`.
- B4 commit full logs (q0..q4) under evidence/pytest-attempt-to-fix-v2/. If B3 fails, commit the logs as NO-GO with the
  failing tags; do not tune anything.
