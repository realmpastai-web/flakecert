# Conformance map — haproxy-mode-http-default

Profile: `haproxy-mode-http-default`
Mode: dry-run replay of `desync-oracle/`. Not a new score.
Pin: `pins/haproxy-3.4.7.tar.gz` sha256 `ccfd342f3724c2cd659574044d788f44e20b212467c6bd5edbbfc517a2775dca` (checked against `FREEZES.txt`).
The sealed holdout remains `desync-oracle/SCORE-SUMMARY.md`. This file restates it.

## Chain-risk rubric

Scored for nginx default `proxy_pass`, and for HAProxy default `mode http` with the HTTP/1 mux. The rubric is the same on both edges.

| Risk | Meaning |
| --- | --- |
| LOW | The two tiers agree, or the front rejects the client message before it writes the upstream request, or the rebuilt upstream request does not contain the client octets the two parsers treated differently. |
| MEDIUM | The rebuilt upstream request still carries a field the two parsers extract differently. |
| HIGH | The rebuilt upstream request still carries a Content-Length, a Transfer-Encoding, or a request line that the two parsers would delimit differently. |

A row is **PAYABLE** only when its chain risk is HIGH or MEDIUM and the difference is not already a public advisory on that pin. **NEEDS-LIVE** is used when the static cites do not decide the risk. Every other row is **NOT-PAYABLE**.

nginx `stream` and HAProxy `mode tcp` were not read. Ratings do not apply to those deployments. That limit is H-ARCH in `HARDENING.md`.

## What this front rebuilds

**HAProxy.** The client bytes are parsed into an internal message. Header names are stored in lower case. A name longer than 255 bytes, or a value longer than 1048575 bytes, is refused before the header block is built (`include/haproxy/htx.h` lines 511-515). The server mux writes a new request line: method, one SP, URI, one SP, the literal `HTTP/1.1` when the version flag is set, otherwise the stored version, then CR LF (`src/h1_htx.c` lines 1053-1074). Header lines are name, colon, SP, value, CR LF (lines 1147-1150). `transfer-encoding` is written as the literal `chunked` only when the message is chunked (`src/mux_h1.c` lines 2679-2687). `content-length` is written only when the length flag is still set (lines 2689-2704). A chunked body is written with a new hex size and CR LF (`src/h1_htx.c` lines 1169-1185; `src/mux_h1.c` lines 3095-3108).


## HAProxy edge

| Rule | RFC | HAProxy | Origin | Chain | Label |
| --- | --- | --- | --- | --- | --- |
| R01-CRLF | 9112 §2.2 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R02-BARE-LF | 9112 §2.2 MAY | CONFORMS | CONFORMS (switch off) | LOW | NOT-PAYABLE |
| R03-BARE-CR-REQLINE | 9112 §2.2 MUST | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R04-HEADER-EXTRA-CR | 9112 §2.2 MUST | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R05-LEAD-SKIP | 9112 §2.2 | CONFORMS | LENIENT | LOW | NOT-PAYABLE |
| R06-MULTI-SP | 9112 §3 MAY | CONFORMS | STRICTER-THAN-RFC | LOW | NOT-PAYABLE |
| R07-HTAB-SEPARATOR | 9112 §3 MAY | CONFORMS | STRICTER-THAN-RFC | LOW | NOT-PAYABLE |
| R08-VERSION-GRAMMAR | 9112 §2.3 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R09-MISSING-VERSION | 9112 §3 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R10-WS-BEFORE-COLON | 9112 §5.1 MUST | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R11-OBS-FOLD | 9112 §5.2 MUST | CONFORMS (replace) | CONFORMS (reject) | LOW | NOT-PAYABLE |
| R12-OWS-SP | 9112 §5.1 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R13-OWS-HTAB | 9112 §5.1; 9110 §5.6.3 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R14-NO-COLON | 9112 §5 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R15-HOST | 9112 §3.2 MUST | LENIENT | CONFORMS | LOW | NOT-PAYABLE |
| R16-CL-REPEAT | 9112 §6.3 item 5 | CONFORMS | STRICTER-THAN-RFC | LOW | NOT-PAYABLE |
| R17-CL-DIGITS | 9112 §6.2 and §6.3 item 5 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R18-CL-AND-TE | 9112 §6.1 MAY; §6.3 item 3 | CONFORMS (process TE, remove CL, close) | CONFORMS (process TE, close by default) | LOW | NOT-PAYABLE |
| R19-TE-HTTP10 | 9112 §6.1 MUST close | CONFORMS | LENIENT | LOW | NOT-PAYABLE |
| R20-TE-FINAL | 9112 §6.3; §6.1 SHOULD 501 | STRICTER-THAN-RFC | CONFORMS | LOW | NOT-PAYABLE |
| R21-TE-REPEAT | 9110 §5.2–§5.3 | STRICTER-THAN-RFC | CONFORMS | LOW | NOT-PAYABLE |
| R22-CHUNK-CRLF | 9112 §7.1 CRLF | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R23-CHUNK-EXT | 9112 §7.1.1 MUST ignore | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R24-CHUNK-OVERFLOW | 9112 §7.1 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |
| R25-TRAILER-FRAMING | 9112 §7.1 | CONFORMS | CONFORMS | LOW | NOT-PAYABLE |

