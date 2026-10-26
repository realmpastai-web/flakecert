# C5 Kestrel HTTP/1.1 request parser — clean-room spec (phase 1, static)

Pair: `Microsoft.AspNetCore.App.Runtime.linux-x64` **10.0.12** (before) and **10.0.13** (after). Both versions are on the nuget.org flat-container index (`c5-kestrel/evidence/nuget-index.json`, sha256 `8a2f0711d9389d7d3e71f000b568d15c95d21b7cc18e7b6feddf366156ae78ea`; the 10.0.x names are listed in `c5-kestrel/evidence/logs/phase1-commands.txt`). Package ids and versions are the nuspec `<id>` / `<version>` values recorded in that same log: `Microsoft.AspNetCore.App.Runtime.linux-x64` 10.0.12 and 10.0.13.

This spec describes the **before** decompilation. Names such as `flag` and `num` are ilspycmd names (ilspycmd 11.1.0.9782, ICSharpCode.Decompiler 11.1.0.9782, .NET SDK 10.0.403; `phase1-commands.txt`). The after tree is byte-identical for 23 of the 25 decompiled files (`phase1-commands.txt`, `decompiled cmp`). The two files that differ are covered in "Observed changes in AFTER".

Assembly metadata reports `Microsoft.AspNetCore.Server.Kestrel.Core` version `10.0.0.0` for both DLLs (`c5-kestrel/evidence/logs/assembly-version.txt`). Package identity is the NuGet version, not `AssemblyVersion`.

Decompiled sources are a mechanical decompilation of the MIT-licensed assemblies. The license copied out of the 10.0.12 nupkg is `c5-kestrel/ASPNETCORE-LICENSE.txt` (identical bytes in the 10.0.13 nupkg; `cmp` during collection).

## Surfaces

Saved under `c5-kestrel/decomp/before/` and `c5-kestrel/decomp/after/`. Per-file sha256: `c5-kestrel/evidence/logs/decomp-sha256.txt`.

| Role | File |
| --- | --- |
| Request line and header line splitter | `Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpParser`1.decompiled.cs` |
| Handler that routes lines to the connection | `...Http1ParsingHandler.decompiled.cs` |
| HTTP/1 connection parse loop | `...Http1Connection.decompiled.cs` |
| Generic subclass | `...Http1Connection`1.decompiled.cs` |
| Body selection (CL vs TE) | `...Http1MessageBody.decompiled.cs` |
| Content-Length body | `...Http1ContentLengthMessageBody.decompiled.cs` |
| Chunked body, chunk size, trailers | `...Http1ChunkedEncodingMessageBody.decompiled.cs` |
| Upgrade body | `...Http1UpgradeMessageBody.decompiled.cs` |
| Zero-length body singletons | `...MessageBody.decompiled.cs`, `...ZeroContentLengthMessageBody.decompiled.cs` |
| Header storage, Content-Length parse | `...HttpRequestHeaders.decompiled.cs` |
| Transfer-coding scan | `...HttpHeaders.decompiled.cs` |
| Shared request loop, `OnHeader` / `OnTrailer` | `...HttpProtocol.decompiled.cs` |
| Decoded-header character check | `...Infrastructure.HttpUtilities.decompiled.cs` |
| Path, method, version, target form, rejection reasons | `PathDecoder`, `HttpMethod`, `HttpVersion`, `HttpRequestTarget`, `HttpVersionAndMethod`, `TargetOffsetPathLength`, `ConnectionOptions`, `TransferCoding`, `RequestRejectionReason`, `BadHttpRequestException`, `KestrelBadHttpRequestException` |

## Request-line framing

`Http1Connection.ParseRequest` (`decomp/before/...Http1Connection.decompiled.cs` lines 180–214) starts in `RequestPending`, skips a leading CR (13) or LF (10) when one is peekable, then moves to `ParsingRequestLine` and calls `TakeStartLine`. On success it moves to `ParsingHeaders` and calls `TakeMessageHeaders` with `trailers: false`. A completed parse returns true and sets `RequestProcessingStatus.AppStarted`.

`TakeStartLine` (lines 216–234) calls `HttpParser.ParseRequestLine` on an `Http1ParsingHandler`. If `reader.Remaining` is at least `MaxRequestLineSize`, it parses only a slice of that length and throws `RequestRejectionReason.RequestLineTooLong` when that slice does not complete a request line.

`HttpParser.ParseRequestLine` (lines 51–125):

