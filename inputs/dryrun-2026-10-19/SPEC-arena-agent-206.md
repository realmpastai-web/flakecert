# Spec: IvanSkainet/arena-agent#206 (pytest, order leak). Clean-room, static only, nothing executed.

## Target (evidence: evidence/arena-agent-206/)
- Issue #206, open, 0 comments, opened 2026-08-30 04:38 IST by the owner (issue-206.json).
- Victim: `tests/test_mcp_client_parity_v4_169_39.py::test_client_start_happy_path`.
- Symptom (issue text): `AssertionError: assert ['/Users/runn..., '--version'] == ['node', 'server.js']`, macOS py3.12 CI cell of PR #205;
  every Linux and Windows CI cell passed the same commit.
- Suspected polluter (issue text): `tests/e2e/test_bridge_live.py`.

## Pinned commits
- Primary, issue-era: `eb925fa3f31eac8e70202debf565f1b32219e62d` = PR #205 base = master at 2026-08-30 03:08 IST.
  codeload tarball sha256 e1cd6340... (eb925fa/TARBALL.sha256).
- Secondary, HEAD of master on 2026-10-19: `aec7800d34c43eb6add78b895729c833ae4f4e0a`, tarball sha256 16af6328... (aec7800/TARBALL.sha256).
- Observed (diff of the copied files): target test, `arena/mcp_client/client.py` and `tests/e2e/test_bridge_live.py` are
  byte-identical at both commits. `tests/conftest.py` is absent at eb925fa and 793 lines at aec7800 (network guard, ARENA_* leak guard).

## Static observations (file:line at eb925fa)
- O1 target test patches via `monkeypatch.setattr(mcp_mod.subprocess, "Popen", _fake_popen)` (test file :157), so the issue's
  "patch outside monkeypatch" guess does not hold for the victim itself.
- O2 `mcp_mod.subprocess` is the stdlib module (client.py imports subprocess), so the patch is process-global.
- O3 `_fake_popen` stores `captured_popen["args"] = args`, overwritten on every call (:152-155): the LAST Popen in the window wins.
- O4 `subprocess.run` builds on module-level `Popen`, so a concurrent `subprocess.run([...,'--version'])` would be recorded.
- O5 The e2e `bridge` fixture is module-scoped and spawns the bridge as a child process (test_bridge_live.py:124); the child's
  own Popen calls cannot reach the parent's patch. Which in-process caller issues `--version` is **UNPROVEN**.
- O6 pyproject addopts carry `--cov=arena ... --cov-fail-under=46`; a single-test run will fail the coverage floor. Runs must add
  `--no-cov` (or `-p no:cov`) so the exit code reflects the test, and must read the per-test outcome from junitxml.
- O7 CI lock pins pytest-randomly 4.1.0; runs here use `-p no:randomly` only (pytest-randomly runs need Santhosh's yes).

## Exact runs (forced order only; in the pinned image; each with `-p no:randomly --no-cov --junitxml=...`)
- A0 victim alone: `pytest -p no:randomly tests/test_mcp_client_parity_v4_169_39.py::test_client_start_happy_path` (issue: passes)
- A1 forced order: `pytest -p no:randomly tests/e2e/test_bridge_live.py tests/test_mcp_client_parity_v4_169_39.py::test_client_start_happy_path` (issue: fails on Windows)
- A2 reverse: victim first, then `tests/e2e/test_bridge_live.py` (control; expect victim passes)
- S1 sabotage: `controls/test_000_sabotage_popen_thread.py` copied into tests/, then the victim, 20 reps.
Each of A0-A2 at eb925fa and aec7800, 3 reps. The issue's `--randomly-seed=1/2/3` rows are NOT run.

## Holdout
Predictions H1-H4 sealed by sha256 in HOLDOUT.sha256 before any run; scored once against the q-logs, never revised.
