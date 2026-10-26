# C7 evidence log (phase 1, static only)

No Kestrel process was started. No DLL was loaded for execution. No HTTP, HTTP/2, HTTP/3, or QUIC request was sent to any host other than `api.nuget.org` for the package download. ilspycmd and `tools/AssemblyIdentity` read PE metadata and IL.

The command transcripts below are also stored as files. Paths are relative to `c7-kestrel-h3/` unless noted.

## Versions

Command:

```text
curl -fsS https://api.nuget.org/v3-flatcontainer/microsoft.aspnetcore.app.runtime.linux-x64/index.json -o evidence/nuget-index.json
sha256sum evidence/nuget-index.json
```

`sha256sum` output (`evidence/logs/freeze-inputs.txt`):

```text
8a2f0711d9389d7d3e71f000b568d15c95d21b7cc18e7b6feddf366156ae78ea  evidence/nuget-index.json
```

That hash matches `c5-kestrel/FREEZES.txt` for `evidence/nuget-index.json`. The saved file is the response body. It lists 255 versions. The last name is `11.0.0-rc.3.26522.148`. Every `10.*` name in that file, printed by `python3` from the saved JSON (`evidence/logs/freeze-inputs.txt`):

```text
count 255
latest 11.0.0-rc.3.26522.148
10.0.0-preview.1.25120.3
10.0.0-preview.2.25164.1
10.0.0-preview.3.25172.1
10.0.0-preview.4.25258.110
10.0.0-preview.5.25277.114
10.0.0-preview.6.25358.103
10.0.0-preview.7.25380.108
10.0.0-rc.1.25451.107
10.0.0-rc.2.25502.107
10.0.0
10.0.1
10.0.2
10.0.3
10.0.4
10.0.5
10.0.6
10.0.7
10.0.8
10.0.9
10.0.10
10.0.11
10.0.12
10.0.13
10.0.14
```

Choice, from that list and no other:

- **10.0.13** is the C5 "after" build, so the HTTP/1.1 leg is the same Core DLL.
- **10.0.12** is the published patch immediately before 10.0.13. The stable names `10.0.12`, `10.0.13`, `10.0.14` are consecutive in the index.
- **10.0.14** is the latest `10.0.x` on this index. `11.0.0-rc.3.26522.148` is newer and is not a `10.0.x` release.

Nuspec lines (`unzip -p` … `Microsoft.AspNetCore.App.Runtime.linux-x64.nuspec | grep -E '<id>|<version>'`):

```text
    <id>Microsoft.AspNetCore.App.Runtime.linux-x64</id>
    <version>10.0.12</version>
    <id>Microsoft.AspNetCore.App.Runtime.linux-x64</id>
    <version>10.0.13</version>
    <id>Microsoft.AspNetCore.App.Runtime.linux-x64</id>
    <version>10.0.14</version>
```

## Downloads and extracts

URLs:

```text
https://api.nuget.org/v3-flatcontainer/microsoft.aspnetcore.app.runtime.linux-x64/10.0.12/microsoft.aspnetcore.app.runtime.linux-x64.10.0.12.nupkg
https://api.nuget.org/v3-flatcontainer/microsoft.aspnetcore.app.runtime.linux-x64/10.0.13/microsoft.aspnetcore.app.runtime.linux-x64.10.0.13.nupkg
https://api.nuget.org/v3-flatcontainer/microsoft.aspnetcore.app.runtime.linux-x64/10.0.14/microsoft.aspnetcore.app.runtime.linux-x64.10.0.14.nupkg
```

`sha256sum` of the files after download (`evidence/logs/freeze-inputs.txt`). Paths here are shortened to the repo-relative suffix; the log has the absolute paths.

