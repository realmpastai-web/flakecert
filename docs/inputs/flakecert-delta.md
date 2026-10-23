FLAKECERT DELTA (Hark, 2026-10-17, apply before starting)

AUTHORITATIVE SPEC
Use CURSOR_TASK_flakecert-poc.md (sha256 1bca7a57d93be709de5d764d93e17d874b37fb48f949f558d2740e84c2537fae) only. Ignore CURSOR_TASK_flakecert.md and CURSOR_TASK_flakecert-v0.2.md, which overlap it and use different verify lettering.

INPUTS: CONFIRMED, NO CHANGE
- frozen-set.csv a788832159f871780197e2cf9736904546ac0fdf36cad1e6b378837719b8a812: 20 main + 12 reserves (F21-F32).
- IDoFT py-data.csv @ 4903dc9233eead4e4191c66f9ed0b14eea091052: sha256 a1cf7425cd23096ae653af275fbba6c82d7d72ce5e17bb3db754e46e0e4c3c32 (Hark re-fetched it). All 32 frozen rows match a py-data row on project, sha and pytest id, with identical Category and Status.
- Swaps, final:
  S01 F18 (main, NIO) out: online_test.py line 49 pygsheets.authorize(service_account_file=...), which needs a live Google credential and network. F21 (first reserve, NOD) promoted. Evidence snap-F18-online_test.py a88e764f73efd618b9a2e81ccf3dd2eb544e6f888ae86e16751864b500ee0c62.
  S02 F31 (reserve, NIO) retired: needs live HDFS (localhost:50070) and MySQL. Evidence snap-F31-test_plugin_mysql_hdfs.py 005f62cc52843cd82857ddee5fd9f8c77d3a85141a126d719fe111fe3d935659.
- Effective set: main F01-F17, F19, F20, F21; reserves F22-F30, F32. Main by category: NOD 11 (F01-F10, F21), OD-Vic 6 (F11-F16), NIO 3 (F17, F19, F20).
- No other test meets the swap rule on a static read. Checked: F02 HttpClient('localhost') catches requests ConnectionError/Timeout and returns an empty response (butter/mas/packets/packet_http.py lines 31-41), so no live server is needed. F19 replays tests/vcr_cassettes/test_user_password_succeeds.yaml, which is present at aead83c, so no network is needed. Builds are unproven until make envs runs; swap only on the rule's own triggers.

CORRECTIONS TO THE TASK
1. Python version (the big one). Replace "Python 3.11, fall back to 3.8/3.9 only when python_requires demands it" with an interpreter ladder: 3.11, then 3.9, 3.8, 3.7. Use the newest interpreter on which the repo's own pinned requirements install AND pytest collects the node id. Log each rung to envs/<id>.install.log. One full ladder = one install attempt, so the 2-attempt swap rule means the whole ladder failed twice.
   Why: no python_requires excludes 3.11, but these pins can't run on it. pytest added Python 3.10 support only in 6.2.5 (changelog: "Python 3.10 is now supported."). F04 pins pytest==5.4.3 and numpy==1.19.0 (wheels cp36-cp38). F06 pins pytest==4.0.1. F07 pins numpy==1.16.1 and scipy==1.2.0 (wheels up to cp37) and pytest==3.7.1. F09 pins pytest==3.1.3, F13 pytest==3.4.2, F14 pytest==5.3.5, F21 pytest==3.2.1. Reserves: F26 pytest==6.0.1, F30 cryptography==2.4.1.
2. Harness and old pytest. Use the repo's pinned pytest, not ours, and keep flakecert working back to pytest 3.1. Do the controls outside pytest plugins: order by passing node ids explicitly on the command line; seeds, PYTHONHASHSEED, time offset and tmpdir via env plus a sitecustomize.py on PYTHONPATH. No dependency on pytest-randomly or new hook APIs.
3. Network off with loopback up. Build images online; run tests offline in a fresh netns with `ip link set lo up`. `unshare -n` leaves lo down, and F02 and F03 (tornado on 127.0.0.1) need loopback. Gate wording: offline_run = "image builds online, test runs with no external network".
4. Install sources. "requirements*.txt" misses real test deps. Install the package (pip install -e . or setup.py), plus every root *requirements*.txt except docs/release/tunnel variants, plus tests/requirements.txt. For a Pipfile with no requirements file, use `pipenv requirements --dev`. Log the files used per test. Examples from deps-preflight.log: F17 has only tests/requirements.txt and dev-requirements.txt, F27 dev-requirements.txt, F30 test_requirements.txt, F25 test-requirements.txt, F20 and F32 Pipfile only.
5. Paths. Use evidence/flakecert/ everywhere (the EVIDENCE FILES list says evidence/resolve-check.log; make it evidence/flakecert/resolve-check.log and the same for deps-preflight.log and effective-set.txt). swaps.csv evidence_file holds bare names; resolve them under evidence/flakecert/.
6. Re-running resolve-check and deps-preflight in make verify. These hit api.github.com and their logs contain a timestamp and a Python DeprecationWarning line. Compare normalised result lines only (id, role, repo, sha10, path, HTTP status; the manifests and req-files lists) plus "RESOLVED 31/32". Use GITHUB_TOKEN in CI and allow --offline to skip with a logged SKIP, never a silent pass.
7. Baseline definition (needed for the denominator). One baseline run = `pytest <target's test file>` in default order, recording the target node's outcome, 100 times. For OD-Vic (F11-F16) also log that a victim run alone is expected to be stable. The order knob may then search across the whole configured suite within the 500 budget, with its scope recorded in the cert.
8. Nothing else changes: gates, certificate schema, Fraction bounds, blind comparator, no upstream contact, no spend.

REPRODUCE HARK'S CHECKS
curl -sL https://raw.githubusercontent.com/TestingResearchIllinois/idoft/4903dc9233eead4e4191c66f9ed0b14eea091052/py-data.csv | sha256sum
curl -sL https://raw.githubusercontent.com/ljvmiranda921/pyswarms/08756526f39699eef28e515cac2ead17cef55710/requirements-dev.txt | grep -E '^(numpy|scipy|pytest)=='
curl -sL https://pypi.org/pypi/numpy/1.16.1/json | python3 -c "import json,sys;print(sorted({u['python_version'] for u in json.load(sys.stdin)['urls']}))"
