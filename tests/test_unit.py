import importlib.util
import json
import tempfile
import unittest
from fractions import Fraction
from unittest import mock
from pathlib import Path
from types import SimpleNamespace

from flakecert.cert import check_bound, normalize_traceback, per_run_lower
from flakecert.effective import committed_effective_text, derive, effective_text, load_frozen, load_swaps
from flakecert.parse import find_outcome, interpret
from flakecert.preflight import (
    blob_paths_from_tree,
    classify_paths,
    committed_deps,
    normalise_deps,
    normalise_resolve,
)
from flakecert.scheduler import order_candidates
from flakecert.selectreq import install_requirements, use_pipenv
from flakecert.summary import numeric_tokens


class EffectiveTests(unittest.TestCase):
    def test_matches_committed_file(self):
        self.assertEqual(effective_text(), committed_effective_text())

    def test_counts(self):
        mains, reserves = derive(load_frozen(), load_swaps())
        self.assertEqual(len(mains), 20)
        self.assertEqual(len(reserves), 10)
        self.assertIn("F21", mains)
        self.assertNotIn("F18", mains)
        self.assertNotIn("F31", reserves)
        self.assertNotIn("F21", reserves)


class BoundTests(unittest.TestCase):
    def test_fraction(self):
        self.assertEqual(per_run_lower(6, 5, 1), Fraction(1, 6))
        self.assertEqual(per_run_lower(4, 5, 2), Fraction(1, 20))
        cert = {
            "m": 6,
            "k": 5,
            "d": 1,
            "bound": {
                "per_run_lower": "1/6",
                "formula": "1/(m*k^(d-1))",
                "empirical_runs_to_failure": 4,
                "empirical_rate": "1/4",
                "compare": "empirical>=lower",
            },
        }
        ok, _msg = check_bound(cert)
        self.assertTrue(ok)

    def test_normalize_stable(self):
        raw = "E       assert 1 == 2\n/work/tests/test_foo.py:2: AssertionError\n"
        once = normalize_traceback(raw)
        self.assertEqual(normalize_traceback(once), once)
        self.assertNotIn("/work/", once)


class ParseTests(unittest.TestCase):
    def test_pytest3_unittest_node_id(self):
        from flakecert.parse import match_node

        nodes = [
            "tests/contrib/quizzes/test_question.py::TestQuestion::()::test_add_choices",
        ]
        want = "tests/contrib/quizzes/test_question.py::TestQuestion::test_add_choices"
        self.assertEqual(match_node(want, nodes), nodes[0])
    def test_pytest_verbose_line(self):
        output = "tests/test_gc.py::test_deco_timeout PASSED\n"
        self.assertEqual(find_outcome(output, "tests/test_gc.py::test_deco_timeout"), "passed")

    def test_pytest3_verbose_drops_empty_instance_and_arrow(self):
        output = (
            "tests/optimizers/test_local_best.py::TestLocalBestOptimizer::test_obj_with_kwargs "
            "<- tests/optimizers/abc_test_optimizer.py PASSED [ 69%]\n"
        )
        node = "tests/optimizers/test_local_best.py::TestLocalBestOptimizer::()::test_obj_with_kwargs"
        self.assertEqual(find_outcome(output, node), "passed")

    def test_pytest3_verbose_without_arrow(self):
        output = "tests/contrib/quizzes/test_question.py::TestQuestion::test_add_choices PASSED\n"
        node = "tests/contrib/quizzes/test_question.py::TestQuestion::()::test_add_choices"
        self.assertEqual(find_outcome(output, node), "passed")

    def test_pytest_verbose_percent_and_second_run(self):
        output = (
            "tests/test_gc.py::test_deco_timeout PASSED                                 [ 50%]\n"
            "tests/test_gc.py::test_deco_timeout FAILED                                 [100%]\n"
        )
        self.assertEqual(find_outcome(output, "tests/test_gc.py::test_deco_timeout"), "failed")

    def test_failure_signature_stable(self):
        output = """
=================================== FAILURES ===================================
________________________________ test_foo _________________________________

    def test_foo():
>       assert 1 == 2
E       assert 1 == 2

tests/test_foo.py:2: AssertionError
=========================== short test summary info ============================
FAILED tests/test_foo.py::test_foo - assert 1 == 2
"""
        first = interpret(output, "tests/test_foo.py::test_foo", 1)
        second = interpret(output.replace("/work", "/work"), "tests/test_foo.py::test_foo", 1)
        self.assertEqual(first["outcome"], "failed")
        self.assertEqual(first["exc"], "AssertionError")
        self.assertEqual(first["sig"], second["sig"])
        self.assertNotEqual(first["sig"], "-")


