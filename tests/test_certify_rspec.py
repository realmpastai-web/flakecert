"""Unit tests for the RSpec certificate rules. No docker, no live suite."""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

from tools.certify_rspec.brittle import brittle_verdict
from tools.certify_rspec.certificate import LABELS, VERDICTS, validate_certificate
from tools.certify_rspec.classify import BRITTLE, ORDER_DEPENDENT, OTHER, classify_discovered, classify_s2, predecessors
from tools.certify_rspec.ddmin import DdminError, one_minimal
from tools.certify_rspec.exit_rule import classification_exit_ok
from tools.certify_rspec.pipeline_g2 import example_stem
from tools.certify_rspec.seeds import primary_seed, union_failing
from tools.certify_rspec.commands import ORDERING_REQUIRE, spec_commands
from tools.certify_rspec.order_guard import INVALID_ORDER, ORDER_OK, order_by_rank, order_guard, rank_of
from tools.certify_rspec.parse_rspec import (
    parse_bisect,
    parse_documentation,
    polluter_ids,
)
from tools.certify_rspec.replay import replay_cert, write_replay_script
from tools.certify_rspec.verdict import (
    CERTIFIED,
    CONTROL,
    DISAGREEMENT,
    FIXED,
    NOT_FIXED,
    POLLUTER_FAILED,
    REJECTED,
    UNRESOLVED,
    judge,
    signature,
)

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "certify_rspec" / "canned_failure.log"
ROOT = Path(__file__).resolve().parents[1]


def _run(failed: bool, error: str | None = "TypeError", order=None, failed_ids=None):
    if order is None:
        order = ["./spec/p.rb[1:1]", "./spec/v.rb[1:1]"]
    if failed_ids is None:
        failed_ids = ["./spec/v.rb[1:1]"] if failed else []
    return {
        "exit_code": 1 if failed else 0,
        "example_count": len(order),
        "failure_count": len(failed_ids),
        "first_error_class": error if failed else None,
        "first_error_message_line": "boom" if failed else None,
        "log_sha256": "ab" * 32,
        "failed_ids": failed_ids,
        "order": order,
    }


def _arm(failed: bool, error: str | None = "TypeError"):
    return [_run(failed, error), _run(failed, error), _run(failed, error)]


def _sides(base_failed: bool, head_failed: bool, c_failed: bool = False, mutate=None):
    base = {"A": _arm(base_failed), "B": _arm(False, None), "C": _arm(c_failed, "TypeError" if c_failed else None)}
    head = {"A": _arm(head_failed), "B": _arm(False, None), "C": _arm(c_failed, "TypeError" if c_failed else None)}
    if mutate:
        mutate(base, head)
    return base, head


VICTIM = "./spec/v.rb[1:1]"
POLLUTER = "./spec/p.rb[1:1]"
EVIDENCE = ROOT / "evidence" / "certify-rspec-g1"


def _judge(base, head, victim=VICTIM, polluters=None):
    if polluters is None:
        polluters = [POLLUTER]
    return judge(base, head, victim, polluters)


class ClassifyTests(unittest.TestCase):
    def test_order_dependent_only_when_s1_fail_and_three_passes(self):
        self.assertEqual(classify_s2(True, [True, True, True]), ORDER_DEPENDENT)
        self.assertEqual(classify_s2(True, [True, True, False]), OTHER)
        self.assertEqual(classify_s2(True, [False, False, False]), OTHER)
        self.assertEqual(classify_s2(False, [True, True, True]), OTHER)
        self.assertEqual(classify_s2(True, [True, True]), OTHER)

    def test_predecessors_keep_s1_order_and_drop_failures(self):
        examples = [
            {"id": "a", "status": "passed"},
            {"id": "b", "status": "failed"},
            {"id": "c", "status": "pending"},
            {"id": "v", "status": "failed"},
            {"id": "d", "status": "passed"},
        ]
        self.assertEqual(predecessors(examples, "v"), ["a", "c"])