- Reads up to the delimiter span `"\n\0"` (line 33). A following delimiter byte of 0, or an empty span, is rejected via `RejectRequestLine`.
- The method token is `GetKnownMethod`. `HttpMethod.Custom` takes `GetUnknownMethodLength` (lines 393–401), which requires `HttpCharacters.IndexOfInvalidTokenChar` to land on a space.
- The byte immediately after the method must not be space (32), `?` (63), or `%` (37), or the line is rejected (lines 76–80).
- The target runs until space, `?`, or `%`. A `%` marks the target encoded and the scan continues to space or `?`. A `?` then consumes the query until a space.
- The version occupies the remainder. The length check (lines 112–115) rejects the line unless the remainder matches the 8-byte version plus a trailing CR, or, when the `AppContext` switch `Microsoft.AspNetCore.Server.Kestrel.DisableHttp1LineFeedTerminators` is off, an 8-byte version with no CR. The switch is read in the constructor (lines 40–48).
- `GetKnownVersion` must not return `HttpVersion.Unknown` (lines 116–121). `HttpVersion` values are `Unknown = -1`, `Http10`, `Http11`, `Http2`, `Http3` (`HttpVersion.decompiled.cs` lines 3–9).

`OnStartLine` (Http1Connection lines 277–310) classifies the target: a leading `/` is origin form, a one-byte `*` is asterisk form (and `OnAsteriskFormTarget` lines 418–430 requires `HttpMethod.Options`), a scheme match is absolute form, otherwise authority form (`OnAuthorityFormTarget` lines 392–416 requires `HttpMethod.Connect` and rejects invalid authority characters). Origin-form paths go through `PathDecoder.DecodePath` (PathDecoder lines 10–24), which removes dot segments and, when the target was marked encoded, percent-decodes in place before UTF-8 decoding.

`EnsureHostHeaderExists` (lines 474–498) runs from `TryParseRequest` once status is `AppStarted` (lines 628–632). HTTP/1.0 may omit Host. More than one Host is `MultipleHostHeaders`. Other failures are `InvalidHostHeader`.

## Header framing

`TakeMessageHeaders` (Http1Connection lines 236–275) calls `HttpParser.ParseHeaders` with `Http1ParsingHandler(this, trailers)`. Bytes consumed are subtracted from `_remainingRequestHeadersBytesAllowed`, which `OnReset` sets to `MaxRequestHeadersTotalSize + 2` (lines 534–539). A slice that does not finish the header block throws `HeadersExceedMaxTotalSize`.

`ParseHeaders` (HttpParser lines 127–215) walks unread bytes:

- A leading CR LF completes the header block (`OnHeadersComplete`, `endStream: false`) (lines 132–136 and 174–180).
- A line split on CR requires the next byte to be LF. A CR that is not part of CR LF is `InvalidRequestHeadersNoCRLF` when the CR is at column 0, otherwise `InvalidRequestHeader` (lines 165–172).
- A line split on LF is accepted when `DisableHttp1LineFeedTerminators` is off. When that switch is on, an LF terminator is `InvalidRequestHeader` (lines 185–197).
- An empty line (CR LF or a lone LF when LF terminators are allowed) completes the block.

`TryTakeSingleHeader` (lines 318–391) finds the first `:`, space, or tab. Column 0, a missing colon, or whitespace before the colon returns false, and the caller rejects the line. The value has one run of leading space/tab skipped and one run of trailing space/tab trimmed, then `OnHeader(name, value)` is called. There is no obs-fold branch: a continuation line would fail the colon test.

`Http1ParsingHandler.OnHeader` (lines 23–33) sends trailer lines to `Connection.OnTrailer` and request lines to `Connection.OnHeader(name, value, checkForNewlineChars: false)`. `OnHeadersComplete` (lines 35–45) calls `OnTrailersComplete` or `OnHeadersComplete` to match.

`HttpProtocol.OnHeader` (lines 1298–1302) counts the header and calls `HttpRequestHeaders.Append(name, value, checkForNewlineChars)`. The count above `MaxRequestHeaderCount` throws `TooManyHeaders` (lines 1317–1323).

`Append` (HttpRequestHeaders lines 7609–8002) matches known header names by length and masked little-endian reads. Content-Length (length 14 branch, lines 7873–7884) does not use the `checkForNewlineChars` argument: `AppendContentLength` (lines 8440–8451) parses the raw bytes with `Utf8Parser.TryParse` and requires the whole span to be consumed and the value to be non-negative. A second Content-Length throws `MultipleContentLengths` (lines 8442–8444). A failed parse throws `InvalidContentLength`. The string passed into that exception is built with `checkForNewlineChars: false` (line 8448). Transfer-Encoding is stored as a string value (length 17 branch, lines 7911–7916) and then goes through `GetRequestHeaderString` with the caller's flag (lines 7986–7994). Unknown names do the same (lines 7997–8001).

