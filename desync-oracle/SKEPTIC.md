# Skeptic

Adversarial pass on the sealed score. The score was not edited after this file was written. The aim is to knock down the nginx HARDENING-REQUIRED verdict, to knock down the HAProxy GO, and to test the claim that would have been tempting and is scored LOW.

Origin statements below are behaviour. They do not cite origin source lines.

## nginx: R13 is MEDIUM, so the audit is HARDENING-REQUIRED

The sealed reason for HARDENING-REQUIRED is only R13 (`VERDICT.md`). The claim is: nginx keeps a leading or trailing HTAB in the field value, `proxy_pass_request_headers` copies it, and the origin's optional-whitespace trim removes it, so the tiers disagree on a request the origin actually parses.

### Knock-down

1. **It is not a body-length disagreement.** Content-Length, Transfer-Encoding, and Host do not survive a HTAB inside nginx. `CONFORMANCE-MAP.md` R13 cites `ngx_http_validate_host` (`src/http/ngx_http_request.c` lines 2225-2226), the digit-only length parser (`src/core/ngx_string.c` lines 1083-1100), and the seven-byte `chunked` test (`src/http/ngx_http_request.c` lines 2026-2039). Those client messages are 400 or 501 before `proxy_pass`. The MEDIUM residue is some other field. Message framing, in the sense of where the body ends, does not change.

2. **The RFC already says this.** RFC 9112 §5.1 says optional whitespace is excluded from the field value. RFC 9110 §5.6.3 defines that whitespace as SP or HTAB. A difference here is a failure to follow published extraction text. It is not a new rule, and CWE-444 already names the class of inconsistent interpretation. Calling the deliverable a new finding overclaims it.

3. **The checklist cannot close it with a parser setting.** `HARDENING.md` H13 states that no cited directive strips HTAB. `proxy_pass_request_headers off` drops every client field. That avoids the copy. It does not make nginx's parser match the origin. An operator who needs the client fields still has the difference. "HARDENING-REQUIRED" reads as if a config line removes the ambiguity. For R13, the honest sentence is: residual, unless client fields are not forwarded.

4. **If the rubric had been body-delimiting only, the MEDIUM would not exist.** The pre-registered rubric counts a forwarded field-value difference as MEDIUM. That choice, not a body-boundary split, is what forces the verdict word. A rubric that reserved MEDIUM and HIGH for Content-Length, Transfer-Encoding, and the request line would have produced zero such rows, and the verdict word would not have been HARDENING-REQUIRED.

The knock-down succeeds as a criticism of weight. It does not succeed as a claim that the two parsers extract the same bytes. The copy at `src/http/modules/ngx_http_proxy_module.c` lines 1549-1556 is real, and the origin's trim includes HTAB. The row stays MEDIUM because that was the rubric. The disposition stays PAYABLE because the chain risk is MEDIUM and no public advisory on this nginx pin covers the row. The verdict word stays. An operator who wanted a body-framing defect does not have one in the sealed set.

## nginx: the tempting claim that R18 is a chain split

The tempting claim is that the origin frames a message with both Content-Length and Transfer-Encoding as chunked, nginx does something else, and the chain is therefore ambiguous.

It does not survive.

- The normative text is a MAY to reject or to process Transfer-Encoding alone, plus a requirement to close (RFC 9112 §6.1). Section 6.3 item 3 says the message ought to be handled as an error. "Ought" is not a requirement to reject. Labelling the origin non-conformant for taking the process branch would misread the RFC.
- nginx 1.28.3 rejects inside request-header processing when the Transfer-Encoding value is `chunked` and Content-Length is also set (`src/http/ngx_http_request.c` lines 2030-2036). The function finalizes 400 and returns. The proxy request builder is not reached. There is no directive in the cited code that skips this test.
- The request object is zero-filled (`src/http/ngx_http_request.c` lines 578-580). Keep-alive is assigned later, in the HTTP handler (`src/http/ngx_http_core_module.c` lines 833-836), after headers have been accepted. This 400 happens before that assignment. The special-response handler also clears keep-alive for 400 if it was set (`src/http/ngx_http_special_response.c` lines 428-438).
- Even the proxy header table, if it were reached, replaces both fields (`src/http/modules/ngx_http_proxy_module.c` lines 845-846) and skips the client copies (lines 1407-1410). An operator rewrite of the client Content-Length cannot revive a request nginx has already rejected.
- The origin's default still clears keep-alive unless `Microsoft.AspNetCore.Server.Kestrel.AllowKeepAliveAfterCLTE` is enabled. That default is the requirement to close, not an open connection. The switch is the thing to leave off (`HARDENING.md` H-DEFAULTS). It is not evidence that the proxied chain disagrees.