class VerdictTests(unittest.TestCase):
    def test_certified_when_base_fails_head_passes_and_swap_passes(self):
        base, head = _sides(True, False)
        judged = _judge(base, head)
        self.assertEqual(judged["label"], CERTIFIED)
        self.assertEqual(judged["verdicts"]["base"], NOT_FIXED)
        self.assertEqual(judged["verdicts"]["head"], FIXED)
        self.assertEqual(judged["plain_retry_verdict"]["base"], FIXED)
        self.assertFalse(judged["rep_disagreement"])

    def test_rep_disagreement_blocks_certified(self):
        def mutate(base, head):
            base["A"][2] = _run(False, None)

        base, head = _sides(True, False, mutate=mutate)
        judged = _judge(base, head)
        self.assertEqual(judged["verdicts"]["base"], DISAGREEMENT)
        self.assertEqual(judged["label"], UNRESOLVED)
        self.assertTrue(judged["rep_disagreement"])

    def test_error_class_disagreement(self):
        def mutate(base, head):
            base["A"][1] = _run(True, "RuntimeError")

        base, head = _sides(True, False, mutate=mutate)
        judged = _judge(base, head)
        self.assertEqual(judged["verdicts"]["base"], DISAGREEMENT)
        self.assertNotEqual(judged["label"], CERTIFIED)

    def test_order_disagreement(self):
        def mutate(base, head):
            changed = _run(True)
            changed["order"] = list(reversed(changed["order"]))
            base["A"][0] = changed

        base, head = _sides(True, False, mutate=mutate)
        judged = _judge(base, head)
        self.assertEqual(judged["verdicts"]["base"], DISAGREEMENT)
        self.assertTrue(judged["rep_disagreement"])

    def test_control_when_not_fixed_at_both(self):
        base, head = _sides(True, True)
        judged = _judge(base, head)
        self.assertEqual(judged["label"], CONTROL)
        self.assertEqual(judged["verdicts"]["base"], NOT_FIXED)
        self.assertEqual(judged["verdicts"]["head"], NOT_FIXED)

    def test_invalid_order_is_not_a_pass_or_a_fail(self):
        def mutate(base, head):
            for side in (base, head):
                for run in side["C"]:
                    run["exit_code"] = 0
                    run["failure_count"] = 0
                    run["failed_ids"] = []
                    run["first_error_class"] = None
                    run["order_status"] = INVALID_ORDER

        base, head = _sides(True, False, mutate=mutate)
        judged = _judge(base, head)
        self.assertFalse(judged["c_passes"])
        self.assertEqual(judged["label"], UNRESOLVED)
        self.assertNotEqual(judged["verdicts"]["base"], "PASS")
        self.assertNotEqual(judged["verdicts"]["base"], "FAIL")

    def test_swap_failure_is_not_certified(self):
        base, head = _sides(True, False, c_failed=True)
        judged = _judge(base, head)
        self.assertEqual(judged["label"], UNRESOLVED)
        self.assertFalse(judged["c_passes"])

    def test_signature_leaves_the_message_out(self):
        first = _run(True)
        second = _run(True)
        second["first_error_message_line"] = first["first_error_message_line"] + " different"
        self.assertNotEqual(first["first_error_message_line"], second["first_error_message_line"])
        self.assertEqual(signature(first), signature(second))
        flat = " ".join(str(part) for part in signature(first))
        self.assertNotIn(first["first_error_message_line"], flat)

    def test_polluter_failure_is_rejected(self):
        def mutate(base, head):
            for run in base["A"]:
                run["failed_ids"] = [POLLUTER]

        base, head = _sides(True, False, mutate=mutate)
        judged = _judge(base, head)
        self.assertEqual(judged["verdicts"]["base"], POLLUTER_FAILED)
        self.assertEqual(judged["verdicts"]["head"], FIXED)
        self.assertEqual(judged["label"], REJECTED)

    def test_one_polluter_rep_rejects(self):
        def mutate(base, head):
            base["A"][0]["failed_ids"] = [POLLUTER]

        base, head = _sides(True, False, mutate=mutate)
        judged = _judge(base, head)
        self.assertEqual(judged["verdicts"]["base"], POLLUTER_FAILED)
        self.assertEqual(judged["label"], REJECTED)
        self.assertTrue(judged["rep_disagreement"])

    def test_victim_plus_other_id_is_not_fixed(self):
        def mutate(base, head):
            for run in base["A"]:
                run["failed_ids"] = [VICTIM, "./spec/other.rb[1:1]"]

        base, head = _sides(True, False, mutate=mutate)
        judged = _judge(base, head)
        self.assertEqual(judged["verdicts"]["base"], DISAGREEMENT)
        self.assertEqual(judged["label"], UNRESOLVED)

    def test_canned_g1_runs(self):
        expected = {
            1: CERTIFIED,
            2: CERTIFIED,
            3: CERTIFIED,
            4: REJECTED,
            5: CERTIFIED,
            6: CONTROL,
        }
        for index, label in expected.items():
            cert = json.loads((EVIDENCE / f"cert-{index}.json").read_text(encoding="utf-8"))
            judged = judge(
                cert["runs"]["base"],
                cert["runs"]["head"],
                cert["victim_id"],
                cert["polluter_ids"],
            )
            self.assertEqual(judged["label"], label, index)
            if index in (1, 2, 3, 5):
                self.assertEqual(judged["verdicts"]["base"], NOT_FIXED)
                self.assertEqual(judged["verdicts"]["head"], FIXED)
                failed = [tuple(run["failed_ids"]) for run in cert["runs"]["base"]["A"]]
                self.assertEqual(failed, [tuple([cert["victim_id"]])] * 3)
            if index == 4:
                self.assertEqual(judged["verdicts"]["base"], POLLUTER_FAILED)
                self.assertEqual(judged["verdicts"]["head"], FIXED)
                failed = [tuple(run["failed_ids"]) for run in cert["runs"]["base"]["A"]]
                self.assertEqual(failed, [tuple(cert["polluter_ids"])] * 3)
                self.assertNotEqual(cert["polluter_ids"], [cert["victim_id"]])
                messages = [run["first_error_message_line"] for run in cert["runs"]["base"]["A"]]
                self.assertEqual(len(set(messages)), 3)
            if index == 5:
                messages = [run["first_error_message_line"] for run in cert["runs"]["base"]["A"]]
                self.assertEqual(len(set(messages)), 3)
            if index == 6:
                self.assertEqual(judged["verdicts"]["base"], NOT_FIXED)
                self.assertEqual(judged["verdicts"]["head"], NOT_FIXED)
        self.assertEqual(VERDICTS, {FIXED, NOT_FIXED, DISAGREEMENT, POLLUTER_FAILED, INVALID_ORDER})
        self.assertEqual(LABELS, {CERTIFIED, CONTROL, UNRESOLVED, REJECTED, "BRITTLE_CERTIFIED"})

    def test_rejudged_g1_log_and_replay(self):
        text = (EVIDENCE / "g1.log").read_text(encoding="utf-8")
        self.assertIn("CERTIFIED 4\n", text)
        self.assertIn("REJECTED build_delivery_spec.rb:5\n", text)
        self.assertIn("CONTROL two_step:76\n", text)
        for index in range(1, 5):
            self.assertIn(f"ACCEPTANCE_{index} True", text)
        replay = (EVIDENCE / "replay-check.log").read_text(encoding="utf-8")
        exits = [line for line in replay.splitlines() if line.startswith("replay_exit=")]
        self.assertEqual(exits, ["replay_exit=0"] * 6)
        cert4 = json.loads((EVIDENCE / "cert-4.json").read_text(encoding="utf-8"))
        self.assertEqual(cert4["label"], REJECTED)
        self.assertEqual(cert4["verdicts"]["base"], POLLUTER_FAILED)


