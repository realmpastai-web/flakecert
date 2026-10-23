"""Interpreter ladder and per-test images.

One full ladder (3.11, 3.9, 3.8, 3.7) is one install attempt. The auto-swap
rule fires only after two failed ladders of the same installer logic.
"""

import json
import os
import re
import shutil
import threading
from pathlib import Path

from flakecert.paths import (
    CACHE,
    ENVS,
    PY_IMAGES,
    PY_LADDER,
    PY_SUITES,
)
from flakecert.plugin import write_support_files
from flakecert.selectreq import has_package, install_requirements, use_pipenv
from flakecert.util import chmod_writable, freeze_sha, log, run_cmd
from flakecert.vcs import checkout

INSTALL_LOGIC_VERSION = "4"
_ATTEMPT_LOCK = threading.Lock()
PIN_RE = re.compile(r"pytest\s*==\s*([0-9][0-9A-Za-z.\-]*)")
BINARY_ONLY = "numpy,scipy,pandas,matplotlib,Pillow"

INSTALL_TEMPLATE = r"""#!/bin/bash
cd /opt/pristine || exit 1
python -c 'import sys; print("FLAKECERT_INSTALL python %d.%d.%d" % sys.version_info[:3])'
echo "FLAKECERT_INSTALL files @@FILES@@"
echo "FLAKECERT_INSTALL pipenv @@PIPENV@@"
echo "FLAKECERT_INSTALL package @@PACKAGE@@"
REQS_COMPLETE=yes

if python -c 'import sys; raise SystemExit(0 if sys.version_info < (3, 10) else 1)'; then
  python -m pip install -U 'pip<24.1' 'setuptools<58' 'wheel<0.38' \
    || python -m pip install -U 'pip<21' 'setuptools<47' 'wheel'
else
  python -m pip install -U pip setuptools wheel
fi

sanitize() {
  python - "$1" "$2" << 'PY'
import pathlib, sys
src, dst = sys.argv[1], sys.argv[2]
out = []
for raw in pathlib.Path(src).read_text(errors="replace").splitlines():
    if "#" in raw:
        raw = raw.split("#", 1)[0]
    line = raw.strip()
    if not line:
        continue
    line = line.replace("~>", "~=").replace("~= ", "~=")
    out.append(line)
pathlib.Path(dst).write_text("\n".join(out) + ("\n" if out else ""))
PY
}

install_req() {
  local f="$1"
  echo "FLAKECERT_INSTALL req $f"
  sanitize "$f" /tmp/fc-req.txt || cp "$f" /tmp/fc-req.txt
  if timeout 600 python -m pip install --prefer-binary --only-binary=@@BINARY@@ -r /tmp/fc-req.txt; then
    echo "FLAKECERT_INSTALL req_ok $f"
    return 0
  fi
  echo "FLAKECERT_INSTALL req_fail_full $f"
  REQS_COMPLETE=no
  # A long file that fails as a unit is not salvaged line-by-line: that path
  # reinstalls every pin and the rung is already ineligible.
  if [ "$(grep -cve '^[[:space:]]*$' /tmp/fc-req.txt)" -gt 40 ]; then
    echo "FLAKECERT_INSTALL skip_line_by_line $f"
    return 0
  fi
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in
      -r\ *|--requirement\ *)
        echo "FLAKECERT_INSTALL include $line"
        timeout 600 python -m pip install --prefer-binary --only-binary=@@BINARY@@ $line \
          && echo "FLAKECERT_INSTALL line_ok $line" \
          || echo "FLAKECERT_INSTALL line_fail $line"
        ;;
      -*)
        echo "FLAKECERT_INSTALL skip_option $line"
        ;;
      *)
        timeout 300 python -m pip install --prefer-binary --only-binary=@@BINARY@@ "$line" \
          && echo "FLAKECERT_INSTALL line_ok $line" \
          || echo "FLAKECERT_INSTALL line_fail $line"
        ;;
    esac
  done < /tmp/fc-req.txt
}

@@REQ_BLOCK@@

if [ "@@PIPENV@@" = "yes" ]; then
  echo "FLAKECERT_INSTALL pipenv_begin"
  python -m pip install 'pipenv>=2022.1.8,<2023.10' \
    || python -m pip install 'pipenv==2022.1.8' \
    || python -m pip install pipenv
  if timeout 300 pipenv requirements --dev > /tmp/pipenv-dev.txt; then
    echo "FLAKECERT_INSTALL pipenv_requirements_ok"
    install_req /tmp/pipenv-dev.txt
  elif timeout 300 pipenv lock -r --dev > /tmp/pipenv-dev.txt; then
    echo "FLAKECERT_INSTALL pipenv_lock_ok"
    install_req /tmp/pipenv-dev.txt
  else
    echo "FLAKECERT_INSTALL pipenv_requirements_fail"
    PIPENV_NOSPIN=1 PIPENV_IGNORE_VIRTUALENVS=1 \
      timeout 600 pipenv install --system --dev --skip-lock \
      || timeout 600 pipenv install --system --dev \
      || echo "FLAKECERT_INSTALL pipenv_install_fail"
  fi
fi

if [ "@@PACKAGE@@" = "yes" ]; then
  echo "FLAKECERT_INSTALL package_begin"
  if [ "@@HASREQ@@" = "no" ]; then
    if timeout 600 python -m pip install --no-build-isolation /opt/pristine; then
      echo "FLAKECERT_INSTALL package_ok with-deps-no-isolation"
    elif timeout 600 python -m pip install /opt/pristine; then
      echo "FLAKECERT_INSTALL package_ok with-deps"
    elif timeout 600 python -m pip install --no-use-pep517 /opt/pristine; then
      echo "FLAKECERT_INSTALL package_ok no-pep517"
    else
      echo "FLAKECERT_INSTALL package_fail"
    fi
  elif timeout 600 python -m pip install --no-deps --no-build-isolation /opt/pristine; then
    echo "FLAKECERT_INSTALL package_ok no-deps-no-isolation"
  elif timeout 600 python -m pip install --no-deps /opt/pristine; then
    echo "FLAKECERT_INSTALL package_ok no-deps"
  elif timeout 600 python -m pip install --no-deps --no-use-pep517 /opt/pristine; then
    echo "FLAKECERT_INSTALL package_ok no-deps-no-pep517"
  elif timeout 600 python -m pip install /opt/pristine; then
    echo "FLAKECERT_INSTALL package_ok with-deps"
  elif timeout 600 python -m pip install --no-use-pep517 /opt/pristine; then
    echo "FLAKECERT_INSTALL package_ok no-pep517"
  else
    echo "FLAKECERT_INSTALL package_fail"
  fi
fi

if python -m pip show paramiko >/dev/null 2>&1; then
  if ! python -c 'import six' >/dev/null 2>&1; then
    echo "FLAKECERT_INSTALL repair six"
    python -m pip install --prefer-binary 'six==1.16.0' || true
  fi
fi

@@PYTEST_PIN@@

echo "FLAKECERT_INSTALL reqs_complete ${REQS_COMPLETE}"

if ! python -c 'import pytest' >/dev/null 2>&1; then
  echo "FLAKECERT_INSTALL pytest_import_fail"
  exit 1
fi
python -c 'import pytest; print("FLAKECERT_INSTALL pytest_version " + pytest.__version__)'
exit 0
"""


