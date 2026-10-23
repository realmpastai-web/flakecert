#!/usr/bin/env python3
"""FlakeCert PR #1 heavy run 39104961633, job 117608702015, HEAD 429d5a3. Offline analysis of the frozen job log against the frozen certs.
The log arrived as one blob from the API, so this script splits records on the timestamp prefix."""
import json, re, sys
from pathlib import Path
H = Path(__file__).resolve().parent
log = (H / "heavy-job-117608702015.log").read_text(encoding="utf-8", errors="replace")
ci = {m[0]: (m[1], m[2]) for m in re.findall(r"image (F\d+) tag=\S+ python=\S+ digest=(sha256:\w+) pip_freeze_sha256=(\w+)", log)}
CERTS = ["F01","F03","F04","F06","F08","F10","F12","F14","F15","F16"]
for f in CERTS:
    c = json.loads((H / "certs-429d5a3" / f"{f}.json").read_text())
    print(f"{f}\tdocker_image_id={'SAME' if ci[f][0]==c['image_digest'] else 'DIFF'}\tpip_freeze={'SAME' if ci[f][1]==c['pip_freeze_sha'] else 'DIFF'}\treplay={'NOT_RUN digest_mismatch' if f'replay {f} NOT_RUN digest_mismatch' in log else '?'}")
g = re.search(r'GATES (\{[^}]*\})', log); print("GATES", g.group(1))
print("make_verify_error1", "make: *** [Makefile:32: verify] Error 1" in log)
print("comparator_fail_lines", log.count("comparator fail"))
