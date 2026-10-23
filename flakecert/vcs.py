"""Fetch pinned project SHAs. Does not touch git config."""

import shutil
import subprocess
from pathlib import Path

from flakecert.paths import CACHE


def checkout(url: str, sha: str, dest: Path | None = None) -> Path:
    dest = dest or (CACHE / "src" / sha)
    marker = dest / ".flakecert-sha"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == sha and any(dest.iterdir()):
        return dest
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    env = None
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "remote", "add", "origin", url],
        cwd=dest,
        check=True,
        capture_output=True,
        text=True,
    )
    fetch = subprocess.run(
        ["git", "fetch", "--depth", "1", "origin", sha],
        cwd=dest,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    if fetch.returncode != 0:
        shutil.rmtree(dest)
        dest.mkdir(parents=True)
        clone = subprocess.run(
            ["git", "clone", "--filter=blob:none", url, str(dest)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if clone.returncode != 0:
            raise RuntimeError(f"fetch failed for {url}@{sha}: {fetch.stderr[-400:]} {clone.stderr[-400:]}")
        checkout_proc = subprocess.run(
            ["git", "checkout", "--detach", sha],
            cwd=dest,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if checkout_proc.returncode != 0:
            raise RuntimeError(checkout_proc.stderr[-400:])
    else:
        checkout_proc = subprocess.run(
            ["git", "checkout", "--detach", "FETCH_HEAD"],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
        )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=dest,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != sha:
        raise RuntimeError(f"sha mismatch for {url}: {head} != {sha}")
    marker.write_text(sha + "\n", encoding="utf-8")
    return dest
