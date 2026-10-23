#!/usr/bin/env python3
"""Print a single-process Minitest replay command for one QueueTrail-Rails worker.

Behaviour is specified in docs/QUEUETRAIL-RAILS-SPEC.md. This file does not
load or execute Rails, activesupport, railties, or minitest.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import sys
from pathlib import Path

REASON = (
    "UNPROVEN. certify_rspec is RSpec-only: tools/certify_rspec/ordering.rb "
    "registers an RSpec global ordering and QueueTrail replay invokes rspec. "
    "A minitest certify path would need its own runner that reads this ids file "
    "of Class#method lines and executes that ordered prefix plus the victim in "
    "one process with PARALLEL_WORKERS=1. That runner is not built here."
)


def load_cli():
    path = Path(__file__).resolve().parent / "cli.py"
    spec = importlib.util.spec_from_file_location("queuetrail_cli_unmodified", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLI = load_cli()
SHIM = Path(__file__).resolve().parent / "rails_order_shim.rb"


def ordered_suites(manifest_path: Path, worker: int) -> tuple[dict, list[dict]]:
    header, suites = CLI.load_checked_trail(manifest_path, worker)
    suites = sorted(suites, key=lambda row: int(row["index"]))
    return header, suites


def recorded_names(suites: list[dict]) -> list[str]:
    names = []
    for row in suites:
        name = row.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def replay_line(manifest_path: Path, worker: int) -> str:
    header, suites = ordered_suites(manifest_path, worker)
    ids_text = " ".join(recorded_names(suites))
    seed = str(header["srand_seed"])
    return (
        f"QUEUETRAIL_SRAND={seed} PARALLEL_WORKERS=1 "
        f"ids={shlex.quote(ids_text)} ruby -r {shlex.quote(str(SHIM))}"
    )


def handoff_document(manifest_path: Path, worker: int, victim: str) -> dict:
    _header, suites = ordered_suites(manifest_path, worker)
    victim_row = next((row for row in suites if row.get("name") == victim), None)
    if victim_row is None:
        raise SystemExit(f"victim not in worker trail: {victim}")
    prefix = [row for row in suites if int(row["index"]) < int(victim_row["index"])]
    names = [str(row.get("name")) for row in prefix]
    return {
        "kind": "queuetrail-rails-candidate",
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
    parser = argparse.ArgumentParser(prog="rails_replay")
    sub = parser.add_subparsers(dest="command", required=True)

    replay = sub.add_parser("replay")
    replay.add_argument("--manifest", required=True, type=Path)
    replay.add_argument("--worker", required=True, type=int)

    hand = sub.add_parser("handoff")
    hand.add_argument("--manifest", required=True, type=Path)
    hand.add_argument("--worker", required=True, type=int)
    hand.add_argument("--victim", required=True)
    hand.add_argument("--out", type=Path)

    args = parser.parse_args(argv)
    if args.command == "replay":
        print(replay_line(args.manifest, args.worker))
        return 0
    emit_json(handoff_document(args.manifest, args.worker, args.victim), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
