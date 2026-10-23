CURSOR TASK: FlakeCert pytest Attempt-to-Fix runner (inputs frozen on hark-inputs-2026-10-18)

Goal
Add `make pytest-attempt-to-fix`. It writes `audit/pytest-attempt-to-fix.json`, which passes
`inputs/rea-brief-pytest-attempt-to-fix/gate_pytest_attempt_to_fix.py --results`. The run must show:
- 20 plain reruns pass both the wrong fix and the real fix.
- FlakeCert's certificate replay fails the wrong fix and passes the real fix.

Repo: realmpastai-web/flakecert, branch feat/pytest-attempt-to-fix off main d713ced.

Inputs
Copy these from hark-inputs-2026-10-18 at the freeze commit, unchanged:
- inputs/rea-brief-pytest-attempt-to-fix/
- inputs/rea-datadog-test-optimization/ (re-frozen: exact one-sided 0.1391 replaces the Wilson line in BRIEF.md and check_dd_gap.py)

Then check the copy: `git diff --quiet <freeze> -- <both dirs>`.

Build
1. Image: build from `inputs/rea-brief-pytest-attempt-to-fix/pins/Dockerfile` as is. It uses the pinned python@sha256:0a310eee… base and installs the lock with --require-hashes.
   - Do NOT install pytest-randomly or pytest-rerunfailures. They are reversed statically only, and running them needs Santhosh's approval.
   - Record `python -V`, `pip freeze` and the built image digest.
2. Certificate: run FlakeCert's existing pytest search on the prefix sample (`sample/`) for the victim `tests/test_cart.py::test_total_without_discount`. Use the sources order, seed and pythonhashseed (tmpdir and time_offset are allowed too). Store the certificate as written by flakecert/cert.py under `cert`.
3. Variants: for prefix, wrong_fix and real_fix, copy `sample/` to a fresh dir and replace `tests/test_cart.py` with `fixes/test_cart.<variant>.py`. Record that file's sha256 plus the sha256 of every other sample file (keys relative to `sample/`).
4. Arms per variant, each run as a fresh `python -m pytest -p no:cacheprovider` process in the container. Read victim and polluter status from junitxml.
   - **plain_retry:** 20 runs with no args (defined file order), unseeded.
   - **cert_replay:** 3 runs of the certificate's replay through FlakeCert's existing replay path. Record victim, polluter, exc, message and sig, using flakecert.cert.exception_type and failure_signature on the victim's traceback; use null when it passes.
   - **sweep:** seeds 0..99. Pass the node ids in exactly the order listed in `expected/predicted-sweep.json` → orders[seed]. Record victim and polluter.
5. Write the results file in the shape documented at the top of the gate, plus `pytest`, `python`, `base_image`, `image_digest` and `pip_freeze`. Do not edit the gate, the predictions or the controls.

Acceptance (paste every tail; commit full logs under evidence/pytest-attempt-to-fix/ as p1..p6.txt, each with its command and exit=)
- A1 cd inputs/rea-brief-pytest-attempt-to-fix && sha256sum -c SHA256SUMS && python3 -B gate_pytest_attempt_to_fix.py | diff - gate-output.txt && cd - && bash inputs/rea-brief-pytest-attempt-to-fix/run_controls.sh | diff - inputs/rea-brief-pytest-attempt-to-fix/controls-output.txt
- A2 make pytest-attempt-to-fix   (full runner log, all 3 variants x 3 arms)
- A3 python3 -B inputs/rea-brief-pytest-attempt-to-fix/gate_pytest_attempt_to_fix.py --results audit/pytest-attempt-to-fix.json   → expected tail in BRIEF.md §6, GATE PASS exit=0
- A4 the jq line in BRIEF.md §6 → true
- A5 the 7-mutant loop in BRIEF.md §6 → exit 0
- A6 make unit && make verify OFFLINE=1 → all gates true; CI verify green

If A3 fails on real output, stop. Commit the results file and the failing tags as a no-go; do not tune anything to pass.
