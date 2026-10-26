# SPEC — static desync-audit pilot runner

Evidence-cited hand-off for the build. The inspect side and the build side are the same session. This file is the only hand-off. The build does not add rules, ratings, or request samples.

The published artifact is `desync-oracle/` at git `2c9209e1` (full `2c9209e1071456e9408497a35e914e43dd37e17c`). This spec cites that tree. It does not cite a private pack path.

## 1. What the runner is

A front-agnostic static replay. It re-checks the sha256 lines in `desync-oracle/FREEZES.txt`, reads one named profile, and writes three Markdown files from the published oracle text:

- `conformance-map.md`
- `hardening.md`
- `verdict.md`

The verdict word is one of `GO`, `HARDENING-REQUIRED`, or `NO-GO`.

The runner has one mode, `--dry-run`. That mode reads files and hashes the pinned bytes. It does not open a socket, does not start a server, and does not parse the inside of a tarball.

## 2. Published facts the replay is allowed to use

Cited from the files named here. The build copies these facts. It does not replace them.

| Fact | Source |
| --- | --- |
| Pins and document hashes | `desync-oracle/FREEZES.txt` |
| 25 rule rows, chain column, label column, count line, rubric | `desync-oracle/CONFORMANCE-MAP.md` |
| Checklist text | `desync-oracle/HARDENING.md` |
| Sealed verdict word and the edge write-up | `desync-oracle/VERDICT.md` |
| Sealed count table | `desync-oracle/SCORE-SUMMARY.md` |
| nginx 1.28.3 `proxy_pass` is HARDENING-REQUIRED, 0 HIGH, 1 MEDIUM, 24 LOW | `desync-oracle/SCORE-SUMMARY.md` and `desync-oracle/VERDICT.md` |
| HAProxy 3.4.7 `mode http` is GO, 0 HIGH, 0 MEDIUM, 25 LOW | same two files |
| The one MEDIUM row on nginx is R13-OWS-HTAB | `desync-oracle/CONFORMANCE-MAP.md` nginx table |
| HIGH means the rebuilt request still carries a Content-Length, a Transfer-Encoding, or a request line the two parsers would delimit differently | rubric in `desync-oracle/CONFORMANCE-MAP.md` |
| MEDIUM means the rebuilt request still carries a field the two parsers extract differently | same rubric |
| No published row is NEEDS-LIVE | `desync-oracle/SCORE-SUMMARY.md` |

## 3. Profiles

Two profiles. The file name is the profile id.

`profiles/nginx-proxy_pass-default.json`

- edge_heading: nginx edge
- count_prefix: `nginx count:`
- score_heading: nginx 1.28.3, default `proxy_pass`
- verdict_heading: nginx 1.28.3 `proxy_pass`
- pin_rel: `pins/nginx-1.28.3.tar.gz`
- rebuild_prefix: `**nginx.**`

`profiles/haproxy-mode-http-default.json`

- edge_heading: HAProxy edge
- count_prefix: `HAProxy count:`
- score_heading: HAProxy 3.4.7, default `mode http`
- verdict_heading: HAProxy 3.4.7 `mode http`
- pin_rel: `pins/haproxy-3.4.7.tar.gz`
- rebuild_prefix: `**HAProxy.**`

A profile id that is not one of those files is an error. The runner does not invent a third front.

## 4. Checks, in order, before any output file is written

1. Resolve the oracle directory. Default is the sibling `desync-oracle/` next to `desync-pilot/`. `--oracle` overrides it.
2. Read `FREEZES.txt`. For every line, sha256 the named file and require the digest to match. `FREEZES.txt` does not list itself. A mismatch stops the run.
3. Parse the Markdown table under `## <edge_heading>` until the next `## ` heading. Keep the original row lines. A data row matches `| R` plus two digits and a hyphen (the header cell `Rule` does not). A separator row is not a data row.
4. Require exactly 25 data rows, in order, with rule ids whose prefixes are `R01-` through `R25-`.
5. Chain cells are only `LOW`, `MEDIUM`, or `HIGH`. Label cells are only `PAYABLE`, `NOT-PAYABLE`, or `NEEDS-LIVE`.
6. Replay invariant from the published rubric sentence: a `PAYABLE` label occurs only on a `HIGH` or `MEDIUM` chain. The runner does not flip any label.
7. Parse the count line that starts with `count_prefix`. Require it to equal the cells just counted.
8. Parse the score table under `## <score_heading>` in `SCORE-SUMMARY.md` and the first bold word under `## <verdict_heading>` in `VERDICT.md`.
9. Map counts with this function, and no other function:

- `HIGH > 0` → `NO-GO`
- else `MEDIUM > 0` → `HARDENING-REQUIRED`
- else `GO`

10. Require that mapped word to equal both sealed words. If the table and the sealed word disagree, exit 1 and write nothing. That is a failed replay, not a new score.
11. At startup, assert the function on three in-memory pairs: `(1, 0) → NO-GO`, `(0, 1) → HARDENING-REQUIRED`, `(0, 0) → GO`. Those asserts do not read the oracle and do not create a finding. On success the process prints `verdict_function_assert: ok` before any profile.

The published tables have zero `HIGH` cells. The dry-run of the two profiles therefore does not take the `NO-GO` branch. The assert is the only exercise of that branch.

## 5. Files the dry-run writes

Under `desync-pilot/out/<profile-id>/`:

- `conformance-map.md` — banner, verified pin digest, the published rubric section, the rebuild paragraph for this front, the verbatim edge table, the verbatim count line, then the published `## Rules` section through the end of `CONFORMANCE-MAP.md`.
- `hardening.md` — banner, the MEDIUM and HIGH rule ids taken from this profile's table, then the whole of `HARDENING.md`.
- `verdict.md` — banner, the mapped word, the counts, the two sealed cross-checks, then the verbatim verdict section for this profile.
- `RUNLOG.txt` — the profile summary, from the `profile:` line through the `wrote:` lines for that profile. The one-time `verdict_function_assert: ok` line is process stdout only. It is not repeated inside each profile log.
- `SHA256SUMS` — sha256 of the three Markdown files and `RUNLOG.txt`, written last.

`--all --dry-run` runs every profile JSON in lexical order. `--dry-run` is required. There is no other mode.

## 6. What this spec refuses

- A new rule, a changed chain cell, or a changed verdict word.
- Origin implementation text, origin line numbers, or a private pack path.
- Request samples, payload bytes, or a procedure for building a message.
- A live parse of tarball members. Line cites stay inside the frozen oracle documents. This runner proves those documents still hash to `FREEZES.txt`. It does not reopen the tarballs.
- A second holdout score. `desync-oracle/SCORE-SUMMARY.md` remains the sealed score. This replay reports it.

## 7. Package documents are outside the runner

`sample-report/SAMPLE-BUYER-REPORT.md` and `package/*.md` are drafts for a human. They may restate only the published nginx and HAProxy results. They use ACME as the buyer name. Prices, if written, are labeled `DRAFT / NOT SENT` on every figure. Nothing in those drafts is a sent offer.