`GetRequestHeaderString` (HttpUtilities lines 129–147), identical in both trees: when `checkForNewlineChars` is true the decoded string is rejected if it contains CR, LF, or NUL; when false only NUL is rejected. The thrown messages are "Newline characters (CR/LF) or Null are not allowed in request headers." and "Null characters are not allowed in request headers." A non-default encoding selector may decode with Latin-1 or `Encoding.GetString` (lines 149–167). Header *names* reject a 0 byte or a failed ASCII conversion via `GetHeaderName` (lines 104–116), which throws `InvalidCharactersInHeaderName`.

Because `ParseHeaders` already cuts the line at CR or LF, a value span that `TryTakeSingleHeader` accepts does not contain those delimiter bytes. The `checkForNewlineChars` flag still applies to characters that appear after decoding, and the false path still rejects NUL.

## Content-Length and Transfer-Encoding

After the request line and headers parse, `HttpProtocol.ProcessRequests` (lines 1385–1416) loops `while (_keepAlive)`, calls `TryParseRequest`, and on a finished request calls `CreateMessageBody`. `Http1Connection.CreateMessageBody` (lines 555–558) returns `Http1MessageBody.For(_httpVersion, HttpRequestHeaders, this)`. If `messageBody.RequestKeepAlive` is false, `DisableKeepAlive` sets `_keepAlive = false` (lines 1412–1416 and 1999–2002).

`Http1MessageBody.For` (lines 120–177) chooses the body in this order:

1. Connection options come from `HttpHeaders.ParseConnection` when `HasConnection` is set. `Upgrade` is remembered. Keep-alive starts true for any version other than `Http10`, and is then forced by `KeepAlive` / cleared by `Close` (lines 122–129). `ConnectionOptions` is `Close = 1`, `KeepAlive = 2`, `Upgrade = 4` (`ConnectionOptions.decompiled.cs` lines 6–12).
2. Upgrade with `ContentLength` defaulting to 0 and an empty `HeaderTransferEncoding` returns `Http1UpgradeMessageBody` and calls `OnTrailersComplete` (lines 130–134).
3. If `HasTransferEncoding` (lines 135–152): `HttpHeaders.GetFinalTransferCoding` must return `TransferCoding.Chunked`. Otherwise the method throws `RequestRejectionReason.FinalTransferCodingNotChunked`. `TransferCoding` is `None = 0`, `Chunked = 1`, `Other = 2` (`TransferCoding.decompiled.cs` lines 6–11). When Content-Length is also present, the current Content-Length value is copied onto the header name `"X-Content-Length"`, `ContentLength` is set to null, and the keep-alive flag is cleared unless the `AppContext` switch `Microsoft.AspNetCore.Server.Kestrel.AllowKeepAliveAfterCLTE` is enabled (lines 18 and 142–149). The returned body is `Http1ChunkedEncodingMessageBody`.
4. Otherwise a present Content-Length of 0 returns `MessageBody.ZeroContentLengthKeepAlive` or `ZeroContentLengthClose` according to the keep-alive flag (lines 153–163). A positive length returns `Http1ContentLengthMessageBody` with that length.
5. HTTP/1.0 `Post` or `Put` with neither header throws `LengthRequiredHttp10` (lines 166–169). Any other request with neither header calls `OnTrailersComplete` and returns a zero-length body (lines 171–176).

`GetFinalTransferCoding` (HttpHeaders lines 597–677) walks each `StringValues` entry, skips spaces and commas, and overwrites `result` for every token. A token whose first character lowercases to `c` and whose following masked integer reads equal `30118294962110568` and `6553701` for the widths those reads use is classified `Chunked`. Any other token is `Other`. Characters after the recognized token, other than space and comma, also force `Other`. The value returned is whatever the last token wrote.

`Http1ContentLengthMessageBody` stores `_contentLength` and `_unexaminedInputLength` (lines 186–191). `CreateReadResultFromConnectionReadResult` (lines 256–267) completes the read once the connection buffer covers the still-unexamined length, and slices the read to that length. `OnReadStarting` (lines 299–307) rejects a length above `MaxRequestBodySize` with `RequestBodyTooLarge` and disables keep-alive. A completed connection read before that many bytes calls `ThrowUnexpectedEndOfRequestContent` (lines 233–244 and Http1MessageBody lines 189–194).

