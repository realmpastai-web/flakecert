"""RSpec runner: pin order (--order rand:S) and Ruby's global RNG (Kernel.srand).

A schedule is {order_seed: S, srand_seed: R} with d = 2. The scheduled command is

    bundle exec rspec --order rand:S --require /flakecert/srand.rb \\
        --format json --out /out/S-R.json

with FLAKECERT_SRAND=R. srand.rb is one line:

    Kernel.srand(Integer(ENV.fetch("FLAKECERT_SRAND")))

Baseline is plain `bundle exec rspec --format json` (defined order, no srand).
`--out` is added so the JSON is a file; .rspec already asks for the progress formatter.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from flakecert import __version__
from flakecert.cert import bound_fields, failure_signature
from flakecert.scheduler import observed_k
from flakecert.util import log, run_cmd, sha256_file

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "envs" / "rspec" / "Dockerfile"
LOCK_PATH = ROOT / "envs" / "rspec" / "Gemfile.lock"
INSTALL_LOG = ROOT / "envs" / "rspec" / "install.log"
SRAND_PATH = ROOT / "flakecert" / "runners" / "srand.rb"
AUDIT = ROOT / "audit"
RESULTS_PATH = AUDIT / "rspec-results.json"
CERT_PATH = AUDIT / "rspec-cert.json"
JENKINS_PATH = AUDIT / "jenkins-ruby.json"
IMAGE_TAG = "flakecert-rspec:sample"

VICTIM = "./spec/models/cart_spec.rb[1:1]"
POLLUTER = "./spec/models/cart_spec.rb[1:2]"
DRAW = "./spec/models/coupon_spec.rb[1:2]"
STABLE = (
    "./spec/models/coupon_spec.rb[1:1]",
    "./spec/models/stable_spec.rb[1:1]",
    "./spec/models/stable_spec.rb[1:2]",
)
EXAMPLE_IDS = (VICTIM, POLLUTER, DRAW, *STABLE)
D = 2
SOURCES = ["order_seed", "srand_seed"]

SRAND_LINE = 'Kernel.srand(Integer(ENV.fetch("FLAKECERT_SRAND")))'

# Ruby calls the installed gem's private jenkins_hash_digest. The three inputs
# are recorded for the unit port test; this process does not invent the digests.
JENKINS_RUBY = r"""
require "json"
require "rspec/core"
strategy = RSpec::Core::Ordering::Random.allocate
pairs = [
  ["0", "./spec/models/cart_spec.rb[1:1]"],
  ["0", "./spec/models/cart_spec.rb[1:2]"],
  ["42", "./spec/models/coupon_spec.rb[1:2]"],
]
rows = pairs.map do |seed, id|
  {
    "seed" => seed,
    "id" => id,
    "input" => seed + id,
    "jenkins" => strategy.send(:jenkins_hash_digest, seed + id),
  }
end
File.write("/out/jenkins-ruby.json", JSON.generate(rows) + "\n")
"""

SWEEP_SCRIPT = r"""
set -eu
cd /app
mkdir -p /out
rm -f /out/FAIL
ruby -v > /out/ruby-v.txt
# JENKINS_RUBY
MAX=$(nproc)
if [ "$MAX" -gt 8 ]; then MAX=8; fi
fifo=/tmp/fc-slots
rm -f "$fifo"
mkfifo "$fifo"
exec 3<>"$fifo"
for _slot in $(seq 1 "$MAX"); do
  echo >&3
done

start_job() {
  read -u 3
  (
    "$@" || true
    echo >&3
  ) &
}

run_sched() {
  local s="$1" r="$2" rep="$3"
  local out="/out/s${s}-r${r}.${rep}.json"
  local err="/tmp/rspec-s${s}-r${r}.${rep}.err"
  local rc=0
  FLAKECERT_SRAND="$r" bundle exec rspec \
    --order "rand:${s}" \
    --require /flakecert/srand.rb \
    --format json \
    --out "$out" >"$err" 2>&1 || rc=$?
  if [ "$rc" -gt 1 ] || [ ! -s "$out" ]; then
    echo "RSPEC_RUN_FAIL s=$s r=$r rep=$rep rc=$rc" >> /out/FAIL
    cat "$err" >> /out/FAIL || true
  fi
  echo "sched s=$s r=$r rep=$rep rc=$rc"
}