```text
8a2f0711d9389d7d3e71f000b568d15c95d21b7cc18e7b6feddf366156ae78ea  evidence/nuget-index.json
cfc21f5e8bd655ae997eec916138b707b1d290b83272c02a95c9f821b8c87310  ASPNETCORE-LICENSE.txt
5e3883d280dac567a4bc19a52a75669bf96e24bd41e29ec9ea1baafbd1a6a800  artifacts/microsoft.aspnetcore.app.runtime.linux-x64.10.0.12.nupkg
d5d2125765a33e05881780c302edc2a1a30fe205a2aaf17f9500bbf59f157704  artifacts/microsoft.aspnetcore.app.runtime.linux-x64.10.0.13.nupkg
b2d4c525351873aec9f4508e6c0e06056d2839823c4dce8fe00a0e92e28264f0  artifacts/microsoft.aspnetcore.app.runtime.linux-x64.10.0.14.nupkg
37db1c74ddd000092618ea357f056dd4b56c0847791434ebe50d4de0390141a9  artifacts/10.0.12/Microsoft.AspNetCore.Server.Kestrel.Core.dll
b8d7950d8bf11b3e34d6cec3cf3d84c36bd926751bad205941380b32d54d26ee  artifacts/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.dll
7861e80a98d91f6e0ea89f1fa4c72b6c7f0ac5bfefd2e91d8e0fe957c79eee7f  artifacts/10.0.14/Microsoft.AspNetCore.Server.Kestrel.Core.dll
236b99ca33d6e47c6f713cf68125b83d74ae66284752d2e4c656073f69360ed8  artifacts/10.0.12/Microsoft.AspNetCore.Server.Kestrel.Transport.Quic.dll
0514ca6517d2a21436ee5223a56e23df891b78e3142d572913343703b370c337  artifacts/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Transport.Quic.dll
a3ea6ecfa724ffce21ed1fcecf6e4d292274fa90cde4c36eb16b298a3b9381c1  artifacts/10.0.14/Microsoft.AspNetCore.Server.Kestrel.Transport.Quic.dll
```

`cmp` against `c5-kestrel` printed:

```text
NUPKG_12_EQ_C5
NUPKG_13_EQ_C5
CORE_12_EQ_C5_BEFORE
CORE_13_EQ_C5_AFTER
LICENSE_EQ_C5
```

The 10.0.12 and 10.0.13 nupkg hashes match `c5-kestrel/FREEZES.txt`. The 10.0.12 and 10.0.13 Core DLL hashes match that file's before and after lines. 10.0.14 was not in the C5 freeze.

Each nupkg contains both:

```text
runtimes/linux-x64/lib/net10.0/Microsoft.AspNetCore.Server.Kestrel.Core.dll
runtimes/linux-x64/lib/net10.0/Microsoft.AspNetCore.Server.Kestrel.Transport.Quic.dll
```

Extract command, per version, is `unzip -p` of those two entries (`fetch-artifacts.sh`). Binaries are gitignored (combined nupkg plus DLL bytes are above 25MB). `artifacts/refs/` is the reference directory `decompile-surfaces.sh` unzips for ilspycmd `-r` and is gitignored.

## Decompile

```text
export PATH="$HOME/.dotnet:$HOME/.dotnet/tools:$PATH"
export DOTNET_ROOT="$HOME/.dotnet"
export DOTNET_ROOT_X64="$HOME/.dotnet"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
ilspycmd --version
```

`evidence/logs/decompile.txt` starts with:

```text
ilspycmd ilspycmd: 11.1.0.9782
ICSharpCode.Decompiler: 11.1.0.9782
```

`dotnet --version` on this machine printed `10.0.403`. `decompile-surfaces.sh` runs `ilspycmd --disable-updatecheck -t <type> -o <tmp> -r <ref> <dll>` and does not execute the DLL. The full transcript is `evidence/logs/decompile.txt`. That run wrote 23 HTTP/3 files, 16 HTTP/2 files, 8 shared files, and 3 QUIC files per version.