The framing choice when both headers are present is the chunked body, with Content-Length removed from the length field and copied to `X-Content-Length`. A peer that counted body bytes from Content-Length would stop at a different offset than this chunked reader. The keep-alive flag on that path is cleared unless `AllowKeepAliveAfterCLTE` is on. That block is byte-identical in the after decompilation (`phase1-commands.txt`: `Http1MessageBody`, `HttpHeaders`, and `Http1ContentLengthMessageBody` are `SAME`).

## Chunk parsing and trailers

`Http1ChunkedEncodingMessageBody` modes are `Prefix`, `Extension`, `Data`, `Suffix`, `Trailer`, `TrailerHeaders`, `Complete` (lines 14–23). `Read` (lines 192–259) runs prefix, extension, data, and suffix until the mode reaches `Trailer`, then either a trailer CRLF or trailer headers.

`ParseChunkedPrefix` (lines 261–302) reads hex through `CalculateChunkSize` (lines 429–455): bytes `0-9`, `A-F`, and `a-f` accumulate `current * 16 + digit`. Any other byte throws `BadChunkSizeData`. Overflow throws `IOException` with `CoreStrings.BadRequest_BadChunkSizeData`. The loop condition is `sequenceReader.Consumed < 10` (the constant `MaxChunkPrefixBytes` is 10, line 29). A `;` (59) switches to `Extension` and stores the size. CR LF with size 0 switches to `Trailer`; CR LF with a positive size switches to `Data`. Exiting the loop without that throws `BadChunkSizeData`.

`ParseExtension` (lines 304–366) reads the switch `Microsoft.AspNetCore.Server.Kestrel.EnableInsecureChunkedRequestParsing` (line 43). With the switch off, the scan looks for CR or LF and requires the two-byte terminator to be CR LF; otherwise it throws `BadChunkExtension`. With the switch on, the scan looks for CR only, and a following LF still ends the extension, while a non-LF second byte advances one byte and continues. A finished extension with a positive size goes to `Data`; size 0 goes to `Trailer`.

`ReadChunkedData` (lines 368–380) copies `min(buffer.Length, _inputLength)` to the body pipe and, at zero remaining, switches to `Suffix`. `ParseChunkedSuffix` (lines 382–403) requires CR LF and returns to `Prefix`, or throws `BadChunkSuffix`.

`ParseChunkedTrailer` (lines 405–427): CR LF sets `Complete` and calls `OnTrailersComplete`. Any other two bytes set `TrailerHeaders`. `Read` then calls `_context.TakeMessageHeaders(ref reader, trailers: true)` (lines 244–257), which is the same `ParseHeaders` path with `Http1ParsingHandler.Trailers == true`, so each trailer line calls `OnTrailer`.

`HttpProtocol.OnTrailer` in the **before** build (lines 1309–1315) counts the header, decodes the name with `GetHeaderName`, decodes the value with `GetRequestHeaderString(..., checkForNewlineChars: false)`, and appends the string to `RequestTrailers`. `OnTrailersComplete` (lines 1331–1334) sets `RequestTrailersAvailable = true`.

## Where the before code leaves a framing choice

These are properties of the before decompilation. The same lines are unchanged in the after decompilation except where the diff hunks below say otherwise.

- Both Content-Length and Transfer-Encoding: `Http1MessageBody.For` lines 135–151 frame the body as chunked when the final coding is `Chunked`, move the length text to `X-Content-Length`, and clear keep-alive unless `AllowKeepAliveAfterCLTE` is enabled. A final coding of `Other` is rejected.
- Chunk extensions: `ParseExtension` lines 304–363 reject a non-CRLF extension terminator unless `EnableInsecureChunkedRequestParsing` is enabled, in which case the CR-only scan can continue.
- Request-line and header terminators: LF-only terminators are accepted unless `DisableHttp1LineFeedTerminators` is enabled (`HttpParser` lines 112–115 and 185–197).
- Request-header values from this parser are handed to `Append` with `checkForNewlineChars: false` (`Http1ParsingHandler` line 31). Trailer values in the before build are also decoded with that flag false (`HttpProtocol.OnTrailer` line 1313). NUL is still rejected (`HttpUtilities` lines 132–146).
- The accept loop continues while `_keepAlive` is true (`HttpProtocol` lines 1387–1388). `CancelRequestAbortedToken` in the before build (lines 1261–1280) sets `_connectionAborted` and does not assign `_keepAlive`.

No byte sequence is supplied here. Live reproduction is out of scope for this phase.

## Observed changes in AFTER

