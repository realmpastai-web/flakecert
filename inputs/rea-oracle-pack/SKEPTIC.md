# Skeptic pass

Payable means one thing here: an accept-versus-reject, framing-source-versus-absent, or normalize-to-different split where one leg accepts a field-set the other refuses, the split is on Kestrel defaults, and a real second hop would disagree about a request that actually crosses the boundary. Both-reject and both-absent are not payable. A class difference with no forwarded request is not payable. No network lookup was done. No CVE id is asserted except the two names already written in the committed C5 spec.

## Recorded holdout (first score, unchanged file)

Scored once, before this evidence sync, as `out/holdout_score_once.json`. Front h3, back h1. 3 rows, 2 divergences emitted.

- HO-01 obs-fold: h1=`reject` vs h3=`absent`. Emitted. Class absent-versus-reject.
- HO-03 te-not-chunked: h1=`reject` vs h3=`absent`. Emitted. Class absent-versus-reject.
- HO-02 dup-content-length: h1 leg was `UNKNOWN`. No emission. Fail-closed.

Those two emissions are not payable. Both legs refuse the body. `payable_at_boundary` on a sold row has to be false for that shape. The holdout file was not edited after this reading. The final generator scores it one more time into `out/holdout_score_final.json` and that score is not used to change the oracle.

With the synced decomp, the same axes are now answered below as OR-003 (CR/LF cannot sit inside an H1 header value), OR-004 (both legs throw on a second content-length), and OR-009 (H1 rejects a non-chunked transfer-encoding; H3 stores the header). The holdout rows themselves stay as sealed inputs.

## Oracle rows after the decomp read

Every yarp leg is `UNKNOWN`. `c7-kestrel-h3` at 434e35b has no YARP FINDINGS file. No C6 path is invented. A row is `CONFIRMED` only for the h1 and h3 (and, where cited, h2) legs whose lines were read. That does not confirm yarp.

### OR-001-chunked-framing — non-payable

Field-set: lowercase `transfer-encoding` whose final coding is chunked. Content-Length may also be present.

(a) Reachable on defaults. H1 `Http1MessageBody.For` takes the chunked body when `HasTransferEncoding` is set and `GetFinalTransferCoding` returns chunked, and it does that with no extra switch (`evidence/c5/Http1MessageBody.decompiled.cs:135-151`, `evidence/c5/HttpHeaders.decompiled.cs:597-636`). The keep-alive switch on that path only clears keep-alive; it does not change the chunked choice (`evidence/c5/Http1MessageBody.decompiled.cs:18`, `142-149`). H3 stores the 17-byte name (`evidence/c7/HttpRequestHeaders.decompiled.cs:7904-7916`). `IsConnectionSpecificHeaderField` rejects `connection` and `te`, not `transfer-encoding` (`evidence/c7/Http3Stream.decompiled.cs:121-125`, `566-577`). `InputRemaining` is `ContentLength` (`evidence/c7/Http3Stream.decompiled.cs:831`) and DATA is checked only against that remainder (`870-886`). `CreateMessageBody` returns an `Http3MessageBody`, not a chunked reader (`929-943`). The H3 static table has no `transfer-encoding` entry (`evidence/c7/H3StaticTable.decompiled.cs:133-233`).

(b) Not identified as a CVE by the committed text. `evidence/c5/SPEC.md:136-138` says the CL/TE selector is not what the before/after diff changes, and that a new framing bug in those functions is not what that diff shows. The two names in that skeptic section are CVE-2026-70188 and CVE-2026-88092 (`evidence/c5/SPEC.md:137-138`). Those sentences describe HTTP/2 trailers/HPACK and an aborted HTTP/1 connection reparsing unread body bytes. They do not describe this H3-versus-H1 length source.

(c) A downstream hop does not disagree on a forwarded request in the committed evidence. Both parsers accept the field-set. They frame different transports: H1 chunk bytes, H3 DATA frames. `evidence/c7/EVIDENCE.md:269` records the same point: this is the protocol difference, not a second framing of the same bytes. No C6 snippet shows a forwarder re-emitting the H3 body plus `transfer-encoding` at an H1 hop.

Label: **non-payable**. Class is same-class different framing target. One leg does not accept a request the other refuses.

### OR-002-extended-connect-protocol — non-payable

