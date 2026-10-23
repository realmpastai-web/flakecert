"""Offline gates for the clean-room policy model.

Heavy fastlane runs are not part of this module. They are evidence under out/.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.atf20_f6 import FIXED, INCONCLUSIVE, NOT_FIXED, judge_commit, parse_run

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "atf20" / "atf20_hook.rb"
P2_LINE = 'break if stop_on_first_failure && status != "passed"'
P3_LINE = "example.run # in_process"
CORE_SHA = "155b54480f28e2b2813185077fe435c2d663031616360ed3b179a9d6a55d2551"
VICTIM = "./spaceship/spec/connect_api/models/build_beta_detail_spec.rb:5"
POLLUTER = ["./spaceship/spec/connect_api/models/webhook_spec.rb"]


def _run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd or ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _ruby(script: str, hook: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ATF20_HOOK"] = str(hook)
    return subprocess.run(
        ["ruby", str(script)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _mutant_a(source: str) -> str:
    if P2_LINE not in source:
        raise AssertionError("P2 stop line is missing from the harness")
    return source.replace(P2_LINE, "# stop removed", 1)


def _mutant_b(source: str) -> str:
    needle = "      " + P3_LINE + "\n"
    if needle not in source:
        raise AssertionError("in-process call is missing from the harness")
    replacement = (
        "      child = Process.fork do\n"
        "        example.run\n"
        "        exit! 0\n"
        "      end\n"
        "      _pid, status = Process.wait2(child)\n"
        "      raise \"relaunch status #{status.inspect}\" unless status.success?\n"
    )
    return source.replace(needle, replacement, 1)


FAIL_LOG = (
    "Spaceship::ConnectAPI::Webhook\n"
    "  returns all webhooks for an app\n"
    "\n"
    "Spaceship::ConnectAPI::BuildBetaDetail\n"
    "  #get_build_beta_details (FAILED - 1)\n"
    "\n"
    "Failures:\n"
    "\n"
    "  1) example\n"
    "     Failure/Error: example\n"
    "\n"
    "     TypeError:\n"
    "       You need to instantiate this module with test_flight_request_client\n"
    "\n"
    "Finished in 0.1 seconds (files took 0.1 seconds to load)\n"
    "7 examples, 1 failure\n"
    "\n"
    "Failed examples:\n"
    "\n"
    "rspec ./spaceship/spec/connect_api/models/build_beta_detail_spec.rb:5 # victim\n"
    "\n"
    "RSPEC_EXIT:1\n"
)
PASS_LOG = (
    "Spaceship::ConnectAPI::Webhook\n"
    "  returns all webhooks for an app\n"
    "\n"
    "Spaceship::ConnectAPI::BuildBetaDetail\n"
    "  #get_build_beta_details\n"
    "\n"
    "Finished in 0.1 seconds (files took 0.1 seconds to load)\n"
    "7 examples, 0 failures\n"
    "\n"
    "RSPEC_EXIT:0\n"
)
REVERSE_LOG = (
    "Spaceship::ConnectAPI::BuildBetaDetail\n"
    "  #get_build_beta_details\n"
    "\n"
    "Spaceship::ConnectAPI::Webhook\n"
    "  returns all webhooks for an app\n"
    "\n"
    "Finished in 0.1 seconds (files took 0.1 seconds to load)\n"
    "7 examples, 0 failures\n"
    "\n"
    "RSPEC_EXIT:0\n"
)


class Atf20Gates(unittest.TestCase):
    def test_ga_grep_datadog_under_atf20_is_empty(self) -> None:
        proc = _run(["grep", "-ri", "datadog", "atf20"])
        print("G-a exit", proc.returncode)
        print("G-a stdout", proc.stdout)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_gb_no_datadog_ci_in_gemfile_locks(self) -> None:
        locks = sorted(ROOT.rglob("Gemfile.lock"))
        print("G-b repo Gemfile.lock count", len(locks))
        for path in locks:
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("datadog-ci", text, str(path))
        evidence = ROOT / "out" / "gate-gb.txt"
        if not evidence.is_file():
            print("G-b evidence not committed yet")
            return
        text = evidence.read_text(encoding="utf-8")
        print(text)
        hits = [line for line in text.splitlines() if line.startswith("datadog-ci-hits ")]
        self.assertGreaterEqual(len(hits), 2)
        for line in hits:
            self.assertEqual(line, "datadog-ci-hits 0")
        self.assertIn("76eeb3f9352a657fd979ae00e89e49a388729e30", text)
        self.assertIn("148c1c9b4c041b1659ea633f2632dd47eef8cb04", text)

    def test_gd_clopper_pearson(self) -> None:
        proc = _run(["python3.11", "atf20/bound.py"])
        print(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("upper_0_of_20=0.139108", proc.stdout)
        self.assertIn("min_n_for_1pct=299", proc.stdout)

    def test_inputs_sha256sums(self) -> None:
        proc = _run(["sha256sum", "-c", "SHA256SUMS"], cwd=ROOT / "inputs" / "rspec-pins")
        print(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        core = (ROOT / "inputs" / "rspec-pins" / "SHA256SUMS").read_text(encoding="utf-8")
        self.assertIn(CORE_SHA, core)

    def test_p1_default_n_is_20(self) -> None:
        proc = _ruby("tests/atf20_named/p1_default_n_is_20.rb", HOOK)
        print(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("test_p1_default_n_is_20 PASS", proc.stdout)

    def test_p1_atf_n_flag(self) -> None:
        proc = _ruby("tests/atf20_named/p1_atf_n_flag.rb", HOOK)
        print(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("test_p1_atf_n_flag PASS", proc.stdout)

    def test_p2_stops_at_first_failure(self) -> None:
        proc = _ruby("tests/atf20_named/p2_stops_at_first_failure.rb", HOOK)
        print(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("test_p2_stops_at_first_failure PASS", proc.stdout)

    def test_p3_in_process_not_relaunch(self) -> None:
        proc = _ruby("tests/atf20_named/p3_in_process_not_relaunch.rb", HOOK)
        print(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("test_p3_in_process_not_relaunch PASS", proc.stdout)
        self.assertIn("report_wording=Fixed", proc.stdout)
        self.assertNotIn('"verdict": "Fixed"', proc.stdout)

    def test_mutant_a_drop_p2_fails_named_test(self) -> None:
        source = HOOK.read_text(encoding="utf-8")
        mutated = _mutant_a(source)
        self.assertNotIn(P2_LINE, mutated)
        with tempfile.TemporaryDirectory(prefix="atf20-mut-a-") as tmp:
            path = Path(tmp) / "atf20_hook.rb"
            path.write_text(mutated, encoding="utf-8")
            proc = _ruby("tests/atf20_named/p2_stops_at_first_failure.rb", path)
        print("===== G-c mutant_a test_p2_stops_at_first_failure =====")
        print(proc.stdout)
        print(proc.stderr)
        print("mutant_a_exit", proc.returncode)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("test_p2_stops_at_first_failure FAIL", proc.stderr + proc.stdout)

    def test_mutant_b_relaunch_fails_named_test(self) -> None:
        source = HOOK.read_text(encoding="utf-8")
        mutated = _mutant_b(source)
        self.assertNotIn(P3_LINE, mutated)
        with tempfile.TemporaryDirectory(prefix="atf20-mut-b-") as tmp:
            path = Path(tmp) / "atf20_hook.rb"
            path.write_text(mutated, encoding="utf-8")
            proc = _ruby("tests/atf20_named/p3_in_process_not_relaunch.rb", path)
        print("===== G-c mutant_b test_p3_in_process_not_relaunch =====")
        print(proc.stdout)
        print(proc.stderr)
        print("mutant_b_exit", proc.returncode)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("test_p3_in_process_not_relaunch FAIL", proc.stderr + proc.stdout)

    def test_f6_stable_failure_is_not_fixed(self) -> None:
        pair = [parse_run(FAIL_LOG, 1) for _ in range(3)]
        reverse = [parse_run(REVERSE_LOG, 0) for _ in range(3)]
        verdict = judge_commit(
            pair,
            reverse,
            [FAIL_LOG] * 3,
            [REVERSE_LOG] * 3,
            VICTIM,
            POLLUTER,
            "Spaceship::ConnectAPI::Webhook",
            "#get_build_beta_details",
            message_contains="request_client",
        )
        self.assertEqual(verdict, NOT_FIXED)

    def test_f6_stable_pass_is_fixed(self) -> None:
        pair = [parse_run(PASS_LOG, 0) for _ in range(3)]
        reverse = [parse_run(REVERSE_LOG, 0) for _ in range(3)]
        verdict = judge_commit(
            pair,
            reverse,
            [PASS_LOG] * 3,
            [REVERSE_LOG] * 3,
            VICTIM,
            POLLUTER,
            "Spaceship::ConnectAPI::Webhook",
            "#get_build_beta_details",
        )
        self.assertEqual(verdict, FIXED)

    def test_f6_disagreement_is_inconclusive(self) -> None:
        logs = [FAIL_LOG, FAIL_LOG, PASS_LOG]
        pair = [parse_run(item, 1) for item in logs]
        reverse = [parse_run(REVERSE_LOG, 0) for _ in range(3)]
        verdict = judge_commit(
            pair,
            reverse,
            logs,
            [REVERSE_LOG] * 3,
            VICTIM,
            POLLUTER,
            "Spaceship::ConnectAPI::Webhook",
            "#get_build_beta_details",
            message_contains="request_client",
        )
        self.assertEqual(verdict, INCONCLUSIVE)


if __name__ == "__main__":
    unittest.main()
