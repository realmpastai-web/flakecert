"""Pytest Attempt-to-Fix runner for the pinned cart sample.

Builds the image from inputs/rea-brief-pytest-attempt-to-fix/pins/Dockerfile,
searches with flakecert.search, and replays through flakecert.runner.run_schedule.
Writes audit/pytest-attempt-to-fix.json. Shape: gate_pytest_attempt_to_fix.py docstring.
"""

from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import flakecert.search as search_mod
from flakecert.cert import exception_type, failure_signature, normalize_traceback, schedule_dict
from flakecert.parse import extract_failure, match_node
from flakecert.plugin import write_support_files
from flakecert.runner import (
    Session,
    collect_in_image,
    image_id,
    pip_freeze,
    python_version,
    run_schedule,
)
from flakecert.search import search_test
from flakecert.sources import active_sources
from flakecert.util import freeze_sha, log, run_cmd, sha256_file

ROOT = Path(__file__).resolve().parents[2]
BRIEF = ROOT / "inputs" / "rea-brief-pytest-attempt-to-fix"
DOCKERFILE = BRIEF / "pins" / "Dockerfile"
SAMPLE = BRIEF / "sample"
SAMPLE_SHA = BRIEF / "sample.sha256"
FIXES = BRIEF / "fixes"
PRED_PATH = BRIEF / "expected" / "predicted-sweep.json"
AUDIT = ROOT / "audit"
OUT_PATH = AUDIT / "pytest-attempt-to-fix.json"
WORK = ROOT / ".cache" / "pytest-attempt-to-fix"
IMAGE_TAG = "flakecert-pytest-atf:pins"
SEARCH_TAG = "flakecert-pytest-atf:search"
TEST_ID = "P01"
VICTIM = "tests/test_cart.py::test_total_without_discount"
POLLUTER = "tests/test_cart.py::test_total_with_discount"
VARIANTS = ("prefix", "wrong_fix", "real_fix")
PLAIN_RUNS = 20
REPLAY_RUNS = 3
PYTEST_ARGS = ["-v", "--tb=short", "-p", "no:cacheprovider"]
JUNIT_PATH = "/tmp/fc-junit.xml"
REVERSED = ("pytest-randomly", "pytest-rerunfailures", "pytest_randomly", "pytest_rerunfailures")


def sh_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def _require(proc, what: str) -> str:
    text = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise SystemExit(f"{what} failed ({proc.returncode})\n{text[-4000:]}")
    return text


def pinned_base() -> str:
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("FROM "):
            image = line.split()[1]
            if "@sha256:" not in image:
                raise SystemExit(f"{DOCKERFILE} FROM line is not a pinned digest")
            return image
    raise SystemExit(f"{DOCKERFILE} has no FROM line")


def other_keys() -> list[str]:
    keys = []
    for line in SAMPLE_SHA.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        _digest, rel = line.split("  ", 1)
        if rel == "sample/tests/test_cart.py":
            continue
        if not rel.startswith("sample/"):
            raise SystemExit(f"sample.sha256 path is not under sample/: {rel}")
        keys.append(rel[len("sample/") :])
    if len(keys) != 5:
        raise SystemExit(f"sample.sha256 other files = {len(keys)}, want 5")
    return keys


def load_orders() -> dict[str, list[str]]:
    pred = json.loads(PRED_PATH.read_text(encoding="utf-8"))
    if pred.get("victim") != VICTIM or pred.get("polluter") != POLLUTER:
        raise SystemExit("predicted-sweep.json victim or polluter does not match the brief")
    orders = pred["orders"]
    keys = sorted(orders, key=lambda item: int(item))
    if keys != [str(seed) for seed in range(100)]:
        raise SystemExit(f"predicted orders keys are {keys[:5]}... not 0..99")
    return orders


def build_pins_image() -> str:
    log(f"docker build -f {DOCKERFILE} -t {IMAGE_TAG} {DOCKERFILE.parent}")
    proc = run_cmd(
        ["docker", "build", "-f", str(DOCKERFILE), "-t", IMAGE_TAG, str(DOCKERFILE.parent)],
        timeout=1800,
    )
    _require(proc, "docker build pins")
    digest = image_id(IMAGE_TAG)
    log(f"image_digest {digest}")
    return digest


