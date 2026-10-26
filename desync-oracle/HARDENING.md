# Hardening checklist

Operator checklist for nginx 1.28.3 `proxy_pass`, and for HAProxy 3.4.7 `mode http`, in front of Kestrel 10.0.12 / 10.0.13. Each item cites `CONFORMANCE-MAP.md` or the public source that file cites. This list does not contain request samples.

The only MEDIUM chain row is nginx R13. The HAProxy edge has no MEDIUM row and no HIGH row. Several entries say that the pinned tree has no directive that changes the parser. That is a residual, not a hidden setting.

## H-ARCH — keep the HTTP proxy, or the LOW ratings do not apply

**nginx.** The chain column is true for `ngx_http_proxy_module`'s `proxy_pass`, which builds a new request line and replaces Content-Length and Transfer-Encoding (`src/http/modules/ngx_http_proxy_module.c` lines 838-851, 1432-1475, and 1549-1556).

A front that forwards client bytes without `ngx_http_parse_request_line` was not read. `ngx_stream` is unsupported. Do not treat the LOW ratings as covering a TCP proxy, a `stream` pass-through, or Kestrel published on its own.

Concrete check: the Kestrel upstream is a `location` with `proxy_pass`, `proxy_request_buffering` left on (default 1, lines 3701-3702), and the default header table still supplies Content-Length and Transfer-Encoding (lines 845-846). Do not replace those two with the raw client field values. The client case of both length fields never reaches this table anyway (H-DEFAULTS), but replacing the table is how a later edit would undo the rebuild.

**HAProxy.** The chain column is true for the HTTP/1 mux in `mode http`, which parses the client bytes and writes a new request line, new header lines, and a new body framing (`src/h1_htx.c` lines 1053-1074 and 1147-1150; `src/mux_h1.c` lines 2679-2704 and 3095-3108).

A front that forwards client bytes without the HTTP/1 header parser was not read. `mode tcp` is unsupported. Do not treat the LOW ratings as covering a TCP proxy or Kestrel published on its own.

Concrete check: the Kestrel server is reached from a `backend` in `mode http`, the default HTTP mode mask is still keep-alive (`include/haproxy/proxy-t.h` lines 112-115), and the server mux is still the one that rewrites `transfer-encoding` to `chunked` and skips a Content-Length that the parser removed. Do not replace that mux with a raw byte path.

## H13 — R13, HTAB in field values

**nginx (MEDIUM, the only row that forces HARDENING-REQUIRED).** nginx keeps a leading or trailing HTAB in the stored field value. The origin excludes HTAB as optional whitespace. Default `proxy_pass_request_headers on` copies nginx's value.

There is no cited core directive that strips or rejects HTAB inside a field value. `ignore_invalid_headers` does not apply.

What an operator can do with directives that exist:

1. Leave Host, Content-Length, and Transfer-Encoding on nginx's own checks. Those three do not forward a HTAB. Do not `proxy_set_header` them from the raw client field.
2. If the application does not need client headers, set `proxy_pass_request_headers off` (`src/http/modules/ngx_http_proxy_module.c` lines 452-456 for the directive and 3936-3937 for the default of 1). The copy loop at lines 1527-1561 does not run, so the HTAB value is not sent. The cost is that no client field other than the default proxy header list is sent.
3. If client headers are required, make allow or deny decisions that depend on those values at the origin, after the origin has trimmed optional whitespace. nginx's copy still contains the HTAB. There is no stock directive that makes the two extracted values match.

This item cannot be closed by a parser flag in the pinned nginx tree. `SKEPTIC.md` argues that this is why H13 is a weak reason to call the body-framing chain broken. The sealed score still marks the row MEDIUM.

**HAProxy (LOW).** HAProxy removes a leading or trailing HTAB before the value is stored. The origin removes it too. There is nothing to set. Leave the default parser in place. Do not add an `http-request set-header` that copies a raw client value back onto the upstream request.

## H15 — R15, missing Host (HAProxy)

HAProxy forwards an HTTP/1.1 request that has no Host. The origin rejects it and clears keep-alive. That is why the row is LOW, and it is still a 400 the application will see.

What an operator can do with directives that exist:

