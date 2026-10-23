#!/usr/bin/env python3
"""Check Rails parallel observations against gem and cited-file bytes.

Does not install or execute activesupport, railties, minitest, i18n, or Rails.
Does not open codeload tarballs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

OBSERVATION_IDS = ("R-Q1", "R-Q2", "R-Q3", "R-Q4", "R-Q5", "R-Q6", "R-Q7")


def load_reverse_check():
    path = Path(__file__).resolve().parent / "reverse_check.py"
    spec = importlib.util.spec_from_file_location("queuetrail_reverse_check_bytes", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RC = load_reverse_check()


def cited_sha_ok(name: str, record: dict, directory: Path) -> bool:
    for key, meta in record["files"].items():
        path = directory / meta["path"]
        if not path.is_file() or RC.sha256_file(path) != meta["sha256"]:
            print(f"SHA FAIL {name} {key}")
            return False
    return True


def load_cited(record: dict, directory: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for key, meta in record["files"].items():
        files[key] = (directory / meta["path"]).read_bytes()
    return files


def load_archive(record: dict, directory: Path, gem_override: Path | None) -> dict[str, bytes]:
    if record["kind"] == "cited":
        return load_cited(record, directory)
    if record["kind"] == "gem":
        path = gem_override if record.get("role") == "target" and gem_override is not None else directory / record["path"]
        return RC.gem_members(path)
    raise SystemExit(f"unknown archive kind {record['kind']}")


def archive_path(record: dict, directory: Path, gem_override: Path | None) -> Path:
    if record.get("role") == "target" and gem_override is not None:
        return gem_override
    return directory / record["path"]


def scan_hits(files: dict[str, bytes], pattern: str, names: list[str]) -> list[dict]:
    regex = re.compile(pattern)
    hits = []
    for name in names:
        blob = files.get(name)
        if blob is None:
            hits.append({"file": name, "line": 0, "text": None})
            continue
        for number, text in enumerate(blob.decode("utf-8").splitlines(), 1):
            if regex.search(text):
                hits.append({"file": name, "line": number, "text": text})
    return hits


def check(gem: Path, expect_path: Path) -> int:
    expect = json.loads(expect_path.read_text(encoding="utf-8"))
    directory = expect_path.parent
    target_record = None
    for record in expect["archives"].values():
        if record.get("role") == "target":
            target_record = record
            break
    if target_record is None:
        print("SHA FAIL target")
        return 1
    target_sha = RC.sha256_file(gem)
    if target_sha != expect["target_sha256"] or target_sha != target_record["sha256"]:
        print("SHA FAIL target")
        return 1
    for name, record in expect["archives"].items():
        if record["kind"] == "cited":
            if not cited_sha_ok(name, record, directory):
                return 1
            continue
        if record["kind"] != "gem":
            print(f"SHA FAIL {name}")
            return 1
        path = archive_path(record, directory, gem)
        actual = RC.sha256_file(path)
        if actual != record["sha256"]:
            print(f"SHA FAIL {name}")
            return 1

    loaded = {
        name: load_archive(record, directory, gem) for name, record in expect["archives"].items()
    }
    failed = False
    for obs_id in OBSERVATION_IDS:
        obs = expect["observations"][obs_id]
        ok = True
        for group in obs.get("groups", []):
            files = loaded[group["archive"]]
            for cite in group["lines"]:
                actual = RC.line_text(files, cite["file"], int(cite["line"]))
                if actual != cite["text"]:
                    ok = False
                    print(f"{obs_id} FAIL {cite['file']}:{cite['line']}")
                    print(f"  expected: {cite['text']!r}")
                    print(f"  actual:   {actual!r}")
        for scan in obs.get("scans", []):
            files = loaded[scan["archive"]]
            if "files" in scan:
                names = list(scan["files"])
            else:
                suffix = scan.get("suffix", "")
                names = sorted(name for name in files if name.endswith(suffix))
            actual_hits = scan_hits(files, scan["pattern"], names)
            if actual_hits != scan["hits"]:
                ok = False
                print(f"{obs_id} FAIL scan {scan['pattern']!r}")
                print(f"  expected hits: {len(scan['hits'])}")
                print(f"  actual hits:   {len(actual_hits)}")
        if ok:
            print(f"{obs_id} PASS")
        else:
            failed = True
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reverse_check_rails")
    parser.add_argument("--gem", required=True, type=Path)
    parser.add_argument("--expect", required=True, type=Path)
    args = parser.parse_args(argv)
    return check(args.gem, args.expect)


if __name__ == "__main__":
    raise SystemExit(main())
