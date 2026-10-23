"""Nominate candidate tests from CI reports.

A report is a nomination only. The commit comes from --sha, CI variables, or
git, never from the report. seed, image_digest, pip_freeze_sha, and bound are
written by the certificate path.
"""

import json
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from flakecert.cert import failure_signature
from flakecert.util import sha256_file

SHA_SOURCE_FLAG = "--sha"
SHA_SOURCE_GIT = "git"
# Acceptance A2: frozen samples are nominated at this commit, not at git HEAD.
PINNED_SAMPLE_SHA = "f711ef3b9426b92e2e73691439bf6d4dbaa6e341"
SHA_ENV_ORDER = (
    "BUILDKITE_COMMIT",
    "CIRCLE_SHA1",
    "CI_COMMIT_SHA",
    "GITHUB_SHA",
)


def resolve_sha(explicit: str | None = None, env: dict | None = None) -> tuple[str, str]:
    if explicit is not None:
        value = explicit.strip()
        if not value:
            raise ValueError("empty --sha")
        return value, SHA_SOURCE_FLAG
    if env is None:
        env = os.environ
    for name in SHA_ENV_ORDER:
        value = (env.get(name) or "").strip()
        if value:
            return value, name
    return git_head(), SHA_SOURCE_GIT


def git_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    sha = (proc.stdout or "").strip()
    if proc.returncode != 0 or not sha:
        detail = (proc.stderr or "").strip() or "no output"
        raise RuntimeError(f"git rev-parse HEAD failed: {detail}")
    return sha


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _iter(root, name: str):
    for el in root.iter():
        if _local(el.tag) == name:
            yield el


def _child(parent, name: str):
    for child in list(parent):
        if _local(child.tag) == name:
            return child
    return None


def detect_junit_format(root) -> str:
    has_file = False
    has_go = False
    for el in root.iter():
        tag = _local(el.tag)
        if tag == "testcase" and el.get("file"):
            has_file = True
        if tag == "property" and el.get("name") == "go.version":
            has_go = True
    if has_go:
        return "gotestsum-junit"
    if has_file:
        return "jest-junit"
    return "pytest-junit"


def junit_key(fmt: str, tc) -> str:
    name = tc.get("name") or ""
    classname = tc.get("classname") or ""
    if fmt == "jest-junit":
        # jest-junit 16 names the suite "undefined" and prefixes the testcase
        # name with a space when there is no describe(). Key on file + name.
        filename = tc.get("file") or ""
        return f"{filename}::{name.strip()}"
    if fmt == "gotestsum-junit":
        return f"{classname}/{name}"
    return f"{classname}::{name}"


def junit_outcome(tc) -> str:
    if _child(tc, "failure") is not None:
        return "failed"
    if _child(tc, "error") is not None:
        return "error"
    if _child(tc, "skipped") is not None:
        return "skipped"
    return "passed"


def junit_failure_text(tc) -> str | None:
    node = _child(tc, "failure")
    if node is None:
        node = _child(tc, "error")
    if node is None:
        return None
    return (node.get("message") or "") + "\n" + (node.text or "")


def _line_from_location(location: str | None) -> int | None:
    if not location or ":" not in location:
        return None
    tail = location.rsplit(":", 1)[1]
    if tail.isdigit():
        return int(tail)
    return None


def _row(
    fmt: str,
    key: str,
    outcome: str,
    duration,
    failure_text: str | None = None,
    file: str | None = None,
    line: int | None = None,
) -> dict:
    row = {"format": fmt, "key": key}
    if file:
        row["file"] = file
    if line is not None:
        row["line"] = line
    row["outcome"] = outcome
    if failure_text is not None:
        row["failure_text"] = failure_text
    if duration is not None:
        row["duration"] = duration
    return row


def parse_junit(path: Path) -> list[dict]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    fmt = detect_junit_format(root)
    rows = []
    for tc in _iter(root, "testcase"):
        outcome = junit_outcome(tc)
        failure = junit_failure_text(tc) if outcome in {"failed", "error"} else None
        filename = tc.get("file") or None
        line = _line_from_location(tc.get("line"))
        rows.append(
            _row(
                fmt,
                junit_key(fmt, tc),
                outcome,
                tc.get("time"),
                failure_text=failure,
                file=filename,
                line=line,
            )
        )
    return rows


def parse_collector(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(f"{path}: collector --json output is a list")
    rows = []
    for item in data:
        if not isinstance(item, dict) or "name" not in item or "scope" not in item:
            raise ValueError(f"{path}: collector row missing scope or name")
        # id is a fresh uuid4 per run, so it cannot key a test.
        outcome = item.get("result") or ""
        failure = None
        if outcome == "failed":
            expanded = item.get("failure_expanded") or []
            failure = item.get("failure_reason", "") + "\n" + "\n".join(
                "\n".join(block.get("expanded", [])) for block in expanded
            )
        history = item.get("history") or {}
        duration = history.get("duration") if isinstance(history, dict) else None
        rows.append(
            _row(
                "buildkite-collector-json",
                f"{item.get('scope') or ''}::{item.get('name') or ''}",
                outcome,
                duration,
                failure_text=failure,
                file=item.get("file_name") or None,
                line=_line_from_location(item.get("location")),
            )
        )
    return rows


def parse_report(path) -> list[dict]:
    path = Path(path)
    raw = path.read_bytes().lstrip()
    if raw.startswith(b"<") or path.suffix.lower() == ".xml":
        return parse_junit(path)
    if raw.startswith((b"[", b"{")) or path.suffix.lower() == ".json":
        return parse_collector(path)
    raise ValueError(f"{path}: unrecognized report")


def ingest_paths(
    paths,
    sha: str,
    sha_source: str,
    repo_root: str | None = None,
) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for path in sorted(Path(item) for item in paths):
        digest = sha256_file(path)
        for index, row in enumerate(parse_report(path)):
            item = dict(row)
            item["_digest"] = digest
            item["_path"] = str(path)
            item["_index"] = index
            grouped.setdefault(item["key"], []).append(item)
    candidates = []
    for key in sorted(grouped):
        items = grouped[key]
        n_pass = sum(1 for row in items if row["outcome"] == "passed")
        n_fail = sum(1 for row in items if row["outcome"] == "failed")
        if n_pass < 1 or n_fail < 1:
            continue
        sigs = []
        for row in sorted(items, key=lambda record: (record["_path"], record["_index"])):
            if row["outcome"] != "failed":
                continue
            sig = failure_signature(row.get("failure_text") or "", repo_root=repo_root)
            if sig:
                sigs.append(sig)
        candidates.append(
            {
                "key": key,
                "sha": sha,
                "sha_source": sha_source,
                "n_pass": n_pass,
                "n_fail": n_fail,
                "sig_of_failures": sigs,
                "reports": sorted({row["_digest"] for row in items}),
            }
        )
    return candidates
