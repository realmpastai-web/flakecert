import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flakecert.cert import failure_signature, normalize_traceback
from flakecert.ingest import (
    PINNED_SAMPLE_SHA,
    SHA_ENV_ORDER,
    ingest_paths,
    parse_report,
    resolve_sha,
)
from flakecert.summary import preserve_ingest_section, readme_text

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "docs" / "inputs" / "flakecert-ingest" / "samples"
SAMPLE_SHA = PINNED_SAMPLE_SHA
FORBIDDEN = re.compile(r'"(seed|image_digest|pip_freeze_sha|bound)"')

FLAKY = {
    "pytest-junit": "test_sample::test_flaky_seeded",
    "jest-junit": "sample.test.js::flaky seeded",
    "gotestsum-junit": "example.com/flakecertsample/TestFlakySeeded",
    "buildkite-collector-json": "test_sample.py::test_flaky_seeded",
}
DETERMINISTIC = {
    "pytest-junit": "test_sample::test_fail_deterministic",
    "jest-junit": "sample.test.js::fail deterministic",
    "gotestsum-junit": "example.com/flakecertsample/TestFailDeterministic",
    "buildkite-collector-json": "test_sample.py::test_fail_deterministic",
}
RERUNS = (
    ("pytest-junit-seed1.xml", "pytest-junit-seed1-rerun.xml", "pytest-junit"),
    ("jest-junit-seed1.xml", "jest-junit-seed1-rerun.xml", "jest-junit"),
    ("gotestsum-junit-seed2.xml", "gotestsum-junit-seed2-rerun.xml", "gotestsum-junit"),
    ("buildkite-collector-seed1.json", "buildkite-collector-seed1-rerun.json", "buildkite-collector-json"),
)


def report_paths() -> list[Path]:
    paths = []
    for pattern in (
        "pytest-junit-*.xml",
        "jest-junit-*.xml",
        "gotestsum-junit-*.xml",
        "buildkite-collector-*.json",
    ):
        paths.extend(sorted(SAMPLES.glob(pattern)))
    return paths


def failure_sig(path: Path, key: str) -> str:
    for row in parse_report(path):
        if row["key"] == key and row["outcome"] == "failed":
            return failure_signature(row["failure_text"])
    raise AssertionError(f"{path.name} has no failure for {key}")


def failure_row(path: Path, key: str) -> dict:
    for row in parse_report(path):
        if row["key"] == key and row["outcome"] == "failed":
            return row
    raise AssertionError(f"{path.name} has no failure for {key}")


def scrubbed_env() -> dict:
    env = os.environ.copy()
    for name in SHA_ENV_ORDER:
        env.pop(name, None)
    return env


def run_ingest(out: Path, reports, extra=None, env=None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(ROOT / "tools" / "ingest.py"), "--out", str(out)]
    if extra:
        cmd.extend(extra)
    cmd.extend(str(path) for path in reports)
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class ParseTests(unittest.TestCase):
    def test_keys_ignore_suite_name_and_collector_id(self):
        pytest_row = failure_row(SAMPLES / "pytest-junit-seed1.xml", FLAKY["pytest-junit"])
        self.assertEqual(pytest_row["format"], "pytest-junit")
        self.assertNotIn("file", pytest_row)
        self.assertNotIn("line", pytest_row)

        jest_row = failure_row(SAMPLES / "jest-junit-seed1.xml", FLAKY["jest-junit"])
        self.assertEqual(jest_row["file"], "sample.test.js")
        self.assertNotIn("undefined", jest_row["key"])
        self.assertNotIn("line", jest_row)

        go_row = failure_row(SAMPLES / "gotestsum-junit-seed2.xml", FLAKY["gotestsum-junit"])
        self.assertEqual(go_row["format"], "gotestsum-junit")
        self.assertNotIn("file", go_row)

        data = json.loads((SAMPLES / "buildkite-collector-seed1.json").read_text(encoding="utf-8"))
        collector_row = failure_row(
            SAMPLES / "buildkite-collector-seed1.json",
            FLAKY["buildkite-collector-json"],
        )
        source = next(item for item in data if item["name"] == "test_flaky_seeded")
        self.assertEqual(collector_row["file"], source["file_name"])
        self.assertEqual(collector_row["line"], int(source["location"].rsplit(":", 1)[1]))
        self.assertEqual(collector_row["duration"], source["history"]["duration"])
        self.assertNotIn(source["id"], collector_row["key"])

    def test_run_env_blob_is_not_a_report(self):
        with self.assertRaises(ValueError):
            parse_report(SAMPLES / "collector-run-env.json")


