# Skeptic

Adversarial pass on the pilot replay. This file does not edit `desync-oracle/SCORE-SUMMARY.md`. The sealed score stays the sealed score.

The inspect side and the build side were the same session. `SPEC.md` is the hand-off. That is a weaker split than two people. It is recorded here and in `METHOD.md`.

## The replay might have invented a count

It did not, on the dry-run that this file quotes. The command was:

```bash
python3 desync-pilot/runner/audit.py --all --dry-run
```

Stdout:

```text
verdict_function_assert: ok
profile: haproxy-mode-http-default
pin: pins/haproxy-3.4.7.tar.gz
pin_sha256: ccfd342f3724c2cd659574044d788f44e20b212467c6bd5edbbfc517a2775dca
pin_check: ok
freezes_checked: 11
rules: 25
HIGH: 0
MEDIUM: 0
LOW: 25
PAYABLE: 0
NOT-PAYABLE: 25
NEEDS-LIVE: 0
verdict: GO
sealed_score: GO
sealed_verdict: GO
medium_rows: none
high_rows: none
wrote: desync-pilot/out/haproxy-mode-http-default/conformance-map.md
wrote: desync-pilot/out/haproxy-mode-http-default/hardening.md
wrote: desync-pilot/out/haproxy-mode-http-default/verdict.md
wrote: desync-pilot/out/haproxy-mode-http-default/RUNLOG.txt
wrote: desync-pilot/out/haproxy-mode-http-default/SHA256SUMS
---
profile: nginx-proxy_pass-default
pin: pins/nginx-1.28.3.tar.gz
pin_sha256: 2c96a946bfb0882a21744ed429770a2123ae1828c7c48665092993ddee91a918
pin_check: ok
freezes_checked: 11
rules: 25
HIGH: 0
MEDIUM: 1
LOW: 24
PAYABLE: 1
NOT-PAYABLE: 24
NEEDS-LIVE: 0
verdict: HARDENING-REQUIRED
sealed_score: HARDENING-REQUIRED
sealed_verdict: HARDENING-REQUIRED
medium_rows: R13-OWS-HTAB
high_rows: none
wrote: desync-pilot/out/nginx-proxy_pass-default/conformance-map.md
wrote: desync-pilot/out/nginx-proxy_pass-default/hardening.md
wrote: desync-pilot/out/nginx-proxy_pass-default/verdict.md
wrote: desync-pilot/out/nginx-proxy_pass-default/RUNLOG.txt
wrote: desync-pilot/out/nginx-proxy_pass-default/SHA256SUMS
---
```

`desync-oracle/FREEZES.txt` has 11 lines. `sha256sum -c FREEZES.txt` from `desync-oracle/` printed `OK` for all 11. The nginx MEDIUM id is the published R13-OWS-HTAB row. No HIGH id was emitted.

A first parse treated the header row as a data row because it starts with `| R`. Stderr was `audit: chain cell 'Chain' on Rule`. `SPEC.md` was tightened so a data row is `| R` plus two digits and a hyphen, and the runner was changed to that rule. The stdout above is after that fix. The sealed oracle files were not edited.

## NO-GO was not produced by a published profile

Both published tables have zero HIGH cells, so both dry-runs stay off the NO-GO branch. The only exercise of that branch is the in-memory assert printed as `verdict_function_assert: ok`, which checks `(1, 0) → NO-GO`, `(0, 1) → HARDENING-REQUIRED`, and `(0, 0) → GO`. That assert does not create a finding and does not read the oracle.

If a later edit put a HIGH cell in the table and left the sealed word as something else, the runner is specified to exit 1 and write nothing. That path was not demonstrated against a modified oracle. There is no NO-GO report in `out/`.

Calling `--dry-run` omitted exits 2 (`audit: only --dry-run is implemented`). An unknown profile exits 2 (`audit: unknown profile missing`). Neither path writes a verdict.

## The pin check does not re-read source lines

The runner hashes the tarball. It does not open members inside it. A pin can match `FREEZES.txt` and a cited line range can still have been misread when the oracle was written. This package does not repeat that citation check. The line cites in the sample report are the cites already published in `desync-oracle/CONFORMANCE-MAP.md` and `desync-oracle/VERDICT.md`.

`grep` of `desync-pilot/runner/audit.py` for `socket`, `urllib`, `requests`, `http.client`, and `subprocess` printed `no network imports`.

## The profile map still contains both fronts' narratives

`out/<profile>/conformance-map.md` copies the published `## Rules` section through the end of `CONFORMANCE-MAP.md`, as `SPEC.md` requires. That section discusses both edges. The profile's own table is the `## nginx edge` or `## HAProxy edge` block above it. A reader who treats a HAProxy sentence inside the nginx file as a new nginx row would be misreading the replay. The banner says the file is not a new score.

## The sample report could have drifted from the replay

The 25 lines in `sample-report/SAMPLE-BUYER-REPORT.md` that match `| R` plus two digits were compared with the same lines in `out/nginx-proxy_pass-default/conformance-map.md`. The command printed:

```text
sample_rule_rows 25
replay_rule_rows 25
identical True
```

The sample says the lab gate was not run. It does not claim ACME's installed nginx matched the pin.

## Buyer-targeting notes and fee figures are not in this tree

An earlier draft of this pilot carried human pages for a buyer note, a fee band, an offer, and a two-week scope. Those pages are not in this public tree. This pass did not re-check them, and they are not evidence for the replay. They are not a sent offer. Nothing was sent.

The sample report remains `sample-report/SAMPLE-BUYER-REPORT.md`. Its buyer name is ACME, a placeholder. It does not state a fee.

## What this pass does not claim

The leak gate can miss a name that was never added to its needle list. It scans the tokens `SPEC.md` and `leak-scan.sh` name. A clean exit means those needles were absent from `desync-pilot/`. It does not mean every possible organisation name was searched.

Envoy, Traefik, and a CDN edge are named as future work in the sample report. No profile exists for them. The runner will not emit a verdict for them.