class OrderGuardTests(unittest.TestCase):
    def test_swapped_canned_json_is_invalid_order(self):
        path = ROOT / "tests" / "fixtures" / "certify_rspec" / "swapped_order.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        intended = ["./spec/v.rb[1:1]", "./spec/p.rb[1:1]"]
        self.assertEqual(order_guard(data["examples"], intended), INVALID_ORDER)
        self.assertEqual(order_guard(data["examples"], list(reversed(intended))), ORDER_OK)

    def test_rank_uses_descendant_minimum(self):
        ids = ["./spec/v.rb[1:1]", "./spec/p.rb[1:1]"]
        items = [
            {"id": "later", "descendants": [{"id": "./spec/p.rb[1:1]"}]},
            {"id": "earlier", "descendants": [{"descendants": [{"id": "./spec/v.rb[1:1]"}]}]},
            {"id": "unknown", "descendants": [{"id": "./spec/z.rb[1:1]"}]},
        ]
        ordered = [item["id"] for item in order_by_rank(items, ids)]
        self.assertEqual(ordered, ["earlier", "later", "unknown"])
        self.assertEqual(rank_of({"id": "./spec/v.rb[1:1]"}, ids), 0)
        self.assertEqual(rank_of({"id": "./spec/p.rb[1:1]"}, ids), 1)
        self.assertEqual(rank_of({"id": "missing"}, ids), 2)

    def test_require_file_registers_global_order_from_env_ids(self):
        text = (ROOT / "tools" / "certify_rspec" / "ordering.rb").read_text(encoding="utf-8")
        self.assertIn("register_ordering(:global)", text)
        self.assertIn('ENV.fetch("ids"', text)
        self.assertIn('ENV.fetch("ids_file"', text)
        self.assertIsNone(re.search(r"custom|ErrorHandlerMiddleware|on_exception|RegistryFixtures|clear!", text))