R18 stays LOW. A HIGH label on it would be the error.

## nginx: other LOW rows checked for the same mistake

**R22.** Bare LF on a chunk line is a real parser difference. It would matter if the origin parsed the client chunk-size bytes. Default buffering is on (`src/http/modules/ngx_http_proxy_module.c` lines 3701-3702). With buffering off and `proxy_http_version 1.1`, the body output filter still formats the size and ends the body with its own CR LF (line 1762 and line 1780). The client chunk-size text is not what the origin reads. LOW holds for that configuration too. It would not hold for an unread byte pipe (H-ARCH). That pipe was not scored, and inventing a HIGH for it would be an unsupported claim.

**R19.** The origin's leniency on HTTP/1.0 Transfer-Encoding is real and is the strongest origin-side gap in the set. It is still not a chain split: nginx returns 400 at `src/http/ngx_http_request.c` lines 2017-2023 before any upstream write. The skeptic does not upgrade it to MEDIUM under the proxy rubric. The skeptic does agree that H19 is mandatory if Kestrel has any listener nginx does not front. That is an architecture control, and it is already in the checklist. It is not a second MEDIUM row.

**R08 and R09.** A multi-digit minor version, or a missing version, is accepted by nginx and rejected by the origin. The upstream version token is one of two string literals (`src/http/modules/ngx_http_proxy_module.c` lines 838-839). The origin accepts those same two tokens. The origin does not apply its version check to the client's version token. LOW holds.

## What would falsify the nginx verdict

- A cited directive, missed in `src/http`, that makes nginx exclude HTAB the way the origin does. Then R13's MEDIUM would be an operator miss, and HARDENING-REQUIRED would still be fair, but H13 would name that directive. None was found.
- Evidence that default `proxy_pass` forwards the client Content-Length and Transfer-Encoding bytes unchanged. The cites at `src/http/modules/ngx_http_proxy_module.c` lines 845-846 and at `src/http/ngx_http_request.c` lines 2030-2036 contradict that. If those lines are misread, R18's LOW is wrong.
- A `stream` or similar path in this tarball that is what the deployment actually uses. That path was not read. The verdict would be unsupported for that deployment, not automatically HIGH.

## HAProxy: the audit is GO because no row is MEDIUM or HIGH

The sealed reason for GO is the chain rubric: a rebuilt request that does not carry a length field or a field value the two parsers extract differently stays LOW. The strongest candidate to break that is R15.

### Knock-down of the GO, via R15

1. **The request does reach the origin.** No missing-Host reject was found in the HTTP/1 parser, and the server mux does not insert Host (`src/mux_h1.c` lines 2857-2954). The origin rejects a missing Host on HTTP/1.1. This is not a case of the front answering 400 first.

2. **A 400 is not proof the body was framed the same way.** The origin rejects the missing Host after the header block is parsed and before it builds the message body. If the unread body stayed in the connection buffer and keep-alive stayed on, the next read could treat those bytes as another request. That would be a chain split the rubric calls HIGH.

3. **The checklist cannot close it with a parser setting.** `HARDENING.md` H15 says the automatic 400 was not found. An operator rule is optional. GO reads as if the deployment is already safe. For a missing Host, the honest sentence is: the origin answers 400, and HAProxy will not.

### Why the knock-down does not retune the row

The second point is the one that would change the score, and the origin path answers it. A bad request clears keep-alive. The accept loop continues only while keep-alive is set. The rejection is handled outside that loop, so the loop does not parse another request. The TCP close itself was not observed. That limit is already in the unsupported list of `CONFORMANCE-MAP.md`. It is not a second delimiting of a length field, which is what HIGH requires.