Later the same ilspycmd invocation added `Http3ControlStream`, `Http3ControlStream`1`, `VariableLengthIntegerHelper`, `KestrelServerLimits`, and `KestrelServerOptions`. Those names are in `h3-types.txt` and `shared-types.txt`, so a fresh `./decompile-surfaces.sh` includes them. `find decomp -name '*.cs' | wc -l` printed `165`. Per-file sha256 is `evidence/logs/decomp-sha256.txt` (165 lines). `sha256sum evidence/logs/decomp-sha256.txt` printed:

```text
b10ffa5a30a5da09fb310f56ec15fbe68ef96dd2325d0fc5ce4cb1a2b356e413  evidence/logs/decomp-sha256.txt
```

## Version diffs of the decompilation

```text
diff -ru decomp/h3/10.0.12 decomp/h3/10.0.13
```

164 lines, only `Http3Stream` (`evidence/logs/h3-10.0.12-vs-10.0.13.diff`). The hunks add `_abortCompletedTcs` and wait for abort completion. They do not change `OnHeaderCore` or `QPackDecoder`.

```text
diff -ru decomp/h2/10.0.12 decomp/h2/10.0.13
```

12 lines, one call (`evidence/logs/h2-10.0.12-vs-10.0.13.diff`):

```text
-					_currentHeadersStream.OnHeader(name, value, checkForNewlineChars: false);
+					_currentHeadersStream.OnHeader(name, value, checkForNewlineChars: true);
```

```text
diff -ru decomp/shared/10.0.12 decomp/shared/10.0.13
```

31 lines, only `HttpProtocol` (`evidence/logs/shared-10.0.12-vs-10.0.13.diff`): `OnRequestProcessingEnding` removed, `_keepAlive = false` added in the abort-cancel path, trailer `checkForNewlineChars` changed to `true`.

`diff -rq` of 10.0.13 against 10.0.14 printed `H3_13_EQ_14`, `H2_13_EQ_14`, `SHARED_13_EQ_14`. The corresponding `diff -ru` files are empty (`wc -l` printed `0`). `diff -rq decomp/quic/10.0.12 decomp/quic/10.0.14` printed `QUIC_12_EQ_14`.

Shared files that also exist in `c5-kestrel/decomp/before` and `decomp/after` all printed `SAME` (`evidence/logs/freeze-inputs.txt`).

`IntegerDecoder` and `Huffman` under `decomp/h2/10.0.13` `cmp` equal to the copies under `decomp/h3/10.0.13` (`INTEGER_H2_EQ_H3`, `HUFFMAN_H2_EQ_H3`).

## Assembly identity and method IL

`dotnet run --project tools/AssemblyIdentity -c Release -- identity <dll>` reads the PE metadata. It does not `Assembly.Load` the DLL. `evidence/logs/assembly-identity.txt`:

```text
File=.../artifacts/10.0.12/Microsoft.AspNetCore.Server.Kestrel.Core.dll
Name=Microsoft.AspNetCore.Server.Kestrel.Core
Version=10.0.0.0
Culture=
Mvid=acf357d0-09c1-4336-a2ba-9aaedaaaa5ab
File=.../artifacts/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.dll
Name=Microsoft.AspNetCore.Server.Kestrel.Core
Version=10.0.0.0
Culture=
Mvid=a6e8193a-1fa2-47c6-9eaa-81b474ae825c
File=.../artifacts/10.0.14/Microsoft.AspNetCore.Server.Kestrel.Core.dll
Name=Microsoft.AspNetCore.Server.Kestrel.Core
Version=10.0.0.0
Culture=
Mvid=58548fb6-304a-418a-b748-f69c298f3ed6
```

QUIC MVIDs in the same log: 10.0.12 `083a5ae0-2907-4889-85e3-63a6f2b42511`, 10.0.13 `7c53278e-85c9-4b5a-92af-80c159523e67`, 10.0.14 `4ce45ed3-4dcb-49a8-954f-e0598a70dd01`. All three report version `10.0.0.0`.

`ildiff` hashes each method body. `evidence/logs/ildiff-core-10.0.13-vs-10.0.14.txt`:

```text
MethodsSame=5082
MethodsDiffer=0
MethodsOnlyLeft=0
MethodsOnlyRight=0
TypesTouched=0
```

`evidence/logs/ildiff-quic-10.0.13-vs-10.0.14.txt`:

```text
MethodsSame=446
MethodsDiffer=0
MethodsOnlyLeft=0
MethodsOnlyRight=0
TypesTouched=0
```

10.0.13 and 10.0.14 Core DLLs still have different sha256 values. The method bodies do not. The module MVID differs. This phase does not attribute the remaining non-IL bytes.

## QPACK caller scan

`callers` scans every method body for the metadata tokens of the named type. `evidence/logs/qpack-callers.txt`:

```text
Query=EncoderStreamReader
Tokens=13
CallerMethods=0
Query=DecoderStreamReader
Tokens=8
CallerMethods=0
Query=Http3.QPack.DynamicTable
Tokens=6
CallerMethods=5
```

The five DynamicTable hits are all inside `EncoderStreamReader` (`.ctor`, `ProcessValue`, `OnDynamicTableCapacity`, `OnDuplicate`, `GetHeader`). Combined with `CallerMethods=0` for `EncoderStreamReader`, nothing else in the Core DLL calls that reader.

`grep -R -n -E 'QPack|Http3Frame|HEADERS|HPack' decomp/quic/10.0.13` printed `QUIC_NO_MATCH`.

`grep -R -n 'IsExtendedConnectRequest =' decomp/h3 decomp/h2 decomp/shared` printed assignments to `true` only in `Http2Stream` line 283 for all three versions, and assignments to `false` only in `HttpProtocol.Reset` line 1164. No HTTP/3 file assigns `true`.

`python3 -c 'print("neg497_equals_bitwise_not_0x1F0", (-497 == (~0x1F0)))'` printed:

```text
neg497_equals_bitwise_not_0x1F0 True
```

## Diff of the decision surfaces

```text
python3 make-h3-vs-h2-diff.py
```

printed `wrote .../h3-vs-h2.diff (27848 bytes, diff exit 1)`. Exit 1 from `diff -u` means the excerpt files differ. The inputs are `excerpts/h2-10.0.13-decisions.txt` and `excerpts/h3-10.0.13-decisions.txt`, copied from the line ranges in `make-h3-vs-h2-diff.py`.

## HONEST-CATCH / SKEPTIC

A static map does not prove a bug. Nothing in this directory was checked against a running server. No MSRC report and no bounty submission follows from it. Both stay gated on an explicit yes from Santhosh and are out of scope here.

**Verdict: NO-GO.** The three request paths in this build are not the same protocol, and they are consistent on the fields that would make a cross-protocol length or request-line bug: accepted method, path, and body length.

What the decompilation shows, and what it does not:

1. **`:protocol` rejection.** HTTP/2 always rejects `:protocol` unless the method is CONNECT, and then requires scheme and path and sets `IsExtendedConnectRequest` (`Http2Stream` `265–283`). HTTP/3 runs the "must be CONNECT" check only when `EnableWebTransportAndH3Datagrams` is true (`Http3Stream` `837–845`). The getter defaults from an AppContext switch (`KestrelServerOptions` `109–118`). `ClearPseudoRequestHeaders` removes the protocol bit from the enumerated header set (`HttpRequestHeaders` `7569–7572`). A non-CONNECT `:protocol` on HTTP/3 therefore does not change method, path, or Content-Length in this code. It changes accept versus reject. That is a protocol-compliance candidate, not a reconstructed-request difference. Confirming it needs a live HTTP/3 request and a live HTTP/2 request on this build, with the switch left unset. That live check is out of scope. This phase does not claim the server accepts the request.

2. **Extended CONNECT body cap.** HTTP/2 sets `IsExtendedConnectRequest` and `Http2MessageBody.AdvanceTo` skips the observed-byte cap when that flag is set (`169–176`). HTTP/3 never assigns the flag. `Http3MessageBody.AdvanceTo` always calls `AddAndCheckObservedBytes` (`155–159`). Whether a CONNECT with `:protocol`, `:scheme`, and `:path` is accepted on HTTP/3 with the switch off, and whether the body cap then differs, needs the same live check. Not done. Not a finding.

3. **Dynamic-table newline flag.** HTTP/3 `OnHeaderCore` passes `checkForNewlineChars: false` for a dynamic field with no static index (`425`). HTTP/2 in 10.0.13 passes `true` (`1225`). 10.0.12 HTTP/2 passed `false` (the diff quoted above). `QPackDecoder` throws `net_http_qpack_no_dynamic_table` instead of calling `OnDynamicIndexedHeader` (`642–644`), and the caller scan found no caller of `EncoderStreamReader`. The `false` argument is not on the live HTTP/3 header path. Literal headers use `true` on both HTTP/2 and HTTP/3 (`1231` and `431`). No live check is justified for this branch unless a caller shows up. None did.

4. **Transfer-Encoding.** HTTP/1.1 can select a chunked body and move Content-Length to `X-Content-Length` (`c5-kestrel/decomp/after/...Http1MessageBody.decompiled.cs` `135–151`). HTTP/2 and HTTP/3 literal headers reject `te` unless the value is `trailers`, and the body is the DATA payload checked against Content-Length. That is the protocol difference, not a second framing of the same bytes. HTTP/2 static index 57 is `transfer-encoding` with an empty value, and the static path does not call `ValidateHeaderContent`. The body reader is still the DATA-frame reader. A live check would be required to see whether that empty header is visible to an application. It would not, on this decompilation, switch the body to chunked. Not done.

5. **QPACK memory.** Integer decode rejects a bad shift and a negative accumulator (`IntegerDecoder` `26–40`). String length is rejected above the configured field cap before the copy (`QPackDecoder` `522–526`). `Huffman.Decode` doubles the destination with no max argument (`143–146`). The encoded length was already capped; the decoded length is counted later in `OnHeaderCore`. The frame reader slices the buffer it already has (`Http3FrameReader` `27–34`). The dynamic-table types are stubs or unused (`CallerMethods=0`). None of this is a demonstrated memory-safety bug. A later review could look at Huffman output size against the field cap. This phase does not supply an input, a length, or a proof.

What would be required to move any of (1), (2), or (4) off NO-GO is a live HTTP/3 and HTTP/2 run against this exact 10.0.13 package, plus a record of the response code, the application-visible method, path, headers, and body length. That is a later phase. It is not this one.

If that live check shows the three paths accept the same method, path, and body, the candidate stays a NO-GO. If it shows a difference, that difference needs its own evidence. This directory does not contain it.