HAProxy count: 25 rules, 0 HIGH, 0 MEDIUM, 25 LOW, 0 PAYABLE, 25 NOT-PAYABLE, 0 NEEDS-LIVE.


## Rules

### R01-CRLF

RFC 9112 §2.2: the line terminator for the start-line and fields is CR LF.

nginx **CONFORMS**. In `ngx_http_parse_request_line`, CR moves to `sw_almost_done` and that state accepts LF (`src/http/ngx_http_parse.c` lines 739-742 and 780-786). A header line ends on the same CR-then-LF pair (lines 1002-1004 and 1046-1049).

HAProxy **CONFORMS**. On the request line, CR is consumed and the next state requires LF (`src/h1.c` lines 620-644). A header value ending in CR requires LF (lines 920-927).

Origin **CONFORMS**. The origin accepts CR LF as the terminator of the request line and of header lines.

Chain: both fronts rewrite the upstream request with CR LF. **LOW. NOT-PAYABLE** on both edges.

### R02-BARE-LF

RFC 9112 §2.2: a recipient MAY recognize a single LF as a line terminator and ignore any preceding CR. The MAY names the start-line and fields. It does not name chunk lines (R22).

nginx **CONFORMS** (uses the MAY). Request-line states accept LF without a preceding CR (`src/http/ngx_http_parse.c` lines 745-746 and 772-773). Header lines do the same (lines 1006-1008). No cited directive disables this.

HAProxy **CONFORMS** (uses the MAY). A request-line LF finishes the line without requiring CR (`src/h1.c` lines 620-622). A header-value LF does the same (lines 920-922).

Origin **CONFORMS** when `Microsoft.AspNetCore.Server.Kestrel.DisableHttp1LineFeedTerminators` is unset. The origin then accepts a single LF on the request line and on header lines. Setting the switch makes the origin reject a bare LF. The scored default is the switch unset.

Chain: the fronts and the origin agree on the default MAY, and both fronts still emit CR LF upstream. **LOW. NOT-PAYABLE** on both edges.

### R03-BARE-CR-REQLINE

RFC 9112 §2.2: a bare CR inside a protocol element other than the content MUST be treated as invalid or replaced with SP.

nginx **CONFORMS** (rejects). After CR, `sw_almost_done` returns an invalid request for any byte other than LF (`src/http/ngx_http_parse.c` lines 780-786). That result is finalized as 400 (`src/http/ngx_http_request.c` lines 1232-1236).

HAProxy **CONFORMS** (rejects). After the request-line CR, any byte other than LF is rejected (`src/h1.c` lines 331-337 and 643). The mux reports a parsing error and the default status is 400 (`src/mux_h1.c` lines 1999-2005 and 3891-3893).

Origin **CONFORMS**. A CR on the request line that is not the single trailing CR of an 8-byte version token is rejected.

Chain: both fronts reject before an upstream write. **LOW. NOT-PAYABLE** on both edges.

### R04-HEADER-EXTRA-CR

Same bare-CR rule as R03, applied to a header line that has already seen one CR.

nginx **LENIENT**. `sw_almost_done` accepts LF, and on another CR it stays in the state and consumes the extra CR (`src/http/ngx_http_parse.c` lines 1046-1054). The field value was already closed at the first CR (lines 1002-1004). No cited directive changes this state.

