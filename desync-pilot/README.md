# Desync audit pilot — static runner

Offline replay of the published HTTP/1.1 request-boundary oracle in `desync-oracle/`. An operator uses it to re-pin the public front bytes and to emit a conformance map, a hardening checklist, and a verdict for one scored profile.

The method is `METHOD.md`. The build contract is `SPEC.md`. The sealed score stays in `desync-oracle/SCORE-SUMMARY.md`. This directory does not score a new rule.

## Profiles

| Profile id | Published edge | Sealed verdict |
| --- | --- | --- |
| `nginx-proxy_pass-default` | nginx 1.28.3 `proxy_pass` | HARDENING-REQUIRED |
| `haproxy-mode-http-default` | HAProxy 3.4.7 `mode http` | GO |

Those words are the sealed words. The runner prints them again only after the table, `SCORE-SUMMARY.md`, and `VERDICT.md` agree. A `HIGH` cell would map to `NO-GO`. The published tables have no `HIGH` cell.

## Run offline

Python 3, standard library only. No network. No server. The command hashes the files named in `desync-oracle/FREEZES.txt` and writes Markdown under `desync-pilot/out/<profile>/`.

From the repository root:

```bash
python3 desync-pilot/runner/audit.py --all --dry-run
```

One profile:

```bash
python3 desync-pilot/runner/audit.py --profile nginx-proxy_pass-default --dry-run
python3 desync-pilot/runner/audit.py --profile haproxy-mode-http-default --dry-run
```

`--dry-run` is required. There is no live mode.

Each output directory contains:

- `conformance-map.md`
- `hardening.md`
- `verdict.md`
- `RUNLOG.txt` — the same lines the command prints
- `SHA256SUMS` — digests of those four files

## Check the freezes and the leak gate

```bash
( cd desync-oracle && sha256sum -c FREEZES.txt )
( cd desync-pilot && sha256sum -c FREEZES.txt )
desync-pilot/leak-scan.sh
```

`desync-pilot/FREEZES.txt` lists this package and does not list itself. `leak-scan.sh` scans `desync-pilot/` only.

## Drafts a human might send later

`sample-report/SAMPLE-BUYER-REPORT.md` is a redacted sample. The buyer name in it is ACME.

`package/` holds the ideal-customer note, the two-week scope, a draft price band, and a proposal draft. The proposal header says not to send it without Santhosh's yes. This runner does not send mail and does not post.