Field-set: `:protocol` on a non-CONNECT request that also has method, path, and scheme.

(a) The H3 reject is not on the default. `EnableWebTransportAndH3Datagrams` reads AppContext switch `Microsoft.AspNetCore.Server.Kestrel.Experimental.WebTransportAndH3Datagrams`, and `TryGetSwitch` failing leaves false (`evidence/c7/KestrelServerOptions.decompiled.cs:109-118`). The must-be-CONNECT throw is inside `if (EnableWebTransportAndH3Datagrams && HeaderProtocol.Count > 0)` (`evidence/c7/Http3Stream.decompiled.cs:837-845`). With the switch unset, that block is skipped. Mandatory method/path/scheme still pass for this field-set (`860-862`). H2 does reject it, unconditionally (`evidence/c7/Http2Stream.decompiled.cs:285-288`). H1 has no pseudo-header: `OnStartLine` takes method, target, and version (`evidence/c5/Http1Connection.decompiled.cs:277-309`).

(b) No CVE in `evidence/c5/SPEC.md:132-138` names `:protocol`. `evidence/c7/EVIDENCE.md:263-265` calls the H3-versus-H2 difference a protocol-compliance candidate, not a reconstructed-request difference, and says this phase does not claim the server accepts the request. The oracle verdict is the decompiled branch: the throw does not run when the switch is false. It is not a live capture.

(c) The field does not cross as an ordinary header. `ClearPseudoRequestHeaders` clears the protocol bit from the enumerated set (`evidence/c7/HttpRequestHeaders.decompiled.cs:7569-7572`). `Reset` sets `IsExtendedConnectRequest = false` (`evidence/c7/HttpProtocol.decompiled.cs:1164`). A search of `decomp/h3/10.0.13/*.cs` for `IsExtendedConnectRequest =` printed no lines (`EVIDENCE-SYNC.md`). An H1 downstream that sees enumerated headers does not see `:protocol`. No C6 snippet shows otherwise.

Label: **non-payable**. H3-versus-H1 is accept-versus-absent, and the accepted field is stripped before enumeration. H3-versus-H2 is accept-versus-reject only while the experimental switch is off, and that still does not put `:protocol` on the enumerated header set.

### OR-003-header-value-ctl — non-payable

Field-set: a header value containing bare CR, bare LF, or NUL.

(a) On defaults, every live leg rejects. H1 ParseHeaders cuts on byte 13 or 10 (evidence/c5/HttpParser`1.decompiled.cs:139) and TryTakeSingleHeader returns false when the line has no colon (evidence/c5/HttpParser`1.decompiled.cs:318-332), so a value span that reaches `OnHeader` does not contain those delimiter bytes. `OnHeader` passes `checkForNewlineChars: false` (`evidence/c5/Http1ParsingHandler.decompiled.cs:31`). `GetRequestHeaderString` then rejects NUL (`evidence/c5/HttpUtilities.decompiled.cs:129-136`). H3 literal headers pass `checkForNewlineChars: true` (`evidence/c7/Http3Stream.decompiled.cs:428-431`), so CR, LF, and NUL throw (`evidence/c7/HttpUtilities.decompiled.cs:129-136`). The dynamic branch passes false (`425`), and `QPackDecoder` throws `net_http_qpack_no_dynamic_table` instead (`evidence/c7/QPackDecoder.decompiled.cs:642-644`). `ProcessHeaderValue` calls `OnHeader` or `OnStaticIndexedHeader` only (`503-514`).

(b) `evidence/c5/SPEC.md:137` ties CVE-2026-70188 to HTTP/2 trailers and HPACK, and says treating the H1 trailer flag flip as a new smuggling finding would go past the diff. This row is request-header CTL, and both live paths reject it.

(c) There is no accepted value for a downstream to reinterpret. Both legs refuse CR, LF, and NUL in a header value.

Label: **non-payable**. Both reject. The generator emits nothing for h3 versus h1 because both classes are `reject`.

### OR-004-dup-content-length — non-payable

Field-set: two content-length values, including two equal values.

