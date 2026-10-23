"""Recompute S4 labels from recorded runs. Does not rerun rspec."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from tools.certify_rspec.certificate import validate_certificate
from tools.certify_rspec.exit_rule import classification_exit_ok
from tools.certify_rspec.verdict import judge

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "inputs" / "dryrun-2026-10-19-g1" / "SPEC-certify-rspec-G1.md"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _cert_paths(out: Path) -> list[Path]:
    paths = list(out.glob("cert-*.json"))

    def index(path: Path) -> int:
        return int(path.stem.split("-", 1)[1])

    return sorted(paths, key=index)


def _check_logs(out: Path, cert: dict) -> None:
    for side in ("base", "head"):
        for arm in ("A", "B", "C"):
            for run in cert["runs"][side][arm]:
                name = Path(run["log"]).name
                path = out / "s4" / name
                if not path.is_file():
                    raise SystemExit(f"missing s4 log {name}")
                digest = _sha256(path)
                if digest != run.get("log_sha256"):
                    raise SystemExit(f"s4 log sha256 mismatch {name}")


def _leaf(location: str) -> str:
    return location.rsplit("/", 1)[-1]


def _compact(location: str) -> str:
    leaf = _leaf(location)
    file_name, sep, line = leaf.rpartition(":")
    if not sep:
        return leaf
    suffix = "_spec.rb"
    stem = file_name[: -len(suffix)] if file_name.endswith(suffix) else file_name
    return stem.split("_or_")[0] + ":" + line


def _acceptance_pattern(spec_text: str) -> str:
    match = re.search(r"grep for (\S+)", spec_text)
    if not match:
        raise SystemExit("spec has no acceptance grep pattern")
    return match.group(1)


def _acceptance_targets(spec_text: str) -> tuple[list[str], str, str]:
    match = re.search(
        r"CERTIFIED for the victims at (.+?),\s*each with \|P\(v\)\| >= 1 and the M4 (\w+) at base\.",
        spec_text,
        re.S,
    )
    if not match:
        raise SystemExit("spec has no acceptance-2 victim list")
    blob = re.sub(r"\s+", " ", match.group(1)).strip()
    victims = [part.strip() for part in re.split(r", | and ", blob) if part.strip()]
    control = re.search(
        r"^\d+\. (\S+) attributed, NOT_FIXED at both commits \(the control\)\.",
        spec_text,
        re.M,
    )
    if not control:
        raise SystemExit("spec has no acceptance-3 control")
    return victims, match.group(2), control.group(1)


def _row_for(rows: list[dict], suffix: str) -> list[dict]:
    return [row for row in rows if row["location"].endswith(suffix)]


def _grep(pattern: str, target: Path, recursive: bool) -> tuple[int, str]:
    argv = ["grep", "-nE" if not recursive else "-RInE", pattern, str(target)]
    proc = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout


def _write_sums(out: Path) -> None:
    rels = []
    for path in out.rglob("*"):
        if path.is_file() and path.name != "SHA256SUMS":
            rels.append("./" + path.relative_to(out).as_posix())
    lines = [f"{_sha256(out / rel[2:])}  {rel}" for rel in sorted(rels)]
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _preserve_skeptic(text: str) -> str:
    marker = "## Skeptic pass"
    if marker not in text:
        return ""
    suffix = text.split(marker, 1)[1]
    if "## Rejudge" in suffix:
        suffix = suffix.split("## Rejudge", 1)[0]
    return marker + suffix.rstrip() + "\n"


def _summary_table(rows: list[dict]) -> str:
    lines = [
        "# PR check",
        "",
        "One line per order-dependent id. Verdicts are arm A. Plain-retry is arm B.",
        "",
        "| victim | base | head | plain-retry base | plain-retry head | polluter ids | label |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        polluters = " ".join(row["polluter_ids"])
        lines.append(
            "| {victim} | {base} | {head} | {pb} | {ph} | {polluters} | {label} |".format(
                victim=row["location"],
                base=row["base"],
                head=row["head"],
                pb=row["plain_base"],
                ph=row["plain_head"],
                polluters=polluters,
                label=row["label"],
            )
        )
    return "\n".join(lines) + "\n"


def _rejudge_note() -> str:
    return "\n".join(
        [
            "## Rejudge",
            "",
            "Rejudged from the recorded S4 runs. Each run's log sha256 matches the file under s4/. No rspec rerun.",
            "",
            "NOT_FIXED requires a stable arm failure whose failed_ids equal [victim_id] on every rep, so the polluter ids passed. If any rep's failed_ids include a polluter id, that arm's verdict is POLLUTER_FAILED and the certificate label is REJECTED. The first error message line stays out of the signature.",
            "",
            "What else could move a verdict:",
            "- Adding the message line to the signature would split reps whose message text changes while the error class and failed ids stay the same.",
            "- Reading the documentation Failed examples file:line instead of the JSON example id would not equal victim_id.",
            "- A failure list of the victim plus any other id is not NOT_FIXED. A polluter id in that list is POLLUTER_FAILED.",
            "- A polluter failure on a single rep is enough for POLLUTER_FAILED.",
            "- Arm C has no verdict field. A polluter failure only on C still sets the label to REJECTED.",
            "- FIXED still means the arm's exit code and failure count say pass. The id check applies to failures.",
            "",
        ]
    )


def _update_summary(path: Path, rows: list[dict]) -> None:
    if not path.is_file():
        return
    summary = json.loads(path.read_text(encoding="utf-8"))
    by_cert = {row["cert"]: row for row in rows}
    summary["certified"] = [row["location"] for row in rows if row["label"] == "CERTIFIED"]
    summary["control"] = [row["location"] for row in rows if row["label"] == "CONTROL"]
    summary["rejected"] = [row["location"] for row in rows if row["label"] == "REJECTED"]
    for old in summary.get("rows") or []:
        updated = by_cert.get(old.get("cert"))
        if not updated:
            continue
        old["base"] = updated["base"]
        old["head"] = updated["head"]
        old["plain_base"] = updated["plain_base"]
        old["plain_head"] = updated["plain_head"]
        old["label"] = updated["label"]
    summary["exit_ok"] = classification_exit_ok(rows)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def _write_g1(out: Path, rows: list[dict], spec_text: str) -> None:
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    run_log = (out / "run.log").read_text(encoding="utf-8", errors="replace")
    victims, error_class, control_suffix = _acceptance_targets(spec_text)
    pattern = _acceptance_pattern(spec_text)
    tool_dir = REPO_ROOT / "tools" / "certify_rspec"
    invocation = out / "invocation.txt"
    tool_code, tool_out = _grep(pattern, tool_dir, True)
    inv_code, inv_out = _grep(pattern, invocation, False)
    acceptance_1 = tool_code == 1 and inv_code == 1 and tool_out == "" and inv_out == ""
    acceptance_2 = True
    for suffix in victims:
        matches = _row_for(rows, suffix)
        if len(matches) != 1:
            acceptance_2 = False
            break
        row = matches[0]
        if row["label"] != "CERTIFIED" or len(row["polluter_ids"]) < 1:
            acceptance_2 = False
            break
        if row["base_error_class"] != error_class:
            acceptance_2 = False
            break
    control_rows = _row_for(rows, control_suffix)
    acceptance_3 = (
        len(control_rows) == 1
        and control_rows[0]["label"] == "CONTROL"
        and control_rows[0]["base"] == "NOT_FIXED"
        and control_rows[0]["head"] == "NOT_FIXED"
    )
    replay_text = (out / "replay-check.log").read_text(encoding="utf-8")
    exits = re.findall(r"^replay_exit=(\d+)$", replay_text, re.M)
    acceptance_4 = len(exits) == len(rows) and all(item == "0" for item in exits)
    go = acceptance_1 and acceptance_2 and acceptance_3 and acceptance_4
    certified = [row["location"] for row in rows if row["label"] == "CERTIFIED"]
    rejected = [row["location"] for row in rows if row["label"] == "REJECTED"]
    control = [row["location"] for row in rows if row["label"] == "CONTROL"]
    ruby = summary["ruby"]
    if not ruby.startswith("ruby "):
        ruby = "ruby " + ruby
    lines = [
        f"image_id {summary['image_id']}",
        f"docker_server {summary['docker_server']}",
        ruby,
        summary["bundler"],
        f"rspec-core {summary['rspec_core']}",
        f"s1 {summary['s1_examples']} examples, {summary['s1_failing']} failures",
    ]
    if run_log.count("bundle_check_exit=0") >= 2:
        lines.append("bundle_check_exit=0 for both trees (run.log)")
    lines.append("")
    lines.append(f"CERTIFIED {len(certified)}")
    for row in rows:
        if row["label"] == "REJECTED":
            lines.append(f"REJECTED {_leaf(row['location'])}")
    for row in rows:
        if row["label"] == "CONTROL":
            lines.append(f"CONTROL {_compact(row['location'])}")
    lines.append("")
    for row in rows:
        lines.append(
            f"{row['label']} {row['location']} base={row['base']} head={row['head']} "
            f"plain={row['plain_base']}/{row['plain_head']} polluters={len(row['polluter_ids'])}"
        )
    lines.extend(
        [
            "",
            f"OD_COUNT {summary.get('od_count', len(rows))}",
            f"ATTRIBUTED {summary.get('attributed_count', len(rows))}",
            "CERTIFIED " + ",".join(certified),
            "REJECTED " + ",".join(rejected),
            "CONTROL " + ",".join(control),
            f"ACCEPTANCE_1 {acceptance_1}",
            f"ACCEPTANCE_2 {acceptance_2}",
            f"ACCEPTANCE_3 {acceptance_3}",
            f"ACCEPTANCE_4 {acceptance_4}",
            f"GO {go}",
            "===== acceptance 1 grep =====",
            f"+ grep -RInE {pattern!r} tools/certify_rspec",
            tool_out.rstrip("\n"),
            f"grep_exit={tool_code}",
            f"+ grep -nE {pattern!r} {invocation.relative_to(REPO_ROOT).as_posix()}",
            inv_out.rstrip("\n"),
            f"grep_exit={inv_code}",
            "===== replay-check.log =====",
        ]
    )
    for item in exits:
        lines.append(f"replay_exit={item}")
    (out / "g1.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def rejudge(out: Path) -> int:
    out = out.resolve()
    if not out.is_dir():
        raise SystemExit(f"not a directory: {out}")
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    rows = []
    for path in _cert_paths(out):
        cert = json.loads(path.read_text(encoding="utf-8"))
        _check_logs(out, cert)
        judged = judge(
            cert["runs"]["base"],
            cert["runs"]["head"],
            cert["victim_id"],
            cert["polluter_ids"],
        )
        cert["verdicts"] = judged["verdicts"]
        cert["plain_retry_verdict"] = judged["plain_retry_verdict"]
        cert["rep_disagreement"] = judged["rep_disagreement"]
        cert["c_passes"] = judged["c_passes"]
        cert["label"] = judged["label"]
        errors = validate_certificate(cert)
        if errors:
            raise SystemExit("certificate failed schema validation: " + "; ".join(errors))
        path.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
        base_classes = [run.get("first_error_class") for run in cert["runs"]["base"]["A"]]
        base_error = base_classes[0] if base_classes and all(item == base_classes[0] for item in base_classes) else None
        row = {
            "cert": path.name,
            "location": cert.get("victim_location") or cert["victim_id"],
            "base": judged["verdicts"]["base"],
            "head": judged["verdicts"]["head"],
            "plain_base": judged["plain_retry_verdict"]["base"],
            "plain_head": judged["plain_retry_verdict"]["head"],
            "polluter_ids": list(cert["polluter_ids"]),
            "label": judged["label"],
            "base_error_class": base_error,
        }
        rows.append(row)
        print(f"{path.name} {row['location']} {row['label']} base={row['base']} head={row['head']}")
    summary_md = out / "check-summary.md"
    skeptic = _preserve_skeptic(summary_md.read_text(encoding="utf-8") if summary_md.is_file() else "")
    parts = [_summary_table(rows).rstrip("\n")]
    if skeptic:
        parts.append(skeptic.rstrip("\n"))
    parts.append(_rejudge_note().rstrip("\n"))
    summary_md.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    _update_summary(out / "summary.json", rows)
    _write_g1(out, rows, spec_text)
    _write_sums(out)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["label"]] = counts.get(row["label"], 0) + 1
    print(f"exit_ok {summary['exit_ok']}")
    print(
        "labels "
        + " ".join(f"{label}={counts.get(label, 0)}" for label in ("CERTIFIED", "REJECTED", "CONTROL"))
    )
    return 0 if summary["exit_ok"] else 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m tools.certify_rspec rejudge DIR", file=sys.stderr)
        return 2
    return rejudge(Path(args[0]))