Source: `c5-kestrel/kestrel-parser.diff` (sha256 `7994f9b5739f98414af4de11d1e3878ce1f22a4de6e1f80ce99ed4233b2a94ae`, 1499 bytes). `patch -p0` on a copy of `decomp/before` reproduces `decomp/after` for both files (`phase1-commands.txt`, the `/tmp/patchcheck4` block: `H1_PATCH_MATCHES_AFTER`, `HP_PATCH_MATCHES_AFTER`).

1. Hunk `@@ -543,10 +543,6 @@` (diff lines 4–12). Removes the empty `Http1Connection.OnRequestProcessingEnding` override (before file lines 546–548). The base virtual method removed in the next hunk is also empty. IL length for that method on `Http1Connection` goes from 1 to absent (`il-length-diff-parser.txt` lines 1–2).

2. Hunk `@@ -1210,10 +1210,6 @@` (diff lines 16–26). Removes empty `HttpProtocol.OnRequestProcessingEnding` (before file lines 1213–1215). Compiler-generated local functions in the IL length report shift by one slot and keep the same lengths (`Is1xxCode|258_0` length 16 versus `|257_0` length 16, and the same pattern for `Is2xxCode`, `FireOnCompleted`, and `FireOnStarting`; `il-length-diff-parser.txt` lines 3–10). That is the method-removal renumber, not a second behavior change.

3. Hunk `@@ -1268,6 +1264,7 @@` (diff lines 27–34). Inside `CancelRequestAbortedToken`, the after file assigns `_keepAlive = false` before `_connectionAborted = true` (after file line 1267). Before file lines 1270–1271 assign `flag` and `_connectionAborted` and do not assign `_keepAlive`. IL length of `CancelRequestAbortedToken` is 118 before and 127 after (`il-length-diff-parser.txt` lines 11–12; raw IL in `il-ontrailer-and-abort.txt`). The accept loop condition remains `while (_keepAlive)` (before file lines 1387–1388; the method is above this hunk, and `HttpProtocol` is otherwise the diff).

4. Hunk `@@ -1310,7 +1307,7 @@` (diff lines 35–42). `OnTrailer` changes `checkForNewlineChars: false` to `true` (before file line 1313; after file line 1310). `GetRequestHeaderString` is unchanged (`phase1-commands.txt`: `HttpUtilities` is `SAME`), so the true flag rejects CR, LF, and NUL in the decoded trailer value (HttpUtilities lines 132–144). `Http1ParsingHandler.OnHeader` still passes false for non-trailer headers (that file is `SAME`, line 31). `OnTrailer` IL stays 52 bytes; the dumps in `il-ontrailer-and-abort.txt` differ by the opcode byte `16` versus `17` (ECMA-335 `ldc.i4.0` versus `ldc.i4.1`) among other bytes that move because metadata tokens were renumbered.

`HttpParser`, `Http1ChunkedEncodingMessageBody`, `Http1MessageBody`, `Http1ContentLengthMessageBody`, `HttpRequestHeaders`, and `HttpHeaders` are `SAME` in the decompiled cmp. Their IL-length multisets are in the 16 unchanged parser-surface types (`il-length-diff-parser.txt` line 15: `unchanged_il_length_multiset=16 changed=2`).

## Skeptic pass (phase 1)

- Decompiled C# is a reconstruction. The check used here is: same ilspycmd on both DLLs, byte compare of the 25 outputs, plus the IL-length multiset in `il-length-diff-parser.txt`. That report says 43 of 465 types differ in method-name/IL-length multiset (line 16). The parser-surface subset is 16 unchanged and 2 changed (line 15). The type-list diff in `evidence/logs/types-before.txt` versus `types-after.txt` shows certificate-manager types added and HTTP/3 state-machine ordinals renamed; those are outside the request parser. Raw IL hashes are not used, because call tokens move when unrelated methods are added.
- The task label "vulnerable/before" versus "patched/after" matches the published range for two public CWE-444 advisories (see `EVIDENCE.md`). It is not a result of this decompilation by itself.
- The request-line splitter, chunk state machine, and CL/TE selector do not appear in `kestrel-parser.diff`. A new framing bug in those functions is not what this diff shows.
- `OnTrailer`'s flag flip is on the shared `HttpProtocol` method. The public text for CVE-2026-70188 talks about HTTP/2 trailers and HPACK. This phase did not decompile the HPACK caller, and the HTTP/1 line splitter still removes CR/LF before `OnTrailer`. Treating the flag flip as a new HTTP/1 smuggling finding would go past the diff.
- `CancelRequestAbortedToken` clearing `_keepAlive` lines up with the public one-sentence description of CVE-2026-88092 (an aborted HTTP/1 connection reparsing unread body bytes). This phase did not run that path.
- Holdout scoring and any live check are a later phase. They are not in this directory.