def image_facts() -> tuple[str, str, list[str]]:
    version_proc = run_cmd(
        ["docker", "run", "--rm", "--network", "none", IMAGE_TAG, "python", "-V"],
        timeout=120,
    )
    py_banner = _require(version_proc, "python -V").strip()
    log(f"python -V {py_banner}")
    py = python_version(IMAGE_TAG)
    log(f"python {py}")
    freeze_text = pip_freeze(IMAGE_TAG)
    freeze = [line.strip() for line in freeze_text.splitlines() if line.strip()]
    log("pip freeze")
    for line in freeze:
        log(line)
    lowered = [line.lower() for line in freeze]
    if any(line.startswith(REVERSED) for line in lowered):
        raise SystemExit("reversed plugin is installed in the pins image")
    pytest_proc = run_cmd(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            IMAGE_TAG,
            "python",
            "-c",
            "import pytest; print(pytest.__version__)",
        ],
        timeout=120,
    )
    pytest_version = _require(pytest_proc, "pytest version").strip()
    log(f"pytest {pytest_version}")
    return py, pytest_version, freeze


def build_search_image() -> None:
    ctx = WORK / "search-context"
    if ctx.exists():
        shutil.rmtree(ctx)
    write_support_files(ctx)
    shutil.copytree(SAMPLE, ctx / "pristine")
    dockerfile = ctx / "Dockerfile"
    dockerfile.write_text(
        "\n".join(
            [
                f"FROM {IMAGE_TAG}",
                "COPY sitecustomize.py collect_nodes.py run_pytest.py /opt/flakecert/",
                "COPY pristine/ /opt/pristine/",
                "ENV PYTHONPATH=/opt/flakecert",
                "WORKDIR /",
                "",
            ]
        ),
        encoding="utf-8",
    )
    log(f"docker build -f {dockerfile} -t {SEARCH_TAG} {ctx}")
    proc = run_cmd(
        ["docker", "build", "-f", str(dockerfile), "-t", SEARCH_TAG, str(ctx)],
        timeout=600,
    )
    _require(proc, "docker build search")
    probe = run_cmd(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            SEARCH_TAG,
            "python",
            "-c",
            "import os; assert os.path.isfile('/opt/flakecert/run_pytest.py'); "
            "assert os.path.isfile('/opt/pristine/tests/test_cart.py'); "
            "assert os.path.isfile('/opt/pristine/app/cart.py')",
        ],
        timeout=120,
    )
    _require(probe, "search image layout")


def run_search(digest: str, python: str, freeze_text: str) -> dict:
    nodes, output = collect_in_image(
        SEARCH_TAG,
        ["-p", "no:cacheprovider", "tests/test_cart.py"],
        timeout=240,
    )
    node = match_node(VICTIM, nodes)
    if node != VICTIM:
        tail = "\n".join(output.splitlines()[-30:])
        raise SystemExit(f"collected node {node!r} from {nodes!r}\n{tail}")
    suite, _suite_out = collect_in_image(
        SEARCH_TAG,
        ["-p", "no:cacheprovider", "tests"],
        timeout=240,
    )
    log_dir = WORK / "flakecert-logs"
    cert_dir = WORK / "certs"
    log_dir.mkdir(parents=True, exist_ok=True)
    cert_dir.mkdir(parents=True, exist_ok=True)
    search_mod.FLAKECERT_LOGS = log_dir
    search_mod.CERTS = cert_dir
    meta = {
        "id": TEST_ID,
        "category": "OD-Vic",
        "project_url": "inputs/rea-brief-pytest-attempt-to-fix/sample",
        "sha": sha256_file(SAMPLE / "tests" / "test_cart.py"),
        "pytest_id": VICTIM,
        "node_id": VICTIM,
        "test_file": "tests/test_cart.py",
        "file_nodes": nodes,
        "suite_nodes": suite,
        "order_scope": "configured_suite" if suite else "test_file",
        "image_tag": SEARCH_TAG,
        "image_digest": digest,
        "pip_freeze_sha": freeze_sha(freeze_text),
        "python": python,
        "pytest_args": list(PYTEST_ARGS),
        "sources": active_sources(False),
        "thread_hits": [],
        "timeout_s": 120,
        "wall_s": 900,
    }
    log(f"search sources {meta['sources']} file_nodes {nodes}")
    cert = search_test(meta, budget=40, no_failure_cap=40)
    written = cert_dir / f"{TEST_ID}.json"
    if cert is None or not written.is_file():
        log_path = log_dir / f"{TEST_ID}.log"
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-4000:] if log_path.is_file() else ""
        raise SystemExit(f"pytest search did not certify {VICTIM}\n{tail}")
    stored = json.loads(written.read_text(encoding="utf-8"))
    schedule = schedule_dict(stored)
    log(f"cert schedule {json.dumps(schedule, sort_keys=True)}")
    log(f"cert expected_failure {json.dumps(stored.get('expected_failure'))}")
    return stored


