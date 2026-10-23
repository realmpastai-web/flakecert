# CURSOR TASK: flakecert-verdict-audit (frozen by Hark 2026-10-18; internal)
**Evidence rule:** a number counts only with the file, log or command output that produced it. Inputs are frozen in `inputs/flakecert-verdict-audit/` (SHA256SUMS). Never modify them.

## Goal
`flakecert audit-verdicts` reads a test run in the public dd-trace test-event shape and, for every test Datadog's remediation flow would mark fixed, prints:
1. the flake-rate upper bound that verdict actually supports (95%, exact), and
2. how many clean FlakeCert seeded runs are needed to certify a target bound (default targets 1% and 0.1%).
No Datadog account, API or network. Input is a file.

**Why:** Datadog's Attempt to Fix retries a test 20 times; if all pass it tags the last retry `test.test_management.attempt_to_fix_passed:"true"` and the test moves to Fixed when the fix merges (sources/tests_flaky_management.txt). 20/20 passes only bound the failure rate at 13.9109% (gate output).

## Input shape (frozen: sample/dd-test-run.json, 92 events)
`{"version":1,"metadata":{...},"events":[{"type":"test","version":2,"content":{"name","resource","service","meta":{...},"metrics":{}}}]}` — the dd-trace@6.21.0 citestcycle event fields (sources/dd-trace-encoder-event.js.txt), as JSON instead of msgpack.
Tags used, all as the tracer writes them (sources/dd-trace-jest-plugin-finish.js.txt, dd-trace-retry-reasons.js.txt): `test.suite`, `test.name`, optional `test.parameters`, `test.status` ("pass"/"fail"/"skip"), `test.test_management.is_attempt_to_fix` ("true"), `test.test_management.attempt_to_fix_passed` ("true"/"false" on the last retry), `test.retry_reason` ("attempt_to_fix", "auto_test_retry", ...).

## Rules
- Test key: `test.suite + "::" + test.name`, plus `"[" + test.parameters + "]"` when present.
- Group only events with `is_attempt_to_fix == "true"`, in file order. n = count, k = count with status "fail". Ignore all other events (auto_test_retry / EFD retries are not a fix verdict).
- verdict: `fixed` if the last event's `attempt_to_fix_passed == "true"` and k == 0; `inconsistent` if that tag is "true" but k > 0; else `not_fixed`.

## Math (exact; no floats in any comparison)
- alpha = 1/20. One-sided exact binomial (Clopper-Pearson) with 0 failures.
- `upper_bound_95` = 1 − alpha^(1/n), as a string rounded UP to 6 decimals. It must satisfy, in `fractions.Fraction`: (1−u)^n ≤ alpha and (1−(u−10⁻⁶))^n > alpha. Compute with `decimal` at precision ≥ 50, then verify with Fraction before printing; abort if verification fails.
- `clean_seeded_runs_required[p*]` = the smallest integer n with (1−p*)^n ≤ alpha, p* parsed as Fraction from its decimal string. Verify n and n−1 with Fraction.
- Do NOT use `flakecert.stats.wilson` here: it is two-sided Wilson (0/20 gives 0.161125) and is not this bound.
- Document in the README: the bound covers only the run distribution that was sampled. Plain retries and FlakeCert seeded schedules sample different distributions, which is why the second number counts seeded runs. A seeded run that fails ends the count and becomes a certificate instead.

## Build
1. `flakecert/verdict_audit.py`: `audit(doc, targets=("0.01","0.001")) -> dict`, stdlib only.
2. `tools/audit_verdicts.py --in FILE --out FILE [--target P ...]`, and `make audit` running it on `inputs/flakecert-verdict-audit/sample/dd-test-run.json` → `audit/verdicts.json` (gitignored).
3. Output JSON exactly as `inputs/flakecert-verdict-audit/expected-audit.json`: keys `alpha` ("0.05"), `method`, `tests` sorted by key; fixed rows carry `test, verdict, atf_runs, atf_failures, upper_bound_95, clean_seeded_runs_required`; other rows carry only `test, verdict, atf_runs, atf_failures`. `json.dump(indent=1, sort_keys=True)` + newline.
4. `tests/test_verdict_audit.py`: n=20 → "0.139109"; n=50 → "0.058156"; required 0.01 → 299, 0.001 → 2995; an `inconsistent` case; a `test.parameters` key; auto_test_retry events ignored.
5. Wire `make audit` and the gate into CI (verify job). README section "Auditing a fixed verdict" showing only `make audit` output.

## Acceptance (fresh clone; non-zero exit on any miss)
```
cd inputs/flakecert-verdict-audit && sha256sum -c SHA256SUMS && python3 gate_verdict_audit.py | diff - gate-output.txt && cd -
make audit && diff audit/verdicts.json inputs/flakecert-verdict-audit/expected-audit.json
python3 inputs/flakecert-verdict-audit/gate_verdict_audit.py --report audit/verdicts.json        # GATE PASS, exit 0
! python3 inputs/flakecert-verdict-audit/gate_verdict_audit.py --report inputs/flakecert-verdict-audit/controls/mutant-approx.json
make unit && make verify OFFLINE=1        # existing 9 gates unchanged; ledger/certs untouched
```
Mutant control (frozen): `controls/mutant-approx.json` reports Wilson 0.161125 and 298 runs for 1%; the gate must FAIL it (controls/mutant-approx.log, exit 1).

## Out of scope / do not
- No Datadog API, msgpack decoding, upload, or account. No claims about Datadog's backend or non-JS tracers.
- No external copy. Don't touch ledger/, certs/, evidence/ or the cert path.
- Don't claim the exponential speedup (ledger: UNPROVEN).