HAProxy **CONFORMS** (rejects). The state after a header CR requires LF (`src/h1.c` lines 924-927). A second CR is not consumed as whitespace.

Origin **CONFORMS**. A CR on a header line that is not followed by LF is rejected.

Chain, nginx: the tiers disagree on the client line. Default `proxy_pass` writes a new CR LF and does not copy the client line ending (`src/http/modules/ngx_http_proxy_module.c` lines 1549-1556). The origin does not see the extra CR. **LOW. NOT-PAYABLE.**

Chain, HAProxy: both reject. **LOW. NOT-PAYABLE.**

### R05-LEAD-SKIP

RFC 9112 §2.2 SHOULD ignore at least one empty line before the request line. The bare-CR requirement in R03 applies inside a protocol element.

nginx **LENIENT** on a bare CR, and it implements the SHOULD for CR LF. `sw_start` discards CR or LF and stays in `sw_start` (`src/http/ngx_http_parse.c` lines 143-148). A bare CR is discarded rather than rejected. No cited directive disables the skip.

HAProxy **CONFORMS**. Before the request line, a bare LF is discarded and a CR must be followed by LF (`src/h1.c` lines 450-479). A bare CR is rejected. No cited directive makes HAProxy skip that bare CR.

Origin **LENIENT**. The origin discards a run of CR and LF before the request line. The line-feed switch in R02 does not control this skip.

Chain, nginx: the tiers agree on the skip. **LOW. NOT-PAYABLE.**

Chain, HAProxy: they disagree on a bare CR, and HAProxy does not forward that message. **LOW. NOT-PAYABLE.**

### R06-MULTI-SP

RFC 9112 §3 uses a single SP in the grammar and MAY parse on whitespace-delimited words, ignoring preceding or trailing SP.

nginx **CONFORMS** (uses the SP part of the MAY). The first SP ends the method and further SP before the target is ignored (`src/http/ngx_http_parse.c` lines 298-303).

HAProxy **CONFORMS** (uses the MAY). The first SP or HTAB ends the method, and further SP and HTAB are skipped (`src/h1.c` lines 487-515).

Origin **STRICTER-THAN-RFC**. The origin rejects a SP in the first byte of the target. It does skip extra SP between the target and the version. The disagreement is the gap after the method.

Chain: both fronts write one SP on the upstream request line (`src/http/modules/ngx_http_proxy_module.c` lines 1434-1435; `src/h1_htx.c` lines 1059-1062). The origin sees one SP. **LOW. NOT-PAYABLE** on both edges.

### R07-HTAB-SEPARATOR

RFC 9112 §3 MAY treat HTAB as whitespace in place of the SP separator, or reject the message.

nginx **STRICTER-THAN-RFC**. Only SP ends the method. HTAB is not a request-line separator (`src/http/ngx_http_parse.c` lines 276-278 and 298-303).

HAProxy **CONFORMS** (uses the MAY). HTAB is in the SP/HTAB class (`src/http.c` line 38), so HTAB is a request-line separator in the states under R06.

Origin **STRICTER-THAN-RFC**. The origin's method/target split looks for SP. HTAB is not accepted as that separator.

Chain: the upstream line has one SP (R06). The origin does not see a client HTAB separator. **LOW. NOT-PAYABLE** on both edges.

### R08-VERSION-GRAMMAR

RFC 9112 §2.3: HTTP-version is `HTTP/` plus one digit, a dot, and one digit, case-sensitive.

nginx **LENIENT** on the minor digit. The parser accepts further minor digits until the minor value exceeds 99 (`src/http/ngx_http_parse.c` lines 754-762). A minor version with more than one digit does not match the one-digit grammar. No cited directive restricts the token to one minor digit.

HAProxy **CONFORMS** on the default path. After the parser accepts version characters, the post-check rejects a length other than 8 and rejects a token that is not `HTTP/`, a digit, a dot, and a digit (`src/h1_htx.c` lines 57-66). The option `accept-unsafe-violations-in-http-request` turns that shape failure into a non-reject. That option is off in the scored default (`src/mux_h1.c` lines 1006-1007).

Origin **CONFORMS**. The origin accepts only the two tokens `HTTP/1.0` and `HTTP/1.1`. Any other version token is rejected.