1. Deny a request that has no Host before it is forwarded, with an `http-request deny` rule whose sample is the Host header. The exact sample syntax was not read as a separate rule in this oracle. The absence of an automatic 400 is what R15 cites.
2. If the application requires a Host, set one explicitly with `http-request set-header` only when the operator has chosen the value. This audit did not find a default that inserts Host (`src/mux_h1.c` lines 2857-2954).
3. Do not publish the Kestrel port as a second public HTTP listener. The 400 is the origin's check. HAProxy is not doing it.

nginx already rejects a missing or duplicate Host (R15). No extra nginx directive is required for that row.

## H04 — R04, extra CR on a header line (nginx)

nginx consumes an extra CR while the header line is already past its first CR. The origin rejects it. No directive was found that changes that state.

The chain stays LOW because `proxy_pass` writes a new CR LF (H-ARCH). Residual: the client-facing parser stays lenient. Closing it requires a build change that this audit did not write. Do not remove `proxy_pass`.

HAProxy rejects this CR. No HAProxy action.

## H05 — R05, leading CR and LF

nginx and the origin both discard a run of CR and LF before the request line. They agree. No nginx directive disables the skip. No origin switch disables it. No chain action.

HAProxy rejects a bare CR before the request line. The origin skips it. The chain stays LOW because HAProxy does not forward that message. No directive was found that makes HAProxy skip the bare CR. No chain action.

## H08 — R08, more than one minor version digit (nginx)

nginx accepts a minor version past one digit until the value exceeds 99. The origin accepts only `HTTP/1.0` and `HTTP/1.1`. No nginx directive restricts the version token.

Chain stays LOW because the upstream line is `HTTP/1.0` or `HTTP/1.1` (`src/http/modules/ngx_http_proxy_module.c` lines 838-839). Leave `proxy_http_version` at `1.0` (default, lines 4056-4057) or set `1.1`. Both strings match the origin's two accepted tokens. Do not expect the client-facing parser to match the origin. The pinned source has no such switch.

HAProxy's default post-check already requires one digit, a dot, and one digit. Leave `option accept-unsafe-violations-in-http-request` unset (H-DEFAULTS).

## H09 — R09, version-less GET (nginx)

nginx accepts a GET with no HTTP-version and does not read a header block. The origin rejects a missing version. No directive that disables the nginx acceptance was found in 1.28.3.

Chain stays LOW because a proxied upstream line includes a version (H08). Residual is client-facing.

HAProxy rejects a missing version on the default path. The unsafe-violations option is what turns that into an acceptance. Leave it unset.

## H14 — R14, field line with no colon (nginx)

nginx stores the line. The origin rejects it. The proxy writer inserts colon and SP (`src/http/modules/ngx_http_proxy_module.c` lines 1551-1554), so the origin sees a colon. No directive rejects the client line.

Same residual as H04: client-facing only, chain LOW while H-ARCH holds. `proxy_pass_request_headers off` (H13) also stops that stored field from being copied.

HAProxy rejects a field line with no colon. No HAProxy action.

## H22 — R22, bare LF on chunk lines (nginx)

nginx accepts LF as the end of a chunk-size line. The origin's chunk-size, suffix, and default extension paths require CR LF. No nginx directive selects CR LF-only chunks.

Keep:

- `proxy_request_buffering on` (default). The origin then does not parse the client chunk-size line.
- If buffering is turned off, keep the body on nginx's output filter, which writes its own CR LF (`src/http/modules/ngx_http_proxy_module.c` line 1762). That is still not the client chunk line.
- On the origin, leave `Microsoft.AspNetCore.Server.Kestrel.EnableInsecureChunkedRequestParsing` unset. Enabling it relaxes the extension terminator and moves the origin away from CR LF, which is the wrong direction for this row.

`Microsoft.AspNetCore.Server.Kestrel.DisableHttp1LineFeedTerminators` does not apply to the chunk parser. It is the request-line and header-line control (R02).

HAProxy already requires CR LF on a chunk-size line and writes its own chunk envelope. No HAProxy action for this row.

## H19 — R19, Transfer-Encoding on HTTP/1.0

nginx already answers 400. HAProxy forces close on the server side and does not add a keep-alive connection token. The origin's body selector still has no version test. No origin switch for this reject was found.

The chain is LOW only while the HTTP front named in H-ARCH is the only public listener. If any listener reaches Kestrel without that front, the leniency is still there. The remediation is the front, not an origin flag. Do not publish the Kestrel port as a second public HTTP listener.

## H-DEFAULTS — confirm the rejects and the rebuild that are already in the binary

