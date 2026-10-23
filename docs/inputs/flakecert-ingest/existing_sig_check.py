#!/usr/bin/env python3
"""Checks that flakecert's own failure_signature (flakecert/cert.py at realmpastai-web/flakecert ef1f8aa) gives a stable sig on the frozen same-seed reruns.
Usage: PYTHONPATH=<flakecert checkout @ef1f8aa> python3 existing_sig_check.py"""
import subprocess, os
from pathlib import Path
from flakecert.cert import failure_signature
import flakecert, sys
H = Path(__file__).resolve().parent
ns = {"__file__": str(H / "gate_flakecert_ingest.py")}
exec((H / "gate_flakecert_ingest.py").read_text().split("for fmt, (ff")[0], ns)
print("flakecert_commit", subprocess.run(["git", "-C", str(Path(flakecert.__file__).parent.parent), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip())
ok = True
for fmt, (ff, rr, pp, flaky, det) in ns["F"].items():
    a = ns["load"](fmt, ff)[0]; b = ns["load"](fmt, rr)[0]
    eq = failure_signature(a[flaky]["text"]) == failure_signature(b[flaky]["text"]); ok &= eq
    print(f"{fmt}\tfailure_signature(flaky) stable across same-seed rerun: {eq}\tsig={failure_signature(a[flaky]['text'])[:16]}")
sys.exit(0 if ok else 1)
