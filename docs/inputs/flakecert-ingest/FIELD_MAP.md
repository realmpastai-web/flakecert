# Field map: what existing test output gives a FlakeCert certificate (frozen 2026-10-18)
These are real outputs generated locally (samples/; versions in samples/tools.log): pytest 8.3.4 --junitxml, jest 29.7.0 + jest-junit 16.0.0, gotestsum v1.13.0 (Go 1.27.2), and the buildkite-test-collector 1.9.0 pytest plugin with --json. Every row below is asserted by gate_flakecert_ingest.py G2 against the samples.

| Cert field (spec step 6) | pytest JUnit | jest-junit | gotestsum JUnit | BK collector --json | Where FlakeCert must get it |
|---|---|---|---|---|---|
| test identity (pytest_id/node_id) | classname+name | file+name (leading space, suite "undefined") | classname(pkg)+name | scope+name (id is uuid4 per run, not stable) | derive key from report; map to node_id |
| file | missing | `file` attr (with JEST_JUNIT_ADD_FILE_ATTRIBUTE) | missing | file_name | report or discovery |
| line | missing | missing | missing | location `file:line` | optional |
| outcome | failure/skipped | failure/skipped | failure/skipped | result | report |
| failure text (→ exc, sig) | failure message+text | failure text (absolute paths) | failure text (`=== RUN` frames) | failure_reason+failure_expanded | report → FlakeCert `failure_signature` |
| duration | time | time | time | history.duration | report |
| **sha** | missing | missing | missing | missing in --json; upload payload run_env.commit_sha on Buildkite/CircleCI only | CI variables (BUILDKITE_COMMIT / CIRCLE_SHA1 / CI_COMMIT_SHA) or `git rev-parse` |
| **seed** | missing | missing | missing | missing | FlakeCert schedule (it sets the seed) |
| **image_digest** | missing | missing | missing | missing | FlakeCert image build (`docker inspect`) |
| **pip_freeze_sha / dep lock** | missing | missing | missing | missing | FlakeCert (pip freeze / lockfile hash) |
| **sig** | missing (derivable) | missing (derivable) | missing (derivable) | missing (derivable) | `flakecert.cert.failure_signature(text)` |
| toolchain version | missing | missing | property go.version | missing in --json (run_env.version/language_version in upload) | runtime |
| m, k, d, schedule, bound | n/a | n/a | n/a | n/a | FlakeCert only |

**What the gate shows (G1, G3, G4):**
- **G1:** every format records the same-commit flip. The seeded test fails at the fail seed (and on its rerun) and passes at the pass seed. So any of the four can nominate a candidate.
- **G3:**
  - Across same-seed reruns, the raw failure text of the flaky failure changes in pytest and the collector (CPython 0x addresses). It doesn't change in jest or gotestsum.
  - With normalization, the sig is stable in all 4 formats.
  - FlakeCert's existing failure_signature @ef1f8aa is also stable in all 4 (existing-sig-check.log).
  - pytest JUnit and the collector produce the same sig.
- **G4 collector:**
  - `--json` writes `data` only. `run_env` (the commit sha) exists only in the upload to Buildkite.
  - run_env.py detects Buildkite, GitHub Actions and CircleCI. With GitLab variables it falls back to `CI=generic` with no commit_sha.

**Adoption answer:** a Buildkite, CircleCI or GitLab user can feed FlakeCert the JUnit XML they already produce. That gives candidates (test identity, same-commit flip, failure text and so the sig). None of the reports carries seed, image_digest or pip_freeze_sha, so those always come from FlakeCert's own controlled reruns. The sha comes from CI variables or git, never from the report.

**UNPROVEN:**
- Other reporters (Maven surefire, RSpec, PHPUnit, nextest).
- Buildkite JS/Go/Ruby collectors.
- The server-side shape of Buildkite, CircleCI and GitLab uploads.
- Absolute-path normalization across machines: the jest paths are identical here only because both runs used the same directory.
- Go `(0.00s)` durations happen to match. FlakeCert's normalizer only strips "N.NN seconds".