class CommandTests(unittest.TestCase):
    def test_a_then_b_then_swapped_c(self):
        commands = spec_commands(7, ["./spec/p.rb[1:1]"], "./spec/v.rb[1:1]")
        self.assertEqual(
            commands["A"],
            ["rspec", "--seed", "7", "./spec/p.rb[1:1]", "./spec/v.rb[1:1]"],
        )
        self.assertEqual(commands["B"], ["rspec", "./spec/v.rb[1:1]"])
        self.assertEqual(
            commands["C"],
            ["rspec", "--require", ORDERING_REQUIRE, "./spec/v.rb[1:1]", "./spec/p.rb[1:1]"],
        )
        self.assertNotIn("--order", commands["C"])


class ParseTests(unittest.TestCase):
    def test_canned_log_fixture(self):
        text = FIXTURE.read_text(encoding="utf-8")
        outcome = parse_documentation(text, 1)
        self.assertEqual(outcome["example_count"], 1)
        self.assertEqual(outcome["failure_count"], 1)
        self.assertEqual(outcome["first_error_class"], "TypeError")
        self.assertEqual(outcome["first_error_message_line"], "need a client")
        self.assertEqual(outcome["failed_ids"], ["./spec/victim_spec.rb:1"])

    def test_bisect_repro_expands_grouped_ids(self):
        text = (
            'Bisect started\n'
            "The minimal reproduction command is:\n"
            r"  rspec ./spec/a_spec.rb\[1:1\] ./spec/b_spec.rb\[1:2,1:3\] --seed 7" + "\n"
        )
        parsed = parse_bisect(text)
        self.assertTrue(parsed["attributed"])
        self.assertEqual(
            parsed["ids"],
            ["./spec/a_spec.rb[1:1]", "./spec/b_spec.rb[1:2]", "./spec/b_spec.rb[1:3]"],
        )
        self.assertEqual(
            polluter_ids(parsed["ids"], "./spec/b_spec.rb[1:3]"),
            ["./spec/a_spec.rb[1:1]", "./spec/b_spec.rb[1:2]"],
        )

    def test_ordering_abort_is_unattributed(self):
        text = "Bisect failed!\n\nThe example ordering is inconsistent. `--bisect` relies upon consistent ordering.\n"
        parsed = parse_bisect(text)
        self.assertFalse(parsed["attributed"])
        self.assertEqual(parsed["reason"], "ordering abort")

    def test_no_failure_is_unattributed(self):
        parsed = parse_bisect("Bisect failed!\n\nNo failures found. Bisect only works when something fails.\n")
        self.assertFalse(parsed["attributed"])
        self.assertEqual(parsed["reason"], "no failure")


