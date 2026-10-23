"""Docker invocations for bundle and rspec. RSpec does not run on the host."""

from __future__ import annotations

import shlex
import subprocess
import time
from pathlib import Path

from tools.certify_rspec.commands import ORDERING_REQUIRE, ordering_dir

BUNDLE_ENV = (
    "-e",
    "BUNDLE_APP_CONFIG=/src/.bundle",
    "-e",
    "BUNDLE_SILENCE_ROOT_WARNING=1",
)


def argv_length(argv: list[str]) -> int:
    if not argv:
        return 0
    return sum(len(arg) for arg in argv) + len(argv) - 1


def docker_base(
    image: str,
    tree: Path,
    extra_mounts: list[str] | None = None,
    extra_env: list[tuple[str, str]] | None = None,
) -> list[str]:
    cmd = [
        "docker",
        "run",
        "--rm",
        *BUNDLE_ENV,
    ]
    for key, value in extra_env or []:
        cmd.extend(["-e", f"{key}={value}"])
    cmd.extend(["-v", f"{tree.resolve()}:/src"])
    if extra_mounts:
        cmd.extend(extra_mounts)
    cmd.extend(["-w", "/src", image])
    return cmd


def run_docker(cmd: list[str], timeout: int) -> tuple[int, str, float]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        text = proc.stdout.decode("utf-8", errors="replace")
        code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout or b""
        if isinstance(raw, str):
            text = raw
        else:
            text = raw.decode("utf-8", errors="replace")
        text += f"\nTIMEOUT after {timeout}s\n"
        code = 124
    elapsed = time.monotonic() - started
    return code, text, elapsed


def docker_bash(
    image: str,
    tree: Path,
    script: str,
    timeout: int,
    extra_mounts: list[str] | None = None,
    extra_env: list[tuple[str, str]] | None = None,
) -> tuple[int, str, float]:
    cmd = docker_base(image, tree, extra_mounts, extra_env) + ["bash", "-lc", script]
    return run_docker(cmd, timeout)


def ordering_mount(rspec_argv: list[str], extra_mounts: list[str] | None) -> list[str]:
    """Mount the require file's directory when this argv loads it."""
    mounts = list(extra_mounts or [])
    if ORDERING_REQUIRE not in rspec_argv:
        return mounts
    spec = f"{ordering_dir().resolve()}:/flakecert:ro"
    if spec not in mounts:
        mounts.extend(["-v", spec])
    return mounts


def rspec_docker_cmd(
    image: str,
    tree: Path,
    rspec_argv: list[str],
    json_host: Path | None,
    bundler: str | None = None,
    extra_mounts: list[str] | None = None,
    extra_env: list[tuple[str, str]] | None = None,
) -> list[str]:
    """Container argv. json_host's parent is mounted at /out when set."""
    mounts = ordering_mount(rspec_argv, extra_mounts)
    if json_host is not None:
        json_host.parent.mkdir(parents=True, exist_ok=True)
        mounts.extend(["-v", f"{json_host.parent.resolve()}:/out"])
    bundle = ["bundle"]
    if bundler:
        bundle.append(f"_{bundler}_")
    bundle.extend(["exec", "rspec"])
    return docker_base(image, tree, mounts, extra_env) + bundle + list(rspec_argv)


def docker_rspec(
    image: str,
    tree: Path,
    rspec_argv: list[str],
    json_host: Path | None,
    timeout: int,
    bundler: str | None = None,
    extra_mounts: list[str] | None = None,
    extra_env: list[tuple[str, str]] | None = None,
) -> tuple[int, str, float]:
    """Run bundle exec rspec. rspec_argv is the argument vector inside the container.

    When json_host is set, its parent directory is mounted at /out and the
    caller must already have put ``--out /out/<name>`` in rspec_argv.
    """
    cmd = rspec_docker_cmd(
        image,
        tree,
        rspec_argv,
        json_host,
        bundler=bundler,
        extra_mounts=extra_mounts,
        extra_env=extra_env,
    )
    return run_docker(cmd, timeout)


def command_preview(cmd: list[str], limit: int = 4000) -> str:
    shown = " ".join(shlex.quote(part) for part in cmd)
    if len(shown) <= limit:
        return shown
    return shown[:limit] + f" ... truncated total_chars={len(shown)}"
