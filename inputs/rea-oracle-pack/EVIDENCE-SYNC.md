# Evidence sync — C7@434e35b into inputs/rea-oracle-pack/evidence

Static copy only. No process was started. No network call was made.
Source tree: `/workspace/hark-tasks/flakecert-c7-kestrel-h3`
Commit: `434e35bff54fdfb162c7d0bf6f596c92ef3eff21` (`git rev-parse HEAD`).
C5 files are the `c5-kestrel/decomp/after/` copies inside that same commit, not a second checkout.
C6 YARP FINDINGS is not in this commit. No C6 path is cited.

Command: `cp -a` of each source onto the evidence path, then `sha256sum` of the source list and of the copy list. A pair matches when the two hashes are equal.

## sha256sum source (verbatim)

```text
9ef76128d0dfd7be491631e8f70fce36a84f6f7ba52fabf5d627c36b590c05f9  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h3/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http3.Http3Stream.decompiled.cs
323f8e701f3b2e3bd6ebf9a44cc82967128b506b2d6cdef703a61648543c3dff  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h3/10.0.13/System.Net.Http.QPack.QPackDecoder.decompiled.cs
3aa5871eb34fd2b38b2300ba220cbee757320c1f0fcabfe3c15204cf1da3a4a8  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h3/10.0.13/System.Net.Http.QPack.H3StaticTable.decompiled.cs
a66c6b888e15fc014dc0e6c2125db138dc9c5275607761a6b2af90b1903bb15e  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h2/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http2.Http2Stream.decompiled.cs
59185957bdc93db22669115e1be443d41a075e82d18df3d8e57adb1e93f5258b  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h2/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http2.Http2Connection.decompiled.cs
5826482e527ee8d33fa43f73298eece902d757f70649563811d310362f90423f  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h2/10.0.13/System.Net.Http.HPack.H2StaticTable.decompiled.cs
8d33b21eaefc9e6b2d8e29169c5e2a31603d070cfc2f55094a9803850213b7a6  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/shared/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure.HttpUtilities.decompiled.cs
6d57a69a54e8e783f9272ac0c02257894cd2cd79c40ffcae15debdfdded99f47  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/shared/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpRequestHeaders.decompiled.cs
f02d9a62ecaa1f3080163a463024405d3bf92cd681577fbf388c1f2137e67dce  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/shared/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpProtocol.decompiled.cs
a07d7da1b2808c20cbbc1ef31e62ebfd33f2a836fe3576a7811e2dfe0fbb0746  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/shared/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.KestrelServerOptions.decompiled.cs
fbedfa5d215cf8d5fb6fed96237165cbf82a64e71a83c857fbbae4c6fecab767  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.Http1MessageBody.decompiled.cs
249f3348e4aadf8acc82af2485eec2b99d82c9c590c5786d6136d08b3e9999d1  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.Http1ParsingHandler.decompiled.cs
56ed8adc77f580c756ae27a41c436e83e9a12242a29442eee22d6a9811496c27  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpParser`1.decompiled.cs
63e065dd0aab21ea852a6350ebc2edb515c57a02506a6ad0f6124d67d5006bd5  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.Http1Connection.decompiled.cs
8d33b21eaefc9e6b2d8e29169c5e2a31603d070cfc2f55094a9803850213b7a6  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure.HttpUtilities.decompiled.cs
6d57a69a54e8e783f9272ac0c02257894cd2cd79c40ffcae15debdfdded99f47  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpRequestHeaders.decompiled.cs
f02d9a62ecaa1f3080163a463024405d3bf92cd681577fbf388c1f2137e67dce  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpProtocol.decompiled.cs
a51e3409fb49e29a5f071634b2314694e4dd4f33f2fda5c5e32f97c0173673b5  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpHeaders.decompiled.cs
093e246b9bc82875387f72665d7979affb14ca58d5cc84530e4854f1e2c5011b  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.Http1ContentLengthMessageBody.decompiled.cs
```

## sha256sum copy (verbatim)

```text
9ef76128d0dfd7be491631e8f70fce36a84f6f7ba52fabf5d627c36b590c05f9  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/Http3Stream.decompiled.cs
323f8e701f3b2e3bd6ebf9a44cc82967128b506b2d6cdef703a61648543c3dff  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/QPackDecoder.decompiled.cs
3aa5871eb34fd2b38b2300ba220cbee757320c1f0fcabfe3c15204cf1da3a4a8  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/H3StaticTable.decompiled.cs
a66c6b888e15fc014dc0e6c2125db138dc9c5275607761a6b2af90b1903bb15e  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/Http2Stream.decompiled.cs
59185957bdc93db22669115e1be443d41a075e82d18df3d8e57adb1e93f5258b  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/Http2Connection.decompiled.cs
5826482e527ee8d33fa43f73298eece902d757f70649563811d310362f90423f  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/H2StaticTable.decompiled.cs
8d33b21eaefc9e6b2d8e29169c5e2a31603d070cfc2f55094a9803850213b7a6  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/HttpUtilities.decompiled.cs
6d57a69a54e8e783f9272ac0c02257894cd2cd79c40ffcae15debdfdded99f47  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/HttpRequestHeaders.decompiled.cs
f02d9a62ecaa1f3080163a463024405d3bf92cd681577fbf388c1f2137e67dce  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/HttpProtocol.decompiled.cs
a07d7da1b2808c20cbbc1ef31e62ebfd33f2a836fe3576a7811e2dfe0fbb0746  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/KestrelServerOptions.decompiled.cs
fbedfa5d215cf8d5fb6fed96237165cbf82a64e71a83c857fbbae4c6fecab767  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/Http1MessageBody.decompiled.cs
249f3348e4aadf8acc82af2485eec2b99d82c9c590c5786d6136d08b3e9999d1  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/Http1ParsingHandler.decompiled.cs
56ed8adc77f580c756ae27a41c436e83e9a12242a29442eee22d6a9811496c27  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/HttpParser`1.decompiled.cs
63e065dd0aab21ea852a6350ebc2edb515c57a02506a6ad0f6124d67d5006bd5  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/Http1Connection.decompiled.cs
8d33b21eaefc9e6b2d8e29169c5e2a31603d070cfc2f55094a9803850213b7a6  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/HttpUtilities.decompiled.cs
6d57a69a54e8e783f9272ac0c02257894cd2cd79c40ffcae15debdfdded99f47  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/HttpRequestHeaders.decompiled.cs
f02d9a62ecaa1f3080163a463024405d3bf92cd681577fbf388c1f2137e67dce  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/HttpProtocol.decompiled.cs
a51e3409fb49e29a5f071634b2314694e4dd4f33f2fda5c5e32f97c0173673b5  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/HttpHeaders.decompiled.cs
093e246b9bc82875387f72665d7979affb14ca58d5cc84530e4854f1e2c5011b  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/Http1ContentLengthMessageBody.decompiled.cs
```