def _sample_cert(tmp: Path) -> dict:
    outcome = parse_documentation(FIXTURE.read_text(encoding="utf-8"), 1)
    outcome["log_sha256"] = "cd" * 32
    run = dict(outcome)
    run["exec_argv"] = ["bash", "-c", f"cat {FIXTURE}; exit 1"]
    runs = {"base": {}, "head": {}}
    for side in ("base", "head"):
        for arm in ("A", "B", "C"):
            reps = []
            for _rep in range(3):
                reps.append(dict(run))
            runs[side][arm] = reps
    passed = dict(run)
    passed["exit_code"] = 0
    passed["failure_count"] = 0
    passed["example_count"] = 1
    passed["first_error_class"] = None
    passed["first_error_message_line"] = None
    passed["failed_ids"] = []
    passed["order"] = []
    passed["exec_argv"] = ["bash", "-c", "printf '%s\\n' '1 example, 0 failures'; exit 0"]
    # B and C are the passing arm in this fixture; A stays the canned failure.
    for side in ("base", "head"):
        runs[side]["B"] = [dict(passed) for _ in range(3)]
        runs[side]["C"] = [dict(passed) for _ in range(3)]
    return {
        "tool": {"name": "certify_rspec", "version": "1", "git_sha": "abc"},
        "repo": "example/example",
        "base": {"commit": "a" * 40, "tarball_sha256": "ab" * 32},
        "head": {"commit": "b" * 40, "tarball_sha256": "cd" * 32},
        "image_id": "sha256:" + "e" * 64,
        "ruby": "ruby 3.1.7",
        "bundler": "Bundler version 2.6.9",
        "rspec_core": "3.12.2",
        "gemfile_lock_sha256": {"base": "11" * 32, "head": "22" * 32},
        "seed": 7,
        "victim_id": "./spec/victim_spec.rb[1:1]",
        "polluter_ids": ["./spec/other_spec.rb[1:1]"],
        "commands": {
            "A": "rspec --seed 7 ./spec/other_spec.rb[1:1] ./spec/victim_spec.rb[1:1]",
            "B": "rspec ./spec/victim_spec.rb[1:1]",
            "C": "rspec --order defined ./spec/victim_spec.rb[1:1] ./spec/other_spec.rb[1:1]",
        },
        "runs": runs,
        "verdicts": {"base": "NOT_FIXED", "head": "FIXED"},
        "plain_retry_verdict": {"base": "FIXED", "head": "FIXED"},
        "label": "CERTIFIED",
        "execution": {"mode": "shell"},
    }


class SchemaTests(unittest.TestCase):
    def test_sample_cert_is_valid(self):
        cert = _sample_cert(Path("."))
        self.assertEqual(validate_certificate(cert), [])

    def test_missing_git_sha_and_bad_polluters(self):
        cert = _sample_cert(Path("."))
        del cert["tool"]["git_sha"]
        cert["polluter_ids"] = "nope"
        errors = validate_certificate(cert)
        self.assertTrue(any("git_sha" in item for item in errors))
        self.assertTrue(any("polluter_ids" in item for item in errors))

    def test_brittle_cert_requires_enabler_and_seed_line(self):
        cert = _sample_cert(Path("."))
        cert["kind"] = "BRITTLE"
        cert["label"] = "BRITTLE_CERTIFIED"
        cert["enabler_ids"] = ["./spec/other_spec.rb[1:1]"]
        cert["seed_provenance"] = {"seed": 7, "seeds_failed": [7], "s0": {"seed": 7, "base_failing_ids": ["./spec/victim_spec.rb[1:1]"]}}
        cert["commands"] = {
            "alone": "rspec ./spec/victim_spec.rb[1:1]",
            "enabled": "rspec --order defined ./spec/other_spec.rb[1:1] ./spec/victim_spec.rb[1:1]",
        }
        alone = cert["runs"]["base"]["A"]
        enabled = cert["runs"]["base"]["B"]
        cert["runs"] = {"base": {"alone": alone, "enabled": enabled}, "head": {"alone": alone}}
        self.assertEqual(validate_certificate(cert), [])
        del cert["enabler_ids"]
        self.assertTrue(any("enabler_ids" in item for item in validate_certificate(cert)))

    def test_rejected_label_is_valid(self):
        cert = _sample_cert(Path("."))
        cert["verdicts"] = {"base": "POLLUTER_FAILED", "head": "FIXED"}
        cert["label"] = "REJECTED"
        self.assertEqual(validate_certificate(cert), [])


