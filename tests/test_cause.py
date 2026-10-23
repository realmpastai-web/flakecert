"""S6 selection, S8 stop rules, and the cause_set schema. No docker."""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

from tools.certify_rspec.cause import (
    CAP_REACHED,
    EXPLAINED,
    G2_OK_LINE,
    UNCONFIRMED,
    UNREPRODUCED,
    format_polluter_line,
    format_residual_line,
    format_seed_line,
    recompute_certificate_label,
    reproduction,
    search_cause,
    select_residual,
    victim_token_matches,
)
from tools.certify_rspec.certificate import validate_cause_set, validate_certificate
from tools.certify_rspec.commands import ORDERING_REQUIRE, ordered_ids, ordered_spec_commands
from tools.certify_rspec.order_guard import INVALID_ORDER, ORDER_OK

ROOT = Path(__file__).resolve().parents[1]


def _example(ident: str, status: str, klass: str | None = None) -> dict:
    item = {"id": ident, "status": status}
    if klass is not None:
        item["exception"] = {"class": klass}
    return item


class ResidualSelectionTests(unittest.TestCase):
    def test_failed_victim_before_every_known_polluter_keeps_prefix_order(self):
        victim = "./spec/v.rb[1:1]"
        polluter = "./spec/p.rb[1:1]"
        examples = [
            _example("./spec/a.rb[1:1]", "passed"),
            _example("./spec/b.rb[1:1]", "failed"),
            _example(victim, "failed", "Boom"),
            _example(polluter, "passed"),
        ]
        found = select_residual(examples, victim, [polluter])
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found["candidate_ids"], ["./spec/a.rb[1:1]", "./spec/b.rb[1:1]"])
        self.assertEqual(found["victim_index"], 2)
        self.assertEqual(found["polluter_indexes"], [3])
        self.assertEqual(found["error_class"], "Boom")

    def test_victim_after_a_known_polluter_is_not_residual(self):
        victim = "./spec/v.rb[1:1]"
        polluter = "./spec/p.rb[1:1]"
        examples = [
            _example(polluter, "passed"),
            _example(victim, "failed", "Boom"),
        ]
        self.assertIsNone(select_residual(examples, victim, [polluter]))

    def test_passed_victim_is_not_residual(self):
        victim = "./spec/v.rb[1:1]"
        polluter = "./spec/p.rb[1:1]"
        examples = [
            _example("./spec/a.rb[1:1]", "passed"),
            _example(victim, "passed"),
            _example(polluter, "passed"),
        ]
        self.assertIsNone(select_residual(examples, victim, [polluter]))

    def test_victim_must_precede_every_polluter(self):
        victim = "./spec/v.rb[1:1]"
        first = "./spec/p.rb[1:1]"
        second = "./spec/q.rb[1:1]"
        between = [
            _example("./spec/a.rb[1:1]", "passed"),
            _example(first, "passed"),
            _example(victim, "failed", "Boom"),
            _example(second, "passed"),
        ]
        self.assertIsNone(select_residual(between, victim, [first, second]))
        after = [
            _example("./spec/a.rb[1:1]", "passed"),
            _example(victim, "failed", "Boom"),
            _example(second, "passed"),
            _example(first, "passed"),
        ]
        found = select_residual(after, victim, [first, second])
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found["candidate_ids"], ["./spec/a.rb[1:1]"])
        self.assertEqual(found["polluter_indexes"], [3, 2])

    def test_missing_polluter_is_not_before_every_polluter(self):
        victim = "./spec/v.rb[1:1]"
        examples = [
            _example("./spec/a.rb[1:1]", "passed"),
            _example(victim, "failed", "Boom"),
        ]
        self.assertIsNone(select_residual(examples, victim, ["./spec/p.rb[1:1]"]))

    def test_id_prefix_is_ignored_when_matching(self):
        examples = [
            _example("./spec/a.rb[1:1]", "passed"),
            _example("./spec/v.rb[1:1]", "failed", "Boom"),
            _example("./spec/p.rb[1:1]", "passed"),
        ]
        found = select_residual(examples, "spec/v.rb[1:1]", ["spec/p.rb[1:1]"])
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found["candidate_ids"], ["./spec/a.rb[1:1]"])