def prepare_variants(variants_dir: Path) -> dict[str, dict]:
    if variants_dir.exists():
        shutil.rmtree(variants_dir)
    keys = other_keys()
    prepared: dict[str, dict] = {}
    for variant in VARIANTS:
        dest = variants_dir / variant
        shutil.copytree(SAMPLE, dest)
        shutil.copyfile(FIXES / f"test_cart.{variant}.py", dest / "tests" / "test_cart.py")
        cart_sha = sha256_file(dest / "tests" / "test_cart.py")
        fix_sha = sha256_file(FIXES / f"test_cart.{variant}.py")
        if cart_sha != fix_sha:
            raise SystemExit(f"{variant} test_cart copy {cart_sha} != fix {fix_sha}")
        others = {key: sha256_file(dest / key) for key in keys}
        prepared[variant] = {
            "test_cart_sha256": cart_sha,
            "sample_other_sha256": others,
        }
        log(f"variant {variant} test_cart_sha256 {cart_sha}")
    return prepared


def jobs_for(variant: str, orders: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    jobs = [(f"{variant}-plain-{index}", []) for index in range(1, PLAIN_RUNS + 1)]
    for seed in range(100):
        jobs.append((f"{variant}-sweep-{seed}", list(orders[str(seed)])))
    return jobs


def render_script(orders: dict[str, list[str]]) -> str:
    blocks = [
        "set -eu",
        "mkdir -p /out /work",
        "rm -f /out/FAIL",
        "chmod a+rwx /out",
        "MAX=$(nproc)",
        'if [ "$MAX" -gt 8 ]; then MAX=8; fi',
        "fifo=/tmp/fc-slots",
        'rm -f "$fifo"',
        'mkfifo "$fifo"',
        'exec 3<>"$fifo"',
        'for _slot in $(seq 1 "$MAX"); do',
        "  echo >&3",
        "done",
        "start_job() {",
        "  read -u 3",
        "  (",
        '    "$@" || true',
        "    echo >&3",
        "  ) &",
        "}",
        "run_one() {",
        '  local name="$1"',
        "  shift",
        '  local err="/out/${name}.log"',
        "  local rc=0",
        '  python -m pytest -p no:cacheprovider --junitxml="/out/${name}.xml" "$@" >"$err" 2>&1 || rc=$?',
        '  if [ "$rc" -gt 1 ] || [ ! -s "/out/${name}.xml" ]; then',
        '    echo "PYTEST_RUN_FAIL name=$name rc=$rc" >> /out/FAIL',
        '    cat "$err" >> /out/FAIL || true',
        "  fi",
        '  echo "done name=$name rc=$rc"',
        "}",
        "apply_variant() {",
        '  local variant="$1"',
        "  cd /",
        "  rm -rf /work",
        "  mkdir -p /work",
        '  cp -a "/variants/${variant}/." /work/',
        "  cd /work",
        "  sha256sum /work/tests/test_cart.py | awk '{print $1}' > \"/out/${variant}-test_cart.sha256\"",
        "}",
        "finish_variant() {",
        "  wait || true",
        "  if [ -s /out/FAIL ]; then",
        "    cat /out/FAIL >&2",
        "    exit 1",
        "  fi",
        "}",
    ]
    for variant in VARIANTS:
        blocks.append(f"echo APPLY {variant}")
        blocks.append(f"apply_variant {sh_quote(variant)}")
        for name, args in jobs_for(variant, orders):
            quoted = " ".join(sh_quote(part) for part in [name, *args])
            blocks.append(f"start_job run_one {quoted}")
        blocks.append("finish_variant")
        blocks.append(f"echo APPLIED_DONE {variant}")
    blocks.append("chmod -R a+rX /out")
    blocks.append("echo ATTEMPT_OK")
    return "\n".join(blocks) + "\n"


def run_plain_and_sweep(variants_dir: Path, orders: dict[str, list[str]]) -> Path:
    out_dir = WORK / "out"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    script_path = WORK / "run.sh"
    script_path.write_text(render_script(orders), encoding="utf-8")
    log(
        "docker run --rm --network none "
        f"-v {variants_dir}:/variants:ro -v {out_dir}:/out -v {script_path}:/run.sh:ro "
        f"{IMAGE_TAG} bash /run.sh"
    )
    proc = run_cmd(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "-v",
            f"{variants_dir}:/variants:ro",
            "-v",
            f"{out_dir}:/out",
            "-v",
            f"{script_path}:/run.sh:ro",
            IMAGE_TAG,
            "bash",
            "/run.sh",
        ],
        timeout=900,
    )
    if proc.stdout:
        log(proc.stdout.rstrip())
    if proc.returncode != 0:
        err = (proc.stderr or "")[-8000:]
        raise SystemExit(f"pytest attempt-to-fix batch failed ({proc.returncode})\n{err}")
    if "ATTEMPT_OK" not in (proc.stdout or ""):
        raise SystemExit("batch container finished without ATTEMPT_OK")
    return out_dir


