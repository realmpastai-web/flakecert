# Sample buyer report

REDACTED SAMPLE. The buyer in this file is ACME, a placeholder. No real customer name is used. No live gate was run for this sample. The counts below are the sealed counts in `desync-oracle/SCORE-SUMMARY.md`, restated after a dry-run replay. This file is the shape of the week-1 deliverable.

## Executive summary

ACME's edge under test is nginx 1.28.3 with default `proxy_pass`, in front of Kestrel. On that path nginx parses the client message and writes a new request before the origin parses it. Body framing on the rebuilt request does not carry the client's Content-Length together with the client's Transfer-Encoding, and it does not carry the client's chunk-size text.

The sealed verdict for this profile is **HARDENING-REQUIRED**. The scale is GO / HARDENING-REQUIRED / NO-GO. This edge is not NO-GO: the sealed table has zero HIGH rows. It is not GO: one row is MEDIUM.

That row is R13-OWS-HTAB. nginx keeps a leading or trailing HTAB in a field value and, with default `proxy_pass_request_headers`, copies that value upstream. The origin's trim excludes HTAB, so the two parsers extract different values from a request the origin actually parses. Host, Content-Length, and Transfer-Encoding do not take this path. The MEDIUM residue is some other field. It is not a body-length disagreement.

The published HAProxy 3.4.7 `mode http` profile is a different edge. Its sealed verdict is GO. This sample does not apply that word to ACME.

## Edge under test

| Item | Value |
| --- | --- |
| Buyer | ACME (placeholder) |
| Profile | `nginx-proxy_pass-default` |
| Front | nginx 1.28.3 |
| Config the rating covers | default `proxy_pass` |
| Pin | `pins/nginx-1.28.3.tar.gz` |
| Pin sha256 | `2c96a946bfb0882a21744ed429770a2123ae1828c7c48665092993ddee91a918` |
| Origin | Kestrel HTTP/1.1 parser in `Microsoft.AspNetCore.App.Runtime.linux-x64` 10.0.12. The framing behaviour scored in the oracle is the same in 10.0.13. This report states behaviour. It does not cite origin source lines. |
| Normative text | RFC 9112 and RFC 9110, pinned under `desync-oracle/pins/` |
| Class name | CWE-444, inconsistent interpretation of an HTTP request. The oracle uses that name as the class. It does not add a technique. |

The pin digest is the nginx line of `desync-oracle/FREEZES.txt`. The dry-run checks that file before it writes a verdict.

Ratings apply to default `proxy_pass`. They do not apply to nginx `stream`, to a TCP pass-through, or to Kestrel published on its own. That limit is H-ARCH in the published checklist.

## Verdict

**HARDENING-REQUIRED**

| Count | Sealed value |
| --- | --- |
| Rules | 25 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 24 |
| PAYABLE | 1 |
| NOT-PAYABLE | 24 |
| NEEDS-LIVE | 0 |

On the report scale: zero HIGH means the word is not NO-GO. One MEDIUM means the word is not GO. The mapped word matches `desync-oracle/VERDICT.md` and `desync-oracle/SCORE-SUMMARY.md`.

The lab config gate in the pilot scope was not run for ACME. This sample therefore does not claim that ACME's installed nginx matches the pinned build or the scored defaults. If that gate fails, this verdict does not apply to the deployment.

## Conformance map for this edge

Replay of the nginx table in `desync-oracle/CONFORMANCE-MAP.md`. Chain is the rating after `proxy_pass` rebuilds the request.

