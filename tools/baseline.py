#!/usr/bin/env python3.11
"""make baseline: 100 plain reruns of each main test file."""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakecert.effective import derive, load_frozen, load_swaps
from flakecert.logs import count_outcomes, header_lines, method_runs, parse_runs, rebuild_results_csv, run_line
from flakecert.paths import BASELINE_LOGS, BASELINE_RUNS, CACHE
from flakecert.runner import Session, cleanup_our_containers, run_schedule
from flakecert.sources import default_schedule
from flakecert.util import log


def _append(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")
        handle.flush()


def _load_meta(test_id: str) -> dict | None:
    path = CACHE / "meta" / f"{test_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def run_one(meta: dict) -> None:
    test_id = meta["id"]
    BASELINE_LOGS.mkdir(parents=True, exist_ok=True)
    path = BASELINE_LOGS / f"{test_id}.log"
    existing = method_runs(parse_runs(path.read_text(encoding="utf-8", errors="replace")), "baseline") if path.exists() else []
    if len(existing) >= BASELINE_RUNS and "OFFLINE_RUN" in path.read_text(encoding="utf-8", errors="replace"):
        log(f"{test_id} baseline already logged")
        return
    if len(existing) == 0 or "flakecert-log-version: 1" not in path.read_text(encoding="utf-8", errors="replace")[:200]:
        lines = header_lines(meta, "baseline")
        lines.append("# cmd: docker run --network none --cap-add NET_ADMIN")
        lines.append("# netns_cmd: ip link set lo up")
        if meta.get("category") == "OD-Vic":
            lines.append(
                "# OD-Vic: a victim run alone is expected to be stable. "
                "Baseline reruns execute pytest on the target file in default order."
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        existing = []
    sources = meta["sources"]
    timeout_s = int(meta.get("timeout_s") or 180)
    # A later test in the same file can catch SIGTERM and sit until kill-after.
    # FLAKECERT_TIMEOUT_<id> shortens that wait once the target outcome is known
    # to appear earlier. The command is still pytest on the target file.
    override = os.environ.get(f"FLAKECERT_TIMEOUT_{test_id}", "")
    if override:
        timeout_s = int(override)
        marker = f"# timeout_s: {timeout_s} source=FLAKECERT_TIMEOUT_{test_id}"
        if marker not in path.read_text(encoding="utf-8", errors="replace"):
            _append(path, marker)
    base_args = list(meta.get("pytest_args") or ["-v", "--tb=short", "-p", "no:cacheprovider"])
    file_schedule = default_schedule([meta["test_file"]], sources)
    alone = default_schedule([meta["node_id"]], sources)
    lo_ok = False
    saw_real = False
    with Session(test_id, meta["image_tag"]) as session:
        if meta.get("category") == "OD-Vic" and not any(
            run["method"] == "victim_alone" for run in parse_runs(path.read_text(encoding="utf-8", errors="replace"))
        ):
            for index in range(1, 6):
                result = run_schedule(session, meta["node_id"], alone, base_args, timeout_s)
                _append(
                    path,
                    run_line("victim_alone", index, result.outcome, result.exc, result.sig, result.duration_s, result.node_id),
                )
                log(f"{test_id} victim_alone {index} {result.outcome}")
        start = len(method_runs(parse_runs(path.read_text(encoding="utf-8", errors="replace")), "baseline"))
        for index in range(start + 1, BASELINE_RUNS + 1):
            result = run_schedule(session, meta["node_id"], file_schedule, base_args, timeout_s)
            if result.lo_ok:
                lo_ok = True
            if result.outcome in {"passed", "failed", "error", "skipped"}:
                saw_real = True
            if index == start + 1 and "FLAKECERT_NETNS_BEGIN" in result.stdout:
                preamble = result.stdout.split("FLAKECERT_NETNS_BEGIN", 1)[1].split("FLAKECERT_NETNS_END", 1)[0]
                _append(path, "NETNS\n" + preamble.rstrip() + "\nENDNETNS")
            _append(
                path,
                run_line("baseline", index, result.outcome, result.exc, result.sig, result.duration_s, result.node_id),
            )
            if index == start + 1 or index % 10 == 0 or index == BASELINE_RUNS:
                log(f"{test_id} baseline {index}/{BASELINE_RUNS} {result.outcome}")
    runs = method_runs(parse_runs(path.read_text(encoding="utf-8", errors="replace")), "baseline")
    counts = count_outcomes(runs)
    fail = counts["failures"] + counts["errors"]
    _append(
        path,
        "BASELINE_SUMMARY id=%s runs=%d failures=%d passes=%d errors=%d skipped=%d timeouts=%d rate=%d/%d"
        % (
            test_id,
            counts["runs"],
            fail,
            counts["passes"],
            counts["errors"],
            counts["skipped"],
            counts["timeouts"],
            fail,
            counts["runs"] if counts["runs"] else 0,
        ),
    )
    offline = lo_ok and saw_real and counts["runs"] >= 1
    _append(
        path,
        "OFFLINE_RUN id=%s install=true run=%s" % (test_id, "true" if offline else "false"),
    )


def main() -> int:
    cleanup_our_containers()
    rows = load_frozen()
    swaps = load_swaps()
    mains, _reserves = derive(rows, swaps)
    jobs = int(os.environ.get("FLAKECERT_JOBS", "4"))
    metas = []
    for test_id in mains:
        meta = _load_meta(test_id)
        if meta is None:
            log(f"{test_id} no image meta; skipping baseline")
            continue
        metas.append(meta)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(run_one, meta): meta["id"] for meta in metas}
        for future in as_completed(futures):
            test_id = futures[future]
            try:
                future.result()
            except Exception as exc:
                log(f"{test_id} baseline error {exc}")
    count = rebuild_results_csv()
    log(f"results.csv rows {count}")
    cleanup_our_containers()
    return 0


if __name__ == "__main__":
    sys.exit(main())
