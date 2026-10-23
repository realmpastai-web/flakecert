"""Attempt-to-Fix runner for the pinned RSpec cart sample.

Reuses flakecert.runners.rspec (image, lock, argv, JSON parse, failure signature).
Writes audit/rspec-attempt-to-fix.json. Shape: gate_attempt_to_fix.py docstring.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from flakecert.runners.rspec import (
    AUDIT,
    CERT_PATH,
    IMAGE_TAG,
    LOCK_PATH,
    POLLUTER,
    ROOT,
    SRAND_LINE,
    SRAND_PATH,
    VICTIM,
    _failure_of,
    _read_json,
    _require_ids,
    base_digest,
    baseline_argv,
    build_image,
    parse_examples,
    rspec_argv,
)
from flakecert.util import log, run_cmd, sha256_file

OUT_PATH = AUDIT / "rspec-attempt-to-fix.json"
SAMPLE = ROOT / "inputs" / "flakecert-rspec-runner" / "sample"
SAMPLE_SHA = ROOT / "inputs" / "flakecert-rspec-runner" / "sample.sha256"
FIXES = ROOT / "inputs" / "flakecert-attempt-to-fix" / "fixes"
WORK = ROOT / ".cache" / "rspec-attempt-to-fix"
VARIANTS = ("prefix", "wrong_fix", "real_fix")
PLAIN_RUNS = 20
REPLAY_RUNS = 3
SWEEP_SEEDS = range(100)


def sh_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def sample_other_expected() -> dict[str, str]:
    expected: dict[str, str] = {}
    for line in SAMPLE_SHA.read_text(encoding="utf-8").splitlines():
        if not line or line.endswith("spec/models/cart_spec.rb"):
            continue
        digest, rel = line.split("  ", 1)
        expected[rel] = digest
    if len(expected) != 7:
        raise SystemExit(f"sample.sha256 other files = {len(expected)}, want 7")
    return expected


def prepare_variants(variants_dir: Path) -> dict[str, dict]:
    """Copy the frozen sample and replace cart_spec.rb for each variant."""
    if variants_dir.exists():
        shutil.rmtree(variants_dir)
    expected_other = sample_other_expected()
    prepared: dict[str, dict] = {}
    for variant in VARIANTS:
        dest = variants_dir / variant
        shutil.copytree(SAMPLE, dest)
        spec_name = f"cart_spec.{variant}.rb"
        shutil.copyfile(FIXES / spec_name, dest / "spec" / "models" / "cart_spec.rb")
        others = {rel: sha256_file(dest / rel) for rel in expected_other}
        if others != expected_other:
            raise SystemExit(f"{variant} sample files other than cart_spec.rb changed")
        cart_sha = sha256_file(dest / "spec" / "models" / "cart_spec.rb")
        fix_sha = sha256_file(FIXES / spec_name)
        if cart_sha != fix_sha:
            raise SystemExit(f"{variant} cart_spec copy {cart_sha} != fix {fix_sha}")
        prepared[variant] = {
            "cart_spec_sha256": cart_sha,
            "sample_other_sha256": others,
        }
    return prepared


def _argv_line(argv: list[str], env: dict[str, str] | None) -> str:
    parts: list[str] = []
    if env:
        parts.append("env")
        parts.extend(f"{key}={value}" for key, value in env.items())
    parts.extend(argv)
    return " ".join(sh_quote(part) for part in parts)


def jobs_for(variant: str) -> list[tuple[str, str, list[str], dict[str, str] | None]]:
    jobs: list[tuple[str, str, list[str], dict[str, str] | None]] = []
    for index in range(1, PLAIN_RUNS + 1):
        name = f"{variant}-plain-{index}"
        out = f"/out/{name}.json"
        jobs.append((name, out, baseline_argv(out), None))
    for index in range(1, REPLAY_RUNS + 1):
        name = f"{variant}-replay-{index}"
        out = f"/out/{name}.json"
        argv = rspec_argv(0, 0)
        argv[-1] = out
        jobs.append((name, out, argv, {"FLAKECERT_SRAND": "0"}))
    if variant != "prefix":
        for seed in SWEEP_SEEDS:
            name = f"{variant}-sweep-{seed}"
            out = f"/out/{name}.json"
            argv = rspec_argv(seed, 0)
            argv[-1] = out
            jobs.append((name, out, argv, {"FLAKECERT_SRAND": "0"}))
    return jobs


def render_script() -> str:
    """One container, variants in series, runs of a variant in parallel.

    The image already has Gemfile.lock and the installed gems. Copying a
    variant over /app replaces the sample files and leaves that lock in place.
    """
    blocks = [
        "set -eu",
        "cd /app",
        "mkdir -p /out",
        "rm -f /out/FAIL",
        "sha256sum /app/Gemfile.lock | awk '{print $1}' > /out/image-lock.sha256",
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
        '  local out="$2"',
        "  shift 2",
        '  local err="/tmp/rspec-${name}.err"',
        "  local rc=0",
        '  "$@" >"$err" 2>&1 || rc=$?',
        '  if [ "$rc" -gt 1 ] || [ ! -s "$out" ]; then',
        '    echo "RSPEC_RUN_FAIL name=$name rc=$rc" >> /out/FAIL',
        '    cat "$err" >> /out/FAIL || true',
        "  fi",
        '  echo "done name=$name rc=$rc"',
        "}",
        "apply_variant() {",
        '  local variant="$1"',
        '  cp -a "/variants/${variant}/." /app/',
        "  sha256sum /app/spec/models/cart_spec.rb | awk '{print $1}' > \"/out/${variant}-cart.sha256\"",
        "  if [ ! -s /app/Gemfile.lock ]; then",
        '    echo "missing Gemfile.lock after ${variant}" >> /out/FAIL',
        "    exit 1",
        "  fi",
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
        for name, out, argv, env in jobs_for(variant):
            blocks.append(
                "start_job run_one "
                + " ".join((sh_quote(name), sh_quote(out), _argv_line(argv, env)))
            )
        blocks.append("finish_variant")
        blocks.append(f"echo APPLIED_DONE {variant}")
    blocks.append("echo ATTEMPT_OK")
    return "\n".join(blocks) + "\n"


def run_container(variants_dir: Path, out_dir: Path, script_path: Path) -> None:
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
        timeout=1800,
    )
    if proc.stdout:
        log(proc.stdout[-4000:])
    if proc.returncode != 0:
        err = proc.stderr or ""
        raise SystemExit(f"rspec attempt-to-fix failed ({proc.returncode})\n{err[-8000:]}")


def _payload(path: Path, order_seed: int | None) -> tuple[dict, dict[str, str]]:
    payload = _read_json(path)
    if order_seed is None and "seed" in payload:
        raise SystemExit(
            f"{path} plain retry recorded seed={payload.get('seed')!r}; "
            "defined order should omit it"
        )
    try:
        examples = parse_examples(payload, order_seed)
    except Exception as exc:
        raise SystemExit(f"{path}: {exc}") from exc
    _require_ids(examples, path)
    return payload, examples


def _replay_row(payload: dict, examples: dict[str, str]) -> dict:
    row: dict = {
        "victim": examples[VICTIM],
        "polluter": examples[POLLUTER],
        "exc": None,
        "message": None,
        "sig": None,
    }
    if examples[VICTIM] != "failed":
        return row
    exc, sig = _failure_of(payload, VICTIM)
    message = None
    for example in payload.get("examples") or []:
        if example.get("id") != VICTIM:
            continue
        exception = example.get("exception") or {}
        message = exception.get("message")
        break
    row["exc"] = exc
    row["message"] = message
    row["sig"] = sig
    return row


def assemble(out_dir: Path, prepared: dict[str, dict], image_digest: str, lock_sha: str) -> dict:
    image_lock = (out_dir / "image-lock.sha256").read_text(encoding="utf-8").strip()
    if image_lock != lock_sha:
        raise SystemExit(f"image Gemfile.lock {image_lock} != committed {lock_sha}")
    versions: set = set()
    variants: dict[str, dict] = {}
    for variant in VARIANTS:
        cart_in_image = (out_dir / f"{variant}-cart.sha256").read_text(encoding="utf-8").strip()
        if cart_in_image != prepared[variant]["cart_spec_sha256"]:
            raise SystemExit(
                f"{variant} in-image cart_spec {cart_in_image} != "
                f"copied {prepared[variant]['cart_spec_sha256']}"
            )
        plain: list[str] = []
        for index in range(1, PLAIN_RUNS + 1):
            path = out_dir / f"{variant}-plain-{index}.json"
            payload, examples = _payload(path, None)
            versions.add(payload.get("version"))
            plain.append(examples[VICTIM])
        replays = []
        for index in range(1, REPLAY_RUNS + 1):
            path = out_dir / f"{variant}-replay-{index}.json"
            payload, examples = _payload(path, 0)
            versions.add(payload.get("version"))
            replays.append(_replay_row(payload, examples))
        entry = {
            "cart_spec_sha256": prepared[variant]["cart_spec_sha256"],
            "sample_other_sha256": prepared[variant]["sample_other_sha256"],
            "plain_retry": plain,
            "cert_replay": replays,
        }
        if variant != "prefix":
            sweep: dict[str, dict[str, str]] = {}
            for seed in SWEEP_SEEDS:
                path = out_dir / f"{variant}-sweep-{seed}.json"
                payload, examples = _payload(path, seed)
                versions.add(payload.get("version"))
                sweep[str(seed)] = {
                    "victim": examples[VICTIM],
                    "polluter": examples[POLLUTER],
                }
            entry["sweep"] = sweep
        variants[variant] = entry
    if len(versions) != 1 or not all(isinstance(item, str) and item for item in versions):
        raise SystemExit(f"rspec version field is not a single string: {versions!r}")
    return {
        "rspec_core": next(iter(versions)),
        "image_digest": image_digest,
        "lock_sha256": lock_sha,
        "schedule": {"order_seed": 0, "srand_seed": 0},
        "variants": variants,
    }


def main() -> int:
    if SRAND_PATH.read_text(encoding="utf-8").strip() != SRAND_LINE:
        raise SystemExit(f"{SRAND_PATH} is not the one-line Kernel.srand hook")
    cert = json.loads(CERT_PATH.read_text(encoding="utf-8"))
    if cert.get("schedule") != {"order_seed": 0, "srand_seed": 0}:
        raise SystemExit(f"cert schedule is not the pinned 0,0: {cert.get('schedule')}")
    expected_replay = "FLAKECERT_SRAND=0 " + " ".join(rspec_argv(0, 0))
    if cert.get("replay") != expected_replay:
        raise SystemExit(f"cert replay does not match rspec.replay argv:\n{cert.get('replay')}")
    digest = base_digest()
    if digest != cert.get("image_digest"):
        raise SystemExit(f"base image {digest} != cert {cert.get('image_digest')}")
    log(f"base image digest {digest}")
    build_image()
    lock_sha = sha256_file(LOCK_PATH)
    if lock_sha != cert.get("lock_sha256"):
        raise SystemExit(f"lock {lock_sha} != cert {cert.get('lock_sha256')}")
    if WORK.exists():
        shutil.rmtree(WORK)
    variants_dir = WORK / "variants"
    out_dir = WORK / "out"
    out_dir.mkdir(parents=True)
    prepared = prepare_variants(variants_dir)
    script_path = WORK / "run.sh"
    script_path.write_text(render_script(), encoding="utf-8")
    run_container(variants_dir, out_dir, script_path)
    # Docker writes /out as root. The directory is world-readable.
    document = assemble(out_dir, prepared, digest, lock_sha)
    if document["schedule"] != cert["schedule"]:
        raise SystemExit("assembled schedule drifted from the certificate")
    AUDIT.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    log(f"wrote {OUT_PATH}")
    for variant in VARIANTS:
        replays = document["variants"][variant]["cert_replay"]
        victims = [row["victim"] for row in replays]
        log(f"{variant} cert_replay victims {victims}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
