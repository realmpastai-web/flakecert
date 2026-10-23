"""Log line format shared by baseline, flakecert, results.csv, and verify."""

import csv
import re
from pathlib import Path

from flakecert.paths import BASELINE_LOGS, FLAKECERT_LOGS, RESULTS

LOG_VERSION = "1"
RUN_RE = re.compile(
    r"^RUN method=(?P<method>\S+) run=(?P<run>\d+) outcome=(?P<outcome>\S+) "
    r"exc=(?P<exc>\S+) sig=(?P<sig>\S+) duration_s=(?P<duration>\S+) node=(?P<node>.*)$"
)
FAILURE_OUTCOMES = {"failed", "error"}


def run_line(method: str, run: int, outcome: str, exc: str, sig: str, duration: float, node: str) -> str:
    exc = exc or "-"
    sig = sig or "-"
    if " " in exc:
        exc = exc.split()[0]
    return (
        f"RUN method={method} run={run} outcome={outcome} exc={exc} sig={sig} "
        f"duration_s={duration:.3f} node={node}"
    )


def parse_runs(text: str) -> list[dict]:
    runs = []
    for line in text.splitlines():
        match = RUN_RE.match(line.strip())
        if not match:
            continue
        item = match.groupdict()
        item["run"] = int(item["run"])
        item["duration"] = float(item["duration"])
        runs.append(item)
    return runs


def count_outcomes(runs: list[dict]) -> dict[str, int]:
    counts = {
        "runs": len(runs),
        "passes": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "timeouts": 0,
        "missing": 0,
    }
    for run in runs:
        outcome = run["outcome"]
        if outcome == "passed":
            counts["passes"] += 1
        elif outcome == "failed":
            counts["failures"] += 1
        elif outcome == "error":
            counts["errors"] += 1
        elif outcome == "skipped":
            counts["skipped"] += 1
        elif outcome == "timeout":
            counts["timeouts"] += 1
        else:
            counts["missing"] += 1
    return counts


def method_runs(runs: list[dict], method: str) -> list[dict]:
    return [run for run in runs if run["method"] == method]


def header_lines(meta: dict, method: str) -> list[str]:
    return [
        f"# flakecert-log-version: {LOG_VERSION}",
        f"# id: {meta['id']}",
        f"# method: {method}",
        f"# category: {meta.get('category', '')}",
        f"# project: {meta.get('project_url', '')}",
        f"# sha: {meta.get('sha', '')}",
        f"# python: {meta.get('python', '')}",
        f"# image: {meta.get('image_digest', '')}",
        f"# image_tag: {meta.get('image_tag', '')}",
        "# network: none",
        "# netns_cmd: ip link set lo up",
        f"# pytest_id: {meta.get('pytest_id', '')}",
        f"# node_id: {meta.get('node_id', '')}",
        f"# test_file: {meta.get('test_file', '')}",
        f"# order_scope: {meta.get('order_scope', '')}",
    ]


def rebuild_results_csv() -> int:
    from flakecert.paths import ROOT

    rows = []
    logs = []
    if BASELINE_LOGS.exists():
        logs.extend(sorted(BASELINE_LOGS.glob("*.log")))
    if FLAKECERT_LOGS.exists():
        logs.extend(sorted(FLAKECERT_LOGS.glob("*.log")))
    for path in logs:
        rel = str(path.resolve().relative_to(ROOT))
        text = path.read_text(encoding="utf-8", errors="replace")
        ident = path.stem
        for run in parse_runs(text):
            rows.append(
                {
                    "id": ident,
                    "method": run["method"],
                    "run": str(run["run"]),
                    "outcome": run["outcome"],
                    "exc": run["exc"],
                    "sig": run["sig"],
                    "log": rel,
                }
            )
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "method", "run", "outcome", "exc", "sig", "log"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