## Cross-check (hash source == hash copy)

```text
MATCH 9ef76128d0dfd7be491631e8f70fce36a84f6f7ba52fabf5d627c36b590c05f9
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h3/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http3.Http3Stream.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/Http3Stream.decompiled.cs
MATCH 323f8e701f3b2e3bd6ebf9a44cc82967128b506b2d6cdef703a61648543c3dff
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h3/10.0.13/System.Net.Http.QPack.QPackDecoder.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/QPackDecoder.decompiled.cs
MATCH 3aa5871eb34fd2b38b2300ba220cbee757320c1f0fcabfe3c15204cf1da3a4a8
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h3/10.0.13/System.Net.Http.QPack.H3StaticTable.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/H3StaticTable.decompiled.cs
MATCH a66c6b888e15fc014dc0e6c2125db138dc9c5275607761a6b2af90b1903bb15e
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h2/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http2.Http2Stream.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/Http2Stream.decompiled.cs
MATCH 59185957bdc93db22669115e1be443d41a075e82d18df3d8e57adb1e93f5258b
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h2/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http2.Http2Connection.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/Http2Connection.decompiled.cs
MATCH 5826482e527ee8d33fa43f73298eece902d757f70649563811d310362f90423f
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h2/10.0.13/System.Net.Http.HPack.H2StaticTable.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/H2StaticTable.decompiled.cs
MATCH 8d33b21eaefc9e6b2d8e29169c5e2a31603d070cfc2f55094a9803850213b7a6
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/shared/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure.HttpUtilities.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/HttpUtilities.decompiled.cs
MATCH 6d57a69a54e8e783f9272ac0c02257894cd2cd79c40ffcae15debdfdded99f47
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/shared/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpRequestHeaders.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/HttpRequestHeaders.decompiled.cs
MATCH f02d9a62ecaa1f3080163a463024405d3bf92cd681577fbf388c1f2137e67dce
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/shared/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpProtocol.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/HttpProtocol.decompiled.cs
MATCH a07d7da1b2808c20cbbc1ef31e62ebfd33f2a836fe3576a7811e2dfe0fbb0746
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/shared/10.0.13/Microsoft.AspNetCore.Server.Kestrel.Core.KestrelServerOptions.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/KestrelServerOptions.decompiled.cs
MATCH fbedfa5d215cf8d5fb6fed96237165cbf82a64e71a83c857fbbae4c6fecab767
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.Http1MessageBody.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/Http1MessageBody.decompiled.cs
MATCH 249f3348e4aadf8acc82af2485eec2b99d82c9c590c5786d6136d08b3e9999d1
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.Http1ParsingHandler.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/Http1ParsingHandler.decompiled.cs
MATCH 56ed8adc77f580c756ae27a41c436e83e9a12242a29442eee22d6a9811496c27
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpParser`1.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/HttpParser`1.decompiled.cs
MATCH 63e065dd0aab21ea852a6350ebc2edb515c57a02506a6ad0f6124d67d5006bd5
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.Http1Connection.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/Http1Connection.decompiled.cs
MATCH 8d33b21eaefc9e6b2d8e29169c5e2a31603d070cfc2f55094a9803850213b7a6
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Infrastructure.HttpUtilities.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/HttpUtilities.decompiled.cs
MATCH 6d57a69a54e8e783f9272ac0c02257894cd2cd79c40ffcae15debdfdded99f47
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpRequestHeaders.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/HttpRequestHeaders.decompiled.cs
MATCH f02d9a62ecaa1f3080163a463024405d3bf92cd681577fbf388c1f2137e67dce
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpProtocol.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/HttpProtocol.decompiled.cs
MATCH a51e3409fb49e29a5f071634b2314694e4dd4f33f2fda5c5e32f97c0173673b5
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.HttpHeaders.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/HttpHeaders.decompiled.cs
MATCH 093e246b9bc82875387f72665d7979affb14ca58d5cc84530e4854f1e2c5011b
  SRC /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/decomp/after/Microsoft.AspNetCore.Server.Kestrel.Core.Internal.Http.Http1ContentLengthMessageBody.decompiled.cs
  DST /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/Http1ContentLengthMessageBody.decompiled.cs
```

