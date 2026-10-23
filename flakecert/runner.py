"""Run pytest inside a fresh Docker netns with loopback up.

Build happens online. Every test command uses --network none and
`ip link set lo up` because unshare -n (and some netns setups) leave lo down.
"""

import os
import time
import uuid
from dataclasses import dataclass, field

from flakecert.parse import interpret
from flakecert.sources import (
    SOURCE_HASH,
    SOURCE_ORDER,
    SOURCE_SEED,
    SOURCE_SWITCH,
    SOURCE_TIME,
    SOURCE_TMP,
)
from flakecert.util import log, run_cmd

PYTEST_SCRIPT = r"""
set +e
echo "FLAKECERT_NETNS_BEGIN"
ip link set lo up
echo "lo_set=$?"
ip -o link show lo || true
ip -o addr show || true
echo "FLAKECERT_ROUTE_BEGIN"
ip route || true
echo "FLAKECERT_ROUTE_END"
echo "FLAKECERT_NETNS_END"
rm -rf /work
mkdir -p /work
cp -a /opt/pristine/. /work/ || exit 96
cd /work || exit 97
if [ -n "${FLAKECERT_TMPDIR:-}" ]; then
  case "$FLAKECERT_TMPDIR" in
    /*) tmp="$FLAKECERT_TMPDIR" ;;
    *) tmp="/tmp/$FLAKECERT_TMPDIR" ;;
  esac
else
  tmp="/tmp/fc-run"
fi
rm -rf "$tmp"
mkdir -p "$tmp"
export TMPDIR="$tmp" TMP="$tmp" TEMP="$tmp"
export PYTHONPATH="/opt/flakecert${PYTHONPATH:+:$PYTHONPATH}"
export PY_COLORS=0
export TERM=dumb
# /work is recopied from /opt/pristine, but pip installs live in the
# interpreter prefix. A test that uninstalls its own package (F08
# test_package_uninstall) deletes the console script for every later
# invocation in this container. Snapshot the prefix once, then put those
# files back before pytest. Hardlinks keep the restore cheap; files pip
# replaced are unlinked here and linked from the snapshot again.
python - << 'PY' || exit 97
import os
import shutil
import sysconfig

def _link(src, dst):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)

def snapshot(src, dst):
    if os.path.exists(dst):
        return
    parent = os.path.dirname(dst)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    shutil.copytree(src, dst, copy_function=_link)

def restore(src, dst):
    if not os.path.isdir(src):
        return
    if not os.path.isdir(dst):
        os.makedirs(dst)
    keep = set()
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        dest_root = dst if rel == "." else os.path.join(dst, rel)
        if not os.path.isdir(dest_root):
            os.makedirs(dest_root)
        for name in files:
            s = os.path.join(root, name)
            d = os.path.join(dest_root, name)
            keep.add(os.path.normpath(d))
            try:
                same = os.path.isfile(d) and os.path.samefile(s, d)
            except OSError:
                same = False
            if same:
                continue
            if os.path.lexists(d):
                os.remove(d)
            _link(s, d)
    for root, dirs, files in os.walk(dst, topdown=False):
        for name in files:
            path = os.path.normpath(os.path.join(root, name))
            if path not in keep:
                try:
                    os.remove(path)
                except OSError:
                    pass
        for name in dirs:
            path = os.path.join(root, name)
            try:
                os.rmdir(path)
            except OSError:
                pass

snap = "/opt/fc-py-snap"
os.makedirs(snap, exist_ok=True)
purelib = sysconfig.get_path("purelib")
scripts = sysconfig.get_path("scripts")
snapshot(purelib, os.path.join(snap, "purelib"))
snapshot(scripts, os.path.join(snap, "scripts"))
restore(os.path.join(snap, "purelib"), purelib)
restore(os.path.join(snap, "scripts"), scripts)
PY
echo "FLAKECERT_ENV_RESTORE=1"
# Offline netns: pip build isolation tries to download setuptools and a
# local `pip install -e` fails after the package was uninstalled. pip's
# ConfigOptionParser assigns strtobool(value) to dest build_isolation, so
# the setting that turns isolation off is `no-build-isolation = false`.
# The image already contains the build tools.
mkdir -p /opt/flakecert
cat > /opt/flakecert/pip-offline.conf << 'EOF'
[install]
no-build-isolation = false
EOF
export PIP_CONFIG_FILE=/opt/flakecert/pip-offline.conf
echo "FLAKECERT_PIP_BUILD_ISOLATION=off"
timeout --signal=TERM --kill-after=10 "${FLAKECERT_TIMEOUT:-180}" python /opt/flakecert/run_pytest.py "$@"
rc=$?
echo "FLAKECERT_PYTEST_RC=${rc}"
exit 0
"""

