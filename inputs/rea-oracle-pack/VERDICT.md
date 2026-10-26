# VERDICT — REA oracle pack, static pass

Payable divergence count: **0**.

`gen/desync_gen.py oracle/kestrel-acceptance.jsonl --front h3 --back h1 --confirmed-only` reports `divergences: 0` and `cases: []`. Five CONFIRMED class differences sit in `conformance_only`. Four CONFIRMED rows do not diverge at all. Nothing was forced to `payable_at_boundary: true`.

## Row counts

Oracle file `oracle/kestrel-acceptance.jsonl`:

- CONFIRMED: 9 (OR-001 through OR-009). Confirmed means the h1 and h3 lines were read in the C7@434e35b tree, and the h2 lines where that leg is not `UNKNOWN`.
- PENDING: 0.
- Every `yarp` leg is `UNKNOWN:no-committed-C6-snippet`. Commit 434e35b contains no YARP FINDINGS. That leg is not part of the CONFIRMED claim, and the generator will not assert a divergence that uses it.

Sealed `holdout/holdout.jsonl` was not edited. Its three rows are still `PENDING-EVIDENCE-SYNC`. Scored once into `out/holdout_score_final.json`: `divergences` 0, `conformance_only` HO-01 and HO-03, HO-02 omitted because its h1 verdict is `UNKNOWN`.

## Why nothing is payable

A row is payable only when one leg accepts a field-set the other refuses, the path is the Kestrel default, and a real second hop would disagree about a request that crosses the boundary. Both-reject, both-absent, and a listener difference with no committed forwarder are not payable. Reasoning and line citations are in `SKEPTIC.md`.

Fell short:

- **OR-001** chunked `transfer-encoding`. H1 frames chunked (`evidence/c5/Http1MessageBody.decompiled.cs:135-151`). H3 stores the header and frames DATA against Content-Length (`evidence/c7/Http3Stream.decompiled.cs:831`, `870-886`). Both accept. Not the same bytes. No C6 forwarder.
- **OR-002** `:protocol` on non-CONNECT. H3's must-be-CONNECT throw is behind a default-false AppContext switch (`evidence/c7/KestrelServerOptions.decompiled.cs:109-118`, `evidence/c7/Http3Stream.decompiled.cs:837-845`). H1 has no pseudo-header slot (`evidence/c5/Http1Connection.decompiled.cs:277-309`). `ClearPseudoRequestHeaders` drops the field from enumeration (`evidence/c7/HttpRequestHeaders.decompiled.cs:7569-7572`).
- **OR-003** CR/LF/NUL in a header value. Both live paths reject (`evidence/c5/Http1ParsingHandler.decompiled.cs:31`, `evidence/c5/HttpUtilities.decompiled.cs:129-136`, `evidence/c7/Http3Stream.decompiled.cs:428-431`, `evidence/c7/QPackDecoder.decompiled.cs:642-644`).
- **OR-004** duplicate content-length. Both throw `MultipleContentLengths` before comparing the texts (`evidence/c7/HttpRequestHeaders.decompiled.cs:8440-8444`).
- **OR-005** duplicate or late pseudo-header. H3 rejects (`evidence/c7/Http3Stream.decompiled.cs:468-486`). H1 has no such field. Both refuse.
- **OR-006** trailer CR/LF/NUL. Both use `OnTrailer` with `checkForNewlineChars: true` (`evidence/c5/HttpProtocol.decompiled.cs:1306-1311`).
- **OR-007** Content-Length and no transfer-encoding. Both frame from that length (`evidence/c5/Http1ContentLengthMessageBody.decompiled.cs:256-266`, `evidence/c7/Http3Stream.decompiled.cs:831`, `880-885`, `750-752`).
- **OR-008** literal `te` other than `trailers`. H3 rejects (`evidence/c7/Http3Stream.decompiled.cs:566-577`) and does not forward. H1 stores it on a field that is not the chunked-body bit (`evidence/c5/HttpRequestHeaders.decompiled.cs:7617-7623`, `449`).
- **OR-009** non-chunked `transfer-encoding` and no Content-Length. H1 throws (`evidence/c5/Http1MessageBody.decompiled.cs:135-141`). H3 stores the header and does not chunk-decode (`evidence/c7/Http3Stream.decompiled.cs:566-577`, `831`, `880-886`). Accept-versus-reject, killed because no committed forwarder carries that header to an H1 hop.

The committed C5 spec names CVE-2026-70188 and CVE-2026-88092 (`evidence/c5/SPEC.md:137-138`). Those sentences are HTTP/2 trailers/HPACK and an aborted HTTP/1 connection reparsing unread body bytes. They are not a license to mark any row above as a new payable finding. No CVE database was queried.

## Week-2 payer-proof plan

Copied from SPEC section 4. This run does not carry it out. No buyer is contacted.

> Produce ONE sample conformance report against a public open-source proxy's **documented** behavior (static, no execution): "here are the N requests where Kestrel-H3 and Kestrel-H1 resolve framing/acceptance differently — your edge must agree or it desyncs." Take it to buyer #1's conformance/security contact. A signed intent-to-pay or a paid pilot = success.

N, from this static pass, is 0 payable boundary divergences. A Week-2 report that stays honest says that, and may attach the conformance-only axes (OR-001, OR-002, OR-005, OR-008, OR-009) as differences that are not a sold desync pack. SPEC section 5 still applies: static only, and no buyer contact until Santhosh's explicit yes.
