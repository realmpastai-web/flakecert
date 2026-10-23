#!/usr/bin/env python3.11
"""make freeze: fetch IDoFT at the pinned commit and record hashes."""

import csv
import io
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakecert.effective import load_frozen
from flakecert.hashes import write_hashes
from flakecert.paths import CACHE, EVIDENCE_ROOT, FROZEN_CSV, FROZEN_SHA256, IDOFT_SHA256, IDOFT_URL
from flakecert.util import log, run_cmd, sha256_file

PYTEST_NAME = (
    "Pytest Test Name (PathToFile::TestClass::TestMethod or PathToFile::TestMethod)"
)


def fetch_idoft() -> str:
    dest = CACHE / "idoft" / "py-data.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(IDOFT_URL, headers={"User-Agent": "flakecert-poc"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    dest.write_bytes(data)
    return data.decode("utf-8")


def match_rows(frozen: list[dict], text: str) -> list[str]:
    buckets: dict[tuple, list[dict]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        key = (row["Project URL"].rstrip("/"), row["SHA Detected"], row[PYTEST_NAME])
        buckets.setdefault(key, []).append(row)
    bad = []
    for row in frozen:
        key = (row["project_url"].rstrip("/"), row["sha"], row["pytest_id"])
        found = buckets.get(key) or []
        if not found:
            bad.append(f"{row['id']} missing from py-data")
            continue
        status = (row.get("idoft_status") or "").strip()
        exact = [
            item
            for item in found
            if item["Category"] == row["category"] and (item.get("Status") or "").strip() == status
        ]
        if not exact:
            seen = ", ".join(f"{item['Category']}/{(item.get('Status') or '').strip() or '-'}" for item in found)
            bad.append(f"{row['id']} category/status {row['category']}/{status or '-'} not in [{seen}]")
    return bad


def hark_curls() -> str:
    commands = [
        ["curl", "-fsSL", IDOFT_URL],
        [
            "curl",
            "-fsSL",
            "https://raw.githubusercontent.com/ljvmiranda921/pyswarms/08756526f39699eef28e515cac2ead17cef55710/requirements-dev.txt",
        ],
        ["curl", "-fsSL", "https://pypi.org/pypi/numpy/1.16.1/json"],
    ]
    chunks = []
    idoft = run_cmd(commands[0], timeout=120)
    digest = __import__("hashlib").sha256((idoft.stdout or "").encode()).hexdigest()
    chunks.append(f"idoft_curl_sha256 {digest}")
    dev = run_cmd(commands[1], timeout=120)
    pins = []
    for line in (dev.stdout or "").splitlines():
        if line.startswith(("numpy==", "scipy==", "pytest==")):
            pins.append(line.strip())
    chunks.append("pyswarms_pins " + " ".join(pins))
    numpy = run_cmd(commands[2], timeout=120)
    versions = ""
    if numpy.returncode == 0:
        proc = run_cmd(
            [
                sys.executable,
                "-c",
                "import json,sys; print(sorted({u['python_version'] for u in json.load(sys.stdin)['urls']}))",
            ],
            timeout=30,
            input_text=numpy.stdout,
        )
        versions = (proc.stdout or "").strip()
    chunks.append("numpy_1_16_1_python_versions " + versions)
    return "\n".join(chunks) + "\n"


def main() -> int:
    frozen_sha = sha256_file(FROZEN_CSV)
    log(f"frozen-set.csv sha256 {frozen_sha}")
    if frozen_sha != FROZEN_SHA256:
        log("FROZEN HASH MISMATCH")
        return 1
    text = fetch_idoft()
    digest = __import__("hashlib").sha256(text.encode("utf-8")).hexdigest()
    # Hash the file bytes we wrote, not a re-encode.
    file_digest = sha256_file(CACHE / "idoft" / "py-data.csv")
    log(f"idoft py-data.csv sha256 {file_digest}")
    if file_digest != IDOFT_SHA256:
        log("IDOFT HASH MISMATCH")
        return 1
    frozen = load_frozen()
    bad = match_rows(frozen, (CACHE / "idoft" / "py-data.csv").read_text(encoding="utf-8"))
    if bad:
        for item in bad:
            log("mismatch " + item)
        return 1
    log(f"idoft-rows-matched {len(frozen)}")
    write_hashes(len(frozen))
    os.chmod(FROZEN_CSV, 0o444)
    try:
        checks = hark_curls()
    except Exception as exc:
        checks = f"hark_curls_error {exc}\n"
    out = EVIDENCE_ROOT / "hark-checks.log"
    out.write_text(checks, encoding="utf-8")
    log(checks.rstrip())
    log(f"wrote {out.relative_to(out.parents[1])}")
    log("freeze ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
