#!/usr/bin/env python3
"""Static Python port of pup v2.0.0 CSV rendering for a CI test-events search response (Hark, 2026-10-18).

Port of DataDog/pup @ v2.0.0 (5c4d2453, Apache-2.0) src/output.rs: unwrap_data (L1663), flatten_deep (L1485),
format_delimited with no column hints (L1574-1640: union of flattened keys, then bytewise sort), csv_cell (L1518),
csv_escape (L1509), and print_csv (L1647: lines joined by "\\n", println adds one "\\n").

  python3 pup_csv_port.py <response.json> > out.csv
"""
import json, sys


def unwrap_data(v):
    while isinstance(v, dict) and "data" in v:
        v = v["data"]
    return v


def flatten_deep(v, prefix, out):
    if isinstance(v, dict):
        for k, x in v.items():
            flatten_deep(x, k if not prefix else f"{prefix}.{k}", out)
    else:
        out[prefix] = v


def cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        return json.dumps(v)
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


def esc(s):
    if any(c in s for c in ',"\n\r'):
        return '"' + s.replace('"', '""') + '"'
    return s


def render(doc) -> str:
    rows = unwrap_data(doc)
    rows = rows if isinstance(rows, list) else ([rows] if isinstance(rows, dict) else [])
    if not rows:
        return ""
    flat = []
    for r in rows:
        o = {}
        flatten_deep(r, "", o)
        flat.append(o)
    headers = []
    seen = set()
    for o in flat:
        for k in o:
            if k not in seen:
                seen.add(k)
                headers.append(k)
    headers.sort(key=lambda h: h.encode())
    lines = [",".join(esc(h) for h in headers)]
    lines += [",".join(esc(cell(o.get(h))) for h in headers) for o in flat]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render(json.loads(open(sys.argv[1], encoding="utf-8").read())))
