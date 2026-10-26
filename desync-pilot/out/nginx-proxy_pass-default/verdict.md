# Verdict — nginx-proxy_pass-default

Profile: `nginx-proxy_pass-default`
Mode: dry-run replay of `desync-oracle/`. Not a new score.
Pin: `pins/nginx-1.28.3.tar.gz` sha256 `2c96a946bfb0882a21744ed429770a2123ae1828c7c48665092993ddee91a918` (checked against `FREEZES.txt`).
The sealed holdout remains `desync-oracle/SCORE-SUMMARY.md`. This file restates it.

**HARDENING-REQUIRED**

Rules 25. HIGH 0. MEDIUM 1. LOW 24.
PAYABLE 1. NOT-PAYABLE 24. NEEDS-LIVE 0.

Cross-check SCORE-SUMMARY.md heading "nginx 1.28.3, default `proxy_pass`": **HARDENING-REQUIRED**.
Cross-check VERDICT.md heading "nginx 1.28.3 `proxy_pass`": **HARDENING-REQUIRED**.
The map is HIGH then NO-GO, else MEDIUM then HARDENING-REQUIRED, else GO.
The mapped word matches both sealed words, so this replay writes the sealed word.

## nginx 1.28.3 `proxy_pass`

**HARDENING-REQUIRED**

One sealed row is MEDIUM: **R13-OWS-HTAB**. nginx 1.28.3 keeps a leading or trailing HTAB in a field value (`src/http/ngx_http_parse.c` lines 972-975, 988-991, and 1028-1030). Default `proxy_pass` copies that value (`src/http/modules/ngx_http_proxy_module.c` lines 1549-1556 and 3936-3937). The origin excludes HTAB as optional whitespace, so the value it extracts does not include that HTAB.

The remediation is H13 in `HARDENING.md`. The pinned nginx tree has no parser directive that makes the two extractions match. `proxy_pass_request_headers off` stops the copy. Otherwise a decision that uses the value has to sit at the origin, after the origin has trimmed the tab.

No row is HIGH. Under default `proxy_pass`, body framing is rebuilt before the origin parses it. `ngx_http_proxy_create_request` writes a new request line and replaces Content-Length and Transfer-Encoding (`src/http/modules/ngx_http_proxy_module.c` lines 838-846 and 1432-1475).

Counts: 25 rules, 0 HIGH, 1 MEDIUM, 24 LOW, 1 PAYABLE, 24 NOT-PAYABLE, 0 NEEDS-LIVE.

