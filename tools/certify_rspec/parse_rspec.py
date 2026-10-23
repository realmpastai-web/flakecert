"""Parse rspec JSON, documentation output, and --bisect text."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
SUMMARY = re.compile(r"(\d+) examples?, (\d+) failures?")
ERROR_LINE = re.compile(r"\n     ([A-Za-z_][\w:]*)\:\n       (.*)")
LOCATION = re.compile(r"^(?P<file>.*\.rb)\[(?P<inner>[0-9:,]+)\]$")

# Flags that consume the following argv token. Anything else starting with
# "-" is a boolean flag. Location tokens are what remain.
VALUE_OPTS = {
    "--seed",
    "--format",
    "--out",
    "--require",
    "--order",
    "--default-path",
    "--exclude-pattern",
    "--pattern",
    "--tag",
    "--failure-exit-code",
    "--example",
    "--profile",
    "-f",
    "-o",
    "-I",
    "-e",
}


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text).replace("\r", "")


def norm_id(value: str) -> str:
    if value.startswith("./"):
        return value[2:]
    return value


def expand_location(token: str) -> list[str]:
    match = LOCATION.match(token)
    if not match:
        return [token]
    file_name = match.group("file")
    parts = [part for part in match.group("inner").split(",") if part]
    return [f"{file_name}[{part}]" for part in parts]


def locations_from_repro(command: str) -> list[str]:
    args = shlex.split(command)
    if args and args[0] == "rspec":
        args = args[1:]
    locs: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in VALUE_OPTS:
            index += 2
            continue
        if arg.startswith("-"):
            index += 1
            continue
        locs.append(arg)
        index += 1
    expanded: list[str] = []
    for loc in locs:
        expanded.extend(expand_location(loc))
    return expanded


def polluter_ids(repro_ids: list[str], victim_id: str) -> list[str] | None:
    """Ids in the repro command except the victim. None if the victim is absent."""
    target = norm_id(victim_id)
    found = False
    polluters: list[str] = []
    for item in repro_ids:
        if norm_id(item) == target:
            found = True
            continue
        polluters.append(item)
    if not found:
        return None
    return polluters


def parse_bisect(text: str) -> dict:
    clean = strip_ansi(text)
    ordering = "ordering is inconsistent" in clean
    no_failure = "No failures found" in clean
    aborted = "Bisect aborted!" in clean
    failed = "Bisect failed!" in clean or aborted
    if failed or ordering or no_failure:
        if ordering:
            reason = "ordering abort"
        elif no_failure:
            reason = "no failure"
        elif aborted:
            reason = "bisect aborted"
        else:
            reason = "bisect failed"
        return {"attributed": False, "reason": reason, "command": None, "ids": []}
    matches = re.findall(r"The minimal reproduction command is:\n  (.+)", clean)
    if not matches:
        return {
            "attributed": False,
            "reason": "no minimal reproduction command",
            "command": None,
            "ids": [],
        }
    command = matches[-1].strip()
    return {
        "attributed": True,
        "reason": None,
        "command": command,
        "ids": locations_from_repro(command),
    }


def example_location(example: dict) -> str:
    file_path = example.get("file_path") or ""
    if file_path.startswith("/src/"):
        file_path = "./" + file_path[len("/src/") :]
    line = example.get("line_number")
    if not file_path:
        return str(example.get("id") or "")
    if line is None:
        return file_path
    return f"{file_path}:{line}"


def parse_json_run(data: dict, exit_code: int) -> dict:
    examples = data.get("examples") or []
    order = [example.get("id") for example in examples]
    failed = [example["id"] for example in examples if example.get("status") == "failed"]
    first = next((example for example in examples if example.get("status") == "failed"), None)
    error_class = None
    message_line = None
    if first:
        exc = first.get("exception") or {}
        error_class = exc.get("class") or None
        message = exc.get("message") or ""
        if isinstance(message, str) and message:
            message_line = message.splitlines()[0]
    summary = data.get("summary") or {}
    example_count = summary.get("example_count", len(examples))
    failure_count = summary.get("failure_count", len(failed))
    return {
        "exit_code": exit_code,
        "example_count": example_count,
        "failure_count": failure_count,
        "first_error_class": error_class,
        "first_error_message_line": message_line,
        "failed_ids": failed,
        "order": order,
        "errors_outside_of_examples_count": summary.get("errors_outside_of_examples_count", 0),
    }


def parse_documentation(text: str, exit_code: int) -> dict:
    clean = strip_ansi(text)
    summary = SUMMARY.findall(clean)
    if summary:
        example_count = int(summary[-1][0])
        failure_count = int(summary[-1][1])
    else:
        example_count = None
        failure_count = None
    error_class = None
    message_line = None
    fail_at = clean.find("\nFailures:\n")
    region = clean[fail_at:] if fail_at >= 0 else clean
    error = ERROR_LINE.search(region)
    if error:
        error_class = error.group(1)
        message_line = error.group(2).strip()
    failed_ids: list[str] = []
    parts = clean.split("Failed examples:", 1)
    if len(parts) == 2:
        failed_ids = re.findall(r"^rspec (\S+)", parts[1], re.M)
    return {
        "exit_code": exit_code,
        "example_count": example_count,
        "failure_count": failure_count,
        "first_error_class": error_class,
        "first_error_message_line": message_line,
        "failed_ids": failed_ids,
        "order": list(failed_ids),
        "errors_outside_of_examples_count": 0,
    }


def parse_outcome(stdout: str, exit_code: int, json_path: Path | None) -> dict:
    if json_path is not None and json_path.is_file() and json_path.stat().st_size > 0:
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            outcome = parse_json_run(data, exit_code)
            outcome["parsed_from"] = "json"
            return outcome
        except json.JSONDecodeError:
            pass
    outcome = parse_documentation(stdout, exit_code)
    outcome["parsed_from"] = "documentation"
    return outcome