class ReplayTests(unittest.TestCase):
    def test_replay_sh_round_trip_on_canned_log(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cert = _sample_cert(root)
            # A reprints the canned failure log. B and C print a passing summary.
            cert_path = root / "cert-1.json"
            cert_path.write_text(json.dumps(cert), encoding="utf-8")
            script = root / "replay.sh"
            write_replay_script(script, cert_path, ROOT)
            first = subprocess.run(["bash", str(script)], cwd=ROOT, capture_output=True, check=False)
            second = subprocess.run(["bash", str(script)], cwd=ROOT, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout.decode() + first.stderr.decode())
            self.assertEqual(second.returncode, 0, second.stdout.decode() + second.stderr.decode())
            self.assertIn(b"REPLAY_OK", first.stdout)
            cert["runs"]["base"]["A"][0]["exit_code"] = 0
            cert_path.write_text(json.dumps(cert), encoding="utf-8")
            mismatched = subprocess.run(["bash", str(script)], cwd=ROOT, capture_output=True, check=False)
            self.assertEqual(mismatched.returncode, 1)
            self.assertEqual(replay_cert(cert_path), 1)


class SourceGuardTests(unittest.TestCase):
    def test_package_source_avoids_named_examples(self):
        package = ROOT / "tools" / "certify_rspec"
        text = "\n".join(path.read_text(encoding="utf-8") for path in package.rglob("*.py"))
        for needle in (
            "web" + "hook",
            "capabil" + "ities",
            "profile_" + "spec",
            "two_" + "step",
            ":" + "94",
        ):
            self.assertNotIn(needle, text)


class SeedPickTests(unittest.TestCase):
    def test_most_base_failures_that_all_pass_at_head_smallest_tie(self):
        records = [
            {"seed": 1, "base_failing_ids": ["a"], "head_failing_ids": ["a"]},
            {"seed": 4, "base_failing_ids": ["a", "b"], "head_failing_ids": []},
            {"seed": 2, "base_failing_ids": ["a", "b"], "head_failing_ids": []},
            {"seed": 3, "base_failing_ids": ["a", "b", "c"], "head_failing_ids": ["c"]},
            {"seed": 5, "base_failing_ids": [], "head_failing_ids": []},
        ]
        self.assertEqual(primary_seed(records), 2)
        union = union_failing(records)
        self.assertEqual(
            union,
            [
                {"id": "a", "seeds": [1, 2, 3, 4]},
                {"id": "b", "seeds": [2, 3, 4]},
                {"id": "c", "seeds": [3]},
            ],
        )

    def test_location_comes_from_base_when_head_line_differs(self):
        from tools.certify_rspec.pipeline_g2 import Discovery

        found = Discovery.__new__(Discovery)
        found.locations = {}
        ident = "./spec/shared.rb[1:1]"
        head = [{"id": ident, "file_path": "./spec/shared.rb", "line_number": 107}]
        base = [{"id": ident, "file_path": "./spec/shared.rb", "line_number": 100}]
        found._remember(head, "head")
        found._remember(base, "base")
        self.assertEqual(found.locations[ident], "./spec/shared.rb:100")
        found._remember(
            [{"id": ident, "file_path": "./spec/shared.rb", "line_number": 107}],
            "head",
        )
        self.assertEqual(found.locations[ident], "./spec/shared.rb:100")

    def test_same_line_keeps_distinct_log_stems(self):
        location = "./spec/shared.rb:100"
        first = example_stem(location, "./spec/shared.rb[1:1]")
        second = example_stem(location, "./spec/shared.rb[1:2]")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("spec_shared.rb-100-"))

    def test_no_qualifying_seed(self):
        records = [{"seed": 1, "base_failing_ids": ["a"], "head_failing_ids": ["a"]}]
        self.assertIsNone(primary_seed(records))