Chain: nginx writes the static `HTTP/1.0` or `HTTP/1.1` string (`src/http/modules/ngx_http_proxy_module.c` lines 838-839 and 1468-1475). HAProxy, when the HTTP/1.1 flag is set, writes the literal `HTTP/1.1` (`src/h1_htx.c` lines 1065-1067). The origin does not see a multi-digit client version. **LOW. NOT-PAYABLE** on both edges.

### R09-MISSING-VERSION

RFC 9112 §3 includes the version in the request line. A line that does not match, aside from the robustness exceptions, SHOULD be answered with 400.

nginx **LENIENT** for GET. If the target is followed by CR or LF with no version token, the parser records a version-less line and accepts it when the method is GET (`src/http/ngx_http_parse.c` lines 807-809). For that version the header block is not read (`src/http/ngx_http_request.c` lines 1195-1205). No configuration directive that disables this was found in the pinned tree.

HAProxy **CONFORMS** (rejects) on the default path. An empty version fails the length test in the post-check (`src/h1_htx.c` lines 57-59). The version-less conversion runs only when the unsafe-violations option is on (lines 67-80). That option is off.

Origin **CONFORMS**. The origin requires an 8-byte version token. A missing version is rejected.

Chain: both rebuilt request lines include a version (R08). **LOW. NOT-PAYABLE** on both edges.

### R10-WS-BEFORE-COLON

RFC 9112 §5.1: a server MUST reject a request that has whitespace between a field name and the colon, with status 400.

nginx **CONFORMS**. In the name state, a character `<= 0x20` returns an invalid header (`src/http/ngx_http_parse.c` lines 962-964). The same test rejects a line that begins with SP or HTAB (lines 893-895). The header processor finalizes that as 400 (`src/http/ngx_http_request.c` lines 1565-1572).

HAProxy **CONFORMS** on the default path. In the name state, a byte that is not a token and not a colon is invalid when the strict error position is in force (`src/h1.c` lines 804-827). SP and HTAB are not tokens (`src/http.c` line 38). The unsafe-violations option stops this being a reject. That option is off.

Origin **CONFORMS**. The first of colon, SP, or HTAB must be a colon. Whitespace before the colon is rejected with 400.

Chain: both fronts reject on the scored default. **LOW. NOT-PAYABLE** on both edges.

### R11-OBS-FOLD

RFC 9112 §5.2: a server that receives obsolete line folding in a request MUST either send 400 or replace each fold with SP before interpreting or forwarding the field value.

nginx **CONFORMS** (rejects). A continuation line starts with SP or HTAB, which is rejected at the start of a line (`src/http/ngx_http_parse.c` lines 893-895). There is no unfold state.

HAProxy **CONFORMS** (replaces). After a header value's CR LF, a following SP or HTAB is a continuation: the CR and LF are replaced with SP and the parser returns to the value (`src/h1.c` lines 929-937). The value is trimmed only after that replacement (lines 949-958).

Origin **CONFORMS** (rejects). The origin has no unfold path. A continuation line fails the colon test in R10 and is rejected.

Chain, nginx: both reject. **LOW. NOT-PAYABLE.**

Chain, HAProxy: the origin sees one field line, already unfolded (`src/h1_htx.c` lines 1147-1150). **LOW. NOT-PAYABLE.**

### R12-OWS-SP

RFC 9112 §5.1: optional whitespace before the first non-whitespace octet of the field value, and after the last, is excluded from the value. RFC 9110 §5.6.3 defines that whitespace as SP or HTAB. The HTAB half is R13.

nginx **CONFORMS** for SP. The state before the value skips SP (`src/http/ngx_http_parse.c` lines 972-975). The state after the value skips trailing SP (lines 1016-1019).

HAProxy **CONFORMS**. Leading and trailing bytes for which the linear-whitespace test is true are removed before the value is stored (`src/h1.c` lines 949-958). SP is in that class.

Origin **CONFORMS**. The origin removes one run of leading SP or HTAB and one run of trailing SP or HTAB.

Chain: both sides exclude SP. **LOW. NOT-PAYABLE** on both edges.

### R13-OWS-HTAB

Same exclusion rule as R12. HTAB is optional whitespace (RFC 9110 §5.6.3).

nginx **LENIENT**. The skip states test SP only. A HTAB falls into the default arm, so a leading HTAB starts the value and a trailing HTAB stays inside it (`src/http/ngx_http_parse.c` lines 988-991 and 1028-1030). `ignore_invalid_headers` does not apply.