class NominationTests(unittest.TestCase):
    def test_frozen_samples_nominate_the_four_flaky_keys(self):
        paths = report_paths()
        rows = []
        for path in paths:
            rows.extend(parse_report(path))
        candidates = ingest_paths(paths, sha=SAMPLE_SHA, sha_source="--sha")
        self.assertEqual(
            [item["key"] for item in candidates],
            [
                "example.com/flakecertsample/TestFlakySeeded",
                "sample.test.js::flaky seeded",
                "test_sample.py::test_flaky_seeded",
                "test_sample::test_flaky_seeded",
            ],
        )
        nominated = {item["key"] for item in candidates}
        self.assertTrue(set(FLAKY.values()) <= nominated)
        for key in DETERMINISTIC.values():
            self.assertNotIn(key, nominated)
        for item in candidates:
            matched = [row for row in rows if row["key"] == item["key"]]
            self.assertEqual(item["n_pass"], sum(row["outcome"] == "passed" for row in matched))
            self.assertEqual(item["n_fail"], sum(row["outcome"] == "failed" for row in matched))
            self.assertGreaterEqual(item["n_pass"], 1)
            self.assertGreaterEqual(item["n_fail"], 1)
            self.assertEqual(item["sha"], SAMPLE_SHA)
            self.assertEqual(item["sha_source"], "--sha")
            self.assertEqual(len(item["sig_of_failures"]), item["n_fail"])
            self.assertEqual(len(set(item["sig_of_failures"])), 1)
            self.assertFalse({"seed", "image_digest", "pip_freeze_sha", "bound"} & set(item))

    def test_sha_is_not_taken_from_the_report(self):
        fail = """<?xml version="1.0"?>
<testsuite name="pytest">
  <testcase classname="pkg" name="test_flaky">
    <failure message="bad">commit f711ef3b9426b92e2e73691439bf6d4dbaa6e341</failure>
  </testcase>
</testsuite>
"""
        passed = """<?xml version="1.0"?>
<testsuite name="pytest">
  <testcase classname="pkg" name="test_flaky" time="0.01"/>
</testsuite>
"""
        wanted = "a" * 40
        env = scrubbed_env()
        env["BUILDKITE_COMMIT"] = "b" * 40
        env["CI_COMMIT_SHA"] = "c" * 40
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "fail.xml").write_text(fail, encoding="utf-8")
            (tmp / "pass.xml").write_text(passed, encoding="utf-8")
            out = tmp / "candidates.json"
            proc = run_ingest(
                out,
                [tmp / "fail.xml", tmp / "pass.xml"],
                extra=["--sha", wanted],
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = out.read_text(encoding="utf-8")
        payload = json.loads(text)
        self.assertEqual(payload[0]["sha"], wanted)
        self.assertEqual(payload[0]["sha_source"], "--sha")
        self.assertIsNone(FORBIDDEN.search(text))


class SignatureTests(unittest.TestCase):
    def test_flaky_sig_matches_across_reruns_and_not_the_deterministic_failure(self):
        for fail_name, rerun_name, fmt in RERUNS:
            flaky = FLAKY[fmt]
            det = DETERMINISTIC[fmt]
            left = failure_sig(SAMPLES / fail_name, flaky)
            right = failure_sig(SAMPLES / rerun_name, flaky)
            other = failure_sig(SAMPLES / fail_name, det)
            self.assertEqual(left, right, fmt)
            self.assertNotEqual(left, other, fmt)

    def test_pytest_junit_sig_equals_collector_sig(self):
        pytest_sig = failure_sig(SAMPLES / "pytest-junit-seed1.xml", FLAKY["pytest-junit"])
        collector_sig = failure_sig(
            SAMPLES / "buildkite-collector-seed1.json",
            FLAKY["buildkite-collector-json"],
        )
        self.assertEqual(pytest_sig, collector_sig)

    def test_go_duration_does_not_change_the_sig(self):
        text = failure_row(SAMPLES / "gotestsum-junit-seed2.xml", FLAKY["gotestsum-junit"])["failure_text"]
        changed = text.replace("(0.00s)", "(0.37s)")
        self.assertNotEqual(text, changed)
        self.assertEqual(failure_signature(text), failure_signature(changed))
        once = normalize_traceback(text)
        self.assertEqual(normalize_traceback(once), once)
        self.assertNotIn("(0.00s)", once)
        self.assertIn("(DUR)", once)
        det = failure_row(
            SAMPLES / "gotestsum-junit-seed2.xml",
            DETERMINISTIC["gotestsum-junit"],
        )["failure_text"]
        self.assertNotEqual(failure_signature(text), failure_signature(det))

    def test_repo_root_strips_rewritten_jest_paths(self):
        original = (SAMPLES / "jest-junit-seed1.xml").read_text(encoding="utf-8")
        passed = (SAMPLES / "jest-junit-seed2.xml").read_text(encoding="utf-8")
        self.assertIn("/tmp/ing/proj", original)
        rewritten_fail = original.replace("/tmp/ing/proj", "/home/ci/build")
        rewritten_pass = passed.replace("/tmp/ing/proj", "/home/ci/build")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            orig_fail = tmp / "fail.xml"
            orig_pass = tmp / "pass.xml"
            moved_fail = tmp / "moved-fail.xml"
            moved_pass = tmp / "moved-pass.xml"
            orig_fail.write_text(original, encoding="utf-8")
            orig_pass.write_text(passed, encoding="utf-8")
            moved_fail.write_text(rewritten_fail, encoding="utf-8")
            moved_pass.write_text(rewritten_pass, encoding="utf-8")
            left_out = tmp / "left.json"
            right_out = tmp / "right.json"
            left = run_ingest(
                left_out,
                [orig_fail, orig_pass],
                extra=["--sha", SAMPLE_SHA, "--repo-root", "/tmp/ing/proj"],
            )
            right = run_ingest(
                right_out,
                [moved_fail, moved_pass],
                extra=["--sha", SAMPLE_SHA, "--repo-root", "/home/ci/build"],
            )
            self.assertEqual(left.returncode, 0, left.stderr)
            self.assertEqual(right.returncode, 0, right.stderr)
            left_doc = json.loads(left_out.read_text(encoding="utf-8"))
            right_doc = json.loads(right_out.read_text(encoding="utf-8"))
        self.assertEqual(left_doc[0]["key"], FLAKY["jest-junit"])
        self.assertEqual(left_doc[0]["sig_of_failures"], right_doc[0]["sig_of_failures"])
        original_text = failure_row(SAMPLES / "jest-junit-seed1.xml", FLAKY["jest-junit"])["failure_text"]
        moved_text = original_text.replace("/tmp/ing/proj", "/home/ci/build")
        self.assertEqual(
            normalize_traceback(original_text, repo_root="/tmp/ing/proj"),
            normalize_traceback(moved_text, repo_root="/home/ci/build"),
        )
        self.assertNotEqual(failure_signature(original_text), failure_signature(moved_text))


class ShaSourceTests(unittest.TestCase):
    def test_flag_beats_ci_variables(self):
        env = {"BUILDKITE_COMMIT": "b" * 40, "CI_COMMIT_SHA": "c" * 40}
        sha, source = resolve_sha("a" * 40, env=env)
        self.assertEqual((sha, source), ("a" * 40, "--sha"))

    def test_buildkite_beats_gitlab(self):
        env = {"BUILDKITE_COMMIT": "b" * 40, "CI_COMMIT_SHA": "c" * 40, "GITHUB_SHA": "d" * 40}
        sha, source = resolve_sha(None, env=env)
        self.assertEqual((sha, source), ("b" * 40, "BUILDKITE_COMMIT"))

    def test_gitlab_style_ci_commit_sha(self):
        token = "c" * 40
        sha, source = resolve_sha(None, env={"CI_COMMIT_SHA": token})
        self.assertEqual(source, "CI_COMMIT_SHA")
        self.assertEqual(sha, token)

    def test_cli_records_git_when_sha_and_ci_are_absent(self):
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "candidates.json"
            proc = run_ingest(out, report_paths(), env=scrubbed_env())
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(payload)
        self.assertTrue(all(item["sha_source"] == "git" for item in payload))
        self.assertTrue(all(item["sha"] == head for item in payload))

    def test_cli_records_gitlab_variable(self):
        token = "c" * 40
        env = scrubbed_env()
        env["CI_COMMIT_SHA"] = token
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "candidates.json"
            proc = run_ingest(out, report_paths(), env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(all(item["sha_source"] == "CI_COMMIT_SHA" for item in payload))
        self.assertTrue(all(item["sha"] == token for item in payload))


class ReadmeTranscriptTests(unittest.TestCase):
    def test_ledger_keeps_the_ingest_transcript(self):
        previous = readme_text("summary\n") + "\n<!-- INGEST:BEGIN -->\nkeep 4242\n<!-- INGEST:END -->\n"
        fresh = readme_text("other\n")
        kept = preserve_ingest_section(fresh, previous)
        self.assertIn("keep 4242", kept)
        self.assertEqual(kept.count("INGEST:BEGIN"), 1)
        self.assertIn("other", kept)
        self.assertNotIn("summary", kept.split("INGEST:BEGIN", 1)[0])


class VerifyTranscriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util

        path = ROOT / "tools" / "verify.py"
        spec = importlib.util.spec_from_file_location("flakecert_verify_ingest", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.v = module

    def test_ingest_transcript_numbers_are_not_scanned(self):
        raw = "before 999\n<!-- INGEST:BEGIN -->\nsha 12345\n<!-- INGEST:END -->\nafter"
        claim = self.v._readme_claim_text(raw)
        self.assertNotIn("12345", claim)
        self.assertIn("999", claim)
        self.assertIn("before", claim)
        self.assertIn("after", claim)

    def test_readme_ingest_gate_passes_on_real_block(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        ok, msg = self.v._readme_ingest_ok(text)
        print(f"readme_ingest real pass={ok} detail={msg}")
        self.assertTrue(ok, msg)
        self.assertIn("matches make ingest", msg)

    def test_readme_ingest_gate_fails_when_a_count_changes(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        start = text.index("<!-- INGEST:BEGIN -->")
        end = text.index("<!-- INGEST:END -->", start) + len("<!-- INGEST:END -->")
        block = text[start:end]
        old = '"n_fail": 2'
        self.assertIn(old, block)
        tampered_block = block.replace(old, '"n_fail": 9', 1)
        tampered = text[:start] + tampered_block + text[end:]
        self.assertNotEqual(tampered, text)
        ok, msg = self.v._readme_ingest_ok(tampered)
        print(f"readme_ingest tamper pass={ok} detail={msg}")
        self.assertFalse(ok, msg)
        self.assertIn("differs from make ingest", msg)