run_base() {
  local rep="$1"
  local out="/out/baseline-${rep}.json"
  local err="/tmp/rspec-baseline-${rep}.err"
  local rc=0
  bundle exec rspec --format json --out "$out" >"$err" 2>&1 || rc=$?
  if [ "$rc" -gt 1 ] || [ ! -s "$out" ]; then
    echo "RSPEC_BASE_FAIL rep=$rep rc=$rc" >> /out/FAIL
    cat "$err" >> /out/FAIL || true
  fi
  echo "baseline rep=$rep rc=$rc"
}

for s in $(seq 0 99); do
  for rep in 1 2; do
    start_job run_sched "$s" 0 "$rep"
  done
done
for r in $(seq 1 99); do
  for rep in 1 2; do
    start_job run_sched 0 "$r" "$rep"
  done
done
for rep in $(seq 1 100); do
  start_job run_base "$rep"
done
wait || true
if [ -s /out/FAIL ]; then
  cat /out/FAIL >&2
  exit 1
fi
"""


class SeedMismatch(RuntimeError):
    def __init__(self, expected: int, actual) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(f"rspec seed {actual!r} != order seed {expected}")


def rspec_argv(order_seed: int, srand_seed: int) -> list[str]:
    return [
        "bundle",
        "exec",
        "rspec",
        "--order",
        f"rand:{order_seed}",
        "--require",
        "/flakecert/srand.rb",
        "--format",
        "json",
        "--out",
        f"/out/{order_seed}-{srand_seed}.json",
    ]


def baseline_argv(out_path: str) -> list[str]:
    return ["bundle", "exec", "rspec", "--format", "json", "--out", out_path]


def parse_examples(payload: dict, order_seed: int | None = None) -> dict[str, str]:
    """Map examples[].id to status. Abort when a scheduled run's seed is not S."""
    if order_seed is not None and payload.get("seed") != order_seed:
        raise SeedMismatch(order_seed, payload.get("seed"))
    examples = payload.get("examples")
    if not isinstance(examples, list):
        raise ValueError("rspec JSON has no examples list")
    parsed: dict[str, str] = {}
    for example in examples:
        example_id = example["id"]
        status = example["status"]
        if example_id in parsed:
            raise ValueError(f"duplicate example id {example_id}")
        if status not in {"passed", "failed", "pending"}:
            raise ValueError(f"unexpected status {status!r} for {example_id}")
        parsed[example_id] = status
    return parsed


def replay_command(order_seed: int, srand_seed: int) -> str:
    return "FLAKECERT_SRAND={srand} {argv}".format(
        srand=srand_seed,
        argv=" ".join(rspec_argv(order_seed, srand_seed)),
    )


def build_rspec_certificate(
    *,
    node_id: str,
    image_digest: str,
    image_tag: str,
    lock_sha256: str,
    ruby_version: str,
    order_seed: int,
    srand_seed: int,
    exc: str,
    sig: str,
    runs_to_failure: int,
    k: int,
) -> dict:
    """Existing certificate fields, with lock_sha256 in place of pip_freeze_sha.

    schedule is {order_seed, srand_seed}, d is 2, and replay is the scheduled command.
    """
    schedule = {"order_seed": order_seed, "srand_seed": srand_seed}
    return {
        "id": "RSPEC-CART",
        "project": "inputs/flakecert-rspec-runner/sample",
        "sha": lock_sha256,
        "node_id": node_id,
        "image_digest": image_digest,
        "image_tag": image_tag,
        "lock_sha256": lock_sha256,
        "flakecert_version": __version__,
        "ruby": ruby_version,
        "sources": list(SOURCES),
        "m": len(SOURCES),
        "k": k,
        "d": D,
        "schedule": schedule,
        "replay": replay_command(order_seed, srand_seed),
        "expected_failure": {"exc": exc, "sig": sig},
        "bound": bound_fields(len(SOURCES), k, D, runs_to_failure),
    }


def _require(proc, what: str) -> str:
    text = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise SystemExit(f"{what} failed ({proc.returncode})\n{text}")
    return text