class SelectTests(unittest.TestCase):
    def test_root_filter_and_tests_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("pytest==4\n", encoding="utf-8")
            (root / "requirements-tunnel.txt").write_text("x\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "requirements.txt").write_text("sphinx\n", encoding="utf-8")
            tests = root / "tests"
            tests.mkdir()
            (tests / "requirements.txt").write_text("cov\n", encoding="utf-8")
            (root / "dev-requirements.txt").write_text("flake8\n", encoding="utf-8")
            chosen = [path.name if path.parent == root else path.relative_to(root).as_posix() for path in install_requirements(root)]
            self.assertEqual(
                chosen,
                ["dev-requirements.txt", "requirements.txt", "tests/requirements.txt"],
            )
            self.assertFalse(use_pipenv(root, install_requirements(root)))

    def test_pipenv_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Pipfile").write_text("[packages]\n", encoding="utf-8")
            self.assertTrue(use_pipenv(root, install_requirements(root)))


class PreflightTests(unittest.TestCase):
    def test_classify_matches_logged_shapes(self):
        manifests, reqs = classify_paths(
            [
                "docs/requirements.txt",
                "requirements.txt",
                "setup.py",
                "setup.cfg",
            ]
        )
        self.assertEqual(manifests, ["requirements.txt", "setup.py", "setup.cfg"])
        self.assertEqual(reqs, ["docs/requirements.txt", "requirements.txt"])

    def test_truncated_tree_fails_loudly(self):
        with self.assertRaises(RuntimeError) as raised:
            blob_paths_from_tree(
                {"truncated": True, "tree": [{"path": "setup.py", "type": "blob"}]},
                "example/repo",
                "abc",
            )
        self.assertIn("truncated", str(raised.exception))

    def test_recorded_trees_reproduce_frozen_deps_lines(self):
        frozen = {}
        for line in committed_deps().splitlines():
            ident = line.split(" ", 1)[0]
            if ident in {"F07", "F17", "F25"}:
                frozen[ident] = line
        self.assertEqual(set(frozen), {"F07", "F17", "F25"})
        fixture_dir = Path(__file__).resolve().parent / "fixtures" / "deps-trees"
        for ident in ("F07", "F17", "F25"):
            data = json.loads((fixture_dir / f"{ident}.json").read_text(encoding="utf-8"))
            paths = blob_paths_from_tree(data, data["repo"], data["sha"])
            manifests, reqs = classify_paths(paths)
            got = (
                f"{data['id']} {data['role']} {data['repo']} "
                f"manifests: {manifests} req files: {reqs} "
            )
            self.assertEqual(got.rstrip(), frozen[ident].rstrip())

    def test_normalise_committed_logs(self):
        from flakecert.preflight import committed_deps, committed_resolve

        rows, resolved = normalise_resolve(committed_resolve())
        self.assertEqual(resolved, (31, 32))
        self.assertEqual(len(rows), 32)
        deps = normalise_deps(committed_deps())
        self.assertEqual(len(deps), 32)
        self.assertEqual(deps[0][0], "F01")


class HypothesisSeedTests(unittest.TestCase):
    def test_seed_from_failure_text(self):
        from types import SimpleNamespace

        from flakecert.search import hypothesis_seed

        text = "run pytest with --hypothesis-seed=23459274458492354473232647118670623521 to reproduce"
        self.assertEqual(hypothesis_seed(SimpleNamespace(traceback=text, stdout="")), "23459274458492354473232647118670623521")
        self.assertEqual(hypothesis_seed(SimpleNamespace(traceback="", stdout="")), "")


class RunnerScriptTests(unittest.TestCase):
    def test_offline_pytest_restores_prefix_and_skips_build_isolation(self):
        from flakecert.runner import PYTEST_SCRIPT

        self.assertIn("/opt/fc-py-snap", PYTEST_SCRIPT)
        self.assertIn("os.link", PYTEST_SCRIPT)
        # pip stores this value on dest build_isolation, so false disables it.
        self.assertIn("no-build-isolation = false", PYTEST_SCRIPT)
        self.assertIn("PIP_CONFIG_FILE=/opt/flakecert/pip-offline.conf", PYTEST_SCRIPT)
        self.assertLess(
            PYTEST_SCRIPT.index("FLAKECERT_ENV_RESTORE=1"),
            PYTEST_SCRIPT.index("run_pytest.py"),
        )


class SchedulerTests(unittest.TestCase):
    def test_orders_include_alone_and_double(self):
        orders = order_candidates("tests/a.py::t", ["tests/a.py::t", "tests/a.py::u"], [])
        self.assertIn(["tests/a.py::t"], orders)
        self.assertIn(["tests/a.py::t", "tests/a.py::t"], orders)
        self.assertIn(["tests/a.py::u", "tests/a.py::t"], orders)


class NumberTests(unittest.TestCase):
    def test_tokens(self):
        self.assertEqual(numeric_tokens("rate=2/100 ci=0.500000"), ["2/100", "0.500000"])


def _verify_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "verify.py"
    spec = importlib.util.spec_from_file_location("flakecert_verify_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReplayReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = _verify_module()

    def test_three_matching_runs_keep_the_matched_record(self):
        runs = [{"ok": True, "sig": "abc", "outcome": "failed", "exc": "E"}] * 3
        record = self.v._replay_record_from_runs(runs)
        self.assertEqual(record, {"matched": "3/3", "runs": runs})
        self.assertEqual(self.v._replay_say("C01", record), "replay C01 3/3")

    def test_real_mismatch_stays_a_fraction(self):
        runs = [{"ok": False, "sig": "no", "outcome": "passed", "exc": ""}] * 3
        record = self.v._replay_record_from_runs(runs)
        self.assertEqual(record["matched"], "0/3")
        self.assertNotIn("status", record)
        self.assertEqual(self.v._replay_say("C01", record), "replay C01 0/3")

    def test_incomplete_replay_is_not_a_fraction(self):
        record = self.v._replay_record_from_runs(
            [{"ok": False, "detail": "digest_mismatch", "sig": "-"}]
        )
        line = self.v._replay_say("C01", record)
        self.assertEqual(record["status"], "unavailable")
        self.assertIsNone(record["pass"])
        self.assertIn("NOT_RUN", line)
        self.assertNotIn("/3", line)

    def test_exception_is_not_a_fraction(self):
        record = self.v._replay_unavailable("Error: No such image: flakecert:C01")
        line = self.v._replay_say("C01", record)
        self.assertIsNone(record["pass"])
        self.assertEqual(record["status"], "unavailable")
        self.assertIn("NOT_RUN", line)
        self.assertNotIn("/3", line)
        self.assertIn("No such image", line)

    def test_skip_pass_is_null(self):
        record = self.v._replay_skip_record()
        gate = self.v._certificates_gate(True, ["C00"], [], [], {})
        self.assertEqual(record["status"], "skip")
        self.assertIsNone(record["pass"])
        self.assertIsNone(gate["pass"])
        self.assertEqual(gate["status"], "skip")
        self.assertNotIn("/3", self.v._replay_say("C01", record))
        self.assertNotEqual(gate["pass"], True)

    def test_full_gate_threshold_is_ten_completed_replays(self):
        ids = [f"C{i:02d}" for i in range(10)]
        paths = [SimpleNamespace(stem=item) for item in ids]
        actual = {item: {"matched": "3/3", "runs": []} for item in ids}
        gate = self.v._certificates_gate(False, list(ids), [], paths, actual)
        self.assertTrue(gate["pass"])
        self.assertEqual(gate["actual"], "10/20")
        self.assertNotIn("status", gate)
        short = ids[:-1]
        short_gate = self.v._certificates_gate(
            False,
            list(short),
            [],
            paths[:-1],
            {item: actual[item] for item in short},
        )
        self.assertFalse(short_gate["pass"])
        self.assertEqual(short_gate["actual"], "9/20")
        missing = dict(actual)
        missing[ids[-1]] = {"status": "unavailable", "pass": None, "detail": "missing image"}
        missing_gate = self.v._certificates_gate(False, ids[:-1], [], paths, missing)
        self.assertFalse(missing_gate["pass"])
        self.assertIn("NOT_RUN", missing_gate["actual"])
        self.assertNotIn("0/3", missing_gate["actual"])

    def test_skip_does_not_fail_the_run_and_a_true_skip_does(self):
        gates = {
            "frozen_hash": {"pass": True},
            "certificates": {"pass": None, "status": "skip", "actual": "SKIP live replay not run"},
        }
        checks = {
            "d_resolve_preflight": {"status": "skip", "pass": False, "actual": "SKIP --offline"},
            "e_cert_replay": {"pass": None, "status": "skip", "actual": {}},
        }
        self.assertEqual(self.v._failures(gates, checks), [])
        gates["certificates"]["pass"] = True
        self.assertEqual(self.v._failures(gates, checks), ["certificates"])

    def test_offline_write_does_not_target_a_committed_online_report(self):
        online = {
            "checks": {
                "d_resolve_preflight": {
                    "status": "match",
                    "pass": True,
                    "actual": "RESOLVED 31/32; deps 32 rows",
                }
            }
        }
        offline_report = {
            "checks": {
                "d_resolve_preflight": {
                    "status": "skip",
                    "pass": False,
                    "actual": "SKIP --offline",
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            evidence.mkdir()
            report = evidence / "verify-report.json"
            report.write_text(json.dumps(online), encoding="utf-8")
            log_path = evidence / "verify.log"
            with (
                mock.patch.object(self.v, "VERIFY_REPORT", report),
                mock.patch.object(self.v, "VERIFY_LOG", log_path),
            ):
                self.assertTrue(self.v._committed_preflight_is_online())
                got_log, got_report, protected = self.v._evidence_write_paths(True)
                self.assertTrue(protected)
                self.assertEqual(got_report, evidence / "offline" / "verify-report.json")
                self.assertEqual(got_log, evidence / "offline" / "verify.log")
                self.assertNotEqual(got_report.resolve(), report.resolve())
                plain_log, plain_report, plain_protected = self.v._evidence_write_paths(False)
                self.assertFalse(plain_protected)
                self.assertEqual(plain_report, report)
                self.assertEqual(plain_log, log_path)
                report.write_text(json.dumps(offline_report), encoding="utf-8")
                self.assertFalse(self.v._committed_preflight_is_online())
                same_log, same_report, same_protected = self.v._evidence_write_paths(True)
                self.assertFalse(same_protected)
                self.assertEqual(same_report, report)
                self.assertEqual(same_log, log_path)

    def test_other_check_failures_still_fail(self):
        gates = {"frozen_hash": {"pass": False, "actual": "no"}}
        checks = {
            "e_cert_replay": {"pass": False, "actual": {}},
            "g_ledger_logs": {"pass": False, "actual": "missing"},
        }
        self.assertEqual(self.v._failures(gates, checks), ["frozen_hash", "g_ledger_logs"])

    def test_rebuilt_image_with_the_same_freeze_replays(self):
        from flakecert.util import freeze_sha

        freeze = "pytest==9.1.1\n"
        cert = {
            "id": "F01",
            "image_tag": "flakecert:F01",
            "image_digest": "sha256:original-local-id",
            "pip_freeze_sha": freeze_sha(freeze),
            "python": "3.11.17",
            "node_id": "tests/test_foo.py::test_foo",
            "pytest_args": ["-v"],
            "schedule": [{"source": "order", "value": ["tests/test_foo.py::test_foo"]}],
            "expected_failure": {"sig": "sig-same", "exc": "AssertionError"},
        }
        seen = {}

        def image_id(_tag):
            raise AssertionError("image digest is informational and must not be read")

        def pip_freeze(tag):
            seen["tag"] = tag
            # A rebuild returns a new image id and the same freeze text.
            return freeze

        def live_python(_tag):
            return "3.11.17"

        class FakeSession:
            def __init__(self, test_id, image_tag, memory="1536m"):
                seen["session"] = (test_id, image_tag)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def run_schedule(_session, node_id, schedule, args, timeout):
            seen["node_id"] = node_id
            seen["schedule"] = schedule
            seen["args"] = args
            seen["timeout"] = timeout
            return SimpleNamespace(outcome="failed", sig="sig-same", exc="AssertionError")

        with (
            mock.patch.object(self.v, "image_id", image_id, create=True),
            mock.patch.object(self.v, "pip_freeze", pip_freeze),
            mock.patch.object(self.v, "python_version", live_python),
            mock.patch.object(self.v, "Session", FakeSession),
            mock.patch.object(self.v, "run_schedule", run_schedule),
        ):
            runs = self.v._replay(cert)
        record = self.v._replay_record_from_runs(runs)
        self.assertEqual(len(runs), 3)
        self.assertTrue(all(item["ok"] for item in runs))
        self.assertEqual(record["matched"], "3/3")
        self.assertEqual(self.v._replay_say("F01", record), "replay F01 3/3")
        self.assertEqual(seen["node_id"], cert["node_id"])
        self.assertEqual(seen["schedule"]["order"], ["tests/test_foo.py::test_foo"])
        self.assertEqual(seen["session"], ("F01", "flakecert:F01"))

    def test_changed_freeze_is_not_run_pip_freeze_mismatch(self):
        from flakecert.util import freeze_sha

        cert = {
            "id": "F08",
            "image_tag": "flakecert:F08",
            "image_digest": "sha256:rebuilt-different",
            "pip_freeze_sha": freeze_sha("pytest==9.1.1\n"),
            "python": "3.11.17",
            "node_id": "tests/functional_test.py::test_version[runnable2]",
            "pytest_args": ["-v"],
            "schedule": [{"source": "order", "value": ["n"]}],
            "expected_failure": {"sig": "sig", "exc": "FileNotFoundError"},
        }

        def pip_freeze(_tag):
            return "pytest==9.9.9\n"

        def live_python(_tag):
            raise AssertionError("freeze mismatch stops before python and replay")

        class FakeSession:
            def __init__(self, *args, **kwargs):
                raise AssertionError("session must not start")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with (
            mock.patch.object(self.v, "pip_freeze", pip_freeze),
            mock.patch.object(self.v, "python_version", live_python),
            mock.patch.object(self.v, "Session", FakeSession),
        ):
            runs = self.v._replay(cert)
        record = self.v._replay_record_from_runs(runs)
        line = self.v._replay_say("F08", record)
        self.assertEqual(runs, [{"ok": False, "detail": "pip_freeze_mismatch", "sig": "-"}])
        self.assertEqual(record["status"], "unavailable")
        self.assertIsNone(record["pass"])
        self.assertIn("NOT_RUN", line)
        self.assertIn("pip_freeze_mismatch", line)
        self.assertNotIn("/3", line)


class RspecRunnerTests(unittest.TestCase):
    def test_srand_hook_is_one_line(self):
        from flakecert.runners.rspec import SRAND_LINE, SRAND_PATH

        text = SRAND_PATH.read_text(encoding="utf-8")
        self.assertEqual(text.strip(), SRAND_LINE)
        self.assertEqual(text.count("\n"), 1)

    def test_schedule_command_pins_order_and_srand_require(self):
        from flakecert.runners.rspec import rspec_argv

        self.assertEqual(
            rspec_argv(7, 3),
            [
                "bundle",
                "exec",
                "rspec",
                "--order",
                "rand:7",
                "--require",
                "/flakecert/srand.rb",
                "--format",
                "json",
                "--out",
                "/out/7-3.json",
            ],
        )

    def test_baseline_command_does_not_pin_order_or_srand(self):
        from flakecert.runners.rspec import baseline_argv

        argv = baseline_argv("/out/baseline.json")
        self.assertEqual(argv[:4], ["bundle", "exec", "rspec", "--format"])
        self.assertNotIn("--order", argv)
        self.assertNotIn("--require", argv)

    def test_parse_examples_keeps_id_and_status(self):
        from flakecert.runners.rspec import parse_examples

        payload = {
            "version": "3.13.6",
            "seed": 4,
            "examples": [
                {"id": "./spec/models/cart_spec.rb[1:1]", "status": "failed", "run_time": 0.01},
                {"id": "./spec/models/cart_spec.rb[1:2]", "status": "passed"},
            ],
        }
        self.assertEqual(
            parse_examples(payload, 4),
            {
                "./spec/models/cart_spec.rb[1:1]": "failed",
                "./spec/models/cart_spec.rb[1:2]": "passed",
            },
        )

    def test_seed_mismatch_aborts(self):
        from flakecert.runners.rspec import SeedMismatch, parse_examples

        payload = {"seed": 2, "examples": [{"id": "a", "status": "passed"}]}
        with self.assertRaises(SeedMismatch) as raised:
            parse_examples(payload, 1)
        self.assertEqual(raised.exception.expected, 1)
        self.assertEqual(raised.exception.actual, 2)
        with self.assertRaises(SeedMismatch):
            parse_examples({"examples": [{"id": "a", "status": "passed"}]}, 0)

    def test_certificate_carries_lock_digest_schedule_and_replay(self):
        from flakecert.cert import check_bound
        from flakecert.runners.rspec import build_rspec_certificate

        lock = "ab" * 32
        digest = "sha256:" + ("cd" * 32)
        cert = build_rspec_certificate(
            node_id="./spec/models/cart_spec.rb[1:1]",
            image_digest=digest,
            image_tag="flakecert-rspec:sample",
            lock_sha256=lock,
            ruby_version="ruby 3.3.12",
            order_seed=3,
            srand_seed=9,
            exc="RSpec::Expectations::ExpectationNotMetError",
            sig="abc",
            runs_to_failure=4,
            k=100,
        )
        self.assertEqual(cert["lock_sha256"], lock)
        self.assertEqual(cert["image_digest"], digest)
        self.assertEqual(cert["schedule"], {"order_seed": 3, "srand_seed": 9})
        self.assertEqual(cert["d"], 2)
        self.assertNotIn("pip_freeze_sha", cert)
        self.assertIn("FLAKECERT_SRAND=9", cert["replay"])
        self.assertIn("--order rand:3", cert["replay"])
        self.assertIn("--require /flakecert/srand.rb", cert["replay"])
        ok, msg = check_bound(cert)
        self.assertTrue(ok, msg)

    def test_jenkins_port_matches_ruby_gem_digests(self):
        # Three digests from rspec-core 3.13.6 Random#jenkins_hash_digest
        # (ordering.rb:39-56), computed in the pinned ruby image. The strings
        # are seed.to_s + example id, the input at ordering.rb:29.
        import importlib.util

        from flakecert.runners.rspec import ROOT

        recorded = (
            ("0./spec/models/cart_spec.rb[1:1]", 3135682379),
            ("0./spec/models/cart_spec.rb[1:2]", 1088897018),
            ("42./spec/models/coupon_spec.rb[1:2]", 1108510911),
        )
        path = ROOT / "inputs" / "flakecert-rspec-runner" / "predict_order.py"
        spec = importlib.util.spec_from_file_location("predict_order_frozen", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for text, digest in recorded:
            self.assertEqual(module.jenkins(text), digest)


if __name__ == "__main__":
    unittest.main()
