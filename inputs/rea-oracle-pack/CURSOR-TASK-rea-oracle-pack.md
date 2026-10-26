# CURSOR TASK — Cross-Protocol Desync Oracle Pack (Week-1 build, static)

> REA clean-room, STATIC ONLY. Legal/public shipped artifacts (C5/C6/C7 committed evidence).
> No target execution, no byte on a wire, no network test. Selling and ANY buyer outreach are
> HARD-GATED on Santhosh's explicit "yes" (spending + outreach-under-name approval rules).
> Evidence rule: no result counts without the committed file/log/command output behind it.

## 0. Starting point (already built in Hark sandbox, /workspace/work/rea-oracle-pack)
Copy these in verbatim; sha256 in SHA256SUMS:
- SPEC.md (method + BUYER/EARN section, publicly cited), recon.log
- oracle/kestrel-acceptance.jsonl (3 seed rows, status PENDING-EVIDENCE-SYNC)
- gen/desync_gen.py (differential generator; demo already emits OR-001, OR-002)
- holdout/holdout.jsonl + out/holdout_score_once.json (sealed holdout, scored once)
- SKEPTIC.md (payable-vs-not analysis from the verbatim holdout)

## 1. Goal (Week 1)
Turn the seed oracle into a CONFIRMED, evidence-cited acceptance oracle for the .NET edge and
prove the generator emits payable cross-protocol divergences — all static.

## 2. Steps (REA_CLEANROOM order)
A. **Sync committed evidence** onto this box and freeze by sha256:
   - C5 Kestrel HTTP/1 (inputs/rea-c5-*), C7 Kestrel HTTP/3 (branch rea-c7-kestrel-h3 @ 434e35b,
     SHA256SUMS verified), C6 YARP FINDINGS. Record each sha in SHA256SUMS.
B. **Fill evidence pointers**: for every verdict in oracle/kestrel-acceptance.jsonl, replace the
   `evidence` placeholder with the exact committed decomp file+line; flip verified rows to
   `status: CONFIRMED`. A verdict with no committed snippet stays PENDING or UNKNOWN — never invent.
C. **Extend rows ONLY from the committed SPECs** (not memory/CVEs): QPACK header-value CTL
   handling (OR-003), pseudo-header duplication/ordering, trailers, CL/DATA reconciliation.
D. **Generator**: add the `payable_at_boundary` default gate (SKEPTIC.md action) so default
   output = payable CONFIRMED divergences; `--confirmed-only` already fails closed.
E. **Score the sealed holdout once** with the final oracle; append verbatim, do not re-tune.
F. **Skeptic pass** on every payable survivor: reachable on Kestrel defaults? already a public
   CVE? would a real downstream actually disagree? Kill the rest.

## 3. Deliverables (branch rea-oracle-pack, PR under realmpastai-web)
Under inputs/rea-oracle-pack/: everything from §0 with CONFIRMED rows, filled SHA256SUMS,
plus VERDICT.md (payable divergence count + the Week-2 payer-proof plan from SPEC §4).
Open PR to main; do not merge without Santhosh.

## 4. Acceptance tests (replay on same sha256s)
1. All synced C5/C7/C6 artifacts + pack files match SHA256SUMS.
2. Every CONFIRMED verdict resolves to a committed decomp file+line.
3. `python3 gen/desync_gen.py oracle/kestrel-acceptance.jsonl --front h3 --back h1 --confirmed-only`
   emits >=1 payable divergence, and emits 0 when no row is CONFIRMED.
4. Holdout hash matches; holdout scored once, recorded verbatim; no re-tune.
5. SKEPTIC.md labels each survivor payable/non-payable with reasoning.

## 5. Gate (fail-closed)
- Static only; no live run, no buyer contact. A sold pack = CONFIRMED + payable rows only.
- Selling / outreach parked behind Santhosh's explicit yes.