| Rule | RFC | nginx | Origin | Chain | Label |
| --- | --- | --- | --- | --- | --- |
| R01-CRLF | 9112 §2.2 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R02-BARE-LF | 9112 §2.2 MAY | CONFORMS | CONFORMS (switch off) | LOW | NOT-PAYABLE |
| R03-BARE-CR-REQLINE | 9112 §2.2 MUST | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R04-HEADER-EXTRA-CR | 9112 §2.2 MUST | LENIENT | CONFORMS | LOW | NOT-PAYABLE |
| R05-LEAD-SKIP | 9112 §2.2 | LENIENT | LENIENT | LOW | NOT-PAYABLE |
| R06-MULTI-SP | 9112 §3 MAY | CONFORMS | STRICTER-THAN-RFC | LOW | NOT-PAYABLE |
| R07-HTAB-SEPARATOR | 9112 §3 MAY | STRICTER-THAN-RFC | STRICTER-THAN-RFC | LOW | NOT-PAYABLE |
| R08-VERSION-GRAMMAR | 9112 §2.3 | LENIENT | CONFORMS | LOW | NOT-PAYABLE |
| R09-MISSING-VERSION | 9112 §3 | LENIENT | CONFORMS | LOW | NOT-PAYABLE |
| R10-WS-BEFORE-COLON | 9112 §5.1 MUST | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R11-OBS-FOLD | 9112 §5.2 MUST | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R12-OWS-SP | 9112 §5.1 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R13-OWS-HTAB | 9112 §5.1; 9110 §5.6.3 | LENIENT | CONFORMS | MEDIUM | PAYABLE |
| R14-NO-COLON | 9112 §5 | LENIENT | CONFORMS | LOW | NOT-PAYABLE |
| R15-HOST | 9112 §3.2 MUST | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R16-CL-REPEAT | 9112 §6.3 item 5; 9110 §5.2 | STRICTER-THAN-RFC | STRICTER-THAN-RFC | LOW | NOT-PAYABLE |
| R17-CL-DIGITS | 9112 §6.2 and §6.3 item 5 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R18-CL-AND-TE | 9112 §6.1 MAY; §6.3 item 3 | CONFORMS (reject) | CONFORMS (process TE, close by default) | LOW | NOT-PAYABLE |
| R19-TE-HTTP10 | 9112 §6.1 MUST | CONFORMS | LENIENT | LOW | NOT-PAYABLE |
| R20-TE-FINAL | 9112 §6.3; §6.1 SHOULD 501 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R21-TE-REPEAT | 9110 §5.2–§5.3 | STRICTER-THAN-RFC | CONFORMS | LOW | NOT-PAYABLE |
| R22-CHUNK-CRLF | 9112 §7.1 CRLF | LENIENT (bare LF) | CONFORMS | LOW | NOT-PAYABLE |
| R23-CHUNK-EXT | 9112 §7.1.1 MUST ignore | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R24-CHUNK-OVERFLOW | 9112 §7.1 MUST | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R25-TRAILER-FRAMING | 9112 §7.1 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |

nginx count: 25 rules, 0 HIGH, 1 MEDIUM, 24 LOW, 1 PAYABLE, 24 NOT-PAYABLE, 0 NEEDS-LIVE.

## The one MEDIUM finding — R13 on nginx

RFC 9112 §5.1 excludes optional whitespace from the field value. RFC 9110 §5.6.3 defines that whitespace as SP or HTAB. The SP half is R12, and both sides exclude it. The HTAB half is R13.

nginx is **LENIENT** on HTAB. The skip states test SP only. A HTAB falls into the default arm, so a leading HTAB starts the value and a trailing HTAB stays inside it (`src/http/ngx_http_parse.c` lines 972-975, 988-991, and 1028-1030, inside `pins/nginx-1.28.3.tar.gz`). `ignore_invalid_headers` does not apply.

The origin **CONFORMS**. Its trim includes HTAB, so a leading or trailing HTAB is not part of the extracted value. That sentence is behaviour. It has no origin line number.

Chain: **MEDIUM. PAYABLE.** With `proxy_pass_request_headers` at its default of on, the stored value is copied (`src/http/modules/ngx_http_proxy_module.c` lines 1549-1556 and 3936-3937). The origin's trim removes the HTAB. The two parsers extract different values from a request the origin actually parses.