def base_digest() -> str:
    """Digest from the Dockerfile FROM line, accepted only if the local image has it."""
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    match = re.search(r"^FROM ruby@(sha256:[0-9a-f]{64})\s*$", dockerfile, re.M)
    if not match:
        raise SystemExit(f"{DOCKERFILE} FROM line is not a pinned ruby digest")
    pinned = match.group(1)
    proc = run_cmd(
        [
            "docker",
            "image",
            "inspect",
            f"ruby@{pinned}",
            "--format",
            "{{json .RepoDigests}}",
        ],
        timeout=60,
    )
    raw = _require(proc, "docker image inspect")
    digests = []
    for item in json.loads(raw):
        if "@" in item:
            digests.append(item.split("@", 1)[1])
    if pinned not in digests:
        raise SystemExit(f"image repo digests {digests} do not include {pinned}")
    return pinned


def build_image() -> str:
    proc = run_cmd(
        ["docker", "build", "-f", str(DOCKERFILE), "-t", IMAGE_TAG, str(ROOT)],
        timeout=900,
    )
    return _require(proc, "docker build")


def ruby_version_text() -> str:
    proc = run_cmd(["docker", "run", "--rm", IMAGE_TAG, "ruby", "-v"], timeout=120)
    return _require(proc, "ruby -v").strip()


def bundle_install_text() -> str:
    proc = run_cmd(
        ["docker", "run", "--rm", IMAGE_TAG, "bundle", "install", "--frozen"],
        timeout=300,
    )
    return _require(proc, "bundle install --frozen").strip()


def write_install_log(ruby_v: str, lock_sha: str, bundle_text: str) -> None:
    proc = run_cmd(["sha256sum", str(LOCK_PATH)], timeout=30)
    summed = _require(proc, "sha256sum Gemfile.lock").strip()
    digest = summed.split()[0]
    if digest != lock_sha:
        raise SystemExit(f"sha256sum {digest} != computed {lock_sha}")
    text = (
        "$ ruby -v\n"
        f"{ruby_v}\n"
        "\n"
        "$ sha256sum Gemfile.lock\n"
        f"{summed}\n"
        "\n"
        "$ bundle install --frozen\n"
        f"{bundle_text}\n"
    )
    INSTALL_LOG.write_text(text, encoding="utf-8")


def sweep_script() -> str:
    ruby = JENKINS_RUBY.strip()
    # Keep the ruby program in the shell script as a quoted heredoc.
    body = SWEEP_SCRIPT.replace(
        "# JENKINS_RUBY\n",
        "ruby <<'RUBY'\n" + ruby + "\nRUBY\n",
    )
    if "# JENKINS_RUBY\n" in body:
        raise SystemExit("sweep script did not receive the jenkins ruby program")
    return body


def run_sweeps(out_dir: Path) -> None:
    script_path = out_dir.parent / "sweep.sh"
    script_path.write_text(sweep_script(), encoding="utf-8")
    proc = run_cmd(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "-v",
            f"{out_dir}:/out",
            "-v",
            f"{script_path}:/sweep.sh:ro",
            IMAGE_TAG,
            "bash",
            "/sweep.sh",
        ],
        timeout=1800,
    )
    if proc.stdout:
        log(proc.stdout[-2000:])
    if proc.returncode != 0:
        err = proc.stderr or ""
        raise SystemExit(f"rspec sweep failed ({proc.returncode})\n{err[-8000:]}")


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"missing rspec output {path}")
    except json.JSONDecodeError as exc:
        body = path.read_text(encoding="utf-8", errors="replace")[:800]
        raise SystemExit(f"{path} is not JSON ({exc})\n{body}")
    if not isinstance(data, dict):
        raise SystemExit(f"{path} JSON is not an object")
    return data


def _require_ids(examples: dict[str, str], path: Path) -> None:
    missing = [example_id for example_id in EXAMPLE_IDS if example_id not in examples]
    if missing:
        raise SystemExit(f"{path} missing {missing}; has {sorted(examples)}")


def _failure_of(payload: dict, node_id: str) -> tuple[str, str]:
    for example in payload.get("examples") or []:
        if example.get("id") != node_id:
            continue
        exc = example.get("exception") or {}
        name = exc.get("class") or "Error"
        lines = [f"{name}: {exc.get('message') or ''}"]
        backtrace = exc.get("backtrace") or []
        if isinstance(backtrace, list):
            lines.extend(str(item) for item in backtrace)
        return name, failure_signature("\n".join(lines) + "\n")
    raise SystemExit(f"no example {node_id} in failing payload")


