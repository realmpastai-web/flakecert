# Verdict

Two edges. One sealed rule set. The score was not edited after `SKEPTIC.md`.

## nginx 1.28.3 `proxy_pass`

**HARDENING-REQUIRED**

One sealed row is MEDIUM: **R13-OWS-HTAB**. nginx 1.28.3 keeps a leading or trailing HTAB in a field value (`src/http/ngx_http_parse.c` lines 972-975, 988-991, and 1028-1030). Default `proxy_pass` copies that value (`src/http/modules/ngx_http_proxy_module.c` lines 1549-1556 and 3936-3937). The origin excludes HTAB as optional whitespace, so the value it extracts does not include that HTAB.

The remediation is H13 in `HARDENING.md`. The pinned nginx tree has no parser directive that makes the two extractions match. `proxy_pass_request_headers off` stops the copy. Otherwise a decision that uses the value has to sit at the origin, after the origin has trimmed the tab.

No row is HIGH. Under default `proxy_pass`, body framing is rebuilt before the origin parses it. `ngx_http_proxy_create_request` writes a new request line and replaces Content-Length and Transfer-Encoding (`src/http/modules/ngx_http_proxy_module.c` lines 838-846 and 1432-1475).

Counts: 25 rules, 0 HIGH, 1 MEDIUM, 24 LOW, 1 PAYABLE, 24 NOT-PAYABLE, 0 NEEDS-LIVE.

## HAProxy 3.4.7 `mode http`

**GO**

No sealed row is HIGH or MEDIUM. Under default `mode http` with the HTTP/1 mux, HAProxy 3.4.7 parses the client message and writes a new request line, new header lines, and a new body framing before the origin parses anything (`src/h1_htx.c` lines 1053-1074 and 1147-1150; `src/mux_h1.c` lines 2679-2704).

R13 does not carry over from the nginx edge. HAProxy's trim includes HTAB (`src/http.c` line 38; `src/h1.c` lines 949-958). The copied value does not contain it.

Counts: 25 rules, 0 HIGH, 0 MEDIUM, 25 LOW, 0 PAYABLE, 25 NOT-PAYABLE, 0 NEEDS-LIVE.

## Rows that are not the verdict

| Edge | Row | What would have made it the verdict | Why it is not |
| --- | --- | --- | --- |
| nginx | R18-CL-AND-TE | The usual place to claim the tiers disagree on both length fields. | RFC 9112 §6.1 is a MAY, not a requirement to reject. nginx takes the reject branch and answers 400 before `proxy_pass` (`src/http/ngx_http_request.c` lines 2030-2036). The origin takes the process-Transfer-Encoding branch and clears keep-alive unless the keep-alive switch named in `HARDENING.md` is set. Confirm H-DEFAULTS. Do not score this HIGH. |
| nginx | R19-TE-HTTP10 | The origin accepts Transfer-Encoding on HTTP/1.0. nginx does not. | nginx answers 400 first (`src/http/ngx_http_request.c` lines 2017-2023). LOW on this chain. If the origin is reachable without nginx, H19 is the control. No origin switch for that reject was found. |
| nginx | R22-CHUNK-CRLF | nginx accepts a bare LF on a chunk line. The origin requires CR LF. | The origin parses nginx's body, not the client chunk-size line. See H22. |
| nginx | R04, R08, R09, R14 | nginx is lenient and the origin is not. | The rebuilt request does not carry the client line. See H-ARCH. |
| HAProxy | R15-HOST | HAProxy forwards a missing HTTP/1.1 Host and the origin rejects it. | The origin's 400 clears keep-alive and leaves the accept loop. That is not a second reading of Content-Length or Transfer-Encoding. `SKEPTIC.md` argues the raise. It does not stick. |
| HAProxy | R18-CL-AND-TE | The usual place to claim the tiers disagree on both length fields. | Both take the process-Transfer-Encoding branch of RFC 9112 §6.1. HAProxy deletes Content-Length before the server mux (`src/h1.c` lines 1191-1201). The origin does not see the client pair. |
| HAProxy | R13-OWS-HTAB | This is the MEDIUM row on the nginx edge. | HAProxy trims HTAB. The copied value does not contain it. |

## What is already public

Already public, and not a new defect class:

- RFC 9112 states the recipient rules scored here, including the MAY for a single LF, the requirement for a bare CR, the requirement to reject space before a colon, the requirement for obsolete line folding, the MAY for both length fields, and the warning that lenient parsing differs across recipients.
- CWE-444 is the public name for inconsistent interpretation of HTTP requests.
- nginx rejecting a request that carries both Content-Length and Transfer-Encoding is the behaviour of this pinned tree (`src/http/ngx_http_request.c` lines 2030-2036).
- CVE-2021-40346 is an integer overflow in `htx_add_header` on HAProxy 2.0 through 2.5. The 3.4.7 tree rejects an over-long name or value before that addition (`include/haproxy/htx.h` lines 511-515). Overlap with that advisory is not a row.

What is specific to these pins is the chain column: body framing stays LOW because each default HTTP front writes a new request and replaces both length fields. R13 crosses the nginx front for field values other than Host, Content-Length, and Transfer-Encoding. It does not cross the HAProxy front.
