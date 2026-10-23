import csv
import importlib.util
import io
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flakecert.verdict_audit import CsvVerdictError, audit, document_from_csv, dumps_audit

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "inputs/flakecert-verdict-audit/sample/dd-test-run.json"
EXPECTED = ROOT / "inputs/flakecert-verdict-audit/expected-audit.json"


def _event(suite, name, status, **meta):
    fields = {"test.suite": suite, "test.name": name, "test.status": status}
    fields.update(meta)
    return {"type": "test", "version": 2, "content": {"meta": fields}}


def _atf(suite, name, statuses, passed, parameters=None):
    events = []
    for index, status in enumerate(statuses):
        meta = {"test.test_management.is_attempt_to_fix": "true"}
        if parameters is not None:
            meta["test.parameters"] = parameters
        if index == len(statuses) - 1:
            meta["test.test_management.attempt_to_fix_passed"] = passed
        events.append(_event(suite, name, status, **meta))
    return events


class VerdictAuditTests(unittest.TestCase):
    def test_upper_and_required_for_zero_failures(self):
        for runs, bound in ((20, "0.139109"), (50, "0.058156")):
            doc = {"events": _atf("t.js", "case", ["pass"] * runs, "true")}
            row = audit(doc)["tests"][0]
            self.assertEqual(row["verdict"], "fixed")
            self.assertEqual(row["atf_runs"], runs)
            self.assertEqual(row["atf_failures"], 0)
            self.assertEqual(row["upper_bound_95"], bound)
            self.assertEqual(row["clean_seeded_runs_required"]["0.01"], 299)
            self.assertEqual(row["clean_seeded_runs_required"]["0.001"], 2995)

    def test_inconsistent_when_passed_tag_and_a_failure(self):
        doc = {"events": _atf("pay.test.js", "captures", ["pass", "fail", "pass"], "true")}
        row = audit(doc)["tests"][0]
        self.assertEqual(row["verdict"], "inconsistent")
        self.assertEqual(row["atf_runs"], 3)
        self.assertEqual(row["atf_failures"], 1)
        self.assertNotIn("upper_bound_95", row)
        self.assertNotIn("clean_seeded_runs_required", row)

    def test_parameters_are_part_of_the_key(self):
        doc = {"events": _atf("api.test.js", "filters", ["pass"] * 20, "true", parameters="region=us")}
        row = audit(doc)["tests"][0]
        self.assertEqual(row["test"], "api.test.js::filters[region=us]")
        self.assertEqual(row["upper_bound_95"], "0.139109")

    def test_auto_test_retry_events_are_ignored(self):
        noise = [
            _event(
                "api.test.js",
                "filters",
                "fail",
                **{"test.is_retry": "true", "test.retry_reason": "auto_test_retry"},
            ),
            {"type": "test_session_end", "content": {"meta": {"test.status": "fail"}}},
        ]
        doc = {"events": noise + _atf("api.test.js", "filters", ["pass"] * 20, "true")}
        report = audit(doc)
        self.assertEqual([row["test"] for row in report["tests"]], ["api.test.js::filters"])
        self.assertEqual(report["tests"][0]["atf_runs"], 20)
        self.assertEqual(report["tests"][0]["atf_failures"], 0)

    def test_sample_matches_frozen_expected(self):
        doc = json.loads(SAMPLE.read_text(encoding="utf-8"))
        expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(audit(doc), expected)

    def test_readme_quote_is_the_pinned_audit(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        begin = "<!-- AUDIT:BEGIN -->"
        end = "<!-- AUDIT:END -->"
        start = readme.index(begin) + len(begin)
        stop = readme.index(end)
        raw = readme[start:stop].strip("\n")
        lines = raw.split("\n")
        self.assertTrue(lines[0].startswith("```"))
        self.assertTrue(lines[-1].startswith("```"))
        quote = "\n".join(lines[1:-1]) + "\n"
        self.assertEqual(quote, EXPECTED.read_text(encoding="utf-8"))
        self.assertIn("make audit", readme[:start])

    def test_readme_quote_matches_fresh_audit_and_fails_if_tampered(self):
        spec = importlib.util.spec_from_file_location("flakecert_verify_readme", ROOT / "tools" / "verify.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        summary = (ROOT / "ledger" / "SUMMARY.md").read_text(encoding="utf-8")
        ok, msg = module._readme_numbers_ok(readme, summary)
        self.assertTrue(ok, msg)
        tampered = readme.replace('"0.01": 299', '"0.01": 298', 1)
        self.assertNotEqual(tampered, readme)
        bad, why = module._readme_numbers_ok(tampered, summary)
        self.assertFalse(bad)
        self.assertIn("does not match fresh make audit output", why)

    def test_cli_bytes_match_expected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "verdicts.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/audit_verdicts.py"),
                    "--in",
                    str(SAMPLE),
                    "--out",
                    str(dest),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(dest.read_bytes(), EXPECTED.read_bytes())


_CSV_PREFIX = "attributes.attributes."
PUP_CSV = ROOT / "inputs/flakecert-csv-sample/sample/pup-export.csv"
PUP_EXPECTED = ROOT / "inputs/flakecert-csv-sample/expected-audit-pup.json"
REAL_CSV = ROOT / "inputs/flakecert-csv-sample/sample/real-cassette-search.csv"
REAL_EXPECTED = ROOT / "inputs/flakecert-csv-sample/expected-audit-real.json"


def _csv_text(headers, rows):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _prefixed(**tags):
    return {_CSV_PREFIX + key: value for key, value in tags.items()}


def _atf_headers(*extra):
    names = ["start", "test.suite", "test.name", "test.status", *extra]
    return [_CSV_PREFIX + name for name in names]


def _run_audit(src, extra_args=None):
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "out.json"
        argv = [sys.executable, str(ROOT / "tools/audit_verdicts.py"), "--in", str(src), "--out", str(dest)]
        if extra_args:
            argv.extend(extra_args)
        proc = subprocess.run(argv, check=False, capture_output=True, text=True)
        body = dest.read_text(encoding="utf-8") if dest.exists() else ""
        return proc, body


class CsvVerdictTests(unittest.TestCase):
    def test_shuffled_rows_match_pup_export_audit(self):
        original = PUP_CSV.read_text(encoding="utf-8")
        expected = PUP_EXPECTED.read_text(encoding="utf-8")
        self.assertEqual(dumps_audit(audit(document_from_csv(original))), expected)
        table = list(csv.reader(io.StringIO(original, newline="")))
        header, body = table[0], table[1:]
        random.Random(0).shuffle(body)
        self.assertNotEqual(body, table[1:])
        buf = io.StringIO(newline="")
        csv.writer(buf, lineterminator="\n").writerows([header, *body])
        self.assertEqual(dumps_audit(audit(document_from_csv(buf.getvalue()))), expected)

    def test_duplicate_start_aborts(self):
        headers = _atf_headers()
        text = _csv_text(
            headers,
            [
                _prefixed(**{"start": "10", "test.suite": "a.js", "test.name": "one", "test.status": "pass"}),
                _prefixed(**{"start": "10", "test.suite": "a.js", "test.name": "one", "test.status": "fail"}),
            ],
        )
        with self.assertRaises(CsvVerdictError) as caught:
            document_from_csv(text)
        self.assertIn("duplicate start", str(caught.exception))
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "dup.csv"
            src.write_text(text, encoding="utf-8")
            proc, body = _run_audit(src)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("duplicate start", proc.stderr)
        self.assertEqual(body, "")

    def test_missing_column_aborts(self):
        headers = [_CSV_PREFIX + name for name in ("start", "test.suite", "test.name")]
        text = _csv_text(
            headers,
            [_prefixed(**{"start": "10", "test.suite": "a.js", "test.name": "one"})],
        )
        with self.assertRaises(CsvVerdictError) as caught:
            document_from_csv(text)
        self.assertIn("test.status", str(caught.exception))
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "missing.csv"
            src.write_text(text, encoding="utf-8")
            proc, _body = _run_audit(src)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("missing required column", proc.stderr)
        self.assertIn("test.status", proc.stderr)

    def test_quoted_cell_keeps_comma(self):
        headers = _atf_headers(
            "test.test_management.is_attempt_to_fix",
            "test.test_management.attempt_to_fix_passed",
        )
        text = _csv_text(
            headers,
            [
                _prefixed(
                    **{
                        "start": "10",
                        "test.suite": "cart.test.js",
                        "test.name": "total, rounded",
                        "test.status": "pass",
                        "test.test_management.is_attempt_to_fix": "true",
                        "test.test_management.attempt_to_fix_passed": "true",
                    }
                )
            ],
        )
        self.assertIn('"total, rounded"', text)
        report = audit(document_from_csv(text))
        self.assertEqual(report["tests"][0]["test"], "cart.test.js::total, rounded")
        self.assertEqual(report["tests"][0]["verdict"], "fixed")

    def test_parameters_column_is_part_of_the_key(self):
        headers = _atf_headers(
            "test.parameters",
            "test.test_management.is_attempt_to_fix",
            "test.test_management.attempt_to_fix_passed",
        )
        text = _csv_text(
            headers,
            [
                _prefixed(
                    **{
                        "start": "10",
                        "test.suite": "api.test.js",
                        "test.name": "filters",
                        "test.status": "pass",
                        "test.parameters": "region=us",
                        "test.test_management.is_attempt_to_fix": "true",
                        "test.test_management.attempt_to_fix_passed": "true",
                    }
                )
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "params.txt"
            src.write_text(text, encoding="utf-8")
            proc, body = _run_audit(src, ["--format", "csv"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = json.loads(body)["tests"][0]
        self.assertEqual(row["test"], "api.test.js::filters[region=us]")

    def test_real_cassette_csv_matches_expected(self):
        report = dumps_audit(audit(document_from_csv(REAL_CSV.read_text(encoding="utf-8"))))
        self.assertEqual(report, REAL_EXPECTED.read_text(encoding="utf-8"))
