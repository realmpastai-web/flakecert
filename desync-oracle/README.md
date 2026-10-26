# HTTP/1.1 request-boundary conformance oracle

Static acceptance record for two default HTTP fronts in front of a .NET Kestrel origin:

- nginx 1.28.3 `proxy_pass`
- HAProxy 3.4.7 `mode http` with the HTTP/1 mux

The oracle scores one sealed set of 25 request-boundary rules (R01–R25) on each edge. It states what each front does, what the origin does, and whether that difference is still present on the request the front writes upstream.

## What this is

An operator checklist and a conformance map. The class name for inconsistent interpretation of an HTTP request is CWE-444. This oracle uses that name as the class. It does not add a technique, a sample message, or a procedure.

Origin behaviour is described as behaviour. This tree does not publish origin implementation text, and it does not cite origin source line numbers.

## Scope boundary

This directory is a static clean-room document build.

- No server is started.
- No request is sent.
- No new URL is fetched. The pinned bytes are the files under `pins/`, identified by the sha256 values in `FREEZES.txt`.
- Nothing in this tree is a live test. No row is waiting on a socket observation. The score says so by marking NEEDS-LIVE as zero on both edges.

The ratings apply only to the default HTTP proxy path named for each edge. They do not apply to nginx `stream`, to HAProxy `mode tcp`, to any other front that forwards client bytes without parsing the HTTP/1 request, or to Kestrel published on its own.

## Method

Two-team clean-room, applied to public artifacts:

1. **Spec first.** Each front's HTTP/1.1 request-boundary behaviour was read from that front's own public source at the pinned tarball. The rule list was fixed at 25 identifiers before either edge was scored. Normative text is RFC 9112 and RFC 9110, pinned as `pins/rfc9112.txt` and `pins/rfc9110.txt`.
2. **Build only from that spec.** The comparison in `CONFORMANCE-MAP.md` uses the front's public file and line, plus a plain-language statement of origin behaviour. It does not copy origin implementation text into this tree.
3. **Check against public behaviour.** Front line ranges name files inside the pinned tarballs. `FREEZES.txt` records the tarball sha256 values. A later reader can open those tarballs and read the same lines.
4. **Frozen baseline.** `FREEZES.txt` is the sha256 freeze of the public pins and of the documents in this directory. It does not list itself.
5. **Sealed holdout.** The 25 rule identifiers were scored once. `SCORE-SUMMARY.md` is that score. The skeptic pass in `SKEPTIC.md` tries to knock the verdicts down. It does not change the score.
6. **Skeptic.** `SKEPTIC.md` is the adversarial pass. What survived is the verdict in `VERDICT.md`.

## Pins

| Artifact | Public location | sha256 |
| --- | --- | --- |
| nginx 1.28.3 | `https://nginx.org/download/nginx-1.28.3.tar.gz` | `2c96a946bfb0882a21744ed429770a2123ae1828c7c48665092993ddee91a918` |
| HAProxy 3.4.7 | `https://www.haproxy.org/download/3.4/src/haproxy-3.4.7.tar.gz` | `ccfd342f3724c2cd659574044d788f44e20b212467c6bd5edbbfc517a2775dca` |
| RFC 9110 | RFC 9110, HTTP Semantics | `21c1cdce6ab0e5509b04d84a28000836c7a087cf786efe6f04877ebfff47232a` |
| RFC 9112 | RFC 9112, HTTP/1.1 | `e4f426bac6206b67fdf9e0da826154f70588db2133a0a86b15cde4ff725d8937` |

Local copies are `pins/nginx-1.28.3.tar.gz`, `pins/haproxy-3.4.7.tar.gz`, `pins/rfc9110.txt`, and `pins/rfc9112.txt`. nginx in this tarball is the 2-clause BSD license shipped with it. HAProxy in this tarball is GNU GPL version 2 for the program and GNU LGPL version 2.1 for the exportable headers, plus the OpenSSL linking exception in that tarball's `LICENSE`.

The origin is the Kestrel HTTP/1.1 parser in `Microsoft.AspNetCore.App.Runtime.linux-x64` 10.0.12. The framing behaviour scored here is the same in 10.0.13. Statements about that parser are behaviour statements.

On 2026-10-26 the nginx.org download page listed 1.28.3 under Legacy. nginx 1.30 was not read. On the same date the HAProxy project listed 3.4.7 as the current 3.4 build. HAProxy 3.5, 3.2, and 2.8 were not read.

## Result

| Edge | Verdict |
| --- | --- |
| nginx 1.28.3 `proxy_pass` | **HARDENING-REQUIRED** (one MEDIUM row, R13) |
| HAProxy 3.4.7 `mode http` | **GO** (no MEDIUM row, no HIGH row) |

Detail is in `VERDICT.md`. Counts are in `SCORE-SUMMARY.md`. What to set is in `HARDENING.md`.

## Read this order

1. `CONFORMANCE-MAP.md` — R01–R25 for both edges.
2. `HARDENING.md` — operator checklist.
3. `VERDICT.md` — the two verdicts.
4. `SKEPTIC.md` — the attempt to knock them down.
5. `SCORE-SUMMARY.md` — sealed counts.
6. `FREEZES.txt` — sha256 freeze.

## Verify

From `desync-oracle/`:

```bash
sha256sum -c FREEZES.txt
./leak-scan.sh
```

`leak-scan.sh` scans this directory and the staged diff. It exits non-zero if a forbidden token is present. `FREEZES.txt` does not list itself.
