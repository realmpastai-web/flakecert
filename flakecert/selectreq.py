"""Choose install inputs. The GitHub preflight lists every requirements path;
installation uses the narrower set from the delta.
"""

from pathlib import Path


def install_requirements(root: Path) -> list[Path]:
    chosen = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        name = path.name
        lower = name.lower()
        if "requirements" not in lower or not lower.endswith(".txt"):
            continue
        if any(token in lower for token in ("docs", "release", "tunnel")):
            continue
        chosen.append(path)
    tests_req = root / "tests" / "requirements.txt"
    if tests_req.is_file() and tests_req not in chosen:
        chosen.append(tests_req)
    return chosen


def use_pipenv(root: Path, reqs: list[Path]) -> bool:
    return not reqs and (root / "Pipfile").is_file()


def has_package(root: Path) -> bool:
    return any((root / name).is_file() for name in ("setup.py", "setup.cfg", "pyproject.toml"))
