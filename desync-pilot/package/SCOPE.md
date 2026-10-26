# Two-week pilot scope

Draft. Not sent.

The pilot is a static replay of the published oracle plus one config gate the buyer runs in their own lab. The auditor does not start a server and does not send a request.

## In

Week 1, static, offline:

- Re-pin the public bytes with `desync-pilot/runner/audit.py --dry-run`, which checks `desync-oracle/FREEZES.txt`.
- One or both published profiles, named in the order:
  - `nginx-proxy_pass-default` (nginx 1.28.3 `proxy_pass`)
  - `haproxy-mode-http-default` (HAProxy 3.4.7 `mode http`)
- The three replay files for each named profile: conformance map, hardening checklist, verdict (`GO`, `HARDENING-REQUIRED`, or `NO-GO`).
- A short written report in the shape of `sample-report/SAMPLE-BUYER-REPORT.md`, using the buyer's deployment name and the sealed counts for the named profile. Origin behaviour stays behaviour. Origin implementation text stays out.

Week 2, one live gate, buyer-operated, lab only:

- The buyer, on a non-production copy of their own front, confirms two facts and writes them down:
  1. The installed front build is the pinned version named in the profile.
  2. The directives that the sealed rating depends on are still the scored defaults. For nginx that is H-ARCH and the nginx rows of H-DEFAULTS in `desync-oracle/HARDENING.md` (`proxy_pass` present, `proxy_request_buffering` left on, the default header table still supplying Content-Length and Transfer-Encoding). For HAProxy that is H-ARCH and the HAProxy rows of H-DEFAULTS (`mode http`, `option accept-unsafe-violations-in-http-request` unset, `h1-do-not-close-on-insecure-transfer-encoding` unset).
- The gate result is pass or fail against that checklist. A fail means the sealed verdict does not apply to that deployment. It does not by itself become `NO-GO`.
- The buyer does not point this gate at production traffic.

The sealed score already records `NEEDS-LIVE` as 0 on both default profiles. The lab gate checks that the deployment is still that default. It is not a second scoring of the 25 rules.

## Out

- Production traffic, and any request the auditor sends.
- An exploit proof of concept, a request sample, or a procedure for building a message.
- A change to the sealed 25-rule score.
- nginx `stream`, HAProxy `mode tcp`, or Kestrel published with no HTTP front.
- nginx 1.30, HAProxy 3.5, HAProxy 3.2, HAProxy 2.8, HTTP/2, and HTTP/3. Those were not read (`desync-oracle/README.md`).
- Envoy, Traefik, and a CDN edge. Those are future work. They are not part of this pilot.
- Origin implementation text, or a line number inside the origin.
- A live observation engagement in which the auditor watches an upstream connection. That is a separate follow-on, priced apart in `PRICE.md`, and it is not started by this pilot.

## Stop rule

If the lab gate fails, the written verdict says the sealed word does not apply, and the engagement stops for a decision. The pilot does not retune the 25 rules to fit the buyer's config.