def assemble(out_dir: Path, image_digest: str, lock_sha: str, ruby_v: str) -> tuple[dict, dict]:
    schedules = []
    versions = set()
    by_key: dict[tuple[int, int], list[dict[str, str]]] = {}
    first_fail_payload = None
    first_fail_seed = None

    def take(path: Path, order_seed: int, srand_seed: int, replay_index: int) -> None:
        nonlocal first_fail_payload, first_fail_seed
        payload = _read_json(path)
        versions.add(payload.get("version"))
        try:
            examples = parse_examples(payload, order_seed)
        except SeedMismatch as exc:
            raise SystemExit(f"{path}: {exc}") from exc
        _require_ids(examples, path)
        schedules.append(
            {"order_seed": order_seed, "srand_seed": srand_seed, "examples": examples}
        )
        by_key.setdefault((order_seed, srand_seed), []).append(examples)
        if (
            srand_seed == 0
            and replay_index == 1
            and examples.get(VICTIM) == "failed"
            and first_fail_seed is None
        ):
            first_fail_seed = order_seed
            first_fail_payload = payload

    for order_seed in range(100):
        for replay_index in (1, 2):
            take(out_dir / f"s{order_seed}-r0.{replay_index}.json", order_seed, 0, replay_index)
    for srand_seed in range(1, 100):
        for replay_index in (1, 2):
            take(out_dir / f"s0-r{srand_seed}.{replay_index}.json", 0, srand_seed, replay_index)

    baseline_runs = []
    for replay_index in range(1, 101):
        path = out_dir / f"baseline-{replay_index}.json"
        payload = _read_json(path)
        versions.add(payload.get("version"))
        if "seed" in payload:
            raise SystemExit(
                f"{path} baseline recorded seed={payload.get('seed')!r}; "
                "defined order should omit it"
            )
        examples = parse_examples(payload, None)
        _require_ids(examples, path)
        baseline_runs.append(examples)

    if len(versions) != 1 or not all(isinstance(item, str) and item for item in versions):
        raise SystemExit(f"rspec version field is not a single string: {versions!r}")
    rspec_core = next(iter(versions))

    victim_failures = sum(1 for examples in baseline_runs if examples[VICTIM] == "failed")
    draw_failures = sum(1 for examples in baseline_runs if examples[DRAW] == "failed")
    results = {
        "rspec_core": rspec_core,
        "image_digest": image_digest,
        "lock_sha256": lock_sha,
        "schedules": schedules,
        "baseline": {
            "runs": len(baseline_runs),
            "victim_failures": victim_failures,
            "draw_failures": draw_failures,
        },
    }
    if first_fail_payload is None or first_fail_seed is None:
        raise SystemExit("order sweep produced no victim failure; not writing a certificate")
    exc, sig = _failure_of(first_fail_payload, VICTIM)
    k = observed_k(
        [
            {"order_seed": item["order_seed"], "srand_seed": item["srand_seed"]}
            for item in schedules
        ],
        SOURCES,
    )
    cert = build_rspec_certificate(
        node_id=VICTIM,
        image_digest=image_digest,
        image_tag=IMAGE_TAG,
        lock_sha256=lock_sha,
        ruby_version=ruby_v,
        order_seed=first_fail_seed,
        srand_seed=0,
        exc=exc,
        sig=sig,
        runs_to_failure=first_fail_seed + 1,
        k=k,
    )
    return results, cert


def main() -> int:
    if SRAND_PATH.read_text(encoding="utf-8").strip() != SRAND_LINE:
        raise SystemExit(f"{SRAND_PATH} is not the one-line Kernel.srand hook")
    digest = base_digest()
    log(f"base image digest {digest}")
    build_image()
    ruby_v = ruby_version_text()
    bundle_text = bundle_install_text()
    lock_sha = sha256_file(LOCK_PATH)
    write_install_log(ruby_v, lock_sha, bundle_text)
    log(f"wrote {INSTALL_LOG}")
    out_dir = ROOT / ".cache" / "rspec-out"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    run_sweeps(out_dir)
    jenkins_src = out_dir / "jenkins-ruby.json"
    if not jenkins_src.is_file():
        raise SystemExit(f"missing {jenkins_src}")
    results, cert = assemble(out_dir, digest, lock_sha, ruby_v)
    AUDIT.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    CERT_PATH.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(jenkins_src, JENKINS_PATH)
    log(f"wrote {RESULTS_PATH}")
    log(f"wrote {CERT_PATH}")
    log(f"wrote {JENKINS_PATH}")
    log("baseline " + json.dumps(results["baseline"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
