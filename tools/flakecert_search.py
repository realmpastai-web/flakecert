#!/usr/bin/env python3.11
"""make flakecert: controlled search, budget 500, certificates where isolated."""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakecert.effective import derive, load_frozen, load_swaps
from flakecert.logs import method_runs, parse_runs, rebuild_results_csv
from flakecert.paths import BASELINE_LOGS, BUDGET, CACHE, FLAKECERT_LOGS
from flakecert.runner import cleanup_our_containers
from flakecert.search import search_test
from flakecert.util import log


def _timeout_from_baseline(test_id: str) -> int:
    path = BASELINE_LOGS / f"{test_id}.log"
    if not path.exists():
        return 180
    runs = method_runs(parse_runs(path.read_text(encoding="utf-8", errors="replace")), "baseline")
    durations = sorted(run["duration"] for run in runs if run["duration"] > 0)
    if not durations:
        return 180
    median = durations[len(durations) // 2]
    return int(min(600, max(180, median * 4 + 30)))


def _search_done(test_id: str) -> bool:
    path = FLAKECERT_LOGS / f"{test_id}.log"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    # Written once, after the session closes. A killed search does not have it.
    return "FLAKECERT_SUMMARY" in text


def _one(meta: dict) -> None:
    if _search_done(meta["id"]):
        log(f"{meta['id']} flakecert already logged")
        return
    meta = dict(meta)
    meta["timeout_s"] = _timeout_from_baseline(meta["id"])
    meta["wall_s"] = int(os.environ.get("FLAKECERT_WALL_S", "2400"))
    cap = int(os.environ.get("FLAKECERT_NO_FAILURE_CAP", "500"))
    budget = int(os.environ.get("FLAKECERT_BUDGET", str(BUDGET)))
    if os.environ.get("FLAKECERT_FULL_BUDGET") == "1":
        cap = budget
    search_test(meta, budget=budget, no_failure_cap=cap)


def main() -> int:
    cleanup_our_containers()
    rows = load_frozen()
    swaps = load_swaps()
    mains, _reserves = derive(rows, swaps)
    jobs = int(os.environ.get("FLAKECERT_JOBS", "4"))
    metas = []
    for test_id in mains:
        path = CACHE / "meta" / f"{test_id}.json"
        if not path.exists():
            log(f"{test_id} no image meta; skipping flakecert")
            continue
        metas.append(json.loads(path.read_text(encoding="utf-8")))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(_one, meta): meta["id"] for meta in metas}
        for future in as_completed(futures):
            test_id = futures[future]
            try:
                future.result()
                log(f"{test_id} flakecert done")
            except Exception as exc:
                log(f"{test_id} flakecert error {exc}")
    count = rebuild_results_csv()
    log(f"results.csv rows {count}")
    cleanup_our_containers()
    return 0


if __name__ == "__main__":
    sys.exit(main())