R15 stays LOW. Raising it to MEDIUM would mean changing the rubric after the score, so that "the origin rejects a request the front forwarded" counts as a field-extraction difference. The pre-registered rubric does not say that. This file does not edit the score.

## HAProxy: the tempting claim that R18 is a chain split

The tempting claim is that the origin frames a message with both Content-Length and Transfer-Encoding as chunked, HAProxy does something else, and the chain is therefore ambiguous.

It does not survive.

- The normative text is a MAY to reject or to process Transfer-Encoding alone, plus a requirement to close (RFC 9112 §6.1). Section 6.3 item 3 says an intermediary that forwards the message must remove Content-Length first.
- HAProxy 3.4.7 removes Content-Length, zeroes the length, and by default sets the close flag (`src/h1.c` lines 1191-1201). The global that skips the close starts at 0 (`src/h1.c` line 28).
- The server mux writes `transfer-encoding` as the literal `chunked` only when the chunked flag is set, and skips Content-Length when the length flag is clear (`src/mux_h1.c` lines 2679-2704).
- CVE-2021-40346 is the public integer overflow in `htx_add_header` on 2.0 through 2.5. This pin rejects an over-long name or value before that addition (`include/haproxy/htx.h` lines 511-515). Treating the guard as a new finding would ignore the advisory.

R18 stays LOW. A HIGH label on it would be the error.

## HAProxy: other LOW rows checked for the same mistake

**R13.** On the nginx edge this is the only MEDIUM row, because nginx keeps a leading or trailing HTAB and `proxy_pass` copies it. HAProxy's trim uses the linear-whitespace flag, and HTAB has that flag (`src/http.c` line 38; `src/h1.c` lines 949-958). The origin's trim also includes HTAB. The copied value does not differ. Importing the nginx MEDIUM into this score would be a different front.

**R19.** The origin's leniency on HTTP/1.0 Transfer-Encoding is real and is the strongest origin-side gap in the set. The server-side close is also real (`src/mux_h1.c` lines 2867-2870). The skeptic does not upgrade the row under the proxy rubric. The skeptic does agree that H19 is mandatory if Kestrel has any listener HAProxy does not front. That is an architecture control. It is not a second MEDIUM row.

**R11.** Replacing obsolete line folding with SP is one of the two branches RFC 9112 §5.2 allows. The origin parses the replaced line. A MEDIUM label would require the two parsers to extract different bytes from that replaced line. Both trims then remove only leading and trailing optional whitespace (R12, R13). The skeptic does not have a cited byte that one side keeps and the other drops.

**R22.** A bare LF on a chunk line is rejected by both parsers. Even if HAProxy had accepted it, the output formatter writes its own CR LF (`src/h1_htx.c` lines 1169-1185). The client chunk-size text is not what the origin reads. LOW holds. It would not hold for an unread byte pipe (H-ARCH). That pipe was not scored.

## What would falsify the HAProxy verdict

- A cited HTTP/1 path, missed in `src/h1.c`, `src/h1_htx.c`, and `src/mux_h1.c`, that forwards the client Content-Length and Transfer-Encoding bytes unchanged. The cites at `src/h1.c` lines 1191-1201 and `src/mux_h1.c` lines 2679-2704 contradict that.
- Evidence that a missing-Host rejection does not clear keep-alive. The behaviour used here is that every bad-request failure clears keep-alive, and a missing Host is one of those failures. If that behaviour is wrong, R15's LOW is wrong.
- `option accept-unsafe-violations-in-http-request` or `h1-do-not-close-on-insecure-transfer-encoding` enabled in the deployment. The scored default is both off. The verdict would be unsupported for that deployment, not automatically HIGH.
- A `mode tcp` path that is what the deployment actually uses. That path was not read.

## Result of the pass

The nginx verdict word stands only because R13 is MEDIUM under a field-value rubric. The strongest body-framing claim on that edge (R18 as a chain split) fails, because nginx already rejects that request. The HAProxy GO stands. The strongest raise (R15 as a chain split) fails because the origin leaves the accept loop. The strongest body-framing claim on that edge (R18, including the already-public header-block length overflow) fails because this pin removes Content-Length and still has the length guard. The score was not retuned.