Shared header types copied from both trees have one hash, so the C5 "after" file and the C7 `decomp/shared/10.0.13` file are the same bytes:

```text
HttpUtilities.decompiled.cs        8d33b21eaefc9e6b2d8e29169c5e2a31603d070cfc2f55094a9803850213b7a6
HttpRequestHeaders.decompiled.cs   6d57a69a54e8e783f9272ac0c02257894cd2cd79c40ffcae15debdfdded99f47
HttpProtocol.decompiled.cs         f02d9a62ecaa1f3080163a463024405d3bf92cd681577fbf388c1f2137e67dce
```

## Absence check used by OR-002

Command:

```text
grep -n "IsExtendedConnectRequest =" /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/decomp/h3/10.0.13/*.cs
```

Output: no lines. The pattern does not occur in the HTTP/3 10.0.13 decompilation. `HttpProtocol.Reset` still assigns `IsExtendedConnectRequest = false` at line 1164 of the shared file (copied above).


## Additional committed prose cited by SKEPTIC.md

These are not decomp. They are copied so the skeptic's CVE and NO-GO citations resolve inside the pack. Hashes below are the verbatim `sha256sum` output.

### sha256sum source (verbatim)

```text
8561d833124720b85a05bb337066a034fbaff8e98a16badd2637e50fef19bc8b  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c5-kestrel/SPEC.md
831f4570f043b387dc989f49334d6b7fbcb9e43f72f01e68567d20154585e5c5  /workspace/hark-tasks/flakecert-c7-kestrel-h3/c7-kestrel-h3/EVIDENCE.md
```

### sha256sum copy (verbatim)

```text
8561d833124720b85a05bb337066a034fbaff8e98a16badd2637e50fef19bc8b  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c5/SPEC.md
831f4570f043b387dc989f49334d6b7fbcb9e43f72f01e68567d20154585e5c5  /workspace/hark-tasks/flakecert-oracle-pack-run/inputs/rea-oracle-pack/evidence/c7/EVIDENCE.md
```

MATCH 8561d833124720b85a05bb337066a034fbaff8e98a16badd2637e50fef19bc8b c5-kestrel/SPEC.md -> evidence/c5/SPEC.md
MATCH 831f4570f043b387dc989f49334d6b7fbcb9e43f72f01e68567d20154585e5c5 c7-kestrel-h3/EVIDENCE.md -> evidence/c7/EVIDENCE.md
