# DRAFT — do not send without Santhosh's yes

HTTP/1.1 request-boundary conformance pilot. Two weeks. Placeholder buyer: ACME. This draft has not been sent.

## Who it is for

ACME platform engineering and ACME security engineering, if ACME runs nginx or HAProxy in front of Kestrel and can spare a non-production copy for one config gate. The ideal-customer note is `ICP.md`. Where that note says NEEDS-CITE, this draft does not fill the gap.

## What the two weeks are

Week 1 is an offline replay of the published oracle (`desync-oracle/`) for the profile ACME names: `nginx-proxy_pass-default`, `haproxy-mode-http-default`, or both. ACME receives a conformance map, a hardening checklist, and a verdict on the scale GO / HARDENING-REQUIRED / NO-GO.

Week 2 is one gate ACME runs in ACME's lab: the installed build is the pinned version, and the directives the sealed rating depends on are still the scored defaults. The gate is a checklist. It is not production traffic, and it is not a request from the auditor.

The sealed result already published for those defaults is: nginx 1.28.3 `proxy_pass` is HARDENING-REQUIRED (one MEDIUM row, R13, zero HIGH); HAProxy 3.4.7 `mode http` is GO (zero MEDIUM, zero HIGH). A deployment that fails the lab gate does not inherit that word.

## What stays out

Production traffic. An exploit proof of concept. Any front other than the named profile. Envoy, Traefik, and a CDN edge, which are future work and are not claimed done. Origin implementation text.

Detail is in `SCOPE.md`.

## Draft commercial terms

DRAFT / NOT SENT. Pilot band USD 18,000 for one published profile, or USD 28,000 for both. DRAFT / NOT SENT. Follow-on figures, not part of the pilot: USD 12,000 for each later front after it is pinned, and USD 22,000 for a separate live-observation engagement. DRAFT / NOT SENT. Santhosh replaces these figures before anyone sends this page. `PRICE.md` is the full draft band.

## Ask

A yes from Santhosh before this page is sent, and a named profile from ACME before week 1 starts.

DRAFT — do not send without Santhosh's yes.
