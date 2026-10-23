#!/usr/bin/env python3
"""QueueTrail manifest, replay, and FlakeCert hand-off.

Behaviour is specified in docs/QUEUETRAIL-SPEC.md. This file does not load
test-queue or parallel_tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

WORKER_RE = re.compile(r"^worker-(\d+)\.jsonl$")
REASON = (
    "UNPROVEN. ordering.rb reads whitespace-separated ids from ENV ids or ids_file "
    "(tools/certify_rspec/ordering.rb:10-14). Suite names are RSpec ids (O6), so ids_file "
    "feeds ordering.rb directly. No certify_rspec CLI accepts an external candidate file."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def worker_files(directory: Path) -> list[Path]:
    found = []
    for path in directory.iterdir():
        if path.is_file() and WORKER_RE.match(path.name):
            found.append(path)
    return sorted(found, key=lambda item: int(WORKER_RE.match(item.name).group(1)))


def header_of(rows: list[dict]) -> dict:
    if not rows or rows[0].get("type") != "worker":
        raise SystemExit("worker file is missing a header")
    return rows[0]


def suites_of(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("type") == "suite"]


def flakecert_commit() -> str | None:
    forced = os.environ.get("QUEUETRAIL_FLAKECERT_COMMIT")
    if forced:
        return forced
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    text = completed.stdout.strip()
    return text or None


def lock_sha(path: Path | None) -> str | None:
    if path is None:
        path = Path("Gemfile.lock")
        if not path.is_file():
            return None
    elif not path.is_file():
        return None
    return sha256_file(path)


def agreed_string(headers: list[dict], key: str) -> str | None:
    values = {item.get(key) for item in headers}
    if len(values) != 1:
        return None
    value = next(iter(values))
    if not isinstance(value, str):
        return None
    return value


def build_manifest(directory: Path, lock: Path | None) -> dict:
    files = worker_files(directory)
    if not files:
        raise SystemExit(f"no worker trails in {directory}")
    headers = []
    trails: dict[str, str] = {}
    for path in files:
        headers.append(header_of(read_jsonl(path)))
        trails[path.name] = sha256_file(path)
    run_ids = {item.get("run_id") for item in headers}
    masters = {item.get("master_seed") for item in headers}
    if len(run_ids) != 1 or len(masters) != 1:
        raise SystemExit("worker headers disagree on run_id or master_seed")
    return {
        "run_id": next(iter(run_ids)),
        "flakecert_commit": flakecert_commit(),
        "ruby_version": agreed_string(headers, "ruby_version"),
        "gemfile_lock_sha256": lock_sha(lock),
        "test_queue_version": agreed_string(headers, "test_queue_version"),
        "worker_count": len(files),
        "master_seed": next(iter(masters)),
        "trails": trails,
    }


def write_manifest(directory: Path, out: Path | None, lock: Path | None) -> None:
    destination = out or (directory / "manifest.json")
    document = build_manifest(directory, lock)
    destination.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def load_checked_trail(manifest_path: Path, worker: int) -> tuple[dict, list[dict]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    path = manifest_path.parent / f"worker-{worker}.jsonl"
    if not path.is_file():
        raise SystemExit(f"missing {path}")
    expected = (manifest.get("trails") or {}).get(path.name)
    actual = sha256_file(path)
    if not isinstance(expected, str) or expected != actual:
        raise SystemExit(f"trail sha256 mismatch for {path.name}")
    rows = read_jsonl(path)
    return header_of(rows), suites_of(rows)


def recorded_id(row: dict) -> str:
    name = row.get("name")
    if isinstance(name, str) and name:
        return name
    return ""


def replay_argument(row: dict) -> str:
    """RSpec argument. A non-empty recorded id is never replaced by path."""
    ident = recorded_id(row)
    if ident:
        return ident
    path = row.get("path") or ""
    if isinstance(path, str) and path:
        return path
    return ""


def replay_line(manifest_path: Path, worker: int, upto: int | None) -> tuple[str, str, list[str], str]:
    if upto is not None and upto < 0:
        raise SystemExit("--upto must be a non-negative integer")
    header, suites = load_checked_trail(manifest_path, worker)
    if upto is not None:
        suites = [row for row in suites if int(row["index"]) <= upto]
    root = Path(__file__).resolve().parents[1]
    ordering = str(root / "certify_rspec" / "ordering.rb")
    shim = str(Path(__file__).resolve().parent / "spec_shim.rb")
    args = [item for item in (replay_argument(row) for row in suites) if item]
    ids = [item for item in (recorded_id(row) for row in suites) if item]
    argv = ["rspec", "--require", ordering, "--require", shim, *args]
    seed = str(header["srand_seed"])
    ids_text = " ".join(ids)
    line = f"QUEUETRAIL_SRAND={seed} ids={shlex.quote(ids_text)} {shlex.join(argv)}"
    return seed, ids_text, argv, line


def run_replay(seed: str, ids_text: str, argv: list[str]) -> int:
    env = os.environ.copy()
    env["QUEUETRAIL_SRAND"] = seed
    env["ids"] = ids_text
    completed = subprocess.run(argv, check=False, env=env)
    return completed.returncode


def handoff_document(manifest_path: Path, worker: int, victim: str) -> dict:
    _header, suites = load_checked_trail(manifest_path, worker)
    victim_row = next((row for row in suites if row.get("name") == victim), None)
    if victim_row is None:
        raise SystemExit(f"victim not in worker trail: {victim}")
    prefix = [row for row in suites if int(row["index"]) < int(victim_row["index"])]
    names = [str(row.get("name")) for row in prefix]
    return {
        "kind": "queuetrail-candidate-polluters",
        "adapter_gap": "UNPROVEN",
        "reason": REASON,
        "worker_num": worker,
        "victim": victim,
        "candidate_ids": names,
        "ids_file": "\n".join([*names, victim]) + "\n",
    }


def emit_json(document: dict, out: Path | None) -> None:
    text = json.dumps(document, indent=2) + "\n"
    if out is None:
        sys.stdout.write(text)
    else:
        out.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="queuetrail")
    sub = parser.add_subparsers(dest="command", required=True)

    manifest = sub.add_parser("manifest")
    manifest.add_argument("--dir", required=True, type=Path)
    manifest.add_argument("--out", type=Path)
    manifest.add_argument("--gemfile-lock", type=Path)

    replay = sub.add_parser("replay")
    replay.add_argument("--manifest", required=True, type=Path)
    replay.add_argument("--worker", required=True, type=int)
    replay.add_argument("--upto", type=int)
    replay.add_argument("--run", action="store_true")

    hand = sub.add_parser("to-flakecert")
    hand.add_argument("--manifest", required=True, type=Path)
    hand.add_argument("--worker", required=True, type=int)
    hand.add_argument("--victim", required=True)
    hand.add_argument("--out", type=Path)

    args = parser.parse_args(argv)
    if args.command == "manifest":
        write_manifest(args.dir, args.out, args.gemfile_lock)
        return 0
    if args.command == "replay":
        seed, ids_text, argv_cmd, line = replay_line(args.manifest, args.worker, args.upto)
        print(line)
        if args.run:
            return run_replay(seed, ids_text, argv_cmd)
        return 0
    document = handoff_document(args.manifest, args.worker, args.victim)
    emit_json(document, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
