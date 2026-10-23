# rea-brief-pytest-attempt-to-fix: reverse first, then certify pytest Attempt-to-Fix (Hark, 2026-10-18, internal)

This brief carries FlakeCert's certified Attempt-to-Fix (RSpec, PR #6, main d713ced) to pytest. It starts from a static read of the two pytest plugins most Python CI uses for flaky tests.

## 1. Reversed artifacts (legal, public, shipped; read as bytes, never executed or installed)
| sdist | sha256 | license | source |
|---|---|---|---|
| pytest_rerunfailures-16.7.tar.gz | 6956ddfb65ca1d07e7e3d99e2c5359d82300f4cb062e6049563bd2c106f72d5c | MPL-2.0 | files.pythonhosted.org via PyPI JSON |
| pytest_randomly-5.0.0.tar.gz | e9c575a5873ef168ddbe340ed9e97ce9edb4492ccc821e4b2ac6bb1f0ed515d2 | MIT | files.pythonhosted.org via PyPI JSON |

The PyPI JSON and pypistats snapshots are in `rea/` (URLs in `rea/URLS.tsv`, fetched 2026-10-18). Recent downloads last month: 37,633,838 for rerunfailures and 14,182,476 for randomly. These are downloads, not user counts.

## 2. Observations (gate tags in brackets; all from the pinned sdists)
- **rerunfailures 16.7** reruns a test only after a failed phase, while `item.execution_count <= reruns` [rea.rerunfailures.rerun_condition].
  - It re-enters `runtestprotocol(item, nextitem=nextitem)` in a `while` loop: same item, same process, straight after the failure [rea.rerunfailures.same_item_same_process_loop].
  - Its module has 0 matches for seed, random or shuffle [rea.rerunfailures.no_seed_random_shuffle].
  - It has 0 matches for certif, replay or sha256 [rea.rerunfailures.no_cert_replay_sha256]. Its only hashlib use is a 10-character sha1 key for xdist crash items in StatusDB [rea.rerunfailures.hashlib_only_xdist_crash_key].
- **randomly 5.0.0** draws one session seed and caches it for `--randomly-seed=last` [rea.randomly.session_seed_cached].
  - It reseeds `random` per test phase with a `crc32(nodeid)` offset [rea.randomly.reseed_random_seed, rea.randomly.per_phase_crc32_nodeid].
  - It orders items by `crc32("{seed}::{nodeid}")` [rea.randomly.order_key_crc32_seed_nodeid].
  - It reports `Using --randomly-seed={seed}` [rea.randomly.header_seed_only].
  - It has 0 matches for certif, replay, sha256, hashlib or signature [rea.randomly.no_cert_replay_hash].