COLLECT_SCRIPT = r"""
set +e
ip link set lo up
echo "lo_set=$?"
rm -rf /work
mkdir -p /work
cp -a /opt/pristine/. /work/ || exit 96
cd /work || exit 97
rm -f /tmp/fc-nodes.txt
python /opt/flakecert/collect_nodes.py "$@"
echo "COLLECT_FILE_BEGIN"
cat /tmp/fc-nodes.txt 2>/dev/null || true
echo "COLLECT_FILE_END"
exit 0
"""


@dataclass
class RunResult:
    outcome: str
    exc: str
    sig: str
    node_id: str
    duration_s: float
    stdout: str
    traceback: str
    command: str
    lo_ok: bool
    pytest_rc: int | None = None
    extra: dict = field(default_factory=dict)


def cleanup_our_containers() -> None:
    proc = run_cmd(["docker", "ps", "-aq", "--filter", "name=^flakecert-"])
    names = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    if not names:
        return
    run_cmd(["docker", "rm", "-f", *names], timeout=120)
    log(f"removed {len(names)} flakecert containers")


def _lo_ok(output: str) -> bool:
    if "lo_set=0" not in output:
        return False
    # A default route would mean the netns is not offline.
    route = ""
    if "FLAKECERT_ROUTE_BEGIN" in output and "FLAKECERT_ROUTE_END" in output:
        route = output.split("FLAKECERT_ROUTE_BEGIN", 1)[1].split("FLAKECERT_ROUTE_END", 1)[0]
    for line in route.splitlines():
        if line.strip().startswith("default"):
            return False
    return True


def _pytest_rc(output: str) -> int | None:
    for line in output.splitlines():
        if line.startswith("FLAKECERT_PYTEST_RC="):
            try:
                return int(line.split("=", 1)[1].strip())
            except ValueError:
                return None
    return None


def image_id(tag: str) -> str:
    proc = run_cmd(["docker", "image", "inspect", "--format", "{{.Id}}", tag], timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"missing image {tag}")
    return proc.stdout.strip()


def pip_freeze(tag: str) -> str:
    proc = run_cmd(
        ["docker", "run", "--rm", "--network", "none", tag, "python", "-m", "pip", "freeze"],
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-400:])
    return proc.stdout


def python_version(tag: str) -> str:
    proc = run_cmd(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            tag,
            "python",
            "-c",
            'import sys; print("%d.%d.%d" % sys.version_info[:3])',
        ],
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-400:])
    return proc.stdout.strip()


class Session:
    def __init__(self, test_id: str, image_tag: str, memory: str = "1536m"):
        self.test_id = test_id
        self.image_tag = image_tag
        self.memory = memory
        self.name = f"flakecert-{test_id}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.started = False

    def start(self) -> None:
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            self.name,
            "--network",
            "none",
            "--cap-add",
            "NET_ADMIN",
            "--label",
            "flakecert=1",
            "--memory",
            self.memory,
            "--cpus",
            "1.5",
            self.image_tag,
            "sleep",
            "infinity",
        ]
        proc = run_cmd(cmd, timeout=120)
        if proc.returncode != 0:
            # Retry without resource flags if this docker rejects them.
            cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                self.name,
                "--network",
                "none",
                "--cap-add",
                "NET_ADMIN",
                "--label",
                "flakecert=1",
                self.image_tag,
                "sleep",
                "infinity",
            ]
            proc = run_cmd(cmd, timeout=120)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr[-500:] or proc.stdout[-500:])
        self.started = True

    def stop(self) -> None:
        if self.started:
            run_cmd(["docker", "rm", "-f", self.name], timeout=60)
            self.started = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False

    def bash(self, script: str, args: list[str], env: dict, timeout: int) -> tuple[int, str]:
        cmd = ["docker", "exec", "-i"]
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])
        cmd.extend([self.name, "bash", "-s", "--", *args])
        proc = run_cmd(cmd, timeout=timeout + 30, input_text=script)
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output


