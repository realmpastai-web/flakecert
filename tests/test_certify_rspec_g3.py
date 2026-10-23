"""Unit tests for the G3 helpers. No live GitLab run."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import unittest
from pathlib import Path

from tools.certify_rspec.g3lib import (
    HEADLINE_RE,
    absence_needle,
    bisect_command,
    armf_verdict,
    armg_pass_armf_fail,
    bound_headline,
    cert_verdict,
    check_script_rel,
    classify_category_a,
    clopper_pearson_upper,
    counts_as_setup_failure,
    first_commit,
    format_percent,
    is_env_failure,
    minimal_enablers,
    next_resume_seed,
    parse_excluded,
    resolve_images,
    resume_action,
    resume_plan,
    same_file,
    seed_finished,
    seed_timeout_s,
    select_s20,
    sha256_file,
    should_stop_setup,
    sibling_names,
    sum_for,
    summarize_rspec,
    target_examples_passed,
    todo_relpath,
)

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "inputs" / "dryrun-2026-10-19-g3"


class BoundTests(unittest.TestCase):
    def test_zero_failure_table(self):
        expected = {5: "45.07%", 10: "25.89%", 30: "9.50%", 59: "4.95%", 299: "1.00%"}
        for trials, percent in expected.items():
            self.assertEqual(format_percent(clopper_pearson_upper(0, trials)), percent)

    def test_positive_failures_sit_above_the_point_rate(self):
        bound = clopper_pearson_upper(1, 30)
        self.assertGreater(bound, 1 / 30)
        self.assertLess(bound, 1)

    def test_headline_and_verdicts(self):
        commit = "a" * 40
        line = bound_headline(0, 30, 1, 30, commit)
        self.assertRegex(line, HEADLINE_RE)
        self.assertTrue(line.startswith("0 failures in 30 seeded runs -> failure rate <= 9.50%"))
        self.assertEqual(armf_verdict(0), "BOUNDED_CLEAN")
        self.assertEqual(armf_verdict(2), "CERTIFIED_ORDER_DEPENDENT")
        failed = bound_headline(2, 30, 1, 30, commit)
        self.assertRegex(failed, HEADLINE_RE)


class SampleTests(unittest.TestCase):
    def test_s20_keeps_foss_models_and_lib_only(self):
        todo = "\n".join(
            [
                "---",
                "- './ee/spec/models/hidden_spec.rb'",
                "- './spec/controllers/nope_spec.rb'",
                "- './spec/models/b_spec.rb'",
                "- './spec/lib/a_spec.rb'",
                "- './spec/models/c_spec.rb'",
            ]
        )
        chosen = select_s20(todo, limit=2)
        self.assertEqual(len(chosen), 2)
        self.assertTrue(all(path.startswith("./spec/") for path in chosen))
        digests = [hashlib.sha256(path.encode()).hexdigest() for path in chosen]
        self.assertEqual(digests, sorted(digests))

    def test_excluded_rows(self):
        description = """
