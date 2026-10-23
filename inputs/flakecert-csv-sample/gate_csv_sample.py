#!/usr/bin/env python3
"""Gate for the FlakeCert CSV-sample task (frozen by Hark 2026-10-18; internal).

  python3 gate_csv_sample.py                         # self-check: inputs reproduce and the CSV carries the JSON sample exactly
  python3 gate_csv_sample.py --report R --kind pup   # judge `audit-verdicts` on sample/pup-export.csv
  python3 gate_csv_sample.py --report R --kind real  # judge `audit-verdicts` on sample/real-cassette-search.csv
"""
import argparse, csv, io, json, sys
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import make_csv_sample, pup_csv_port  # noqa: E402

P = "attributes.attributes."
fails = []


def chk(tag, ok, note=""):
    print(("PASS" if ok else "FAIL") + f"\t{tag}\t{note}")
    ok or fails.append(tag)


def rows_of(path: Path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"), newline="")))


def self_check():
    src = json.loads((H / "sample/dd-test-run.json").read_text())
    resp = make_csv_sample.build(src)
    chk("C1.response_reproduces", json.dumps(resp, indent=1) + "\n" == (H / "sample/search-response.json").read_text())
    chk("C2.csv_reproduces", pup_csv_port.render(resp) == (H / "sample/pup-export.csv").read_text())
    real = json.loads((H / "sample/real-cassette-search-response.json").read_text())
    chk("C3.real_csv_reproduces", pup_csv_port.render(real) == (H / "sample/real-cassette-search.csv").read_text())
    rows = rows_of(H / "sample/pup-export.csv")
    starts = [int(r[P + "start"]) for r in rows]
    chk("C4.rows_newest_first", starts == sorted(starts, reverse=True) and len(set(starts)) == len(starts), f"n={len(rows)}")
    rows.sort(key=lambda r: int(r[P + "start"]))
    rebuilt = []
    for r in rows:
        meta = {k[len(P):]: v for k, v in r.items() if k.startswith(P) and v != ""
                and k[len(P):] not in ("start", "service", "language", "library_version")}
        rebuilt.append(meta)
    want = [ev["content"]["meta"] for ev in src["events"]]
    chk("C5.csv_carries_json_sample_exactly", rebuilt == want, f"{len(rebuilt)} vs {len(want)} events")
    tags = {r["attributes.tags"] for r in rows}
    chk("C6.quoted_json_array_cell", tags == {'["service:sample","env:ci"]'}, f"{tags}")
    rr = rows_of(H / "sample/real-cassette-search.csv")
    chk("C7.real_rows_no_atf_column", len(rr) == 3 and not any("test_management" in k for k in rr[0]), f"rows={len(rr)}")


def judge(report: Path, kind: str):
    want = (H / ("expected-audit-pup.json" if kind == "pup" else "expected-audit-real.json")).read_text()
    got = report.read_text()
    chk(f"R1.{kind}.byte_identical", got == want)
    doc = json.loads(got)
    by = {t["test"]: t for t in doc.get("tests", [])}
    if kind == "pup":
        for name, n, u in (("cart.test.js::total rounds to cents", 20, "0.139109"), ("sync.test.js::drains queue", 50, "0.058156")):
            t = by.get(name, {})
            chk(f"R2.fixed {name}", t.get("verdict") == "fixed" and t.get("atf_runs") == n and t.get("upper_bound_95") == u
                and t.get("clean_seeded_runs_required") == {"0.01": 299, "0.001": 2995}, f"{t.get('verdict')} n={t.get('atf_runs')} u={t.get('upper_bound_95')}")
        t = by.get("auth.test.js::token refresh", {})
        chk("R3.not_fixed auth", t.get("verdict") == "not_fixed" and t.get("atf_failures") == 1)
    else:
        chk("R2.real.no_tests", doc.get("tests") == [])


ap = argparse.ArgumentParser()
ap.add_argument("--report")
ap.add_argument("--kind", choices=["pup", "real"], default="pup")
a = ap.parse_args()
judge(Path(a.report), a.kind) if a.report else self_check()
print("GATE " + ("PASS" if not fails else f"FAIL {fails}"))
sys.exit(1 if fails else 0)
