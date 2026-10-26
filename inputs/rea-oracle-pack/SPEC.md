# SPEC — Cross-Protocol Desync Oracle Pack (REA clean-room, static)

## 0. What this is
A per-implementation **acceptance oracle** extracted statically from the shipped .NET edge
(Kestrel HTTP/1, HTTP/2, HTTP/3 + YARP forwarder) — a table of
`{request field-set} x {h1,h2,h3,yarp} -> {accept|reject|normalize:X|framing-source:Y|n/a}`,
every verdict cited to a committed C5/C7/C6 decompiled snippet — plus a **differential
generator** (`gen/desync_gen.py`) that emits the request-sets any two hops resolve
differently. Output of Step B is built ONLY from this SPEC, never from guesswork.

## 1. Method (REA_CLEANROOM, in order)
A. Evidence-cited oracle rows first: each verdict cites file+line of committed decomp.
B. Build the generator/divergence logic ONLY from the oracle verdicts.
C. Re-check each emitted divergence against the decompiled code; contradiction -> drop.
D. One sealed holdout (holdout/, hashed in SHA256SUMS), scored once, recorded verbatim.
E. Skeptic pass: reachable on defaults? already public? would a real downstream disagree?

## 2. Evidence rule + current evidence state
No row counts CONFIRMED without the committed decomp file behind its verdict. This sandbox
holds only the C5/C7 CURSOR-TASK files, not the snippets, so seed rows ship
`status: PENDING-EVIDENCE-SYNC`. The box run syncs C5 (inputs/rea-c5-*), C7
(branch rea-c7-kestrel-h3 @ 434e35b, SHA256SUMS verified) and C6 FINDINGS, fills file+line
into each verdict's `evidence`, flips verified rows to CONFIRMED, and re-runs the generator
with `--confirmed-only`. The in-sandbox demo already proves the generator emits non-trivial
divergence rows (OR-001 chunked-framing, OR-002 extended-CONNECT) and that `--confirmed-only`
fails closed to 0 until evidence lands.

## 3. BUYER + HOW WE EARN  (the thing Santhosh asked to put here first)

### The gap (public, cited — fetched 2026-10-26)
Every shipped desync tool is **dynamic**: it fires payloads at *running* servers and infers
parsing from responses. None ships a *static, per-implementation acceptance oracle* read from
the binary. Evidence:
- **Burp HTTP Request Smuggler** (PortSwigger, the canonical tool): detects via **timing**
  and **parser-discrepancy** probing against a live target; v3.0 (2025) added parser-
  discrepancy detection but still by sending probes. [portswigger.net/web-security/request-
  smuggling/finding ; github.com/PortSwigger/http-request-smuggler]
- **USENIX Security 2025, "The Silent Danger in HTTP"**: existing tools "send a series of
  predefined payloads to test exploitability ... this method lacks the capability to uncover
  new variants," and frames the open need for an **oracle** to decide desync.
  [usenix.org/system/files/usenixsecurity25-mu.pdf]
- **T-Reqs (CCS'21)** and **Gudifu (RAID'24)**: differential fuzzing that sends identical
  requests to **multiple running servers** and diffs the forwarded output — needs live echo
  servers, has no static per-implementation oracle. [swsprec.com/papers/treqs.pdf ;
  onarlioglu.com/publications/raid2024gudifu.pdf]
=> Our differentiator: the oracle is extracted from the shipped artifact, offline, and tells
   you *which exact requests* a Kestrel/YARP edge will disagree with a second hop on — before
   you send a single byte, and regenerable per .NET patch release.

### Buyer (ranked, with the earn model for each)
1. **API-gateway / edge-proxy vendors** (Kong, Traefik, Envoy/Tetrate, F5/NGINX, Cloudflare)
   — they ship the *second hop* and must prove conformance against a Kestrel origin.
   EARN: **sold conformance pack per release**, annual **license** to the regeneration
   pipeline. Highest willingness-to-pay; recurring because every .NET release re-opens it.
2. **Appsec scanner vendors** (Tenable, Rapid7, Detectify, Intruder) wanting a .NET-specific
   desync test pack their dynamic scanner can fire. EARN: **OEM license / per-seat** of the
   generated corpus.
3. **Large .NET enterprise red teams**, direct. EARN: **sold pack** + yearly refresh sub.
Not PortSwigger — they own Burp's smuggler and build their own.

### Pricing shape (to validate in Week 2, not committed)
- Sold pack (one .NET version): one-off per pack.
- Pipeline license (regenerate every release): annual subscription — the recurring core.
- Scanner OEM: per-seat or revenue-share.

## 4. Week-2 payer proof (what makes a real buyer, not a clean artifact)
Produce ONE sample conformance report against a public open-source proxy's **documented**
behavior (static, no execution): "here are the N requests where Kestrel-H3 and Kestrel-H1
resolve framing/acceptance differently — your edge must agree or it desyncs." Take it to buyer
#1's conformance/security contact. A signed intent-to-pay or a paid pilot = success.

## 5. Gate (fail-closed)
- Static only. No live run, no byte on a wire, no buyer contact until Santhosh's explicit yes.
- `--confirmed-only` is the ship gate: a pack may only contain CONFIRMED rows.
- Selling / outreach parked behind Santhosh per approval prefs (spending + outreach-under-name).
