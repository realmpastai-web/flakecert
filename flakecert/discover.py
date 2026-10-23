"""Locate a pytest file and a rootdir config in a checkout."""

import re
from pathlib import Path

CONFIG_NAMES = ("pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg")
TESTPATHS_RE = re.compile(r"(?m)^\s*testpaths\s*=\s*(.+)$")


def resolve_test_file(root: Path, pytest_id: str) -> str:
    rel = pytest_id.split("::", 1)[0]
    if (root / rel).is_file():
        return rel
    base = Path(rel).name
    matches = []
    for path in root.rglob(base):
        if any(part in {".git", ".tox", ".venv", "site-packages"} for part in path.parts):
            continue
        if not path.is_file():
            continue
        posix = path.relative_to(root).as_posix()
        if posix.endswith(rel) or path.name == base:
            matches.append(posix)
    if not matches:
        return rel
    matches.sort(key=lambda item: (0 if item.endswith(rel) else 1, len(item)))
    return matches[0]


def _config_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def has_pytest_config(directory: Path) -> bool:
    if (directory / "pytest.ini").is_file():
        return True
    tox = directory / "tox.ini"
    if tox.is_file() and "[pytest]" in _config_text(tox):
        return True
    setup = directory / "setup.cfg"
    if setup.is_file():
        text = _config_text(setup)
        if "[tool:pytest]" in text or "[pytest]" in text:
            return True
    pyproject = directory / "pyproject.toml"
    if pyproject.is_file() and "[tool.pytest" in _config_text(pyproject):
        return True
    return False


def discover_rootdir(root: Path, test_file: str) -> str:
    current = (root / test_file).parent
    while True:
        if has_pytest_config(current):
            rel = current.relative_to(root).as_posix()
            return "." if rel == "" else rel
        if current == root:
            break
        current = current.parent
    return "."


def configured_testpaths(root: Path) -> list[str]:
    found = []
    for name in CONFIG_NAMES:
        path = root / name
        if not path.is_file():
            continue
        match = TESTPATHS_RE.search(_config_text(path))
        if not match:
            continue
        raw = match.group(1).strip().strip("\"'")
        for part in raw.replace(",", " ").split():
            if part and not part.startswith("#"):
                found.append(part)
    return found
