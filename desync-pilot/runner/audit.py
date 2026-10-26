#!/usr/bin/env python3
"""Static replay of the published desync-oracle pack.

Implements desync-pilot/SPEC.md. Dry-run only. Reads files, checks sha256
freezes, writes a conformance map, a hardening checklist, and a verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PILOT = Path(__file__).resolve().parents[1]
REPO = PILOT.parent

CHAINS = {"LOW", "MEDIUM", "HIGH"}
LABELS = {"PAYABLE", "NOT-PAYABLE", "NEEDS-LIVE"}
VERDICT_WORDS = {"GO", "HARDENING-REQUIRED", "NO-GO"}
COUNT_RE = re.compile(
    r"^(\d+) rules, (\d+) HIGH, (\d+) MEDIUM, (\d+) LOW, "
    r"(\d+) PAYABLE, (\d+) NOT-PAYABLE, (\d+) NEEDS-LIVE\.$"
)
SCORE_ROW_RE = re.compile(
    r"^\| (Rules|HIGH|MEDIUM|LOW|PAYABLE|NOT-PAYABLE|NEEDS-LIVE) \| (\d+) \|$"
)
VERDICT_RE = re.compile(r"^\*\*([A-Z-]+)\*\*$")
SCORE_VERDICT_RE = re.compile(r"^Verdict: \*\*([A-Z-]+)\*\*$")


def verdict_word(high: int, medium: int) -> str:
    if high > 0:
        return "NO-GO"
    if medium > 0:
        return "HARDENING-REQUIRED"
    return "GO"


def assert_verdict_function() -> None:
    pairs = (
        (1, 0, "NO-GO"),
        (0, 1, "HARDENING-REQUIRED"),
        (0, 0, "GO"),
    )
    for high, medium, expected in pairs:
        got = verdict_word(high, medium)
        if got != expected:
            raise SystemExit(
                f"verdict function assert failed: ({high}, {medium}) -> {got}, expected {expected}"
            )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def die(message: str) -> None:
    print(f"audit: {message}", file=sys.stderr)
    raise SystemExit(1)


def heading_index(lines: list[str], title: str) -> int:
    needle = f"## {title}"
    for index, line in enumerate(lines):
        if line == needle:
            return index
    die(f"heading not found: {needle}")
    return -1


def section_end(lines: list[str], start: int) -> int:
    end = start + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return end


def load_profile(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = (
        "id",
        "edge_heading",
        "count_prefix",
        "score_heading",
        "verdict_heading",
        "pin_rel",
        "rebuild_prefix",
    )
    missing = [key for key in required if key not in data]
    if missing:
        die(f"{path.name} missing keys: {', '.join(missing)}")
    if data["id"] != path.stem:
        die(f"{path.name} id is {data['id']}, expected {path.stem}")
    return data


def verify_freezes(oracle: Path) -> list[str]:
    freeze_path = oracle / "FREEZES.txt"
    if not freeze_path.is_file():
        die(f"missing {freeze_path}")
    notes = []
    for raw in read_lines(freeze_path):
        if not raw.strip():
            continue
        if "  " not in raw:
            die(f"FREEZES line has no sha256sum separator: {raw}")
        digest, rel = raw.split("  ", 1)
        target = oracle / rel
        if not target.is_file():
            die(f"FREEZES names a missing file: {rel}")
        got = sha256_file(target)
        if got != digest:
            die(f"sha256 mismatch {rel}: expected {digest}, got {got}")
        notes.append(f"freeze ok {rel} {got}")
    if not notes:
        die("FREEZES.txt has no lines")
    return notes


def parse_table(lines: list[str]) -> tuple[list[dict], str]:
    rows = []
    count_line = ""
    for line in lines:
        if re.match(r"^\| R[0-9]{2}-", line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) != 6:
                die(f"row does not have 6 cells: {line}")
            rule, rfc, front, origin, chain, label = cells
            if chain not in CHAINS:
                die(f"chain cell {chain!r} on {rule}")
            if label not in LABELS:
                die(f"label cell {label!r} on {rule}")
            if label == "PAYABLE" and chain not in {"HIGH", "MEDIUM"}:
                die(f"PAYABLE on {chain} for {rule}; rubric says PAYABLE only on HIGH or MEDIUM")
            rows.append(
                {
                    "rule": rule,
                    "rfc": rfc,
                    "front": front,
                    "origin": origin,
                    "chain": chain,
                    "label": label,
                    "line": line,
                }
            )
        elif " count: " in line or line.startswith("nginx count:") or line.startswith("HAProxy count:"):
            count_line = line
    return rows, count_line


def count_rows(rows: list[dict]) -> dict[str, int]:
    counts = {
        "Rules": len(rows),
        "HIGH": sum(1 for row in rows if row["chain"] == "HIGH"),
        "MEDIUM": sum(1 for row in rows if row["chain"] == "MEDIUM"),
        "LOW": sum(1 for row in rows if row["chain"] == "LOW"),
        "PAYABLE": sum(1 for row in rows if row["label"] == "PAYABLE"),
        "NOT-PAYABLE": sum(1 for row in rows if row["label"] == "NOT-PAYABLE"),
        "NEEDS-LIVE": sum(1 for row in rows if row["label"] == "NEEDS-LIVE"),
    }
    return counts


def require_rule_order(rows: list[dict]) -> None:
    if len(rows) != 25:
        die(f"expected 25 rules, parsed {len(rows)}")
    for index, row in enumerate(rows, start=1):
        prefix = f"R{index:02d}-"
        if not row["rule"].startswith(prefix):
            die(f"rule {index} is {row['rule']}, expected prefix {prefix}")


def parse_count_line(line: str, prefix: str) -> dict[str, int]:
    if not line.startswith(prefix):
        die(f"count line {line!r} does not start with {prefix!r}")
    match = COUNT_RE.match(line[len(prefix) :].strip())
    if not match:
        die(f"count line does not match the sealed shape: {line}")
    rules, high, medium, low, payable, not_payable, needs_live = (
        int(part) for part in match.groups()
    )
    return {
        "Rules": rules,
        "HIGH": high,
        "MEDIUM": medium,
        "LOW": low,
        "PAYABLE": payable,
        "NOT-PAYABLE": not_payable,
        "NEEDS-LIVE": needs_live,
    }


def parse_score(lines: list[str], heading: str) -> tuple[dict[str, int], str]:
    start = heading_index(lines, heading)
    end = section_end(lines, start)
    counts: dict[str, int] = {}
    word = ""
    for line in lines[start:end]:
        row = SCORE_ROW_RE.match(line)
        if row:
            counts[row.group(1)] = int(row.group(2))
        verdict = SCORE_VERDICT_RE.match(line)
        if verdict:
            word = verdict.group(1)
    if set(counts) != {"Rules", "HIGH", "MEDIUM", "LOW", "PAYABLE", "NOT-PAYABLE", "NEEDS-LIVE"}:
        die(f"score table under {heading} is incomplete: {sorted(counts)}")
    if word not in VERDICT_WORDS:
        die(f"sealed score verdict {word!r} under {heading}")
    return counts, word


def parse_verdict_word(lines: list[str], heading: str) -> str:
    start = heading_index(lines, heading)
    end = section_end(lines, start)
    for line in lines[start + 1 : end]:
        match = VERDICT_RE.match(line)
        if match:
            word = match.group(1)
            if word not in VERDICT_WORDS:
                die(f"sealed verdict word {word!r} under {heading}")
            return word
    die(f"no bold verdict under {heading}")
    return ""


def same_counts(left: dict[str, int], right: dict[str, int], label: str) -> None:
    for key in ("Rules", "HIGH", "MEDIUM", "LOW", "PAYABLE", "NOT-PAYABLE", "NEEDS-LIVE"):
        if left[key] != right[key]:
            die(f"{label} {key}: replay {left[key]} versus sealed {right[key]}")


def extract_rebuild(lines: list[str], prefix: str) -> list[str]:
    start = heading_index(lines, "What each default front rebuilds")
    end = section_end(lines, start)
    collected: list[str] = []
    capturing = False
    for line in lines[start + 1 : end]:
        if line.startswith(prefix):
            capturing = True
            collected.append(line)
            continue
        if capturing and line.startswith("**"):
            break
        if capturing:
            collected.append(line)
    if not collected:
        die(f"rebuild paragraph not found for {prefix}")
    return collected


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def render(profile: dict, oracle: Path, out_dir: Path, freeze_notes: list[str]) -> list[str]:
    conformance_lines = read_lines(oracle / "CONFORMANCE-MAP.md")
    hardening_lines = read_lines(oracle / "HARDENING.md")
    verdict_lines = read_lines(oracle / "VERDICT.md")
    score_lines = read_lines(oracle / "SCORE-SUMMARY.md")

    edge_start = heading_index(conformance_lines, profile["edge_heading"])
    edge_end = section_end(conformance_lines, edge_start)
    rows, count_line = parse_table(conformance_lines[edge_start:edge_end])
    require_rule_order(rows)
    counted = count_rows(rows)
    from_line = parse_count_line(count_line, profile["count_prefix"])
    same_counts(counted, from_line, "count line")

    score_counts, score_word = parse_score(score_lines, profile["score_heading"])
    verdict_sealed = parse_verdict_word(verdict_lines, profile["verdict_heading"])
    same_counts(counted, score_counts, "SCORE-SUMMARY")
    mapped = verdict_word(counted["HIGH"], counted["MEDIUM"])
    if mapped != score_word or mapped != verdict_sealed:
        die(
            "sealed verdict disagrees with the replay map: "
            f"map {mapped}, SCORE-SUMMARY {score_word}, VERDICT.md {verdict_sealed}. "
            "No file written."
        )

    pin_note = next(note for note in freeze_notes if note.split()[2] == profile["pin_rel"])
    pin_digest = pin_note.split()[-1]
    medium_ids = [row["rule"] for row in rows if row["chain"] == "MEDIUM"]
    high_ids = [row["rule"] for row in rows if row["chain"] == "HIGH"]

    rubric_start = heading_index(conformance_lines, "Chain-risk rubric")
    rubric_end = heading_index(conformance_lines, "What each default front rebuilds")
    rules_start = heading_index(conformance_lines, "Rules")
    rebuild = extract_rebuild(conformance_lines, profile["rebuild_prefix"])
    verdict_start = heading_index(verdict_lines, profile["verdict_heading"])
    verdict_end = section_end(verdict_lines, verdict_start)

    banner = [
        f"Profile: `{profile['id']}`",
        "Mode: dry-run replay of `desync-oracle/`. Not a new score.",
        f"Pin: `{profile['pin_rel']}` sha256 `{pin_digest}` (checked against `FREEZES.txt`).",
        "The sealed holdout remains `desync-oracle/SCORE-SUMMARY.md`. This file restates it.",
        "",
    ]

    conformance = [
        f"# Conformance map — {profile['id']}",
        "",
        *banner,
        *conformance_lines[rubric_start:rubric_end],
        "## What this front rebuilds",
        "",
        *rebuild,
        "",
        *conformance_lines[edge_start:edge_end],
        "",
        *conformance_lines[rules_start:],
        "",
    ]

    medium_text = ", ".join(medium_ids) if medium_ids else "none"
    high_text = ", ".join(high_ids) if high_ids else "none"
    hardening = [
        f"# Hardening checklist — {profile['id']}",
        "",
        *banner,
        f"HIGH rows in this profile's table: {high_text}.",
        f"MEDIUM rows in this profile's table: {medium_text}.",
        "The checklist below is the published `desync-oracle/HARDENING.md`, copied whole.",
        "Paragraphs name the front they apply to. The other published front is included so the operator can see it is a different profile.",
        "",
        *hardening_lines,
        "",
    ]

    verdict = [
        f"# Verdict — {profile['id']}",
        "",
        *banner,
        f"**{mapped}**",
        "",
        f"Rules {counted['Rules']}. HIGH {counted['HIGH']}. MEDIUM {counted['MEDIUM']}. LOW {counted['LOW']}.",
        f"PAYABLE {counted['PAYABLE']}. NOT-PAYABLE {counted['NOT-PAYABLE']}. NEEDS-LIVE {counted['NEEDS-LIVE']}.",
        "",
        f"Cross-check SCORE-SUMMARY.md heading \"{profile['score_heading']}\": **{score_word}**.",
        f"Cross-check VERDICT.md heading \"{profile['verdict_heading']}\": **{verdict_sealed}**.",
        "The map is HIGH then NO-GO, else MEDIUM then HARDENING-REQUIRED, else GO.",
        "The mapped word matches both sealed words, so this replay writes the sealed word.",
        "",
        *verdict_lines[verdict_start:verdict_end],
        "",
    ]

    summary = [
        f"profile: {profile['id']}",
        f"pin: {profile['pin_rel']}",
        f"pin_sha256: {pin_digest}",
        "pin_check: ok",
        f"freezes_checked: {len(freeze_notes)}",
        f"rules: {counted['Rules']}",
        f"HIGH: {counted['HIGH']}",
        f"MEDIUM: {counted['MEDIUM']}",
        f"LOW: {counted['LOW']}",
        f"PAYABLE: {counted['PAYABLE']}",
        f"NOT-PAYABLE: {counted['NOT-PAYABLE']}",
        f"NEEDS-LIVE: {counted['NEEDS-LIVE']}",
        f"verdict: {mapped}",
        f"sealed_score: {score_word}",
        f"sealed_verdict: {verdict_sealed}",
        f"medium_rows: {medium_text}",
        f"high_rows: {high_text}",
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "conformance-map.md": "\n".join(conformance),
        "hardening.md": "\n".join(hardening),
        "verdict.md": "\n".join(verdict),
    }
    for name, text in files.items():
        write_text(out_dir / name, text)
        summary.append(f"wrote: {out_dir.relative_to(REPO) / name}")

    runlog = "\n".join(summary) + "\n"
    write_text(out_dir / "RUNLOG.txt", runlog)
    summary.append(f"wrote: {out_dir.relative_to(REPO) / 'RUNLOG.txt'}")

    sums = []
    for name in ("conformance-map.md", "hardening.md", "verdict.md", "RUNLOG.txt"):
        sums.append(f"{sha256_file(out_dir / name)}  {name}")
    write_text(out_dir / "SHA256SUMS", "\n".join(sums) + "\n")
    summary.append(f"wrote: {out_dir.relative_to(REPO) / 'SHA256SUMS'}")
    return summary


def profile_paths(single: str | None) -> list[Path]:
    directory = PILOT / "profiles"
    if single:
        path = directory / f"{single}.json"
        if not path.is_file():
            print(f"audit: unknown profile {single}", file=sys.stderr)
            raise SystemExit(2)
        return [path]
    found = sorted(directory.glob("*.json"))
    if not found:
        die("no profiles")
    return found


def main(argv: list[str]) -> int:
    assert_verdict_function()
    print("verdict_function_assert: ok")
    parser = argparse.ArgumentParser(description="Replay the published desync oracle. Dry-run only.")
    parser.add_argument("--profile", help="Profile id, for example nginx-proxy_pass-default")
    parser.add_argument("--all", action="store_true", help="Replay every profile")
    parser.add_argument("--dry-run", action="store_true", help="Required. Read files and write out/<profile>/")
    parser.add_argument("--oracle", type=Path, default=REPO / "desync-oracle")
    args = parser.parse_args(argv)
    if not args.dry_run:
        print("audit: only --dry-run is implemented", file=sys.stderr)
        return 2
    if args.all == bool(args.profile):
        print("audit: pass exactly one of --profile NAME or --all", file=sys.stderr)
        return 2
    oracle = args.oracle.resolve()
    if not oracle.is_dir():
        die(f"oracle directory not found: {oracle}")
    freeze_notes = verify_freezes(oracle)
    for path in profile_paths(args.profile):
        profile = load_profile(path)
        if profile["pin_rel"] not in {note.split()[2] for note in freeze_notes}:
            die(f"profile pin is not in FREEZES.txt: {profile['pin_rel']}")
        out_dir = PILOT / "out" / profile["id"]
        summary = render(profile, oracle, out_dir, freeze_notes)
        print("\n".join(summary))
        print("---")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
