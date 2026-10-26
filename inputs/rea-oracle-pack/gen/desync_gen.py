#!/usr/bin/env python3
"""
REA Oracle Pack — Cross-Protocol Desync Generator (static slice).

Input : an acceptance-oracle (JSONL). Each row is one request field-set and a
        per-implementation verdict taken from committed decomp, not from a live hop.
Action: given two hops (front, back), emit rows whose verdict classes differ.

Default gate (SKEPTIC.md): `cases` contains only divergences that are both
payable_at_boundary and status CONFIRMED. Divergences that are not payable go
in `conformance_only`. A payable row that is not CONFIRMED is omitted.

`--confirmed-only` still fails closed: a row whose status is not CONFIRMED is
skipped before any divergence is asserted, so an all-PENDING oracle emits
nothing in either section.

UNKNOWN legs still fail closed inside diverges(): if either verdict class is
unknown, no divergence is asserted.
This program does not open a socket and does not run a target.
"""
import json, sys, argparse

def load(path):
    rows=[]
    for ln in open(path):
        ln=ln.strip()
        if ln: rows.append(json.loads(ln))
    return rows

def kind(v):
    # collapse a verdict string to a boundary-behavior class
    if v.startswith("accept"): return ("accept", v)
    if v.startswith("reject"): return ("reject", v)
    if v.startswith("normalize"): return ("normalize", v)
    if v.startswith("framing-source"): return ("framing-source", v)
    if v.startswith("n/a"): return ("absent", v)
    return ("unknown", v)

def diverges(a, b):
    ka,_=kind(a); kb,_=kind(b)
    if "unknown" in (ka,kb): return None            # cannot assert a divergence
    if ka==kb:
        # same class, but different normalize/framing target still desyncs
        if ka in ("normalize","framing-source") and a!=b: return "same-class-diff-target"
        return None
    # accept-vs-reject and framing-source-vs-absent are the payable splits
    if {ka,kb} <= {"accept","reject","normalize","framing-source","absent"}:
        return f"{ka}-vs-{kb}"
    return None

def entry(r, front, back, why):
    v=r["verdicts"]
    return {"id":r["id"],"axis":r["axis"],"front":front,"front_verdict":v[front],
            "back":back,"back_verdict":v[back],"divergence_class":why,
            "payable_at_boundary":bool(r.get("payable_at_boundary", False)),
            "status":r.get("status"),"evidence":r.get("evidence"),
            "field_set":r["input"],"narrative":r.get("divergence","")}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("oracle"); ap.add_argument("--front",required=True)
    ap.add_argument("--back",required=True); ap.add_argument("--confirmed-only",action="store_true")
    a=ap.parse_args()
    rows=load(a.oracle); cases=[]; conformance_only=[]
    for r in rows:
        v=r["verdicts"]
        if a.front not in v or a.back not in v: continue
        if a.confirmed_only and r.get("status")!="CONFIRMED": continue
        why=diverges(v[a.front], v[a.back])
        if not why: continue
        item=entry(r, a.front, a.back, why)
        payable=bool(r.get("payable_at_boundary", False))
        confirmed=r.get("status")=="CONFIRMED"
        # Sold list: payable AND confirmed. Unconfirmed payable stays out.
        if payable and confirmed:
            cases.append(item)
        elif not payable:
            conformance_only.append(item)
    print(json.dumps({"front":a.front,"back":a.back,"confirmed_only":a.confirmed_only,
                      "oracle_rows":len(rows),"divergences":len(cases),"cases":cases,
                      "conformance_only_count":len(conformance_only),
                      "conformance_only":conformance_only},indent=2))

if __name__=="__main__": main()