def find_pytest_pin(root: Path, reqs: list[Path]) -> str | None:
    ordered = list(reqs)
    for name in ("tox.ini", "setup.py", "setup.cfg", "pyproject.toml", "pytest.ini"):
        path = root / name
        if path.is_file():
            ordered.append(path)
    for path in ordered:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = PIN_RE.search(text)
        if match:
            return match.group(1)
    return None


def render_install_sh(root: Path) -> tuple[str, list[str]]:
    reqs = install_requirements(root)
    rels = [str(path.relative_to(root)).replace("\\", "/") for path in reqs]
    pipenv = "yes" if use_pipenv(root, reqs) else "no"
    package = "yes" if has_package(root) else "no"
    if rels:
        block = "\n".join(f'install_req "/opt/pristine/{rel}"' for rel in rels)
    else:
        block = 'echo "FLAKECERT_INSTALL no_requirements"'
    pin = find_pytest_pin(root, reqs)
    if pin:
        # pytest 3.x/4.x call attr.ib(convert=...), removed in attrs 19.2.
        attrs_pin = ""
        if pin.startswith(("3.", "4.")):
            attrs_pin = (
                "  python -m pip install --prefer-binary 'attrs>=17.4.0,<19.2.0' || true\n"
            )
        pin_block = (
            "if ! python -c 'import pytest' >/dev/null 2>&1; then\n"
            f'  echo "FLAKECERT_INSTALL pytest_pin {pin}"\n'
            f"{attrs_pin}"
            f'  python -m pip install --prefer-binary "pytest=={pin}" || true\n'
            "fi"
        )
    else:
        pin_block = """echo "FLAKECERT_INSTALL pytest_pin none"
if ! python -c 'import pytest' >/dev/null 2>&1; then
  echo "FLAKECERT_INSTALL pytest_fallback"
  if python -c 'import sys; raise SystemExit(0 if sys.version_info < (3, 8) else 1)'; then
    python -m pip install --prefer-binary 'pytest==7.4.4' \\
      || python -m pip install --prefer-binary 'pytest==6.2.5' \\
      || python -m pip install --prefer-binary 'pytest==4.6.11'
  else
    python -m pip install --prefer-binary 'pytest==7.4.4' \\
      || python -m pip install --prefer-binary 'pytest==8.3.5' \\
      || python -m pip install --prefer-binary 'pytest==6.2.5'
  fi
fi"""
    script = (
        INSTALL_TEMPLATE.replace("@@FILES@@", ",".join(rels) if rels else "none")
        .replace("@@PIPENV@@", pipenv)
        .replace("@@PACKAGE@@", package)
        .replace("@@HASREQ@@", "yes" if rels else "no")
        .replace("@@BINARY@@", BINARY_ONLY)
        .replace("@@REQ_BLOCK@@", block)
        .replace("@@PYTEST_PIN@@", pin_block)
    )
    return script, rels


