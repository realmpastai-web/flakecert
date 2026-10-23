"""Re-run Hark's resolve-check and deps-preflight.

Logs contain a timestamp and, for resolve-check, a DeprecationWarning.
Comparison uses normalised result lines only.

The deps-preflight classifier implements a rule Hark states is
RECONSTRUCTED and verified against the frozen log, not the original
script. Source is api.github.com/repos/<repo>/git/trees/<sha>?recursive=1,
blobs only. A truncated recursive tree is an error; this module does not
walk the tree as a fallback. Manifests are root-level files only (no
'/'), taken from a fixed list in that list's order. Requirement files are
any depth: path.endswith('.txt') and 'requirements' in the full path
(case-sensitive), then sorted() and capped at 4. That cap is a display
limit of the preflight log only. Install selection does not use it.
"""

import ast
import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request

from flakecert.effective import load_frozen, slug
from flakecert.paths import EVIDENCE

RESOLVE_RE = re.compile(
    r"^(F\d+)\s+(main|reserve)\s+(\S+)\s+([0-9a-f]{10})\s+(\S+)\s+HTTP\s+(\d+)\b"
)
RESOLVED_RE = re.compile(r"^RESOLVED\s+(\d+)/(\d+)\s*$")
DEPS_RE = re.compile(
    r"^(F\d+)\s+(main|reserve)\s+(\S+)\s+manifests:\s+(\[[^\]]*\])\s+req files:\s+(\[[^\]]*\])\s*$"
)


def _headers() -> dict[str, str]:
    headers = {
        "User-Agent": "flakecert-poc",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch(url: str, timeout: int, read_all: bool) -> tuple[int, bytes]:
    """GET url. Retry timeouts and transient HTTP statuses. Return status and body."""
    request = urllib.request.Request(url, headers=_headers(), method="GET")
    delay = 2
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read() if read_all else response.read(64)
                return int(response.status), body
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 500, 502, 503, 504} and attempt < 3:
                last = exc
                print(f"preflight retry {attempt} HTTP {exc.code} {url}", flush=True)
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError, http.client.IncompleteRead) as exc:
            last = exc
            if attempt >= 3:
                break
            print(f"preflight retry {attempt} {url} {exc}", flush=True)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"preflight request failed {url}: {last}") from last


def http_status(url: str, timeout: int = 60) -> int:
    try:
        status, _body = _fetch(url, timeout, read_all=False)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    return status


def get_json(url: str, timeout: int = 180) -> dict:
    _status, body = _fetch(url, timeout, read_all=True)
    return json.loads(body.decode("utf-8"))


# Display limit of the preflight log only. Install selection does not use it.
REQ_DISPLAY_CAP = 4

MANIFEST_ORDER = (
    "requirements.txt",
    "requirements-dev.txt",
    "requirements_dev.txt",
    "setup.py",
    "setup.cfg",
    "pyproject.toml",
    "tox.ini",
    "pytest.ini",
    "environment.yml",
    "Pipfile",
)


def blob_paths_from_tree(data: dict, owner_repo: str, sha: str) -> list[str]:
    if "tree" not in data or data.get("truncated"):
        raise RuntimeError(
            f"git tree for {owner_repo}@{sha} is missing or truncated; refusing to walk"
        )
    return [item["path"] for item in data["tree"] if item.get("type") == "blob"]


def list_paths(owner_repo: str, sha: str) -> list[str]:
    url = f"https://api.github.com/repos/{owner_repo}/git/trees/{sha}?recursive=1"
    data = get_json(url)
    return blob_paths_from_tree(data, owner_repo, sha)


def classify_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    root = {path for path in paths if "/" not in path}
    manifests = [name for name in MANIFEST_ORDER if name in root]
    reqs = sorted(
        path for path in paths if path.endswith(".txt") and "requirements" in path
    )[:REQ_DISPLAY_CAP]
    return manifests, reqs


def normalise_resolve(text: str) -> tuple[list[tuple], tuple[int, int] | None]:
    rows = []
    resolved = None
    for line in text.splitlines():
        match = RESOLVE_RE.match(line.strip())
        if match:
            rows.append(tuple(match.groups()))
            continue
        done = RESOLVED_RE.match(line.strip())
        if done:
            resolved = (int(done.group(1)), int(done.group(2)))
    return rows, resolved


def normalise_deps(text: str) -> list[tuple]:
    rows = []
    for line in text.splitlines():
        match = DEPS_RE.match(line.strip())
        if not match:
            continue
        ident, role, repo, manifests, reqs = match.groups()
        rows.append(
            (
                ident,
                role,
                repo,
                tuple(ast.literal_eval(manifests)),
                tuple(ast.literal_eval(reqs)),
            )
        )
    return rows


def run_resolve(rows=None) -> str:
    rows = load_frozen() if rows is None else rows
    lines = []
    ok = 0
    for row in rows:
        repo = slug(row["project_url"])
        path = row["pytest_id"].split("::", 1)[0]
        url = f"https://raw.githubusercontent.com/{repo}/{row['sha']}/{path}"
        print(f"resolve {row['id']}", flush=True)
        status = http_status(url)
        if status == 200:
            ok += 1
            label = "OK"
        else:
            label = "FAIL"
        lines.append(
            f"{row['id']} {row['role']} {repo} {row['sha'][:10]} {path} HTTP {status} {label}"
        )
    lines.append(f"RESOLVED {ok}/{len(rows)}")
    return "\n".join(lines) + "\n"


def run_deps(rows=None) -> str:
    rows = load_frozen() if rows is None else rows
    lines = [
        "run rerun source: api.github.com/repos/<repo>/git/trees/<sha>?recursive=1"
    ]
    for row in rows:
        repo = slug(row["project_url"])
        print(f"deps {row['id']}", flush=True)
        paths = list_paths(repo, row["sha"])
        manifests, reqs = classify_paths(paths)
        lines.append(
            f"{row['id']} {row['role']} {repo} manifests: {manifests!r} req files: {reqs!r} "
        )
    return "\n".join(lines) + "\n"


def committed_resolve() -> str:
    return (EVIDENCE / "resolve-check.log").read_text(encoding="utf-8")


def committed_deps() -> str:
    return (EVIDENCE / "deps-preflight.log").read_text(encoding="utf-8")


def compare_resolve(rerun: str, committed: str | None = None) -> tuple[bool, str]:
    committed = committed_resolve() if committed is None else committed
    got_rows, got_res = normalise_resolve(rerun)
    exp_rows, exp_res = normalise_resolve(committed)
    if got_rows != exp_rows or got_res != exp_res:
        return False, f"resolve mismatch rows={got_rows == exp_rows} resolved={got_res} expected={exp_res}"
    return True, f"RESOLVED {got_res[0]}/{got_res[1]}"


def compare_deps(rerun: str, committed: str | None = None) -> tuple[bool, str]:
    committed = committed_deps() if committed is None else committed
    got = normalise_deps(rerun)
    exp = normalise_deps(committed)
    if got != exp:
        diffs = []
        got_map = {item[0]: item for item in got}
        exp_map = {item[0]: item for item in exp}
        for ident in sorted(set(got_map) | set(exp_map)):
            if got_map.get(ident) != exp_map.get(ident):
                diffs.append(ident)
        return False, "deps mismatch " + ",".join(diffs[:12])
    return True, f"deps {len(got)} rows"