```yaml
- spec/models/one_spec.rb # batch-001 Category A: setup failure
- spec/services/two_spec.rb # batch-001 Category B1: reverse-order failure
- spec/lib/three_spec.rb # batch-002 Category A: setup failure
```
"""
        parsed = parse_excluded([description])
        self.assertEqual(
            parsed["category_a"],
            ["spec/models/one_spec.rb", "spec/lib/three_spec.rb"],
        )
        self.assertEqual(parsed["b1"], ["spec/services/two_spec.rb"])


class LabelTests(unittest.TestCase):
    def test_category_labels(self):
        self.assertEqual(classify_category_a(True, False, False, False), "PASSES_ALONE")
        self.assertEqual(classify_category_a(False, True, False, True), "ENABLER_CERTIFIED")
        self.assertEqual(classify_category_a(False, True, False, False), "UNRESOLVED")
        self.assertEqual(classify_category_a(False, False, True, False), "ENV_FAILURE")
        self.assertEqual(classify_category_a(False, False, False, False), "UNRESOLVED")

    def test_env_failure_is_structural(self):
        self.assertTrue(is_env_failure(0, 1, "", "boom"))
        self.assertTrue(is_env_failure(2, 1, "LoadError", "cannot load such file"))
        self.assertFalse(
            is_env_failure(1, 1, "RSpec::Expectations::ExpectationNotMetError", "expected 1")
        )
        self.assertTrue(is_env_failure(1, 1, "RuntimeError", "helper not running"))

    def test_cross_arm_list(self):
        rows = [
            {"path": "./spec/lib/a_spec.rb", "arm_g_pass": True, "arm_f_failures": 0},
            {"path": "./spec/lib/b_spec.rb", "arm_g_pass": True, "arm_f_failures": 2},
            {"path": "./spec/models/c_spec.rb", "arm_g_pass": False, "arm_f_failures": 4},
        ]
        self.assertEqual(armg_pass_armf_fail(rows), ["./spec/lib/b_spec.rb"])

    def test_same_file_and_target_pass(self):
        target = "spec/lib/a_spec.rb"
        self.assertTrue(same_file(["./spec/lib/a_spec.rb[1:1]", "spec/lib/a_spec.rb[1:2]"], target))
        self.assertFalse(same_file(["./spec/lib/b_spec.rb[1:1]"], target))
        summary = summarize_rspec(
            {
                "summary": {"example_count": 2, "failure_count": 0},
                "examples": [
                    {"id": "./spec/lib/a_spec.rb[1:1]", "file_path": "./spec/lib/a_spec.rb", "status": "passed"},
                    {"id": "./spec/lib/b_spec.rb[1:1]", "file_path": "./spec/lib/b_spec.rb", "status": "failed",
                     "exception": {"class": "RuntimeError", "message": "nope"}},
                ],
            },
            1,
        )
        self.assertTrue(target_examples_passed(summary, target))
        self.assertEqual(summary["failure_count"], 0)
        self.assertEqual(summary["error_class"], "RuntimeError")

    def test_ddmin_keeps_one_enabler(self):
        def test(subset):
            return "b" in subset

        self.assertEqual(minimal_enablers(["a", "b", "c"], test), ["b"])


class SpecParseTests(unittest.TestCase):
    def test_frozen_spec_parses_without_naming_subjects_in_the_helper(self):
        spec = (INPUTS / "SPEC-G3.md").read_text(encoding="utf-8")
        amended = (INPUTS / "SPEC-G3.1.md").read_text(encoding="utf-8")
        self.assertEqual(len(first_commit(spec)), 40)
        self.assertTrue(check_script_rel(spec).startswith("scripts/"))
        needle = absence_needle(amended)
        self.assertTrue(needle[:1].isupper())
        helper = (ROOT / "tools" / "certify_rspec" / "g3lib.py").read_text(encoding="utf-8")
        pipeline = (ROOT / "tools" / "certify_rspec" / "pipeline_g3.py").read_text(encoding="utf-8")
        for source in (helper, pipeline):
            self.assertNotIn(needle, source)
            self.assertNotIn("Category A", source)
            self.assertNotIn("delete_service_spec", source)

    def test_todo_assignment_and_images(self):
        script = "TODO_YAML='./spec/support/rspec_order_todo.yml'\n"
        self.assertEqual(todo_relpath(script), "./spec/support/rspec_order_todo.yml")
        version = """
variables:
  BUILD_OS: "debian"
  OS_VERSION: "trixie"
  RUBY_VERSION_DEFAULT: "3.3.12"
  GO_VERSION: "1.26"
  NODE_VERSION: "22.23"
  PYTHON_VERSION: "3.12"
  RUBYGEMS_VERSION: "3.6"
  GIT_VERSION: "2.51"
  LFS_VERSION: "3.7"
  CHROME_VERSION: "151"
  YARN_VERSION: "1.22"
  GRAPHICSMAGICK_VERSION: "1.3.36"
  POETRY_VERSION: "2.2"
