"""Replay A/B/C from a certificate and compare parsed outcomes."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tools.certify_rspec.parse_rspec import norm_id, parse_outcome
from tools.certify_rspec.runner import docker_rspec

COMPARE_FIELDS = (
    "exit_code",
    "example_count",
    "failure_count",
    "first_error_class",
    "failed_ids",
    "order",
)


def outcomes_match(actual: dict, recorded: dict) -> list[str]:
    mismatches = []
    fields = list(COMPARE_FIELDS)
    if "victim_status" in recorded:
        fields.append("victim_status")
    for field in fields:
        if actual.get(field) != recorded.get(field):
            mismatches.append(
                f"{field}: actual={actual.get(field)!r} recorded={recorded.get(field)!r}"
            )
    return mismatches


def _victim_status(path: Path, victim_id: str) -> str | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    target = norm_id(victim_id)
    for example in data.get("examples") or []:
        ident = example.get("id") or ""
        if norm_id(str(ident)) == target:
            status = example.get("status")
            return status if isinstance(status, str) else None
    return None


def _execute(cert: dict, run: dict) -> dict:
    execution = cert["execution"]
    argv = list(run["exec_argv"])
    json_host = Path(run["json_host"]) if run.get("json_host") else None
    if execution["mode"] == "shell":
        proc = subprocess.run(argv, capture_output=True, check=False)
        text = proc.stdout.decode("utf-8", errors="replace")
        text += proc.stderr.decode("utf-8", errors="replace")
        return parse_outcome(text, proc.returncode, json_host)
    if execution["mode"] != "docker":
        raise SystemExit(f"unknown execution mode {execution['mode']}")
    tree = Path(execution["trees"][run["tree_side"]])
    if execution.get("clear_status"):
        status = tree / ".rspec_status"
        if status.exists():
            status.unlink()
    raw_env = run.get("extra_env")
    if raw_env is None:
        raw_env = execution.get("extra_env") or None
    env = [tuple(item) for item in raw_env] if raw_env is not None else None
    code, text, _elapsed = docker_rspec(
        image=execution["image"],
        tree=tree,
        rspec_argv=argv,
        json_host=json_host,
        timeout=int(execution.get("timeout_s", 240)),
        bundler=execution.get("bundler"),
        extra_mounts=execution.get("extra_mounts"),
        extra_env=env,
    )
    return parse_outcome(text, code, json_host)


def replay_cert(cert_path: Path) -> int:
    cert = json.loads(cert_path.read_text(encoding="utf-8"))

    def replay_side(side: str) -> list[str]:
        found = []
        block = cert["runs"][side]
        arms = ("A", "B", "C") if cert.get("kind") != "BRITTLE" else tuple(block.keys())
        for arm in arms:
            for index, run in enumerate(block[arm], start=1):
                actual = _execute(cert, run)
                if "victim_status" in run and run.get("json_host"):
                    actual["victim_status"] = _victim_status(Path(run["json_host"]), cert["victim_id"])
                bad = outcomes_match(actual, run)
                if bad:
                    found.append(f"{side} {arm} r{index}: " + "; ".join(bad))
        return found

    # Base and head are different trees, so their reps can run together.
    if cert.get("execution", {}).get("mode") == "docker":
        with ThreadPoolExecutor(max_workers=2) as pool:
            parts = pool.map(replay_side, ("base", "head"))
        mismatches = [item for part in parts for item in part]
    else:
        mismatches = replay_side("base") + replay_side("head")
    if mismatches:
        for line in mismatches:
            print(line)
        print(f"REPLAY_MISMATCHES {len(mismatches)}")
        return 1
    print("REPLAY_OK")
    return 0


def write_replay_script(path: Path, cert_path: Path, repo_root: Path) -> None:
    script = "\n".join(
        [
            "#!/bin/sh",
            f"# replay.sh for {cert_path.name}",
            "set -eu",
            f"cd {shlex.quote(str(repo_root))}",
            f"export PYTHONPATH={shlex.quote(str(repo_root))}",
            "exec python3 -m tools.certify_rspec.replay --cert "
            + shlex.quote(str(cert_path.resolve())),
            "",
        ]
    )
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] != "--cert":
        print("usage: python3 -m tools.certify_rspec.replay --cert CERT.json", file=sys.stderr)
        return 2
    return replay_cert(Path(args[1]))


if __name__ == "__main__":
    sys.exit(main())
