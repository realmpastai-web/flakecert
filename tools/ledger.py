#!/usr/bin/env python3.11
"""make ledger: SUMMARY.md and README numbers, both derived from logs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakecert.logs import rebuild_results_csv
from flakecert.paths import README, SUMMARY, SUMMARY_BUILD
from flakecert.summary import build_summary, preserve_ingest_section, readme_text
from flakecert.util import log


def main() -> int:
    count = rebuild_results_csv()
    summary, build_log = build_summary()
    SUMMARY.write_text(summary, encoding="utf-8")
    SUMMARY_BUILD.write_text(build_log, encoding="utf-8")
    previous = README.read_text(encoding="utf-8") if README.exists() else ""
    README.write_text(preserve_ingest_section(readme_text(summary), previous), encoding="utf-8")
    log(f"results.csv rows {count}")
    log(f"wrote {SUMMARY}")
    log(f"wrote {README}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
