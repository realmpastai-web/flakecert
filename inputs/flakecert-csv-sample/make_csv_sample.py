#!/usr/bin/env python3
"""Build the CSV-sample inputs from the frozen verdict-audit sample (Hark, 2026-10-18).

dd-test-run.json (flakecert inputs/flakecert-verdict-audit @1371e26, 92 dd-trace test events, file order = run order)
  -> sample/search-response.json: the same events in the Datadog API v2 CI test-events search response shape
     (datadog-api-client-rust CIAppTestEvent: id, type "citest", attributes{attributes{nested}, tags[], test_level}),
     with attributes.attributes.start = increasing nanoseconds in run order, and rows sorted newest first,
     as pup v2.0.0 `cicd tests search` requests (CIAppSort::TIMESTAMP_DESCENDING, src/commands/cicd.rs:201).
  -> sample/pup-export.csv: pup_csv_port.render() of that response.

  python3 make_csv_sample.py <dd-test-run.json> <outdir>
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pup_csv_port  # noqa: E402

T0 = 1760000000000000000  # 2025-10-09T08:53:20Z in ns; fixed, synthetic
STEP = 1_000_000_000


def nest(meta: dict) -> dict:
    out: dict = {}
    for key, value in meta.items():
        parts = key.split(".")
        cur = out
        for p in parts[:-1]:
            nxt = cur.setdefault(p, {})
            if not isinstance(nxt, dict):
                raise SystemExit(f"nesting conflict at {key}")
            cur = nxt
        if parts[-1] in cur:
            raise SystemExit(f"duplicate key {key}")
        cur[parts[-1]] = value
    return out


def build(doc: dict) -> dict:
    lang = doc["metadata"]["*"]
    rows = []
    for i, ev in enumerate(doc["events"]):
        c = ev["content"]
        attrs = nest(c["meta"])
        attrs.update({"service": c["service"], "language": lang["language"],
                      "library_version": lang["library_version"], "start": T0 + i * STEP})
        rows.append({"id": f"hark-sample-{i:03d}", "type": "citest",
                     "attributes": {"attributes": attrs, "tags": [f"service:{c['service']}", "env:ci"], "test_level": "test"}})
    rows.sort(key=lambda r: -r["attributes"]["attributes"]["start"])
    return {"data": rows}


if __name__ == "__main__":
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    resp = build(json.loads(src.read_text()))
    (out / "search-response.json").write_text(json.dumps(resp, indent=1) + "\n")
    (out / "pup-export.csv").write_text(pup_csv_port.render(resp))
