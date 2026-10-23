"""Locate frozen tarballs and extracted trees. Do not reinstall a healthy bundle."""

from __future__ import annotations

import hashlib
import re
import urllib.request
from pathlib import Path

from tools.certify_rspec.runner import docker_bash


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def commit_from_url(url: str) -> str:
    commit = url.rstrip("/").split("/")[-1]
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", commit):
        raise SystemExit(f"commit sha not found in url: {url}")
    return commit


def repo_from_url(url: str) -> str:
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/", url)
    if not match:
        raise SystemExit(f"repo not found in url: {url}")
    return f"{match.group(1)}/{match.group(2)}"


def find_tree(cache: Path, commit: str) -> Path | None:
    matches = []
    for path in cache.glob(f"extract-*/*-{commit}"):
        if (path / "Gemfile.lock").is_file():
            matches.append(path)
    if not matches:
        return None
    with_vendor = [path for path in matches if (path / "vendor" / "bundle").is_dir()]
    if with_vendor:
        return sorted(with_vendor)[0]
    return sorted(matches)[0]


def ensure_tarball(cache: Path, url: str, commit: str) -> tuple[Path, str]:
    dest_dir = cache / "tarballs"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{commit}.tar.gz"
    if not dest.is_file():
        urllib.request.urlretrieve(url, dest)
    return dest, sha256_file(dest)


def ensure_tree(cache: Path, tarball: Path, commit: str) -> Path:
    found = find_tree(cache, commit)
    if found is not None and (found / "Gemfile.lock").is_file():
        return found
    dest_root = cache / "src"
    dest_root.mkdir(parents=True, exist_ok=True)
    import tarfile

    with tarfile.open(tarball, "r:gz") as archive:
        archive.extractall(dest_root)
    found = find_tree(cache, commit)
    if found is None:
        # extractall landed under src/, which find_tree does not search.
        extracted = list(dest_root.glob(f"*-{commit}"))
        if not extracted:
            raise SystemExit(f"extract produced no tree for {commit}")
        return extracted[0]
    return found


def bundle_check(image: str, tree: Path, timeout: int = 180) -> tuple[int, str]:
    code, text, _elapsed = docker_bash(image, tree, "bundle _2.6.9_ check", timeout)
    return code, text
