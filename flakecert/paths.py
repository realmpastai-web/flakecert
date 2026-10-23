from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
FROZEN_CSV = BASELINE / "frozen-set.csv"
HASHES = BASELINE / "HASHES"
LEDGER = ROOT / "ledger"
SWAPS = LEDGER / "swaps.csv"
RESULTS = LEDGER / "results.csv"
SUMMARY = LEDGER / "SUMMARY.md"
SUMMARY_BUILD = LEDGER / "summary-build.log"
BASELINE_LOGS = LEDGER / "baseline"
FLAKECERT_LOGS = LEDGER / "flakecert"
EVIDENCE = ROOT / "evidence" / "flakecert"
EVIDENCE_ROOT = ROOT / "evidence"
COMPARATOR_CSV = EVIDENCE_ROOT / "comparator.csv"
VERIFY_LOG = EVIDENCE_ROOT / "verify.log"
VERIFY_REPORT = EVIDENCE_ROOT / "verify-report.json"
SHA256SUMS = EVIDENCE_ROOT / "SHA256SUMS"
CERTS = ROOT / "certs"
ENVS = ROOT / "envs"
CACHE = ROOT / ".cache"
README = ROOT / "README.md"

FROZEN_SHA256 = "a788832159f871780197e2cf9736904546ac0fdf36cad1e6b378837719b8a812"
IDOFT_COMMIT = "4903dc9233eead4e4191c66f9ed0b14eea091052"
IDOFT_SHA256 = "a1cf7425cd23096ae653af275fbba6c82d7d72ce5e17bb3db754e46e0e4c3c32"
IDOFT_URL = (
    "https://raw.githubusercontent.com/TestingResearchIllinois/idoft/"
    f"{IDOFT_COMMIT}/py-data.csv"
)
SPEC_SHA256 = "1bca7a57d93be709de5d764d93e17d874b37fb48f949f558d2740e84c2537fae"
SEED = 20261017
BUDGET = 500
BASELINE_RUNS = 100
PY_LADDER = ("3.11", "3.9", "3.8", "3.7")
PY_IMAGES = {
    "3.11": "python:3.11-slim-bookworm",
    "3.9": "python:3.9-slim-bookworm",
    "3.8": "python:3.8-slim-bookworm",
    "3.7": "python:3.7-slim-buster",
}
PY_SUITES = {
    "3.11": "bookworm",
    "3.9": "bookworm",
    "3.8": "bookworm",
    "3.7": "buster",
}