This is not HIGH. Host, Content-Length, and Transfer-Encoding do not pass a HTAB through nginx. Host fails validation when the character is `<= 0x20` (`src/http/ngx_http_request.c` lines 2225-2226). Content-Length fails the digit parser (`src/core/ngx_string.c` lines 1083-1100). Transfer-Encoding fails the seven-byte `chunked` test (`src/http/ngx_http_request.c` lines 2026-2039). Those client messages are rejected before `proxy_pass`. MEDIUM is other field values.

The difference is not a published advisory on nginx 1.28.3, which is why the sealed disposition is PAYABLE. `desync-oracle/SKEPTIC.md` argues the weight of that label. It does not change the sealed score.

Public names already in use for this class, and not a new defect: RFC 9112, RFC 9110, and CWE-444.

## Hardening steps

From `desync-oracle/HARDENING.md` H-ARCH and H13. The pinned nginx tree has no parser directive that makes the two extractions match.

1. Keep `proxy_pass`. The LOW ratings for body framing depend on `ngx_http_proxy_create_request` writing a new request line and replacing Content-Length and Transfer-Encoding (`src/http/modules/ngx_http_proxy_module.c` lines 838-846 and 1432-1475). Leave `proxy_request_buffering` on (default 1, lines 3701-3702). Do not replace the default header-table entries for those two fields with the raw client values (lines 845-846).
2. Leave Host, Content-Length, and Transfer-Encoding on nginx's own checks. Those three do not forward a HTAB. Do not `proxy_set_header` them from the raw client field.
3. If the application does not need client headers, set `proxy_pass_request_headers off` (directive at lines 452-456, default of 1 at lines 3936-3937). The copy loop at lines 1527-1561 does not run, so the HTAB value is not sent. The cost is that no client field other than the default proxy header list is sent.
4. If client headers are required, make allow or deny decisions that depend on those values at the origin, after the origin has trimmed optional whitespace. nginx's copy still contains the HTAB.
5. Do not publish the Kestrel port as a second public HTTP listener. R19 is LOW on this chain because nginx answers 400 first. If a listener reaches Kestrel without this front, that leniency is still there. Leave `Microsoft.AspNetCore.Server.Kestrel.AllowKeepAliveAfterCLTE` unset on any listener that is not behind this front. Leave `Microsoft.AspNetCore.Server.Kestrel.EnableInsecureChunkedRequestParsing` unset.

## Residual risk

H13 cannot be closed by a parser flag in the pinned nginx tree. `proxy_pass_request_headers off` avoids the copy. It does not make nginx's parser match the origin. An operator who needs the client fields still has the difference. The sealed word stays HARDENING-REQUIRED for that reason.

The client-facing parser stays lenient on R04, R08, R09, R14, and R22. Those rows stay LOW while `proxy_pass` rebuilds the request. The checklist does not claim a directive that removes them.

`desync-oracle/SKEPTIC.md` records the knock-down that was tried: R13 is not a body-length disagreement; the RFC already describes this whitespace; and a rubric that reserved MEDIUM for Content-Length, Transfer-Encoding, and the request line would not have produced this word. The knock-down does not show that the two parsers extract the same bytes. The score was not edited after that pass.

What would make this verdict the wrong word for a deployment, as that skeptic file already lists: a missed directive that excludes HTAB the way the origin does; evidence that default `proxy_pass` forwards the client Content-Length and Transfer-Encoding bytes unchanged (the cites above contradict that); or a `stream` path that is what ACME actually runs. That path was not read.

## Next fronts

FUTURE. Not scored. Not delivered.

- Envoy in front of Kestrel.
- Traefik in front of Kestrel.
- One CDN edge in front of Kestrel.

Also not read, and not claimed: nginx 1.30, HAProxy 3.5, HAProxy 3.2, HAProxy 2.8, HTTP/2, and HTTP/3. The published HAProxy 3.4.7 `mode http` profile is already in the oracle (verdict GO) and can be a second week-1 profile if ACME names it. It is not part of this sample's edge.
