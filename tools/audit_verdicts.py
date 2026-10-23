#!/usr/bin/env python3.11
"""make audit: write the exact one-sided verdict audit for a test-run file."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakecert.verdict_audit import DEFAULT_TARGETS, CsvVerdictError, audit, document_from_csv, dumps_audit


def _load_document(src: Path, fmt: str | None) -> dict:
    text = src.read_text(encoding="utf-8")
    use_csv = fmt == "csv" or (fmt is None and src.suffix == ".csv")
    if use_csv:
        return document_from_csv(text)
    return json.loads(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Audit attempt-to-fix verdicts in a test-run file.")
    parser.add_argument("--in", dest="src", required=True)
    parser.add_argument("--out", dest="dst", required=True)
    parser.add_argument("--format", choices=("json", "csv"), default=None)
    parser.add_argument("--target", action="append", dest="targets")
    args = parser.parse_args(argv)
    try:
        doc = _load_document(Path(args.src), args.format)
    except CsvVerdictError as exc:
        print(f"csv audit: {exc}", file=sys.stderr)
        return 2
    targets = tuple(args.targets) if args.targets else DEFAULT_TARGETS
    report = audit(doc, targets=targets)
    text = dumps_audit(report)
    dest = Path(args.dst)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