HAProxy **CONFORMS**. HTAB carries the linear-whitespace flag (`src/http.c` line 38), so the trim at `src/h1.c` lines 949-958 removes a leading or trailing HTAB. The stored value does not keep it.

Origin **CONFORMS**. The origin's trim includes HTAB, so a leading or trailing HTAB is not part of the extracted value.

Chain, nginx: **MEDIUM. PAYABLE.** With `proxy_pass_request_headers` at its default of on, the stored value is copied (`src/http/modules/ngx_http_proxy_module.c` lines 1549-1556 and 3936-3937). The origin's trim removes the HTAB, so the two parsers extract different values from a request the origin actually parses. This is not HIGH. Host, Content-Length, and Transfer-Encoding do not pass a HTAB through nginx. Host fails validation when the character is `<= 0x20` (`src/http/ngx_http_request.c` lines 2225-2226). Content-Length fails the digit parser (`src/core/ngx_string.c` lines 1083-1100). Transfer-Encoding fails the seven-byte `chunked` test (`src/http/ngx_http_request.c` lines 2026-2039). Those client messages are rejected before `proxy_pass`. MEDIUM is other field values. The difference is not a published advisory on nginx 1.28.3, so the disposition rule marks the row PAYABLE. `SKEPTIC.md` argues the weight of that label. It does not change it.

Chain, HAProxy: the value copied upstream does not contain the HTAB. **LOW. NOT-PAYABLE.**

### R14-NO-COLON

RFC 9112 §5: a field line includes a colon. A message that does not match, aside from the listed robustness exceptions, SHOULD be answered with 400.

nginx **LENIENT**. In the name state, CR or LF closes the name and sets an empty value without requiring a colon (`src/http/ngx_http_parse.c` lines 937-949). If the name characters were otherwise valid, the line is stored (`src/http/ngx_http_request.c` lines 1476-1527). No cited directive rejects a missing colon.

HAProxy **CONFORMS** (rejects). A header line that reaches LF while still in the name state is invalid (`src/h1.c` lines 824-827). An empty name is invalid (lines 815-819).

Origin **CONFORMS**. A field line with no colon is rejected.

Chain, nginx: the proxy writer emits colon and SP before the stored value (`src/http/modules/ngx_http_proxy_module.c` lines 1551-1554). The origin sees a colon. **LOW. NOT-PAYABLE.**

Chain, HAProxy: both reject. **LOW. NOT-PAYABLE.**

### R15-HOST

RFC 9112 §3.2: a server MUST answer 400 to an HTTP/1.1 request that lacks a Host field, to any request with more than one Host field line, and to a Host value that is invalid.

nginx **CONFORMS**. A duplicate Host is 400 (`src/http/ngx_http_request.c` lines 1854-1861). A missing Host on a version greater than HTTP/1.0 is 400 (lines 1997-2001). An invalid Host is 400 (lines 1871-1875 and 2225-2226). HTTP/1.0 may omit Host.

HAProxy **LENIENT** on a missing Host. Two Host values that differ are invalid, and two Host values that compare equal are not stored twice (`src/h1.c` lines 1030-1046). A missing HTTP/1.1 Host is not rejected by the header parser or by the post-parse step, and the server mux does not insert one (`src/mux_h1.c` lines 2857-2954).

Origin **CONFORMS**. An HTTP/1.1 request with no Host is rejected with 400, and keep-alive on that connection is cleared, so the accept loop does not parse another request. More than one Host line is also 400. HTTP/1.0 may omit Host.

Chain, nginx: the accept/reject rule on the client message agrees. The default upstream Host is the proxy host variable, not a second reading of the client Host (`src/http/modules/ngx_http_proxy_module.c` line 843). **LOW. NOT-PAYABLE.**

Chain, HAProxy: a missing Host does reach the origin. The origin answers 400 and clears keep-alive. An equal duplicate is dropped by HAProxy before the server mux, so the origin sees one Host line. A differing duplicate is rejected by HAProxy first. The missing-Host case is an origin 400, not a second delimiting of a length field. **LOW. NOT-PAYABLE.** `SKEPTIC.md` tries to raise it.

Character-by-character equality of the two Host validators is unsupported. The 400 rules above are the scored rules.

### R16-CL-REPEAT

