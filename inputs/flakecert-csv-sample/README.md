# flakecert-csv-sample inputs (frozen by Hark 2026-10-18, base main 2a986a1; internal)
- CURSOR_TASK_flakecert-csv-sample.md: the task.
- gate_csv_sample.py (self-check C1-C7; --report judge R1-R3), make_csv_sample.py, pup_csv_port.py (static port of pup v2.0.0 CSV rendering).
- sample/: dd-test-run.json (verdict-audit sample, same sha), search-response.json + pup-export.csv (92 events, newest first), real-cassette-search-response.json + real-cassette-search.csv (Datadog-recorded response).
- expected-audit-pup.json (= verdict-audit expected-audit.json), expected-audit-real.json (tests []).
- gate-output.txt (self-check GATE PASS); controls/mutant-file-order.{json,log} (exit 1); main-2a986a1-csv-attempt.txt (JSONDecodeError, exit 1).
- sources/ (pup v2.0.0 excerpts, api-client models, cassettes, checksums, PIN.txt), rea/ (inspect-rust-binary Evidence JSON, binary strings), observations/ (flagged runtime runs, not gate inputs).
