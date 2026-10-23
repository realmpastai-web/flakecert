#!/usr/bin/env python3
"""Check observations.json against gem bytes. Does not install or execute them."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
from pathlib import Path

OBSERVATION_IDS = ("Q1", "Q2", "Q3", "Q4", "Q5", "C1", "O6", "O7")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gem_members(path: Path) -> dict[str, bytes]:
    """Read data.tar.gz out of a .gem tar. No install, no Ruby."""
    with tarfile.open(path, "r") as gem:
        extracted = gem.extractfile("data.tar.gz")
        if extracted is None:
            raise SystemExit(f"{path} has no data.tar.gz")
        raw = extracted.read()
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as data:
        for member in data.getmembers():
            if not member.isfile():
                continue
            handle = data.extractfile(member)
            if handle is None:
                continue
            files[member.name] = handle.read()
    return files


def line_text(files: dict[str, bytes], name: str, number: int) -> str | None:
    blob = files.get(name)
    if blob is None:
        return None
    lines = blob.decode("utf-8").splitlines()
    if number < 1 or number > len(lines):
        return None
    return lines[number - 1]


def check(gem: Path, control: Path, expect_path: Path) -> int:
    expect = json.loads(expect_path.read_text(encoding="utf-8"))
    target_sha = sha256_file(gem)
    control_sha = sha256_file(control)
    sha_ok = True
    if target_sha != expect["target_sha256"]:
        print("SHA FAIL target")
        sha_ok = False
    if control_sha != expect["control_sha256"]:
        print("SHA FAIL control")
        sha_ok = False
    if not sha_ok:
        return 1

    archives = {"target": gem_members(gem), "control": gem_members(control)}
    failed = False
    for obs_id in OBSERVATION_IDS:
        obs = expect["observations"][obs_id]
        files = archives[obs["gem"]]
        ok = True
        for cite in obs["lines"]:
            actual = line_text(files, cite["file"], int(cite["line"]))
            if actual != cite["text"]:
                ok = False
                print(f"{obs_id} FAIL {cite['file']}:{cite['line']}")
                print(f"  expected: {cite['text']!r}")
                print(f"  actual:   {actual!r}")
        absent = obs.get("absent")
        if absent:
            pattern = re.compile(rf"\b{re.escape(str(absent))}\b")
            for name, blob in files.items():
                if not name.endswith(".rb"):
                    continue
                if pattern.search(blob.decode("utf-8", "replace")):
                    ok = False
                    print(f"{obs_id} FAIL found {absent} in {name}")
        if ok:
            print(f"{obs_id} PASS")
        else:
            failed = True
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reverse_check")
    parser.add_argument("--gem", required=True, type=Path)
    parser.add_argument("--control", required=True, type=Path)
    parser.add_argument("--expect", required=True, type=Path)
    args = parser.parse_args(argv)
    return check(args.gem, args.control, args.expect)


if __name__ == "__main__":
    raise SystemExit(main())
