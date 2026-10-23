"""QueueTrail-Rails static checks. Does not execute Rails, activesupport, or minitest."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "tools" / "queuetrail" / "rails_replay.py"
CHECK = ROOT / "tools" / "queuetrail" / "reverse_check_rails.py"
CLI = ROOT / "tools" / "queuetrail" / "cli.py"
HOOK = ROOT / "tools" / "queuetrail" / "rails.rb"
SHIM = ROOT / "tools" / "queuetrail" / "rails_order_shim.rb"
GEM = ROOT / "inputs" / "rea-brief-rails-parallel" / "activesupport-8.1.4.gem"
EXPECT = ROOT / "inputs" / "rea-brief-rails-parallel" / "observations.json"
SPEC = ROOT / "docs" / "QUEUETRAIL-RAILS-SPEC.md"
SUMS = ROOT / "inputs" / "rea-brief-rails-parallel" / "SHA256SUMS"
REASON = (
    "UNPROVEN. certify_rspec is RSpec-only: tools/certify_rspec/ordering.rb "
    "registers an RSpec global ordering and QueueTrail replay invokes rspec. "
    "A minitest certify path would need its own runner that reads this ids file "
    "of Class#method lines and executes that ordered prefix plus the victim in "
    "one process with PARALLEL_WORKERS=1. That runner is not built here."
)


def seed(master: int, worker: int) -> int:
    return ((master + 1) * 1_000_003 + worker * 9_176) % (1 << 31)


def write_worker(directory: Path, worker: int, suites: list[dict], **header_overrides: object) -> Path:
    header = {
        "type": "worker",
        "run_id": "rails-run",
        "worker_num": worker,
        "pid": 5000 + worker,
        "host": "builder",
        "srand_seed": seed(7, worker),
        "minitest_seed": 42,
        "master_seed": 7,
        "ruby_version": "3.3.8",
        "rspec_seed": None,
        "test_queue_version": None,
    }
    header.update(header_overrides)
    rows = [header]
    for index, suite in enumerate(suites):
        rows.append(
            {
                "type": "suite",
                "index": index,
                "name": suite["name"],
                "path": "",
                "start_monotonic": float(index),
                "end_monotonic": float(index) + 0.1,
                "status": suite.get("status", "pass"),
            }
        )
    path = directory / f"worker-{worker}.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def run_replay(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(REPLAY), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def manifest(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(CLI), "manifest", "--dir", str(directory)],
        cwd=directory,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "QUEUETRAIL_FLAKECERT_COMMIT": "rails-static"},
    )


def test_seed_formula_matches_spec_table() -> None:
    assert seed(0, 0) == 1_000_003
    assert seed(0, 1) == 1_009_179
    assert seed(42, 3) == 43_027_657


def test_rails_manifest_accepts_hook_trail(tmp_path: Path) -> None:
    write_worker(
        tmp_path,
        0,
        [
            {"name": "AlphaTest#test_one", "status": "pass"},
            {"name": "LocaleVictimTest#test_expects_english_greeting", "status": "fail"},
        ],
    )
    completed = manifest(tmp_path)
    assert completed.returncode == 0, completed.stderr
    document = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert document["run_id"] == "rails-run"
    assert document["master_seed"] == 7
    assert document["worker_count"] == 1
    assert "worker-0.jsonl" in document["trails"]


def test_rails_replay_prints_single_process_command(tmp_path: Path) -> None:
    write_worker(
        tmp_path,
        2,
        [
            {"name": "AlphaTest#test_one"},
            {"name": "BetaTest#test_two"},
        ],
        srand_seed=43_027_657,
    )
    manifest(tmp_path)
    completed = run_replay(["replay", "--manifest", str(tmp_path / "manifest.json"), "--worker", "2"])
    assert completed.returncode == 0, completed.stderr
    tokens = shlex.split(completed.stdout.strip())
    assert tokens[0] == "QUEUETRAIL_SRAND=43027657"
    assert tokens[1] == "PARALLEL_WORKERS=1"
    assert tokens[2].startswith("ids=")
    assert shlex.split(completed.stdout.strip())[2].split("=", 1)[1] == "AlphaTest#test_one BetaTest#test_two"
    assert tokens[3:6] == ["ruby", "-r", str(SHIM)]
    assert "rspec" not in tokens
    assert "--order" not in tokens
    workers = [token for token in tokens if token.startswith("PARALLEL_WORKERS=")]
    assert workers == ["PARALLEL_WORKERS=1"]


def test_rails_replay_preserves_recorded_order(tmp_path: Path) -> None:
    write_worker(
        tmp_path,
        1,
        [
            {"name": "LocalePolluterTest#test_sets_french_and_leaves_it"},
            {"name": "LocaleVictimTest#test_expects_english_greeting"},
            {"name": "AlphaTest#test_one"},
        ],
    )
    manifest(tmp_path)
    completed = run_replay(["replay", "--manifest", str(tmp_path / "manifest.json"), "--worker", "1"])
    ids = shlex.split(completed.stdout.strip())[2].split("=", 1)[1]
    assert ids.split() == [
        "LocalePolluterTest#test_sets_french_and_leaves_it",
        "LocaleVictimTest#test_expects_english_greeting",
        "AlphaTest#test_one",
    ]


def test_rails_replay_rejects_sha_mismatch(tmp_path: Path) -> None:
    path = write_worker(tmp_path, 1, [{"name": "AlphaTest#test_one"}])
    manifest(tmp_path)
    path.write_bytes(path.read_bytes() + b"\n")
    completed = run_replay(["replay", "--manifest", str(tmp_path / "manifest.json"), "--worker", "1"])
    assert completed.returncode != 0
    assert "mismatch" in completed.stderr


def test_rails_replay_refuses_parallel_workers_above_one(tmp_path: Path) -> None:
    write_worker(tmp_path, 4, [{"name": "AlphaTest#test_one"}])
    manifest(tmp_path)
    completed = run_replay(["replay", "--manifest", str(tmp_path / "manifest.json"), "--worker", "4"])
    assert completed.returncode == 0, completed.stderr
    assert re.search(r"PARALLEL_WORKERS=[2-9]", completed.stdout) is None
    assert "PARALLEL_WORKERS=1" in completed.stdout


def test_rails_handoff_ids_file_prefix_and_victim(tmp_path: Path) -> None:
    write_worker(
        tmp_path,
        3,
        [
            {"name": "AlphaTest#test_one"},
            {"name": "LocalePolluterTest#test_sets_french_and_leaves_it"},
            {"name": "LocaleVictimTest#test_expects_english_greeting"},
            {"name": "ZetaTest#test_zeta_six"},
        ],
    )
    manifest(tmp_path)
    out = tmp_path / "handoff.json"
    completed = run_replay(
        [
            "handoff",
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--worker",
            "3",
            "--victim",
            "LocaleVictimTest#test_expects_english_greeting",
            "--out",
            str(out),
        ]
    )
    assert completed.returncode == 0, completed.stderr
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["candidate_ids"] == [
        "AlphaTest#test_one",
        "LocalePolluterTest#test_sets_french_and_leaves_it",
    ]
    assert document["ids_file"] == (
        "AlphaTest#test_one\n"
        "LocalePolluterTest#test_sets_french_and_leaves_it\n"
        "LocaleVictimTest#test_expects_english_greeting\n"
    )
    assert document["worker_num"] == 3
    assert document["victim"] == "LocaleVictimTest#test_expects_english_greeting"


def test_rails_handoff_adapter_gap_unproven(tmp_path: Path) -> None:
    write_worker(tmp_path, 0, [{"name": "LocaleVictimTest#test_expects_english_greeting"}])
    manifest(tmp_path)
    completed = run_replay(
        [
            "handoff",
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--worker",
            "0",
            "--victim",
            "LocaleVictimTest#test_expects_english_greeting",
        ]
    )
    assert completed.returncode == 0, completed.stderr
    document = json.loads(completed.stdout)
    assert document["kind"] == "queuetrail-rails-candidate"
    assert document["adapter_gap"] == "UNPROVEN"
    assert document["reason"] == REASON
    assert document["candidate_ids"] == []
    assert "certify_rspec" in document["reason"]
    assert "minitest" in document["reason"]
    assert "Class#method" in document["reason"]


def test_rails_reverse_check_passes() -> None:
    completed = subprocess.run(
        ["python3", str(CHECK), "--gem", str(GEM), "--expect", str(EXPECT)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    for obs_id in ("R-Q1", "R-Q2", "R-Q3", "R-Q4", "R-Q5", "R-Q6", "R-Q7"):
        assert f"{obs_id} PASS" in completed.stdout


def test_fixture_declares_en_and_fr_locales() -> None:
    pair = ROOT / "fixtures" / "rails-parallel-pair"
    en = (pair / "config" / "locales" / "en.yml").read_text(encoding="utf-8")
    fr = (pair / "config" / "locales" / "fr.yml").read_text(encoding="utf-8")
    polluter = (pair / "test" / "locale_polluter_test.rb").read_text(encoding="utf-8")
    application = (pair / "config" / "application.rb").read_text(encoding="utf-8")

    def greeting(text: str) -> str:
        for line in text.splitlines():
            if line.strip().startswith("greeting:"):
                return line.split(":", 1)[1].strip()
        raise AssertionError("locale file has no greeting")

    assert re.search(r"(?m)^en:\s*$", en)
    assert re.search(r"(?m)^fr:\s*$", fr)
    assert greeting(en) == "Hello"
    assert greeting(fr) == "Bonjour"
    assert greeting(en) != greeting(fr)
    assert re.search(r"I18n\.locale\s*=\s*:fr\b", polluter)
    assert "config.i18n.available_locales = [:en, :fr]" in application
    assert 'require "active_support/railtie"' in application


def test_rails_reverse_check_rejects_wrong_sha256(tmp_path: Path) -> None:
    expect = json.loads(EXPECT.read_text(encoding="utf-8"))
    expect["target_sha256"] = "0" * 64
    forged = tmp_path / "observations.json"
    forged.write_text(json.dumps(expect), encoding="utf-8")
    completed = subprocess.run(
        ["python3", str(CHECK), "--gem", str(GEM), "--expect", str(forged)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "SHA FAIL" in completed.stdout
    assert "R-Q1 PASS" not in completed.stdout


def test_spec_every_rr_cites_an_observation() -> None:
    text = SPEC.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^## RR(\d+)\b", text)
    found = {}
    # re.split keeps the captured number between sections: [pre, num, body, num, body, ...]
    it = iter(parts[1:])
    for number, body in zip(it, it):
        found[number] = body
    assert list(found) == ["1", "2", "3", "4", "5", "6"]
    for number, body in found.items():
        assert re.search(r"R-Q[1-6]", body), f"RR{number} has no observation citation"


def test_spec_sha256_matches_frozen_sums() -> None:
    digest = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    line = f"{digest}  ../../docs/QUEUETRAIL-RAILS-SPEC.md"
    assert line in SUMS.read_text(encoding="utf-8").splitlines()


def test_order_shim_reads_ids_env() -> None:
    text = SHIM.read_text(encoding="utf-8")
    assert 'ENV.fetch("ids"' in text
    assert 'ENV.fetch("ids_file"' in text
    assert "run_all_suites" in text
    assert "PARALLEL_WORKERS=4" not in text
    assert "fork" not in text


def test_hook_does_not_require_rails() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "require \"activesupport\"" not in text
    assert "require \"minitest\"" not in text
    assert "require \"rails\"" not in text
    assert "parallelize_setup" in text
    assert "perform_job" in text


def test_hook_trail_round_trip_matches_manifest() -> None:
    script = textwrap.dedent(
        f"""
        require "json"
        require "tmpdir"
        dir = Dir.mktmpdir("qtr-round", "/var/tmp")
        ENV["QUEUETRAIL_DIR"] = dir
        ENV["QUEUETRAIL_MASTER_SEED"] = "0"
        ENV["QUEUETRAIL_RUN_ID"] = "round"
        module ActiveSupport
          class TestCase
            def self.parallelize_setup(&block)
              @hooks ||= []
              @hooks << block
            end
            def self.hooks
              @hooks || []
            end
          end
          module Testing
            class Parallelization
              class Worker
                def initialize
                  @queue = Class.new do
                    def record(_reporter, result); end
                  end.new
                end
                def perform_job(job)
                  @queue.record(job[2], job[0].new(job[1]).run)
                  "(idle)"
                end
              end
            end
          end
        end
        module Minitest
          def self.seed
            7
          end
        end
        class AlphaTest
          def initialize(method)
            @method = method
          end
          def run
            result = Object.new
            def result.skipped?; false; end
            def result.error?; false; end
            def result.passed?; true; end
            result
          end
        end
        require {str(HOOK)!r}
        ActiveSupport::TestCase.hooks.each {{ |hook| hook.call(0) }}
        ActiveSupport::Testing::Parallelization::Worker.new.perform_job([AlphaTest, "test_one", nil])
        puts dir
        """
    )
    completed = subprocess.run(["ruby", "-e", script], text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    directory = Path(completed.stdout.strip().splitlines()[-1])
    try:
        manifest_run = manifest(directory)
        assert manifest_run.returncode == 0, manifest_run.stderr
        replay = run_replay(["replay", "--manifest", str(directory / "manifest.json"), "--worker", "0"])
        assert replay.returncode == 0, replay.stderr
        ids = shlex.split(replay.stdout.strip())[2].split("=", 1)[1]
        assert ids == "AlphaTest#test_one"
        assert "PARALLEL_WORKERS=1" in replay.stdout
    finally:
        for path in directory.iterdir():
            path.unlink()
        directory.rmdir()