def victim_traceback(output: str, node_id: str) -> str:
    """Failure text for the victim, without pytest's junit reporter footer.

    --junitxml prints ``generated xml file:`` between the failure and the
    short summary. extract_failure keeps that line, and it is not part of
    the traceback the certificate was signed from.
    """
    kept = []
    for line in output.splitlines(keepends=True):
        if "generated xml file:" in line:
            continue
        kept.append(line)
    return extract_failure("".join(kept), node_id)


def parse_junit(path: Path) -> dict[str, dict]:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise SystemExit(f"{path} is not junitxml: {exc}") from exc
    parsed: dict[str, dict] = {}
    for case in tree.iter("testcase"):
        classname = case.get("classname") or ""
        name = case.get("name") or ""
        node_id = classname.replace(".", "/") + ".py::" + name
        failure = case.find("failure")
        error = case.find("error")
        if failure is not None:
            status = "failed"
            element = failure
        elif error is not None:
            status = "error"
            element = error
        else:
            status = "passed"
            element = None
        message = element.get("message") if element is not None else None
        if node_id in parsed:
            raise SystemExit(f"{path} duplicate node {node_id}")
        parsed[node_id] = {"status": status, "message": message}
    return parsed


def _status(cases: dict[str, dict], node_id: str, path: Path) -> str:
    row = cases.get(node_id)
    if row is None:
        known = ", ".join(sorted(cases))
        raise SystemExit(f"{path} has no {node_id} (have {known})")
    return row["status"]