These are not new settings. They are how the pinned builds already behave. The check is that the deployment has not been edited or wrapped in a way that skips them.

### nginx 1.28.3

| Check | Why | Cite |
| --- | --- | --- |
| Content-Length and Transfer-Encoding together are 400 inside request-header processing | RFC 9112 §6.1 allows reject. nginx takes it. There is no directive to turn the 400 off. | `src/http/ngx_http_request.c` lines 2030-2036 |
| HTTP/1.0 plus Transfer-Encoding is 400 | R19. | `src/http/ngx_http_request.c` lines 2017-2023 |
| Duplicate Content-Length, Transfer-Encoding, and Host are 400 | R16, R21, R15. | `src/http/ngx_http_request.c` lines 106-108, 125-127, 1830-1843, 1854-1861 |
| `ignore_invalid_headers on` | Default 1. Drops soft-invalid field names. Turning it off stores them. It does not create a 400. | `src/http/ngx_http_core_module.c` lines 3517-3518; `src/http/ngx_http_request.c` lines 1480-1488 |
| `underscores_in_headers off` | Default 0. An underscore then marks the field soft-invalid, and the default ignore drops it. | `src/http/ngx_http_core_module.c` lines 3522-3523 |
| `client_max_body_size` | Default 1 MiB. Set it explicitly to the application limit. Chunk data is checked against it. | `src/http/ngx_http_core_module.c` lines 3800-3801; `src/http/ngx_http_request_body.c` lines 1142-1154 |
| Header buffer limits | `client_header_buffer_size` 1k, `large_client_header_buffers` 4 8k, `client_header_timeout` 60s. | `src/http/ngx_http_core_module.c` lines 3502-3508 |

### HAProxy 3.4.7

| Check | Why | Cite |
| --- | --- | --- |
| Do not set `option accept-unsafe-violations-in-http-request` | Version shape, missing version, and whitespace before a colon stop being rejects. | `src/mux_h1.c` lines 1006-1007; `src/proxy.c` line 146 |
| Do not set `h1-do-not-close-on-insecure-transfer-encoding` | Content-Length is still removed, but the close flag is not set. | `src/h1.c` lines 24-28 and 1191-1200 |
| Content-Length together with Transfer-Encoding is removed, and the body is chunked | RFC 9112 §6.1 allows that branch. The server mux does not copy the client Content-Length. | `src/mux_h1.c` lines 2679-2704 |
| A transfer-coding other than chunked is 422 | R20. The status is set before the body is forwarded. | `src/mux_h1.c` lines 2036-2049 |
| `option http-drop-request-trailers` left unset | Default forwards rewritten trailer lines. Turning it on drops them. Either is one framing, not two. | `src/proxy.c` line 116; `src/mux_h1.c` lines 3483-3486 |

### Origin, any listener that is not behind one of these fronts

| Check | Why |
| --- | --- |
| Do not set `Microsoft.AspNetCore.Server.Kestrel.AllowKeepAliveAfterCLTE` | If Kestrel is reached directly, the default clears keep-alive after the process-Transfer-Encoding branch. The switch keeps the connection up, which drops the requirement to close. |
| Optional: `Microsoft.AspNetCore.Server.Kestrel.DisableHttp1LineFeedTerminators` | Makes the origin reject a bare LF on the request line and on header lines (R02). It does not change chunk lines (H22) and it does not change the proxied bytes, which are already CR LF. Use it when a listener exists that is not one of these two fronts. |
| Do not set `Microsoft.AspNetCore.Server.Kestrel.EnableInsecureChunkedRequestParsing` | See H22. |
| Set `MaxRequestLineSize`, `MaxRequestHeadersTotalSize`, and `MaxRequestBodySize` in the app to values the operator has written down | This oracle cannot cite the framework default integers. |

## What this checklist does not claim

- It does not claim a directive that makes nginx's client-facing parser match the origin on R04, R08, R09, R14, or R22. Those rows stay lenient on the client socket.
- It does not claim a directive that makes HAProxy reject a missing Host. H15 is an operator rule, not a parser flag found in the cited mux.
- It does not claim nginx 1.30, or HAProxy 3.5, 3.2, or 2.8. Those tarballs were not read.
- It does not retune the sealed score. nginx R13 stays MEDIUM after H13, because H13 does not make the two parsers extract the same HTAB value unless client headers are not forwarded at all. HAProxy R15 stays LOW after H15, because H15 is optional and the origin path already clears keep-alive.