RFC 9110 §5.2 combines repeated field lines. RFC 9112 §6.3 item 5: differing Content-Length values are an unrecoverable error; a list of identical valid values may be used as that single value.

nginx **STRICTER-THAN-RFC**. Content-Length is a unique header. A second field line is 400 without comparing the two values (`src/http/ngx_http_request.c` lines 106-108 and 1830-1843). Identical duplicates are rejected, which is stricter than the identical-list exception.

HAProxy **CONFORMS**. A later value that differs is rejected. A later identical value can be dropped (`src/http.c` lines 829-853; `src/h1.c` lines 1000-1011).

Origin **STRICTER-THAN-RFC**. A second Content-Length field is rejected as soon as one is already set, including when the values match.

Chain, nginx: the upstream Content-Length is the internal body length, and the client field is not copied (`src/http/modules/ngx_http_proxy_module.c` lines 845-846 and 1407-1410). **LOW. NOT-PAYABLE.**

Chain, HAProxy: the server mux emits at most one Content-Length, and skips it when the message is chunked (`src/mux_h1.c` lines 2689-2704). The origin sees one length field or none. **LOW. NOT-PAYABLE.**

### R17-CL-DIGITS

RFC 9112 §6.2 and §6.3 item 5: Content-Length is a decimal number of octets. An invalid value is an unrecoverable error.

nginx **CONFORMS**. The digit parser returns an error on an empty span, on any byte outside `0`–`9`, and on overflow (`src/core/ngx_string.c` lines 1083-1100). The caller sends 400 (`src/http/ngx_http_request.c` lines 2004-2014).

HAProxy **CONFORMS**. The parser accepts only `0`–`9` after optional whitespace, rejects a leading plus sign or any other non-digit, rejects overflow, and strips leading zeros from the value it stores (`src/http.c` lines 786-835).

Origin **CONFORMS**. The length parser must consume the whole value, and the value must be non-negative. Otherwise the origin rejects the field. Whether that parser accepts a leading plus sign is unsupported. It is not a scored disagreement. On the HAProxy edge, leading zeros are stripped before the value is stored, so the origin does not see them.

Chain: **LOW. NOT-PAYABLE** on both edges.

### R18-CL-AND-TE

RFC 9112 §6.1: a server MAY reject a request that contains both Content-Length and Transfer-Encoding, or process it in accordance with Transfer-Encoding alone. Regardless, the server MUST close the connection after responding. Section 6.3 item 3 says an intermediary that forwards the message MUST remove Content-Length first. "Ought to be handled as an error" in that item is not a requirement to reject.

nginx **CONFORMS** (reject). When the Transfer-Encoding value is exactly `chunked` and Content-Length is also set, the function finalizes 400 (`src/http/ngx_http_request.c` lines 2030-2036). The request object is zero-filled (lines 578-580), and this return happens before keep-alive is assigned (`src/http/ngx_http_core_module.c` lines 833-836). The 400 response path also clears keep-alive if it was set (`src/http/ngx_http_special_response.c` lines 428-438). There is no cited directive that skips the 400.

HAProxy **CONFORMS** (process Transfer-Encoding, remove Content-Length, close by default). When both are present, the parser clears the length flag, zeroes the length, sets close unless `h1-do-not-close-on-insecure-transfer-encoding` is set, and deletes every Content-Length field (`src/h1.c` lines 24-28 and 1191-1201). The global that skips the close starts at 0 (line 28).

Origin **CONFORMS** (process Transfer-Encoding, close by default). When the final coding is chunked, the origin frames the body as chunked, copies the length text onto a header named `X-Content-Length`, clears the length field, and clears keep-alive unless `Microsoft.AspNetCore.Server.Kestrel.AllowKeepAliveAfterCLTE` is enabled. The default is the process branch plus close, which is the other half of RFC 9112 §6.1.

Chain, nginx: the client message does not reach `proxy_pass`. **LOW. NOT-PAYABLE.** Scoring this row HIGH would be wrong. `SKEPTIC.md` says why.

Chain, HAProxy: the server mux writes `transfer-encoding: chunked` and does not write the removed Content-Length (`src/mux_h1.c` lines 2679-2704). The origin does not see the client pair. **LOW. NOT-PAYABLE.**

### R19-TE-HTTP10

