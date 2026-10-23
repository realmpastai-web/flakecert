"""QueueTrail CLI and static gem checks. Does not execute test-queue."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "queuetrail" / "cli.py"
CHECK = ROOT / "tools" / "queuetrail" / "reverse_check.py"
GEM = ROOT / "inputs" / "rea-brief-test-queue" / "test-queue-0.12.0.gem"
CONTROL = ROOT / "inputs" / "rea-brief-test-queue" / "parallel_tests-5.8.0.gem"
EXPECT = ROOT / "inputs" / "rea-brief-test-queue" / "observations.json"
SHIM = ROOT / "tools" / "queuetrail" / "spec_shim.rb"
ORDERING = ROOT / "tools" / "certify_rspec" / "ordering.rb"
HOOK = ROOT / "tools" / "queuetrail" / "queuetrail.rb"
REASON = (
    "UNPROVEN. ordering.rb reads whitespace-separated ids from ENV ids or ids_file "
    "(tools/certify_rspec/ordering.rb:10-14). Suite names are RSpec ids (O6), so ids_file "
    "feeds ordering.rb directly. No certify_rspec CLI accepts an external candidate file."
)


def write_worker(directory: Path, worker: int, suites: list[dict], **header_overrides: object) -> Path:
    header = {
        "type": "worker",
        "run_id": "run-1",
        "worker_num": worker,
        "pid": 4000 + worker,
        "host": "builder",
        "srand_seed": 1009179 + worker,
        "rspec_seed": 1234,
        "master_seed": 7,
        "ruby_version": "3.3.8",
        "test_queue_version": "0.12.0",
    }
    header.update(header_overrides)
    rows = [header]
    for index, suite in enumerate(suites):
        rows.append(
            {
                "type": "suite",
                "index": index,
                "name": suite["name"],
                "path": suite.get("path", f"{suite['name']}.rb"),
                "start_monotonic": float(index),
                "end_monotonic": float(index) + 0.25,
                "status": suite.get("status", "passed"),
            }
        )
    path = directory / f"worker-{worker}.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def run_cli(args: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.pop("QUEUETRAIL_FLAKECERT_COMMIT", None)
    if env:
        merged.update(env)
    return subprocess.run(
        ["python3", str(CLI), *args],
        cwd=cwd,
        env=merged,
        text=True,
        capture_output=True,
        check=False,
    )


def manifest_for(directory: Path, cwd: Path | None = None, env: dict | None = None, lock: Path | None = None) -> dict:
    args = ["manifest", "--dir", str(directory)]
    if lock is not None:
        args.extend(["--gemfile-lock", str(lock)])
    completed = run_cli(args, cwd=cwd, env=env)
    assert completed.returncode == 0, completed.stderr
    return json.loads((directory / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_records_every_trail_sha256(tmp_path: Path) -> None:
    first = write_worker(tmp_path, 1, [{"name": "a"}])
    second = write_worker(tmp_path, 2, [{"name": "b"}])
    document = manifest_for(tmp_path, cwd=tmp_path)
    assert document["worker_count"] == 2
    assert document["trails"]["worker-1.jsonl"] == hashlib.sha256(first.read_bytes()).hexdigest()
    assert document["trails"]["worker-2.jsonl"] == hashlib.sha256(second.read_bytes()).hexdigest()
    assert "manifest.json" not in document["trails"]


def test_manifest_run_id_master_seed_and_versions(tmp_path: Path) -> None:
    write_worker(tmp_path, 1, [{"name": "a"}])
    write_worker(tmp_path, 4, [{"name": "b"}])
    document = manifest_for(tmp_path, cwd=tmp_path, env={"QUEUETRAIL_FLAKECERT_COMMIT": "abc123"})
    assert document["run_id"] == "run-1"
    assert document["master_seed"] == 7
    assert document["ruby_version"] == "3.3.8"
    assert document["test_queue_version"] == "0.12.0"
    assert document["flakecert_commit"] == "abc123"
    assert document["worker_count"] == 2


def test_manifest_gemfile_lock_sha256(tmp_path: Path) -> None:
    write_worker(tmp_path, 1, [{"name": "a"}])
    lock = tmp_path / "Gemfile.lock"
    lock.write_text("GEM\n  remote: https://rubygems.org/\n", encoding="utf-8")
    document = manifest_for(tmp_path, cwd=tmp_path, lock=lock)
    assert document["gemfile_lock_sha256"] == hashlib.sha256(lock.read_bytes()).hexdigest()


def test_manifest_gemfile_lock_absent_is_null(tmp_path: Path) -> None:
    write_worker(tmp_path, 1, [{"name": "a"}])
    document = manifest_for(tmp_path, cwd=tmp_path)
    assert document["gemfile_lock_sha256"] is None


def test_manifest_rejects_disagreeing_run_ids(tmp_path: Path) -> None:
    write_worker(tmp_path, 1, [{"name": "a"}], run_id="one")
    write_worker(tmp_path, 2, [{"name": "b"}], run_id="two")
    completed = run_cli(["manifest", "--dir", str(tmp_path)], cwd=tmp_path)
    assert completed.returncode != 0
    assert not (tmp_path / "manifest.json").exists()


def parse_replay(stdout: str) -> tuple[str, str, list[str]]:
    tokens = shlex.split(stdout.strip())
    assert tokens[0].startswith("QUEUETRAIL_SRAND="), tokens
    assert tokens[1].startswith("ids="), tokens
    seed = tokens[0].split("=", 1)[1]
    ids = tokens[1].split("=", 1)[1]
    return seed, ids, tokens[2:]


def test_replay_prints_ids_ordering_require_and_recorded_seed(tmp_path: Path) -> None:
    write_worker(
        tmp_path,
        2,
        [
            {"name": "alpha", "path": "spec/alpha.rb"},
            {"name": "beta", "path": "spec/beta.rb"},
            {"name": "gamma", "path": "spec/gamma.rb"},
        ],
        srand_seed=43027657,
    )
    manifest_for(tmp_path, cwd=tmp_path)
    completed = run_cli(["replay", "--manifest", str(tmp_path / "manifest.json"), "--worker", "2"], cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    seed, ids, argv = parse_replay(completed.stdout)
    assert seed == "43027657"
    assert ids == "alpha beta gamma"
    assert argv[:5] == ["rspec", "--require", str(ORDERING), "--require", str(SHIM)]
    assert "--order" not in argv
    assert argv[5:] == ["alpha", "beta", "gamma"]


def test_replay_upto_keeps_inclusive_prefix(tmp_path: Path) -> None:
    write_worker(
        tmp_path,
        1,
        [
            {"name": "alpha", "path": "spec/alpha.rb"},
            {"name": "beta", "path": "spec/beta.rb"},
            {"name": "gamma", "path": "spec/gamma.rb"},
        ],
    )
    manifest_for(tmp_path, cwd=tmp_path)
    completed = run_cli(
        ["replay", "--manifest", str(tmp_path / "manifest.json"), "--worker", "1", "--upto", "1"],
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr
    _seed, ids, argv = parse_replay(completed.stdout)
    assert ids == "alpha beta"
    assert argv[5:] == ["alpha", "beta"]


def test_replay_upto_zero_is_the_first_suite(tmp_path: Path) -> None:
    write_worker(
        tmp_path,
        1,
        [{"name": "alpha", "path": "spec/alpha.rb"}, {"name": "beta", "path": "spec/beta.rb"}],
    )
    manifest_for(tmp_path, cwd=tmp_path)
    completed = run_cli(
        ["replay", "--manifest", str(tmp_path / "manifest.json"), "--worker", "1", "--upto", "0"],
        cwd=tmp_path,
    )
    _seed, ids, argv = parse_replay(completed.stdout)
    assert ids == "alpha"
    assert argv[5:] == ["alpha"]


def test_replay_empty_path_uses_suite_name(tmp_path: Path) -> None:
    write_worker(tmp_path, 1, [{"name": "spec/webhook_spec.rb:5", "path": ""}])
    manifest_for(tmp_path, cwd=tmp_path)
    completed = run_cli(["replay", "--manifest", str(tmp_path / "manifest.json"), "--worker", "1"], cwd=tmp_path)
    _seed, ids, argv = parse_replay(completed.stdout)
    assert ids == "spec/webhook_spec.rb:5"
    assert argv[5:] == ["spec/webhook_spec.rb:5"]


def test_replay_rejects_trail_sha256_mismatch(tmp_path: Path) -> None:
    path = write_worker(tmp_path, 1, [{"name": "alpha", "path": "spec/alpha.rb"}])
    manifest_for(tmp_path, cwd=tmp_path)
    path.write_bytes(path.read_bytes() + b"\n")
    completed = run_cli(["replay", "--manifest", str(tmp_path / "manifest.json"), "--worker", "1"], cwd=tmp_path)
    assert completed.returncode != 0
    assert "mismatch" in completed.stderr


def test_to_flakecert_prefix_order(tmp_path: Path) -> None:
    write_worker(
        tmp_path,
        3,
        [
            {"name": "spec/a.rb", "path": "spec/a.rb"},
            {"name": "spec/b.rb", "path": "spec/b.rb"},
            {"name": "spec/webhook_spec.rb", "path": "spec/webhook_spec.rb"},
            {"name": "spec/after.rb", "path": "spec/after.rb"},
        ],
    )
    manifest_for(tmp_path, cwd=tmp_path)
    out = tmp_path / "handoff.json"
    completed = run_cli(
        [
            "to-flakecert",
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--worker",
            "3",
            "--victim",
            "spec/webhook_spec.rb",
            "--out",
            str(out),
        ],
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["candidate_ids"] == ["spec/a.rb", "spec/b.rb"]
    assert document["ids_file"] == "spec/a.rb\nspec/b.rb\nspec/webhook_spec.rb\n"
    assert document["worker_num"] == 3
    assert document["victim"] == "spec/webhook_spec.rb"


def test_to_flakecert_adapter_gap_is_unproven(tmp_path: Path) -> None:
    write_worker(tmp_path, 1, [{"name": "victim", "path": "victim.rb"}])
    manifest_for(tmp_path, cwd=tmp_path)
    completed = run_cli(
        [
            "to-flakecert",
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--worker",
            "1",
            "--victim",
            "victim",
        ],
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stderr
    document = json.loads(completed.stdout)
    assert document["adapter_gap"] == "UNPROVEN"
    assert document["kind"] == "queuetrail-candidate-polluters"
    assert document["reason"] == REASON
    assert document["candidate_ids"] == []
    assert document["ids_file"] == "victim\n"


def test_to_flakecert_missing_victim_exits(tmp_path: Path) -> None:
    write_worker(tmp_path, 1, [{"name": "other", "path": "other.rb"}])
    manifest_for(tmp_path, cwd=tmp_path)
    completed = run_cli(
        ["to-flakecert", "--manifest", str(tmp_path / "manifest.json"), "--worker", "1", "--victim", "missing"],
        cwd=tmp_path,
    )
    assert completed.returncode != 0


def test_reverse_check_passes_pinned_gems() -> None:
    completed = subprocess.run(
        ["python3", str(CHECK), "--gem", str(GEM), "--control", str(CONTROL), "--expect", str(EXPECT)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    for obs_id in ("Q1", "Q2", "Q3", "Q4", "Q5", "C1", "O6", "O7"):
        assert f"{obs_id} PASS" in completed.stdout


def test_reverse_check_rejects_wrong_gem_sha256(tmp_path: Path) -> None:
    expect = json.loads(EXPECT.read_text(encoding="utf-8"))
    expect["target_sha256"] = "0" * 64
    forged = tmp_path / "observations.json"
    forged.write_text(json.dumps(expect), encoding="utf-8")
    completed = subprocess.run(
        ["python3", str(CHECK), "--gem", str(GEM), "--control", str(CONTROL), "--expect", str(forged)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "SHA FAIL target" in completed.stdout
    assert "Q1 PASS" not in completed.stdout


def test_replay_shim_path_exists() -> None:
    assert SHIM.is_file()
    assert ORDERING.is_file()


def run_hook(source: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in (
        "QUEUETRAIL_DIR",
        "QUEUETRAIL_MASTER_SEED",
        "QUEUETRAIL_RUN_ID",
        "QUEUETRAIL_TEST_QUEUE_VERSION",
        "QUEUETRAIL_WORKER_PATH",
    ):
        env.pop(key, None)
    return subprocess.run(["ruby", "-e", source], text=True, capture_output=True, check=False, env=env)


def test_suite_name_id_then_full_description_then_metadata() -> None:
    script = f"""
