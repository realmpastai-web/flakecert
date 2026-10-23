#!/usr/bin/env python3.11
"""make comparator: one blind subprocess per certificate."""

import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakecert.paths import CERTS, COMPARATOR_CSV, ROOT
from flakecert.runner import cleanup_our_containers
from flakecert.util import log, run_cmd


def _one(cert_path: Path) -> dict:
    proc = run_cmd([sys.executable, str(ROOT / "tools" / "blind_rerun.py"), str(cert_path)], timeout=420)
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    while len(lines) < 4:
        lines.append("-")
    verdict = "pass" if lines[0] == "PASS" and proc.returncode == 0 else "fail"
    return {
        "id": cert_path.stem,
        "result": verdict,
        "sig": lines[1],
        "outcome": lines[2],
        "exc": lines[3],
    }


def main() -> int:
    cleanup_our_containers()
    certs = sorted(CERTS.glob("*.json")) if CERTS.exists() else []
    if not certs:
        log("no certificates")
        COMPARATOR_CSV.parent.mkdir(parents=True, exist_ok=True)
        COMPARATOR_CSV.write_text("id,result,sig,outcome,exc\n", encoding="utf-8")
        return 0
    jobs = int(os.environ.get("FLAKECERT_JOBS", "4"))
    rows = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(_one, path): path for path in certs}
        for future in as_completed(futures):
            path = futures[future]
            try:
                row = future.result()
            except Exception as exc:
                row = {"id": path.stem, "result": "fail", "sig": "-", "outcome": "harness_error", "exc": type(exc).__name__}
            rows.append(row)
            log(f"{row['id']} comparator {row['result']}")
    rows.sort(key=lambda item: item["id"])
    COMPARATOR_CSV.parent.mkdir(parents=True, exist_ok=True)
    with COMPARATOR_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "result", "sig", "outcome", "exc"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    passed = sum(1 for row in rows if row["result"] == "pass")
    log(f"comparator {passed}/{len(rows)}")
    cleanup_our_containers()
    return 0


if __name__ == "__main__":
    sys.exit(main())