RFC 9112 §6.1: a server that receives an HTTP/1.0 message containing Transfer-Encoding MUST treat the framing as faulty, even if Content-Length is present, and close the connection after processing.

nginx **CONFORMS**. If Transfer-Encoding is set and the version is below HTTP/1.1, the function finalizes 400 (`src/http/ngx_http_request.c` lines 2017-2023).

HAProxy **CONFORMS** (process, then close). The parser does not reject the message. If Transfer-Encoding is present and the HTTP/1.1 flag is clear, it sets close (`src/h1.c` lines 1202-1204). On output, Transfer-Encoding without that flag forces the server stream to close mode and does not add a keep-alive connection token (`src/mux_h1.c` lines 2867-2870 and 1681-1691).

Origin **LENIENT**. The body selector accepts Transfer-Encoding with no version test. Keep-alive starts false for HTTP/1.0 and can be turned on by a keep-alive connection token. The keep-alive clear described in R18 runs only when Content-Length is also present. An HTTP/1.0 message with Transfer-Encoding and no Content-Length is not rejected by that selector. No origin switch for this reject was found.

Chain, nginx: the 400 happens before any upstream write. **LOW. NOT-PAYABLE.** Direct exposure of the origin is H19.

Chain, HAProxy: the origin sees HTTP/1.0 without a keep-alive token, because the server mux closed the server side. **LOW. NOT-PAYABLE** on this chain. Direct exposure of the origin is H19.

### R20-TE-FINAL

RFC 9112 §6.3: if a request has Transfer-Encoding and chunked is not the final coding, the server MUST respond with 400 and close. A coding the server does not understand SHOULD get 501. A final chunked coding is valid framing even when an earlier coding is present.

nginx **CONFORMS** to the unknown-coding SHOULD, and it is stricter than framing by a final chunked coding. The value length must be 7 and the value must match `chunked` (`src/http/ngx_http_request.c` lines 2026-2039). Any other value, including a longer list, is finalized as 501 (lines 2041-2046). The sealed label for this row is CONFORMS. The 501 happens before `proxy_pass`.

HAProxy **STRICTER-THAN-RFC** for a request that carries any transfer-coding other than a single chunked coding, including a coding before a final chunked coding. The mux rejects the message when that other coding is set and uses status 422 (`src/mux_h1.c` lines 2036-2049). The 422 happens before the body is forwarded.

Origin **CONFORMS**. The origin keeps the last transfer-coding token. A final token that is not chunked is rejected. A list whose final token is chunked is accepted.

Chain: the front rejects before the origin sees the client coding list. **LOW. NOT-PAYABLE** on both edges.

### R21-TE-REPEAT

RFC 9110 §5.2–§5.3: a recipient MAY combine field lines with the same name. The combined value is then subject to R20.

nginx **STRICTER-THAN-RFC**. Transfer-Encoding is a unique header. A second field line is 400 (`src/http/ngx_http_request.c` lines 125-127 and 1830-1843).

HAProxy **STRICTER-THAN-RFC**. A second `chunked` token is rejected (`src/h1.c` lines 79-87). The message does not reach the server mux.

Origin **CONFORMS**. Another Transfer-Encoding field is appended, and the final-token walk includes every entry.

Chain: the client field lines do not reach the origin. The upstream Transfer-Encoding is the front's own token (nginx: `src/http/modules/ngx_http_proxy_module.c` lines 845-846). **LOW. NOT-PAYABLE** on both edges.

### R22-CHUNK-CRLF

RFC 9112 §7.1 uses CR LF after the chunk size. The bare-LF MAY in §2.2 is not stated for chunk lines.

nginx **LENIENT** for a bare LF on a chunk-size line, and **CONFORMS** for a bare CR. The chunk-size state accepts LF as the end of the size line (`src/http/ngx_http_parse.c` lines 2242-2243). CR moves to a state that requires LF (lines 2239-2240 and 2266-2271). No cited directive selects CR LF only.

HAProxy **CONFORMS** (requires CR LF). The chunk-size parser accepts CR only when the next byte is LF (`include/haproxy/h1.h` lines 309-366). The output formatter writes its own hex size and CR LF (`src/h1_htx.c` lines 1169-1185).

Origin **CONFORMS**. A chunk-size line completes on CR followed by LF. The chunk suffix requires the same pair. With `Microsoft.AspNetCore.Server.Kestrel.EnableInsecureChunkedRequestParsing` unset, the extension path also requires CR LF. The line-feed switch in R02 does not apply to the chunk parser.