require "json"
require "tmpdir"
dir = Dir.mktmpdir("qt-name", "/var/tmp")
ENV["QUEUETRAIL_DIR"] = dir
ENV["QUEUETRAIL_MASTER_SEED"] = "0"
ENV["QUEUETRAIL_RUN_ID"] = "names"
module TestQueue
  class Runner
    def after_fork(num); end
  end
  class Iterator
    def initialize(suites)
      @suites = suites
    end
    def each
      @suites.each {{ |suite| yield suite }}
    end
  end
end
class ConstantName
  def name
    raise "suite.name is the Ruby constant"
  end
  def id
    "./spec/const_spec.rb[1:1]"
  end
  def file_path
    "./spec/const_spec.rb"
  end
end
class NilId
  def id
    nil
  end
  def full_description
    "after nil id"
  end
  def file_path
    "./spec/nil_spec.rb"
  end
end
class DescriptionOnly
  def full_description
    "Widget is red"
  end
  def file_path
    "./spec/widget_spec.rb"
  end
end
class MetadataOnly
  def metadata
    {{ full_description: "from metadata" }}
  end
  def file_path
    "./spec/meta_spec.rb"
  end
end
class GroupMeta
  def metadata
    {{ example_group: {{ full_description: "from group" }} }}
  end
end
require {str(HOOK)!r}
TestQueue::Runner.new.after_fork(1)
TestQueue::Iterator.new([
  ConstantName.new,
  NilId.new,
  DescriptionOnly.new,
  MetadataOnly.new,
  GroupMeta.new,
]).each {{ |_suite| }}
rows = File.readlines(File.join(dir, "worker-1.jsonl"), chomp: true).map {{ |line| JSON.parse(line) }}
suites = rows.select {{ |row| row["type"] == "suite" }}
names = suites.map {{ |row| row["name"] }}
paths = suites.map {{ |row| row["path"] }}
expected = ["./spec/const_spec.rb[1:1]", "after nil id", "Widget is red", "from metadata", "from group"]
abort(names.inspect) unless names == expected
abort(paths.inspect) unless paths == ["./spec/const_spec.rb", "./spec/nil_spec.rb", "./spec/widget_spec.rb", "./spec/meta_spec.rb", ""]
puts "NAME_OK"
"""
    completed = run_hook(script)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "NAME_OK" in completed.stdout


def test_replay_uses_recorded_ids_not_paths(tmp_path: Path) -> None:
    write_worker(
        tmp_path,
        4,
        [
            {"name": "./spec/alpha_spec.rb[1:1]", "path": "./spec/alpha_spec.rb"},
            {"name": "./spec/alpha_spec.rb[1:2]", "path": "./spec/alpha_spec.rb"},
        ],
    )
    manifest_for(tmp_path, cwd=tmp_path)
    completed = run_cli(["replay", "--manifest", str(tmp_path / "manifest.json"), "--worker", "4"], cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    _seed, ids, argv = parse_replay(completed.stdout)
    assert ids == "./spec/alpha_spec.rb[1:1] ./spec/alpha_spec.rb[1:2]"
    assert argv[5:] == ["./spec/alpha_spec.rb[1:1]", "./spec/alpha_spec.rb[1:2]"]
    assert "./spec/alpha_spec.rb" not in argv
    assert "--order" not in argv


def test_ordering_rb_reads_ids_by_line() -> None:
    lines = ORDERING.read_text(encoding="utf-8").splitlines()
    assert lines[9] == '  raw = ENV.fetch("ids", "")'
    assert lines[11] == '  file_name = ENV.fetch("ids_file", "")'
    assert lines[12] == "  raw = File.read(file_name) if raw.empty? && !file_name.empty?"
    assert lines[13] == r"  raw.split(/\s+/).each_with_index do |ident, index|"
    assert lines[29] == "  config.register_ordering(:global) do |items|"


def test_status_does_not_read_failure_count() -> None:
    script = f"""
