# Verdict — haproxy-mode-http-default

Profile: `haproxy-mode-http-default`
Mode: dry-run replay of `desync-oracle/`. Not a new score.
Pin: `pins/haproxy-3.4.7.tar.gz` sha256 `ccfd342f3724c2cd659574044d788f44e20b212467c6bd5edbbfc517a2775dca` (checked against `FREEZES.txt`).
The sealed holdout remains `desync-oracle/SCORE-SUMMARY.md`. This file restates it.

**GO**

Rules 25. HIGH 0. MEDIUM 0. LOW 25.
PAYABLE 0. NOT-PAYABLE 25. NEEDS-LIVE 0.

Cross-check SCORE-SUMMARY.md heading "HAProxy 3.4.7, default `mode http`": **GO**.
Cross-check VERDICT.md heading "HAProxy 3.4.7 `mode http`": **GO**.
The map is HIGH then NO-GO, else MEDIUM then HARDENING-REQUIRED, else GO.
The mapped word matches both sealed words, so this replay writes the sealed word.

## HAProxy 3.4.7 `mode http`

**GO**

No sealed row is HIGH or MEDIUM. Under default `mode http` with the HTTP/1 mux, HAProxy 3.4.7 parses the client message and writes a new request line, new header lines, and a new body framing before the origin parses anything (`src/h1_htx.c` lines 1053-1074 and 1147-1150; `src/mux_h1.c` lines 2679-2704).

R13 does not carry over from the nginx edge. HAProxy's trim includes HTAB (`src/http.c` line 38; `src/h1.c` lines 949-958). The copied value does not contain it.

Counts: 25 rules, 0 HIGH, 0 MEDIUM, 25 LOW, 0 PAYABLE, 25 NOT-PAYABLE, 0 NEEDS-LIVE.