class ReproductionTests(unittest.TestCase):
    def test_same_class_under_a_guarded_order(self):
        self.assertTrue(reproduction(ORDER_OK, "failed", "Boom", "Boom"))

    def test_rejects_bad_order_pass_class_mismatch_and_empty_expected(self):
        self.assertFalse(reproduction(INVALID_ORDER, "failed", "Boom", "Boom"))
        self.assertFalse(reproduction(ORDER_OK, "passed", "Boom", "Boom"))
        self.assertFalse(reproduction(ORDER_OK, "failed", "Other", "Boom"))
        self.assertFalse(reproduction(ORDER_OK, "failed", "", ""))


class CauseSearchTests(unittest.TestCase):
    def test_probe_zero_miss_is_unreproduced_and_stops(self):
        calls = []

        def run(ids, phase, round_index):
            calls.append((list(ids), phase, round_index))
            return {"reproduced": False}

        found = search_cause(["a", "b"], run)
        self.assertEqual(found["status"], UNREPRODUCED)
        self.assertEqual(found["sets"], [])
        self.assertEqual(len(found["rounds"]), 1)
        self.assertEqual(calls, [(["a", "b"], "probe", 1)])

    def test_one_set_then_a_miss_is_explained_when_round_one_is_three_of_three(self):
        first = {}

        def run(ids, phase, round_index):
            first.setdefault((round_index, phase), list(ids))
            return {"reproduced": "p" in ids}

        found = search_cause(["a", "p", "b"], run)
        self.assertEqual(found["status"], EXPLAINED)
        self.assertEqual(found["sets"], [["p"]])
        self.assertEqual(found["rounds"][0]["confirmed"], [True, True, True])
        self.assertEqual(first[(1, "probe")], ["a", "p", "b"])
        self.assertEqual(first[(2, "probe")], ["a", "b"])
        self.assertNotIn("p", first[(2, "probe")])
        self.assertEqual(len(found["rounds"]), 2)

    def test_three_rounds_stop_at_the_cap(self):
        seen = set()

        def run(ids, phase, round_index):
            seen.add(round_index)
            return {"reproduced": any(item.startswith("p") for item in ids)}

        found = search_cause(["p1", "p2", "p3", "tail"], run)
        self.assertEqual(found["status"], CAP_REACHED)
        self.assertEqual(found["sets"], [["p1"], ["p2"], ["p3"]])
        self.assertEqual(seen, {1, 2, 3})
        self.assertEqual(len(found["rounds"]), 3)
        self.assertNotIn(4, seen)

    def test_failed_confirmation_is_not_explained(self):
        confirmations = {"n": 0}

        def run(ids, phase, round_index):
            if phase == "confirm":
                confirmations["n"] += 1
                return {"reproduced": confirmations["n"] != 1}
            return {"reproduced": "p" in ids}

        found = search_cause(["a", "p"], run)
        self.assertEqual(found["status"], UNCONFIRMED)
        self.assertEqual(found["rounds"][0]["confirmed"], [False, True, True])
        self.assertEqual(found["sets"], [["p"]])


class CauseSchemaTests(unittest.TestCase):
    def _good(self) -> dict:
        return {
            "polluter_ids": ["./spec/p.rb[1:1]"],
            "verdicts": {"base": "NOT_FIXED", "head": "FIXED"},
            "seed_provenance": {"seeds": [4, 2]},
            "replay": "replay-1.sh",
        }

    def test_empty_list_and_a_complete_entry(self):
        self.assertEqual(validate_cause_set([]), [])
        self.assertEqual(validate_cause_set([self._good()]), [])

    def test_missing_polluters_seeds_replay_and_verdict(self):
        for key, value in (
            ("polluter_ids", []),
            ("replay", ""),
            ("verdicts", {"base": "NOT_FIXED", "head": "MAYBE"}),
            ("seed_provenance", {"seeds": []}),
        ):
            item = self._good()
            item[key] = value
            errors = validate_cause_set([item])
            self.assertTrue(errors, key)
            self.assertTrue(any(key in error or "seeds" in error or "verdicts" in error for error in errors))

    def test_cause_set_on_a_certificate_is_checked(self):
        from tests.test_certify_rspec import _sample_cert

        cert = _sample_cert(ROOT)
        cert["cause_set"] = [self._good()]
        self.assertEqual(validate_certificate(cert), [])
        cert["cause_set"] = [{"polluter_ids": []}]
        errors = validate_certificate(cert)
        self.assertTrue(any(error.startswith("cause_set[0]") for error in errors))