class BrittleRuleTests(unittest.TestCase):
    def test_classify_discovered(self):
        self.assertEqual(classify_discovered([True, True, True], False), ORDER_DEPENDENT)
        self.assertEqual(classify_discovered([False, False, False], True), BRITTLE)
        self.assertEqual(classify_discovered([False, False, False], False), OTHER)
        self.assertEqual(classify_discovered([True, False, True], True), OTHER)
        self.assertEqual(classify_discovered([False, False], True), OTHER)

    def test_brittle_certified_and_rejected(self):
        def failed(error="NameError"):
            run = _run(True, error, order=["./spec/v.rb[1:1]"], failed_ids=["./spec/v.rb[1:1]"])
            run["victim_status"] = "failed"
            return run

        def passed():
            run = _run(False, None, order=["./spec/v.rb[1:1]"], failed_ids=[])
            run["victim_status"] = "passed"
            run["example_count"] = 1
            return run

        base_alone = [failed(), failed(), failed()]
        enabled = []
        for _ in range(3):
            run = passed()
            run["order"] = ["./spec/e.rb[1:1]", "./spec/v.rb[1:1]"]
            run["example_count"] = 2
            enabled.append(run)
        head = [passed(), passed(), passed()]
        verdict = brittle_verdict(base_alone, enabled, head, "./spec/v.rb[1:1]")
        self.assertEqual(verdict["label"], "BRITTLE_CERTIFIED")
        self.assertEqual(verdict["error_class"], "NameError")
        base_alone[1] = failed("RuntimeError")
        rejected = brittle_verdict(base_alone, enabled, head, "./spec/v.rb[1:1]")
        self.assertEqual(rejected["label"], "REJECTED")
        self.assertIn("stable failure", rejected["reason"])


class DdminTests(unittest.TestCase):
    def test_one_element_and_two_element_fixtures(self):
        universe = ["a", "b", "c", "d", "e"]
        probes = []

        def contains_c(subset):
            probes.append(list(subset))
            return "c" in subset

        self.assertEqual(one_minimal(universe, contains_c), ["c"])
        self.assertIn(["c"], probes)
        self.assertFalse(contains_c([]))

        def both(subset):
            return "b" in subset and "d" in subset

        found = one_minimal(universe, both)
        self.assertEqual(found, ["b", "d"])
        for index in range(len(found)):
            trial = found[:index] + found[index + 1 :]
            self.assertFalse(both(trial))

    def test_full_set_must_reproduce(self):
        with self.assertRaises(DdminError):
            one_minimal(["a", "b"], lambda subset: False)


class ExitRuleTests(unittest.TestCase):
    def test_settled_labels_and_explained_rejections(self):
        self.assertTrue(
            classification_exit_ok(
                [
                    {"label": "CERTIFIED"},
                    {"label": "CONTROL"},
                    {"label": "BRITTLE_CERTIFIED"},
                    {"label": "REJECTED", "base": "POLLUTER_FAILED"},
                    {"label": "UNATTRIBUTED", "reason": "no failure"},
                ]
            )
        )

    def test_unresolved_and_bare_rejection_are_not_exit_ok(self):
        self.assertFalse(classification_exit_ok([{"label": "UNRESOLVED"}]))
        self.assertFalse(classification_exit_ok([{"label": "REJECTED", "base": "FIXED"}]))
        self.assertFalse(classification_exit_ok([{"label": "UNATTRIBUTED"}]))
        self.assertFalse(classification_exit_ok([{"label": "OTHER"}]))

    def test_g1_rows_stay_settled(self):
        summary = json.loads((EVIDENCE / "summary.json").read_text(encoding="utf-8"))
        labels = [row["label"] for row in summary["rows"]]
        self.assertEqual(labels.count("CERTIFIED"), 4)
        self.assertEqual(labels.count("REJECTED"), 1)
        self.assertEqual(labels.count("CONTROL"), 1)
        self.assertEqual(len(labels), 6)
        self.assertTrue(classification_exit_ok(summary["rows"]))


if __name__ == "__main__":
    unittest.main()