## 3. Inference (to be tested by this brief's run, UNPROVEN until then)
- **rerunfailures:** a retry gives a pass count. It does not record the schedule that produced a failure.
- **randomly:** the seed can rebuild a session's order for the same collected set and the same plugin version. Within the pinned sdist, nothing records a per-test failing schedule, an environment identity, a failure signature or an interval.
- **Neither:** without a schedule, a fix that only moves the leak cannot be separated from a fix that removes it.
- **Sample setup:** the FlakeCert sample has an order-dependent victim. The Attempt-to-Fix arm is 20 plain reruns in defined order (Datadog's documented count, `rea-datadog-test-optimization` docs.attempt_to_fix_20).
- **Prediction:** those 20 plain reruns pass both the wrong fix and the real fix. A FlakeCert certificate replay fails the wrong fix 3/3 and passes the real fix 3/3.

**Not claimed:**
- Any statement about other versions of either plugin, about plugins layered on them, or about Datadog, Trunk or other vendor products.
- Any failure rate from 3 replays.
- Any result from running either plugin: they are not installed, and running them needs Santhosh's explicit approval.
- On the 20/20 plain passes: they still allow a failure rate up to 13.9% (exact one-sided 95% bound, 1 - 0.05^(1/20) = 0.1391). That bound describes the plain retries, not FlakeCert. The two-sided Wilson figure is not used.

## 4. Reader (hypothesis, not evidenced)
The Python CI or platform lead whose pipelines already lean on reruns for flaky tests. Naming companies needs a further REA step: public CI configs that pin `--reruns`.

## 5. Sample and arms
- **`sample/`:** `app/cart.py` keeps a module global `DEFAULT_DISCOUNT`.
  - Victim: `tests/test_cart.py::test_total_without_discount`.
  - Polluter: `tests/test_cart.py::test_total_with_discount` (sets the global to 10 and never resets it).
  - RNG noise: `tests/test_coupon.py`. Stable: `tests/test_stable.py`.
- **`fixes/`:** three variants of `tests/test_cart.py`, made by insertions only.
  - `wrong_fix` adds a module-level reset at import. Collection precedes every test, so the polluter still leaks.
  - `real_fix` adds an autouse fixture that resets the global after every test.
  - `app/` is untouched.
- **Arms per variant:**
  - plain_retry: 20 runs in defined order.
  - cert_replay: 3 replays of FlakeCert's certificate for the victim on prefix.
  - sweep: seeds 0..99, with order = `random.Random(seed).shuffle(sorted(ids))`, node ids passed explicitly.
  - The predicted fail seeds (53/100) are in `expected/predicted-sweep.json`, recomputed by the gate from the stdlib.
- **Pins:** `pins/Dockerfile` uses `python@sha256:0a310eee…` (3.11-slim-bookworm). `pins/requirements.lock` holds pytest 8.4.2 plus 4 deps, installed with `--require-hashes`, with neither reversed plugin.
- **Hark sandbox precheck (`precheck/`, Python 3.12.15, not the gate's evidence):** plain 3/3 pass for all variants. Replay [P,V] fails prefix and wrong_fix 3/3 with `assert 90 == 100` and passes real_fix 3/3. Sweep fail seeds equal the prediction (53, 53, 0).

## 6. Commands
```
A1 cd inputs/rea-brief-pytest-attempt-to-fix && sha256sum -c SHA256SUMS && python3 -B gate_pytest_attempt_to_fix.py | diff - gate-output.txt && cd - && bash inputs/rea-brief-pytest-attempt-to-fix/run_controls.sh | diff - inputs/rea-brief-pytest-attempt-to-fix/controls-output.txt
A2 make pytest-attempt-to-fix        # Cursor builds it; writes audit/pytest-attempt-to-fix.json (Docker run, team box)
A3 python3 -B inputs/rea-brief-pytest-attempt-to-fix/gate_pytest_attempt_to_fix.py --results audit/pytest-attempt-to-fix.json   # GATE PASS, exit 0
A4 jq -e '([range(20)|"passed"]) as $p | .variants.wrong_fix.plain_retry==$p and .variants.real_fix.plain_retry==$p' audit/pytest-attempt-to-fix.json
A5 for m in mutant-wrong-fix-accepted mutant-plain-retry-only mutant-schedule-drift mutant-real-fix-edits-app mutant-omitted-env-and-seed mutant-rerun-plugin-installed mutant-fabricated-sig; do ! python3 -B inputs/rea-brief-pytest-attempt-to-fix/gate_pytest_attempt_to_fix.py --results inputs/rea-brief-pytest-attempt-to-fix/controls/$m.json || exit 1; done
A6 make unit && make verify OFFLINE=1
```
A1 also needs `inputs/rea-datadog-test-optimization/` at this commit, since the gate reads its check-output.txt. `run_controls.sh` cds to its own directory, so it runs from any cwd.

**Expected A3 tail:**
```
INFO	certified={'prefix': 'NOT_FIXED', 'wrong_fix': 'NOT_FIXED', 'real_fix': 'FIXED'} plain_retry={'prefix': 'FIXED', 'wrong_fix': 'FIXED', 'real_fix': 'FIXED'}
GATE PASS
```

## 7. No-go rule
If A3 fails on real output, the result is a written no-go with the failing tags and the results file. Neither the predictions nor the gate get edited to fit.