class LineFormatTests(unittest.TestCase):
    def test_required_log_words(self):
        self.assertEqual(format_residual_line("./spec/v.rb[1:1]", [16, 24]), "RESIDUAL_SEEDS ./spec/v.rb[1:1] 16,24")
        self.assertEqual(format_residual_line("./spec/v.rb[1:1]", []), "RESIDUAL_SEEDS ./spec/v.rb[1:1]")
        self.assertEqual(
            format_seed_line(16, 1, ["./spec/p.rb[1:1]"], 4, EXPLAINED),
            "SEED 16 ROUND 1 SET ./spec/p.rb[1:1] PROBES 4 STATUS EXPLAINED",
        )
        self.assertEqual(format_seed_line(3, 2, [], 1, UNREPRODUCED), "SEED 3 ROUND 2 SET - PROBES 1 STATUS UNREPRODUCED")
        self.assertEqual(format_polluter_line(["./spec/p.rb[1:1]"], "CERTIFIED"), "NEW_POLLUTERS ./spec/p.rb[1:1] CERTIFIED")
        self.assertEqual(G2_OK_LINE, "G2_LABELS_UNCHANGED, EXIT_OK")

    def test_token_matches_a_stem_and_bracket(self):
        self.assertTrue(victim_token_matches("./spec/dir/foo_spec.rb[1:2:3]", "foo_spec[1:2:3]"))
        self.assertFalse(victim_token_matches("./spec/dir/foo_spec.rb[1:2:3]", "foo_spec[1:9]"))
        self.assertFalse(victim_token_matches("./spec/dir/foo_spec.rb[1:2:3]", "other[1:2:3]"))


class OrderedArmTests(unittest.TestCase):
    def test_all_three_arms_use_the_ordering_require(self):
        commands = ordered_spec_commands(["./spec/p.rb[1:1]"], "./spec/v.rb[1:1]")
        self.assertEqual(
            commands["A"],
            ["rspec", "--require", ORDERING_REQUIRE, "./spec/p.rb[1:1]", "./spec/v.rb[1:1]"],
        )
        self.assertEqual(commands["B"], ["rspec", "--require", ORDERING_REQUIRE, "./spec/v.rb[1:1]"])
        self.assertEqual(
            commands["C"],
            ["rspec", "--require", ORDERING_REQUIRE, "./spec/v.rb[1:1]", "./spec/p.rb[1:1]"],
        )
        self.assertEqual(ordered_ids("A", ["./spec/p.rb[1:1]"], "./spec/v.rb[1:1]"), ["./spec/p.rb[1:1]", "./spec/v.rb[1:1]"])
        self.assertEqual(ordered_ids("C", ["./spec/p.rb[1:1]"], "./spec/v.rb[1:1]"), ["./spec/v.rb[1:1]", "./spec/p.rb[1:1]"])


class AcceptanceGuardTests(unittest.TestCase):
    def test_package_source_misses_the_g22_pattern(self):
        spec = (ROOT / "inputs" / "dryrun-2026-10-19-g2-2" / "SPEC-G2-2.md").read_text(encoding="utf-8")
        match = re.search(r"grep -RInE '([^']+)'", spec)
        self.assertIsNotNone(match)
        assert match is not None
        proc = subprocess.run(
            ["grep", "-RInE", match.group(1), "tools/certify_rspec"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stdout, "")


class PriorLabelTests(unittest.TestCase):
    def test_recorded_g2_labels_recompute(self):
        prior = ROOT / "evidence" / "certify-rspec-g2"
        summary = json.loads((prior / "summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["exit_ok"])
        for row in summary["rows"]:
            cert = json.loads((prior / row["cert"]).read_text(encoding="utf-8"))
            self.assertEqual(recompute_certificate_label(cert), row["label"])
            self.assertEqual(cert["label"], row["label"])


if __name__ == "__main__":
    unittest.main()