(a) On defaults, `AppendContentLength` throws `MultipleContentLengths` as soon as a length is already set (`evidence/c5/HttpRequestHeaders.decompiled.cs:8440-8444`, same bytes as `evidence/c7/HttpRequestHeaders.decompiled.cs:8440-8444`). There is no equality compare before the throw. Literal content-length (`7866-7884`), HPACK index 28 (`8067-8077`), and QPACK index 4 (`evidence/c7/HttpRequestHeaders.decompiled.cs:8218-8227`, static entry at `evidence/c7/H3StaticTable.decompiled.cs:139`) all call that helper.

(b) Not named in `evidence/c5/SPEC.md:132-138`.

(c) Both hops reject the field-set. A downstream does not receive a second, accepted length.

Label: **non-payable**. Both reject. No generator emission. This is the committed answer to sealed holdout HO-02, whose own h1 leg stays `UNKNOWN` because that file was not edited.

### OR-005-pseudo-dup-and-order — non-payable

Field-set: a repeated pseudo-header, or a pseudo-header after a regular header.

(a) H3 throws for a pseudo-header after regular headers, for an unknown pseudo-header, and for a duplicate (`evidence/c7/Http3Stream.decompiled.cs:468-486`). H2 throws on the same three shapes (`evidence/c7/Http2Connection.decompiled.cs:1277-1296`). H1 has no pseudo-header slot (`evidence/c5/Http1Connection.decompiled.cs:277-309`). No switch gates these throws.

(b) Not named in `evidence/c5/SPEC.md:132-138`.

(c) H3 refuses the field-set. H1 cannot carry it. Nothing is accepted on one side and forwarded.

Label: **non-payable**. Reject-versus-absent. Both refuse.

### OR-006-trailer-ctl — non-payable

Field-set: a trailer value containing CR, LF, or NUL.

(a) On the after build, `OnTrailer` decodes with `checkForNewlineChars: true` (`evidence/c5/HttpProtocol.decompiled.cs:1306-1311`, same bytes as `evidence/c7/HttpProtocol.decompiled.cs:1306-1311`). That rejects CR, LF, and NUL (`evidence/c5/HttpUtilities.decompiled.cs:129-136`). H1 trailers go through `Http1ParsingHandler` when `Trailers` is true (`evidence/c5/Http1ParsingHandler.decompiled.cs:25-27`). H3 calls `OnTrailer` from the trailer state (`evidence/c7/Http3Stream.decompiled.cs:399-403`) after a HEADERS frame in body state switches to trailers (`803-805`). A pseudo-header in those trailers throws (`472-474`).

(b) `evidence/c5/SPEC.md:137` says CVE-2026-70188's public text is about HTTP/2 trailers and HPACK, and that the H1 line splitter still removes CR/LF before `OnTrailer`. This row does not turn that flag into a new finding. Both protocols reject the characters.

(c) Both legs reject the trailer value. No accepted trailer crosses.

Label: **non-payable**. Both reject. No generator emission.

### OR-007-cl-data-reconciliation — non-payable

Field-set: Content-Length present, transfer-encoding absent.

(a) H1 returns `Http1ContentLengthMessageBody` for a positive length (`evidence/c5/Http1MessageBody.decompiled.cs:153-164`). The reader keeps `_unexaminedInputLength` at that length (`evidence/c5/Http1ContentLengthMessageBody.decompiled.cs:186-190`) and slices the buffer to the remaining count (`256-266`). H3 sets `InputRemaining = ContentLength` (`evidence/c7/Http3Stream.decompiled.cs:831`), throws if DATA is longer (`880-885`), and throws if the stream ends with a remainder (`750-752`). H2 does the same (`evidence/c7/Http2Connection.decompiled.cs:983`, `evidence/c7/Http2Stream.decompiled.cs:404-410` and `432-434`).

(b) Not named as a new bug in `evidence/c5/SPEC.md:136`. `evidence/c7/EVIDENCE.md:259` says the paths are consistent on accepted body length.

(c) The hops agree on the length value. There is no second interpretation to disagree about.

Label: **non-payable**. Same framing-source string on h1, h2, and h3. No generator emission.

### OR-008-te-token-not-trailers — non-payable

Field-set: literal header `te` whose value is not the bytes `trailers`.

