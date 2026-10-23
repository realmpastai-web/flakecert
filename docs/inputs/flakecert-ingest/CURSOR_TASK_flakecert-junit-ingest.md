# CURSOR TASK: flakecert-junit-ingest (start only after flakecert#1 CI is green)
**Evidence rule:** a number counts only with the file, log or command output that produced it. Inputs are frozen at clawscore-fleet `inputs/flakecert-ingest/` (see SHA256SUMS). Don't change any frozen file. Copy what you need into the flakecert repo under `docs/inputs/flakecert-ingest/`, together with its SHA256SUMS.

## Goal
Add `flakecert ingest` so a user's existing CI test reports nominate candidate flaky tests for FlakeCert's controlled reruns. A report is only a nomination. A certificate still requires FlakeCert's own run (sha, seed, image_digest, pip_freeze_sha, schedule, bound) and a 3/3 replay with the same sig.

## Repo and files
- **Repo:** realmpastai-web/flakecert, branched from main after flakecert#1 merges.
- **New:**
  - `flakecert/ingest.py`
  - `tools/ingest.py`
  - `tests/test_ingest.py`
  - `docs/inputs/flakecert-ingest/` (copied samples + SHA256SUMS)
  - a `make ingest` target
- **Touch only as needed:** `flakecert/cert.py` normalize_traceback, as additive rules (see step 4).

## Steps
1. **Parsers**, stdlib only (xml.etree, json):
   - JUnit XML for pytest, jest-junit and gotestsum.
   - The Buildkite collector `--json` list.
   - Output one row per testcase: {format, key, file?, line?, outcome, failure_text?, duration}.
2. **Keys:**
   - pytest: `classname::name`
   - jest: `file::name.strip()`, and ignore suite name "undefined"
   - gotestsum: `classname/name`
   - collector: `scope::name`; never `id`, which is a uuid4 per run
3. **Nomination:** a key is a candidate when the same sha has ≥1 failed and ≥1 passed row. The sha comes from the `--sha` flag, else CI variables in this order: BUILDKITE_COMMIT, CIRCLE_SHA1, CI_COMMIT_SHA, GITHUB_SHA, else `git rev-parse HEAD`. Never take it from the report.
   - Write `ingest/candidates.json` with {key, sha, sha_source, n_pass, n_fail, sig_of_failures[], reports[]: file sha256}.
4. **Sig:** use the existing `flakecert.cert.failure_signature`. Add rules additively for:
   - (a) absolute repo-root prefixes: pass `--repo-root` and strip it;
   - (b) Go `(N.NNs)` durations.
   The existing sigs of the frozen pytest certs must stay byte-identical: re-run verify's sig check.
5. **No invented fields:** candidates.json must not contain seed, image_digest, pip_freeze_sha or bound. Those are written only by the existing cert path.
6. **Docs:** add a README "Feeding FlakeCert from Buildkite/CircleCI/GitLab" section. It shows only commands and real outputs from `make ingest`.

## Acceptance (all from a fresh clone; non-zero exit on any miss)
- **A1.** `sha256sum -c docs/inputs/flakecert-ingest/SHA256SUMS` passes.
- **A2.** `make ingest` on the frozen samples, with `--sha f711ef3b9426b92e2e73691439bf6d4dbaa6e341`, nominates exactly 4 candidates, one per format:
  - `test_sample::test_flaky_seeded`
  - `sample.test.js::flaky seeded`
  - `example.com/flakecertsample/TestFlakySeeded`
  - `test_sample.py::test_flaky_seeded`
  Deterministic-fail tests must not be nominated, because they fail in every run.
- **A3.** For each format, the sig of the flaky failure is equal across the fail-seed file and its `-rerun` file. It differs from the deterministic-fail sig.
- **A4.** The pytest JUnit sig equals the collector JSON sig for the same test (frozen evidence: e65f2d82… with the normalizer at ef1f8aa, existing-sig-check.log). If the normalizer change alters it, record the new value in the PR from the command output.
- **A5.**
  - A jest report with its paths rewritten from `/tmp/ing/proj` to `/home/ci/build`, run with `--repo-root`, gives the same sig as the original.
  - A gotestsum failure with `(0.00s)` changed to `(0.37s)` gives the same sig.
  - Add both as unit tests.
- **A6.** No CI variables and no `--sha`: falls back to git and records `sha_source: git`. With only CI_COMMIT_SHA set (GitLab-style), it records `sha_source: CI_COMMIT_SHA`.
- **A7.** `grep -E '"(seed|image_digest|pip_freeze_sha|bound)"' ingest/candidates.json` finds nothing.
- **A8.** `make unit` and `make verify OFFLINE=1` still pass. Existing cert sigs are unchanged, as shown by the diff of evidence/verify-report.json sig fields.
- **A9.** The PR body shows the outputs of A2–A8 verbatim, plus the commit sha. Mark anything not run as UNPROVEN.

## Out of scope
- Uploading anywhere.
- Buildkite, CircleCI or GitLab APIs and tokens.
- Non-JUnit reporters.
- Claiming certification from reports alone.