require "json"
require "tmpdir"
dir = Dir.mktmpdir("qt-status", "/var/tmp")
ENV["QUEUETRAIL_DIR"] = dir
ENV["QUEUETRAIL_MASTER_SEED"] = "0"
ENV["QUEUETRAIL_RUN_ID"] = "status"
module TestQueue
  class Runner
    def after_fork(num); end
  end
  class Iterator
    def initialize(suites)
      @suites = suites
    end
    def each
      @suites.each {{ |suite| yield suite }}
    end
  end
end
Example = Struct.new(:execution_result)
Result = Struct.new(:status)
class GemGroup
  def initialize(id, examples)
    @id = id
    @examples = examples
  end
  def id
    @id
  end
  def file_path
    @id.sub(/\\[.+\\]\\z/, "")
  end
  def examples
    @examples
  end
  def descendant_filtered_examples
    examples
  end
  def failure_count
    examples.map {{ |example| example.execution_result.status == "failed" }}.length
  end
end
class SplitExample
  def id
    "./spec/split_spec.rb[1:1]"
  end
  def file_path
    "./spec/split_spec.rb"
  end
  def execution_result
    Result.new("failed")
  end
  def failure_count
    0
  end
end
passed = Example.new(Result.new("passed"))
failed = Example.new(Result.new("failed"))
require {str(HOOK)!r}
TestQueue::Runner.new.after_fork(1)
TestQueue::Iterator.new([
  GemGroup.new("./spec/ok_spec.rb[1:1]", [passed, passed]),
  GemGroup.new("./spec/bad_spec.rb[1:1]", [passed, failed]),
  SplitExample.new,
]).each {{ |_suite| }}
rows = File.readlines(File.join(dir, "worker-1.jsonl"), chomp: true).map {{ |line| JSON.parse(line) }}
statuses = rows.select {{ |row| row["type"] == "suite" }}.map {{ |row| row["status"] }}
abort(statuses.inspect) unless statuses == ["passed", "failed", "failed"]
puts "STATUS_OK"
"""
    completed = run_hook(script)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "STATUS_OK" in completed.stdout
