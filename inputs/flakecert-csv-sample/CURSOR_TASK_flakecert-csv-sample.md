# CURSOR TASK: flakecert-csv-sample (frozen by Hark 2026-10-18; internal)
Repo realmpastai-web/flakecert, branch `feat/csv-sample` from main **2a986a1** (verdict-audit merged).

**Evidence rule:** a number counts only with the file, log or command output that produced it. Inputs are frozen in `inputs/flakecert-csv-sample/` (SHA256SUMS). Never modify them.

## Why: the reverse (files in this folder)
- **The input is a CSV.** A public engineering post seeds a fix loop from a flaky-test CSV export. main's `audit-verdicts` reads only JSON. `main-2a986a1-csv-attempt.txt` shows `JSONDecodeError`, exit 1.
  - **UNPROVEN:** the exact export path and columns. We pin the one public, shipped CSV path we can cite: Datadog's own CLI **pup v2.0.0** (Apache-2.0), `pup cicd tests search … --output csv`.
- **The column rule.** These come from pup v2.0.0 source (`sources/pup-v2.0.0-excerpts.txt`), with the strings confirmed in the shipped binary (`rea/`):
  - **R1, columns:** the header is the bytewise-sorted union of dot-flattened keys from each `data[]` event. Nested event attributes become `attributes.attributes.test.name`, `…test.status`, `…test.suite`, `…test.test_management.is_attempt_to_fix`, `…test.test_management.attempt_to_fix_passed`, `…start` and so on. A column only exists if some row has it.
  - **R2, cell values:** arrays and objects are compact JSON (`attributes.tags` = `"[""service:sample"",""env:ci""]"`). Bools print as `true`/`false`. Cells containing `, " \n \r` are quoted. Rows are joined with `\n`, plus one trailing `\n`.
  - **R3, row order:** `cicd tests search` asks for `TIMESTAMP_DESCENDING`, so rows are **newest first**. It fetches **one page** (default `--limit 50`, `--from 1h`, no cursor loop).
- **Real shape.** Datadog's recorded API response (datadog-api-client-rust cassette, `sample/real-cassette-search-response.json`) has nested attributes and `start` in ns. The frozen `sample/real-cassette-search.csv` is the R1/R2 rendering of it. A pup binary run gave the same bytes (`observations/`, flagged).

## Frozen samples
- **`sample/pup-export.csv`:** the 92 verdict-audit events (`sample/dd-test-run.json`, same sha256 as `inputs/flakecert-verdict-audit`) in the real API shape, rendered by R1/R2 with R3 ordering. Gate C5 shows it carries every event's tags exactly. So its audit must equal `expected-audit-pup.json` (byte-identical to verdict-audit's `expected-audit.json`, sha256 `09987c86…`).
- **`sample/real-cassette-search.csv`:** 3 real recorded skip events with no Attempt-to-Fix columns. Its audit is `expected-audit-real.json` (`tests: []`).

## Build
1. **CSV support in `flakecert/verdict_audit.py`:**
   - parse with `csv.DictReader` (never split lines); strip the `attributes.attributes.` prefix to get the dd-trace tag names;
   - build the same event list the JSON path uses, then call the unchanged `audit()`.
   - **Required columns:** `start`, `test.suite`, `test.name`, `test.status`. The `test.parameters`, `is_attempt_to_fix` and `attempt_to_fix_passed` columns are optional (missing means no such tag). An empty cell means the tag is absent.
   - **Order:** sort rows by `int(start)` ascending before grouping (R3). If two rows share a `start`, or a required column is missing, abort with exit 2 and a clear message.
2. **`tools/audit_verdicts.py --in FILE`:** treat the file as CSV when the name ends in `.csv` or `--format csv` is given.
   - Add `make audit-csv` (writes `audit/verdicts-csv.json` from `sample/pup-export.csv`) and `make audit-csv-real` (writes `audit/verdicts-csv-real.json`).
3. **README:** the "Auditing a fixed verdict" section gets a short CSV paragraph naming the pup command, with **no digits** in it. The README number check only accepts digits from SUMMARY.md or the audit quote. State the caveat in words: pup fetches one page, newest first, and a truncated export drops the oldest retries, so n shrinks and the bound loosens.
4. **Tests:** order independence (shuffled rows give the same output), the duplicate-`start` abort, a missing-column abort, a quoted cell with a comma, and a `test.parameters` key.
5. **CI:** add the acceptance lines below to the verify job.

## Acceptance (fresh clone; non-zero exit on any miss)
```
A0 (team box, runtime OK) pup 2.0.0 from the pinned release tarball: pup format --output csv --input inputs/flakecert-csv-sample/sample/search-response.json | cmp - inputs/flakecert-csv-sample/sample/pup-export.csv
A1 cd inputs/flakecert-csv-sample && sha256sum -c SHA256SUMS && python3 gate_csv_sample.py | diff - gate-output.txt && cd -
A2 make audit-csv && python3 inputs/flakecert-csv-sample/gate_csv_sample.py --report audit/verdicts-csv.json --kind pup          # GATE PASS
A3 make audit-csv-real && python3 inputs/flakecert-csv-sample/gate_csv_sample.py --report audit/verdicts-csv-real.json --kind real  # GATE PASS
A4 ! python3 inputs/flakecert-csv-sample/gate_csv_sample.py --report inputs/flakecert-csv-sample/controls/mutant-file-order.json --kind pup
A5 make audit && diff audit/verdicts.json inputs/flakecert-verdict-audit/expected-audit.json   # JSON path unchanged
A6 make unit && make verify REPLAY_SKIP=1   # existing gates and the README audit-quote check stay green; no files under evidence/, ledger/ or certs/
```
**Mutant control (frozen):** `controls/mutant-file-order.json` is the audit you get if rows are read in file order (newest first). The last Attempt-to-Fix row becomes the oldest retry, so cart and sync drop from `fixed` to `not_fixed`. The gate must FAIL it (`controls/mutant-file-order.log`, exit 1).

## Out of scope / do not
- No Datadog API calls, accounts, keys, or pagination client.
- No claim about the Datadog UI's CSV export columns (UNPROVEN until a sample exists).
- No external copy. Don't touch `ledger/`, `certs/`, `evidence/` or the cert path. Don't claim the exponential speedup (still UNPROVEN).
