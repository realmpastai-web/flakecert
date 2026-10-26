# Score summary

Sealed holdout. Same 25 rule identifiers on both edges. Scored once. `SKEPTIC.md` did not change the score.

No row on either edge is NEEDS-LIVE.

## nginx 1.28.3, default `proxy_pass`

| Count | Value |
| --- | --- |
| Rules | 25 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 24 |
| PAYABLE | 1 |
| NOT-PAYABLE | 24 |
| NEEDS-LIVE | 0 |

Verdict: **HARDENING-REQUIRED**

## HAProxy 3.4.7, default `mode http`

| Count | Value |
| --- | --- |
| Rules | 25 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 25 |
| PAYABLE | 0 |
| NOT-PAYABLE | 25 |
| NEEDS-LIVE | 0 |

Verdict: **GO**