"""
        gitlab_ci = (INPUTS / "reverse" / "gitlab-ci-8004fe1c.yml").read_text(encoding="utf-8")
        global_ci = (INPUTS / "reverse" / "global.gitlab-ci-8004fe1c.yml").read_text(encoding="utf-8")
        images = resolve_images(version, gitlab_ci, global_ci)
        self.assertIn("slim-ruby-3.3.12", images["ci_image"])
        self.assertTrue(images["postgres_image"].endswith(":postgres-17"))
        self.assertEqual(images["redis_image"], "redis:7.2-alpine")
        self.assertTrue(images["redis_cluster_image"].endswith(":redis-cluster-7.0.11"))
        self.assertIn("fsync=off", images["postgres_command"])

    def test_bisect_rerun_line(self):
        text = "Bisect complete!\nRerun with: bin/rspec --seed 3 spec/lib/a_spec.rb[1:1]\n"
        self.assertEqual(bisect_command(text), "bin/rspec --seed 3 spec/lib/a_spec.rb[1:1]")

    def test_sibling_order_is_sorted(self):
        self.assertEqual(sibling_names(["b_spec.rb", "a_spec.rb", "notes.md"]), ["a_spec.rb", "b_spec.rb"])


class ResumeTests(unittest.TestCase):
    def test_skip_only_when_clean_sha_matches(self):
        digest = "ab" * 32
        other = "cd" * 32
        self.assertEqual(resume_action("BOUNDED_CLEAN", digest, digest), "skip_verified")
        self.assertEqual(resume_action("BOUNDED_CLEAN", digest, other), "sha_mismatch")
        self.assertEqual(resume_action("BOUNDED_CLEAN", digest, None), "sha_mismatch")
        self.assertEqual(resume_action("INCOMPLETE", digest, digest), "run")
        text = "0 failures in 30 seeded runs -> failure rate <= 9.50% (one-sided 95%, Clopper-Pearson); seeds=1..30; commit=" + ("a" * 40) + "\nBOUNDED_CLEAN\n{}\n"
        self.assertEqual(cert_verdict(text), "BOUNDED_CLEAN")
        sums = f"{digest}  certificates/example.txt\n"
        self.assertEqual(sum_for(sums, "certificates/example.txt"), digest)

    def test_unfinished_seed_is_the_timeout(self):
        metas = {
            1: {"exit_code": 0, "timeout": False, "passed": True},
            2: {"exit_code": 0, "timeout": False, "passed": True},
            3: {"exit_code": 0, "passed": True},
            4: {"exit_code": 124, "timeout": True, "passed": False, "elapsed_s": 159.445},
        }
        self.assertTrue(seed_finished(metas[1]))
        self.assertFalse(seed_finished(metas[4]))
        self.assertEqual(next_resume_seed(metas), 4)
        self.assertIsNone(
            next_resume_seed({seed: {"exit_code": 0, "timeout": False} for seed in range(1, 31)})
        )

    def test_seed_timeout_is_three_times_arm_g_at_least_300(self):
        self.assertEqual(seed_timeout_s(0), 300)
        self.assertEqual(seed_timeout_s(39.768), 300)
        self.assertEqual(seed_timeout_s(100), 300)
        self.assertEqual(seed_timeout_s(721.66), 2165)
        self.assertGreaterEqual(seed_timeout_s(721.66), math.ceil(3 * 721.66))

    def test_two_setup_failures_stop_and_a_timeout_does_not_count(self):
        self.assertFalse(counts_as_setup_failure(0, 124, "", "", timeout=True))
        self.assertTrue(counts_as_setup_failure(0, 1, "", ""))
        self.assertFalse(
            counts_as_setup_failure(
                1,
                1,
                "RSpec::Expectations::ExpectationNotMetError",
                "expected 1",
            )
        )
        self.assertFalse(should_stop_setup(1))
        self.assertTrue(should_stop_setup(2))

    def test_resume_order_runs_unfinished_before_unstarted(self):
        rows = [
            {"path": "./spec/a_spec.rb", "verdict": "BOUNDED_CLEAN", "cert": "certificates/a.txt", "arm_f_trials": 30},
            {
                "path": "./spec/b_spec.rb",
                "verdict": "INCOMPLETE",
                "cert": "certificates/b.txt",
                "arm_f_trials": 3,
                "arm_g_log": "arm-g/b.log",
            },
            {"path": "./spec/c_spec.rb", "verdict": "NOT_RUN", "cert": "", "arm_f_trials": 0},
            {"path": "./spec/d_spec.rb", "verdict": "NOT_RUN", "cert": "", "arm_f_trials": 0},
        ]
        plan = resume_plan(rows)
        self.assertEqual(plan["skip"], ["./spec/a_spec.rb"])
        self.assertEqual(plan["continue"], ["./spec/b_spec.rb"])
        self.assertEqual(plan["later"], ["./spec/c_spec.rb", "./spec/d_spec.rb"])

    def test_resumed_evidence_keeps_verified_certs(self):
        evidence = ROOT / "evidence" / "certify-rspec-g3"
        summary = json.loads((evidence / "summary.json").read_text(encoding="utf-8"))
        plan = resume_plan(summary["s20"])
        self.assertEqual([row["verdict"] for row in summary["s20"]].count("BOUNDED_CLEAN"), 5)
        self.assertEqual(len(plan["skip"]), 5)
        self.assertEqual(len(plan["continue"]), 2)
        self.assertEqual(len(plan["later"]), 13)
        sums = (evidence / "SHA256SUMS").read_text(encoding="utf-8")
        verified = [row for row in summary["s20"] if row.get("sha256_verified")]
        self.assertEqual(len(verified), 3)
        for row in verified:
            cert = evidence / row["cert"]
            actual = sha256_file(cert)
            self.assertEqual(actual, row["sha256_verified"])
            self.assertEqual(sum_for(sums, row["cert"]), actual)
            self.assertEqual(cert_verdict(cert.read_text(encoding="utf-8")), "BOUNDED_CLEAN")
            self.assertEqual(resume_action("BOUNDED_CLEAN", actual, actual), "skip_verified")
        run_log = (evidence / "run.log").read_text(encoding="utf-8")
        finished = []
        for row in summary["s20"]:
            needle = (
                "END rc=124 elapsed_s=159.4 log=evidence/certify-rspec-g3/arm-f/"
                + row["slug"]
                + "/seed-04.log"
            )
            if needle in run_log:
                finished.append(row)
        self.assertEqual(len(finished), 1)
        row = finished[0]
        self.assertEqual(row["verdict"], "BOUNDED_CLEAN")
        self.assertEqual(row["arm_f_failures"], 0)
        self.assertEqual(row["arm_f_trials"], 30)
        self.assertNotIn("sha256_verified", row)
        meta = json.loads((evidence / "arm-f" / row["slug"] / "seed-04.meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["exit_code"], 0)
        self.assertFalse(meta["timeout"])
        self.assertIn("RESUME rerun unfinished seed=4 log=seed-04.log", run_log)
        self.assertIn("END rc=0 elapsed_s=98.0 log=evidence/certify-rspec-g3/arm-f/" + row["slug"] + "/seed-04.log", run_log)
        pipeline = (ROOT / "tools" / "certify_rspec" / "pipeline_g3.py").read_text(encoding="utf-8")
        helper = (ROOT / "tools" / "certify_rspec" / "g3lib.py").read_text(encoding="utf-8")
        for source in (pipeline, helper):
            self.assertNotIn("blame_spec", source)
            self.assertNotIn("board_spec", source)
            self.assertIn("--resume" if source is pipeline else "resume_action", source)

    def test_acceptance_grep_on_tools_is_all_misses(self):
        evidence = ROOT / "evidence" / "certify-rspec-g3"
        names = []
        for filename in ("s20.txt", "cat_a.txt", "b1.txt"):
            names.extend((evidence / filename).read_text(encoding="utf-8").splitlines())
        self.assertGreaterEqual(len([name for name in names if name]), 20)
        for name in names:
            if not name:
                continue
            proc = subprocess.run(
                ["grep", "-RInF", "-e", name, "tools"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1, name)
            self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