Chain, nginx: default `proxy_request_buffering` is on, so the origin receives a body length from nginx rather than the client chunk-size line. With buffering off and `proxy_http_version 1.1`, the output filter still writes its own hex size and CR LF (`src/http/modules/ngx_http_proxy_module.c` lines 1035-1041 and 1762). **LOW. NOT-PAYABLE.**

Chain, HAProxy: the origin parses HAProxy's chunk envelope, not the client's. **LOW. NOT-PAYABLE.**

### R23-CHUNK-EXT

RFC 9112 §7.1.1: a recipient MUST ignore unrecognized chunk extensions. A limit on their total length is stated as an ought, not as a requirement scored here.

nginx **CONFORMS**. The extension state does not inspect extension bytes except CR and LF (`src/http/ngx_http_parse.c` lines 2256-2264). A dedicated extension-length cap inside the chunk parser was not found.

HAProxy **CONFORMS** (ignores the extension octets, and can reject a bad quote). A semicolon starts an extension scan (`include/haproxy/h1.h` lines 325-363). A reject is not forwarded. An accept is re-chunked without the extension.

Origin **CONFORMS**. The origin does not check extension token grammar. It searches for the line ending. A separate extension-length cap is unsupported.

Chain: the line-ending split is R22. The origin does not parse the client extension. **LOW. NOT-PAYABLE** on both edges.

### R24-CHUNK-OVERFLOW

RFC 9112 §7.1: recipients MUST prevent integer overflow or precision loss on large hex numerals.

nginx **CONFORMS**. The chunk-size state rejects a value that would overflow the signed offset type before multiplying (`src/http/ngx_http_parse.c` lines 2197-2200 and 2363-2365). An invalid chunk parse becomes 400 (`src/http/ngx_http_request_body.c` lines 1253-1258).

HAProxy **CONFORMS**. The accumulator stops when the value would exceed the 13-digit guard (`include/haproxy/h1.h` lines 285-290).

Origin **CONFORMS**. The chunk-size prefix loop stops at 10 bytes. A non-hex byte and an overflow are rejected. The ceiling differs from each front.

Chain: the origin sees the size of the data the front copied, not the client's hex text (R22). **LOW. NOT-PAYABLE** on both edges.

### R25-TRAILER-FRAMING

RFC 9112 §7.1: chunked is complete at a zero-size chunk, an optional trailer section, and a final empty line. Trailer lines use field-line syntax.

nginx **CONFORMS**. A zero chunk moves into trailer processing when trailers are not being kept, and an empty trailer line finishes the body (`src/http/ngx_http_parse.c` lines 2214-2225 and 2320-2326). The request-body caller does not keep trailers (`src/http/ngx_http_request_body.c` lines 873 and 1134).

HAProxy **CONFORMS**. A zero size selects the trailer state. Trailer lines are parsed with the header parser (`src/h1_htx.c` lines 991-1014). By default they are written again on a chunked upstream request unless `option http-drop-request-trailers` is set (`src/mux_h1.c` lines 3483-3486; `src/proxy.c` line 116).

Origin **CONFORMS**. The origin consumes a trailer section with the same header parser before the chunked body is complete.

Chain: the trailer lines the origin parses are the front's rewritten lines, not the client trailer block. **LOW. NOT-PAYABLE** on both edges.

## Unsupported

- Whether the origin's decimal parser accepts a leading plus sign in Content-Length (R17).
- The origin's numeric defaults for the request-line limit, the header-size limit, the header-count limit, and the body-size limit. Size caps are not a second framing rule. Set them explicitly; this oracle does not cite framework default integers.
- Host-character equality beyond the 400 rules in R15.
- nginx `stream`, HAProxy `mode tcp`, or any front that does not parse the HTTP/1 request.
- A dedicated chunk-extension length cap (R23).
- HAProxy `tune.bufsize` and `tune.http.maxhdr` numeric defaults.
- HTTP/2 and HTTP/3.
- A socket-level observation that the origin's 400 is followed by a TCP close. The HAProxy R15 rating uses the keep-alive flag and the accept loop. The TCP close was not observed. That is why the row is not NEEDS-LIVE: the static cites decide the risk, and the missing observation is recorded here.
