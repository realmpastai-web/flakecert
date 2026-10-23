#!/usr/bin/env python3.11
"""make ingest: nominate candidates from JUnit XML and Buildkite collector JSON."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakecert.ingest import ingest_paths, resolve_sha


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Nominate flaky-test candidates from JUnit XML and Buildkite "
            "collector JSON. Does not certify."
        )
    )
    parser.add_argument(
        "--sha",
        default=None,
        help=(
            "commit under test; otherwise BUILDKITE_COMMIT, CIRCLE_SHA1, "
            "CI_COMMIT_SHA, GITHUB_SHA, else git rev-parse HEAD"
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="absolute checkout prefix to strip before failure signatures",
    )
    parser.add_argument(
        "--out",
        default="ingest/candidates.json",
        help="candidates JSON path",
    )
    parser.add_argument("reports", nargs="+", help="JUnit XML or collector JSON files")
    args = parser.parse_args(argv)
    try:
        sha, source = resolve_sha(args.sha)
        candidates = ingest_paths(
            args.reports,
            sha=sha,
            sha_source=source,
            repo_root=args.repo_root,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ingest: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(candidates, indent=2) + "\n"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