def _ignore_copy(directory, names):
    skip = {
        ".git",
        "__pycache__",
        ".tox",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        ".hg",
        ".svn",
    }
    return [name for name in names if name in skip]


def prepare_context(test_id: str, source: Path, script: str) -> Path:
    ctx = CACHE / "context" / test_id
    if ctx.exists():
        shutil.rmtree(ctx)
    ctx.mkdir(parents=True)
    shutil.copytree(source, ctx / "src", ignore=_ignore_copy, dirs_exist_ok=True)
    write_support_files(ctx)
    (ctx / "install.sh").write_text(script, encoding="utf-8")
    (ctx / ".dockerignore").write_text(
        "src/.git\n**/__pycache__\n**/*.pyc\n**/.tox\n**/.venv\n",
        encoding="utf-8",
    )
    return ctx


def dockerfile_text(py: str, test_id: str) -> str:
    return (
        f"# flakecert image for {test_id} on Python {py}\n"
        f"# ladder: {' '.join(PY_LADDER)}\n"
        f"FROM flakecert-base:{py}\n"
        "COPY sitecustomize.py collect_nodes.py run_pytest.py /opt/flakecert/\n"
        "COPY install.sh /tmp/install.sh\n"
        "COPY src/ /opt/pristine/\n"
        "RUN bash /tmp/install.sh\n"
        "ENV PYTHONPATH=/opt/flakecert\n"
        "WORKDIR /\n"
    )


def build_base_images() -> None:
    ENVS.mkdir(parents=True, exist_ok=True)
    for py in PY_LADDER:
        tag = f"flakecert-base:{py}"
        if os.environ.get("FLAKECERT_REBUILD_BASE") != "1":
            probe = run_cmd(["docker", "image", "inspect", tag], timeout=30)
            if probe.returncode == 0:
                log(f"base {tag} present")
                continue
        log(f"base {tag} from {PY_IMAGES[py]}")
        cmd = [
            "docker",
            "build",
            "--progress=plain",
            "-f",
            str(ENVS / "Dockerfile.base"),
            "--build-arg",
            f"PY_IMAGE={PY_IMAGES[py]}",
            "--build-arg",
            f"DEBIAN_SUITE={PY_SUITES[py]}",
            "-t",
            tag,
            str(ENVS),
        ]
        env = os.environ.copy()
        env["DOCKER_BUILDKIT"] = "1"
        proc = run_cmd(cmd, timeout=1800, env=env)
        log_path = CACHE / "build" / f"base-{py}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-800:]
            raise RuntimeError(f"base image {py} failed: {tail}")


def _attempts_path() -> Path:
    return CACHE / "attempts.json"


def attempt_count(test_id: str) -> int:
    path = _attempts_path()
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    item = data.get(test_id) or {}
    if item.get("logic") != INSTALL_LOGIC_VERSION:
        return 0
    return int(item.get("count") or 0)


def bump_attempt(test_id: str) -> int:
    path = _attempts_path()
    with _ATTEMPT_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        item = data.get(test_id) or {}
        count = int(item.get("count") or 0) if item.get("logic") == INSTALL_LOGIC_VERSION else 0
        count += 1
        data[test_id] = {"logic": INSTALL_LOGIC_VERSION, "count": count}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return count


def concise_log(full: str) -> str:
    kept = []
    for line in full.splitlines():
        if "FLAKECERT_INSTALL" in line or line.startswith("rung ") or line.startswith("collect "):
            kept.append(line)
    if not kept:
        kept = full.splitlines()[-40:]
    return "\n".join(kept).rstrip() + "\n"


def build_rung(test_id: str, py: str, ctx: Path) -> tuple[int, str]:
    dockerfile = ENVS / f"Dockerfile.{test_id}"
    chmod_writable(dockerfile)
    dockerfile.write_text(dockerfile_text(py, test_id), encoding="utf-8")
    tag = f"flakecert:{test_id}"
    cmd = [
        "docker",
        "build",
        "--progress=plain",
        "-f",
        str(dockerfile),
        "-t",
        tag,
        str(ctx),
    ]
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"
    proc = run_cmd(cmd, timeout=1200, env=env)
    full = (proc.stdout or "") + "\n" + (proc.stderr or "")
    out_path = CACHE / "build" / f"{test_id}-{py}.log"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full, encoding="utf-8")
    return proc.returncode, full


def docker_python(tag: str, args: list[str], timeout: int = 180) -> tuple[int, str]:
    cmd = ["docker", "run", "--rm", "--network", "none", tag, "python", *args]
    proc = run_cmd(cmd, timeout=timeout)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def protect_frozen_set() -> None:
    from flakecert.paths import FROZEN_CSV

    if FROZEN_CSV.exists():
        os.chmod(FROZEN_CSV, 0o444)