(a) On defaults, H1 stores it. Append's length-2 arm matches `te` and writes `_TE` (`evidence/c5/HttpRequestHeaders.decompiled.cs:7617-7623`), then `GetRequestHeaderString` (`7986-7994`). `HasTransferEncoding` is a different bit (`449`), so this header does not select the chunked body. H3 literal validation throws unless the value equals `trailers` (`evidence/c7/Http3Stream.decompiled.cs:121-125`, `445-449`, `566-577`). The call is on the literal path (`428-431`). The static table has no `te` entry (`evidence/c7/H3StaticTable.decompiled.cs:133-233`), and the dynamic table throws (`evidence/c7/QPackDecoder.decompiled.cs:642-644`), so that literal path is the live H3 path. H2's literal path does the same (`evidence/c7/Http2Connection.decompiled.cs:1228-1231`, `1364-1374`).

(b) Not the CVE text in `evidence/c5/SPEC.md:137-138`. Those sentences are trailer CTL and aborted-connection reparsing, not the `te` token.

(c) For front h3 and back h1, the front throws (`Http3StreamErrorException` at `evidence/c7/Http3Stream.decompiled.cs:447-449`) before a request is forwarded. The back would have stored a header that does not even change the body reader. No C6 snippet shows `te` being forwarded into that reject. This is a conformance difference between two listeners, not a boundary that accepts two different messages.

Label: **non-payable**. The class is reject-versus-accept, and it is killed because the rejecting front does not forward and the accepted H1 header is not a second framing of the body.

### OR-009-te-not-chunked — non-payable

Field-set: lowercase `transfer-encoding` whose final coding is not chunked, and no Content-Length.

(a) On defaults, H1 throws `FinalTransferCodingNotChunked` (`evidence/c5/Http1MessageBody.decompiled.cs:135-141`) when `GetFinalTransferCoding` does not return chunked (`evidence/c5/HttpHeaders.decompiled.cs:597-641`). H3 does not reject the name `transfer-encoding` (`evidence/c7/Http3Stream.decompiled.cs:566-577` returns false for every name other than `connection` and non-trailers `te`). The name is stored (`evidence/c7/HttpRequestHeaders.decompiled.cs:7904-7916`). With no Content-Length, `InputRemaining` is null (`evidence/c7/Http3Stream.decompiled.cs:831`) and the DATA length throw is skipped (`880-886` runs only when `InputRemaining.HasValue`). H2 uses the same store and the same `InputRemaining = ContentLength` (`evidence/c7/Http2Connection.decompiled.cs:983`, `1228-1231`). Its `te` reject is a different name (`1364-1374`).

(b) `evidence/c5/SPEC.md:136` says a new framing bug in the CL/TE selector is not what the before/after diff shows. The committed CVE sentences (`137-138`) do not describe an H3 accept of non-chunked `transfer-encoding`.

(c) Front h3 accepts and does not itself speak HTTP/1 to a backend. A downstream H1 would reject this header only if some forwarder preserved it. No such forwarder is in the committed C6 evidence, because that evidence is absent. The disagreement stops at "one listener rejects a header the other stores." It does not show two accepted parses of one forwarded byte stream.

Label: **non-payable**. Killed after the accept-versus-reject class check. It stays in `conformance_only` so the axis is visible, and it stays out of `cases`.

## What the sold list is

`gen/desync_gen.py` puts a row in `cases` only when it diverges, `payable_at_boundary` is true, and `status` is `CONFIRMED`. Every row above has `payable_at_boundary` false. The sold list for h3-front / h1-back is empty. The five class differences (OR-001, OR-002, OR-005, OR-008, OR-009) are conformance-only. OR-003, OR-004, OR-006, and OR-007 do not diverge.

Holdout survivors HO-01 and HO-03 stay **non-payable** (absent-versus-reject, both refuse). HO-02 stays unemitted because its h1 verdict in the sealed file is `UNKNOWN`.

## Final holdout score (one run, not used to edit the oracle)

Command, run once: `python3 gen/desync_gen.py holdout/holdout.jsonl --front h3 --back h1`

Output file: `out/holdout_score_final.json`. `confirmed_only` false. `divergences` 0. `cases` empty. `conformance_only` is HO-01 and HO-03. HO-02 omitted. `holdout/holdout.jsonl` sha256 stayed `5c2859812105641a9c4b0c26132f55df40b97a218e43c4470ada5876d712000a`. No oracle or generator edit followed that output.