def replay_rows(cert: dict, variants_dir: Path) -> dict[str, list[dict]]:
    schedule = schedule_dict(cert)
    args = list(cert.get("pytest_args") or PYTEST_ARGS) + [f"--junitxml={JUNIT_PATH}"]
    rows: dict[str, list[dict]] = {}
    junit_dir = WORK / "replay-junit"
    junit_dir.mkdir(parents=True, exist_ok=True)
    with Session(cert["id"], cert["image_tag"]) as session:
        for variant in VARIANTS:
            src = variants_dir / variant / "tests" / "test_cart.py"
            copied = run_cmd(
                ["docker", "cp", str(src), f"{session.name}:/opt/pristine/tests/test_cart.py"],
                timeout=60,
            )
            _require(copied, f"docker cp {variant} test_cart.py")
            variant_rows = []
            for index in range(1, REPLAY_RUNS + 1):
                result = run_schedule(session, cert["node_id"], schedule, args, 120)
                local = junit_dir / f"{variant}-replay-{index}.xml"
                fetched = run_cmd(
                    ["docker", "cp", f"{session.name}:{JUNIT_PATH}", str(local)],
                    timeout=60,
                )
                _require(fetched, f"docker cp junit {variant} replay {index}")
                cases = parse_junit(local)
                victim = _status(cases, VICTIM, local)
                polluter = _status(cases, POLLUTER, local)
                if victim == "passed":
                    row = {
                        "victim": victim,
                        "polluter": polluter,
                        "exc": None,
                        "message": None,
                        "sig": None,
                        "tb_norm": None,
                    }
                else:
                    tb = victim_traceback(result.stdout, cert["node_id"])
                    exc = exception_type(tb)
                    sig = failure_signature(tb) or None
                    message = cases[VICTIM]["message"] or tb
                    row = {
                        "victim": victim,
                        "polluter": polluter,
                        "exc": exc,
                        "message": message,
                        "sig": sig,
                        "tb_norm": normalize_traceback(tb),
                    }
                    for line in tb.splitlines():
                        if "test_cart.py:" in line:
                            log(f"REPLAY_LOC variant={variant} index={index} {line}")
                            break
                variant_rows.append(row)
                log(
                    f"RUN variant={variant} arm=cert_replay index={index} "
                    f"victim={victim} polluter={polluter} exc={row['exc']} sig={row['sig']}"
                )
            rows[variant] = variant_rows
    return rows


def assemble(
    out_dir: Path,
    prepared: dict[str, dict],
    replays: dict[str, list[dict]],
    digest: str,
    python: str,
    pytest_version: str,
    freeze: list[str],
    cert: dict,
) -> dict:
    variants: dict[str, dict] = {}
    for variant in VARIANTS:
        in_image = (out_dir / f"{variant}-test_cart.sha256").read_text(encoding="utf-8").strip()
        if in_image != prepared[variant]["test_cart_sha256"]:
            raise SystemExit(
                f"{variant} in-image test_cart {in_image} != copied {prepared[variant]['test_cart_sha256']}"
            )
        plain = []
        for index in range(1, PLAIN_RUNS + 1):
            path = out_dir / f"{variant}-plain-{index}.xml"
            cases = parse_junit(path)
            victim = _status(cases, VICTIM, path)
            plain.append(victim)
            log(f"RUN variant={variant} arm=plain_retry index={index} victim={victim}")
        sweep: dict[str, dict[str, str]] = {}
        for seed in range(100):
            path = out_dir / f"{variant}-sweep-{seed}.xml"
            cases = parse_junit(path)
            victim = _status(cases, VICTIM, path)
            polluter = _status(cases, POLLUTER, path)
            sweep[str(seed)] = {"victim": victim, "polluter": polluter}
            log(
                f"RUN variant={variant} arm=sweep seed={seed} "
                f"victim={victim} polluter={polluter}"
            )
        variants[variant] = {
            "test_cart_sha256": prepared[variant]["test_cart_sha256"],
            "sample_other_sha256": prepared[variant]["sample_other_sha256"],
            "plain_retry": plain,
            "cert_replay": replays[variant],
            "sweep": sweep,
        }
    return {
        "pytest": pytest_version,
        "python": python,
        "base_image": pinned_base(),
        "image_digest": digest,
        "pip_freeze": freeze,
        "cert": cert,
        "variants": variants,
    }


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    base = pinned_base()
    log(f"base_image {base}")
    digest = build_pins_image()
    python, pytest_version, freeze = image_facts()
    freeze_text = "\n".join(freeze) + ("\n" if freeze else "")
    build_search_image()
    orders = load_orders()
    cert = run_search(digest, python, freeze_text)
    if cert.get("image_digest") != digest or cert.get("python") != python:
        raise SystemExit("certificate env identity does not match the pins image")
    variants_dir = WORK / "variants"
    prepared = prepare_variants(variants_dir)
    out_dir = run_plain_and_sweep(variants_dir, orders)
    replays = replay_rows(cert, variants_dir)
    document = assemble(out_dir, prepared, replays, digest, python, pytest_version, freeze, cert)
    AUDIT.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    log(f"wrote {OUT_PATH}")
    for variant in VARIANTS:
        victims = [row["victim"] for row in document["variants"][variant]["cert_replay"]]
        log(f"{variant} cert_replay victims {victims}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
