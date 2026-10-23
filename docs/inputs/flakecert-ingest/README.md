# flakecert-ingest (Hark, frozen 2026-10-18)
**Question:** how would a Buildkite, CircleCI or GitLab user feed FlakeCert? The answer is in FIELD_MAP.md.
- **sample-src/:** sample tests, each with pass, deterministic fail, seeded flaky and skip. Go's seeded test fails at SEED=2, pytest's and jest's at SEED=1. The tests live in a sample git repo at commit f711ef3b9426b92e2e73691439bf6d4dbaa6e341.
- **samples/:** real local outputs, with each run's output in *.log and the versions in tools.log. collector-run-env.json is RunEnvBuilder(vars).build() for Buildkite, CircleCI and GitLab variable dicts, run in-process with no token, so nothing was uploaded (api.py: submit returns when no token).
- **collector-src/:** unmodified files from buildkite_test_collector-1.9.0 wheel sha256 e2c5013b414b8a4ee0475e92ad563903b1aea99b8962fc6c7bce55e36097856d, which matches PyPI (WHEEL.txt).
- **Gate:** `python3 gate_flakecert_ingest.py` reads only this folder (exit 0, output == gate-output.txt).
- **Optional check:** `PYTHONPATH=<flakecert@ef1f8aa> python3 existing_sig_check.py` (existing-sig-check.log).
- **Next build:** CURSOR_TASK_flakecert-junit-ingest.md, to start only once flakecert#1 CI is green.