def schedule_env(schedule: dict, timeout_s: int) -> dict[str, str]:
    env = {"FLAKECERT_TIMEOUT": str(timeout_s)}
    seed = str(schedule.get(SOURCE_SEED, "") or "")
    if seed != "":
        env["FLAKECERT_SEED"] = seed
    pyhash = str(schedule.get(SOURCE_HASH, "") or "")
    if pyhash != "":
        env["PYTHONHASHSEED"] = pyhash
    offset = str(schedule.get(SOURCE_TIME, "") or "")
    if offset != "":
        env["FLAKECERT_TIME_OFFSET"] = offset
    tmp = str(schedule.get(SOURCE_TMP, "") or "")
    if tmp != "":
        env["FLAKECERT_TMPDIR"] = tmp
    switch = str(schedule.get(SOURCE_SWITCH, "") or "")
    if switch != "":
        env["FLAKECERT_SWITCH_INTERVAL"] = switch
    return env


def pytest_args_for(schedule: dict, base_args: list[str]) -> list[str]:
    order = schedule.get(SOURCE_ORDER) or []
    if isinstance(order, str):
        order = [order]
    return list(base_args) + [str(item) for item in order]


def run_schedule(
    session: Session,
    node_id: str,
    schedule: dict,
    base_args: list[str],
    timeout_s: int,
) -> RunResult:
    args = pytest_args_for(schedule, base_args)
    env = schedule_env(schedule, timeout_s)
    started = time.time()
    try:
        rc, output = session.bash(PYTEST_SCRIPT, args, env, timeout_s)
    except Exception as exc:
        return RunResult(
            outcome="harness_error",
            exc=type(exc).__name__,
            sig="-",
            node_id=node_id,
            duration_s=time.time() - started,
            stdout=str(exc),
            traceback="",
            command="docker exec --network none ip link set lo up",
            lo_ok=False,
        )
    duration = time.time() - started
    parsed = interpret(output, node_id, _pytest_rc(output))
    if parsed["outcome"] == "missing" and (rc == 124 or _pytest_rc(output) == 124):
        parsed["outcome"] = "timeout"
    elif rc != 0 and parsed["outcome"] == "missing":
        parsed["outcome"] = "harness_error"
    return RunResult(
        outcome=parsed["outcome"],
        exc=parsed["exc"],
        sig=parsed["sig"],
        node_id=node_id,
        duration_s=duration,
        stdout=output,
        traceback=parsed["traceback"],
        command="docker exec --network none ; ip link set lo up ; python /opt/flakecert/run_pytest.py",
        lo_ok=_lo_ok(output),
        pytest_rc=_pytest_rc(output),
    )


def oneshot(image: str, script: str, args: list[str], timeout: int = 180) -> tuple[int, str]:
    cmd = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--network",
        "none",
        "--cap-add",
        "NET_ADMIN",
        image,
        "bash",
        "-s",
        "--",
        *args,
    ]
    proc = run_cmd(cmd, timeout=timeout, input_text=script)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def collect_in_image(image: str, pytest_args: list[str], timeout: int = 240) -> tuple[list[str], str]:
    from flakecert.parse import parse_nodeids

    _rc, output = oneshot(image, COLLECT_SCRIPT, pytest_args, timeout=timeout)
    return parse_nodeids(output), output
