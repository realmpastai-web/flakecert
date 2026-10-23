"""Derive the effective set from the frozen set plus swaps.csv."""

import csv
from pathlib import Path

from flakecert.paths import EVIDENCE, FROZEN_CSV, FROZEN_SHA256, SWAPS

SWAP_FIELDS = [
    "swap_id",
    "ts_ist",
    "removed_id",
    "removed_role",
    "removed_category",
    "replacement_id",
    "replacement_role",
    "replacement_category",
    "rule",
    "reason",
    "evidence_file",
    "evidence_sha256",
]


def load_frozen(path: Path = FROZEN_CSV) -> list[dict]:
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_swaps(path: Path = SWAPS) -> list[dict]:
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def derive(rows: list[dict], swaps: list[dict]) -> tuple[list[str], list[str]]:
    mains = [row["id"] for row in rows if row["role"] == "main"]
    reserves = [row["id"] for row in rows if row["role"] == "reserve"]
    for swap in swaps:
        removed = (swap.get("removed_id") or "").strip()
        if removed in mains:
            mains.remove(removed)
        if removed in reserves:
            reserves.remove(removed)
        replacement = (swap.get("replacement_id") or "").strip()
        if not replacement:
            continue
        if replacement in reserves:
            reserves.remove(replacement)
        if replacement not in mains:
            mains.append(replacement)
    return mains, reserves


def format_effective(mains: list[str], reserves: list[str], swap_ids: list[str]) -> str:
    joined = ",".join(swap_ids)
    lines = [
        (
            f"# Derived view after swaps.csv {joined}. "
            f"frozen-set.csv UNCHANGED (sha256 {FROZEN_SHA256})"
        ),
        f"main({len(mains)}): {','.join(mains)}",
        f"reserves({len(reserves)}): {','.join(reserves)}",
    ]
    return "\n".join(lines) + "\n"


def effective_text(rows=None, swaps=None) -> str:
    rows = load_frozen() if rows is None else rows
    swaps = load_swaps() if swaps is None else swaps
    mains, reserves = derive(rows, swaps)
    swap_ids = [swap["swap_id"] for swap in swaps]
    return format_effective(mains, reserves, swap_ids)


def committed_effective_text() -> str:
    return (EVIDENCE / "effective-set.txt").read_text(encoding="utf-8")


def row_map(rows=None) -> dict[str, dict]:
    rows = load_frozen() if rows is None else rows
    return {row["id"]: row for row in rows}


def effective_main_rows() -> list[dict]:
    rows = load_frozen()
    swaps = load_swaps()
    by_id = row_map(rows)
    mains, _reserves = derive(rows, swaps)
    return [by_id[item] for item in mains]


def slug(project_url: str) -> str:
    url = project_url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    marker = "github.com/"
    idx = url.find(marker)
    if idx == -1:
        raise ValueError(f"not a github project url: {project_url}")
    return url[idx + len(marker) :]


def evidence_path(name: str) -> Path:
    return EVIDENCE / name
