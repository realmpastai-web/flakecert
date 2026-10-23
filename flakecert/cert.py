"""Certificate schema, traceback signature, and Fraction bounds."""

import json
import re
from fractions import Fraction

from flakecert import __version__
from flakecert.paths import SEED

FORMULA = "1/(m*k^(d-1))"


def per_run_lower(m: int, k: int, d: int) -> Fraction:
    if m < 1 or k < 1 or d < 1:
        raise ValueError(f"bound requires m>=1, k>=1, d>=1 (got m={m} k={k} d={d})")
    return Fraction(1, m * (k ** (d - 1)))


def normalize_traceback(text: str, repo_root: str | None = None) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\\", "/")
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    # Strip a caller-supplied checkout prefix before the fixed prefixes below.
    # Default None leaves existing certificate tracebacks unchanged.
    if repo_root:
        root = repo_root.replace("\\", "/").rstrip("/")
        if root:
            text = text.replace(root + "/", "")
    for prefix in ("/work/", "/opt/pristine/", "/src/", "/tmp/fc-run/"):
        text = text.replace(prefix, "")
    text = re.sub(r"/tmp/fc-[A-Za-z0-9._/-]+", "/tmp/fc-TMP", text)
    text = re.sub(r"\b0x[0-9a-fA-F]+\b", "0xADDR", text)
    text = re.sub(r"\bpid=\d+\b", "pid=PID", text)
    text = re.sub(r"\b\d+\.\d+\s*seconds?\b", "DUR", text)
    # Go's testing package prints (0.00s). Pytest already uses "N.NN seconds".
    text = re.sub(r"\(\d+\.\d+s\)", "(DUR)", text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    normalized = "\n".join(lines)
    if len(normalized) > 20000 and "...[truncated]..." not in normalized:
        normalized = normalized[:10000] + "\n...[truncated]...\n" + normalized[-10000:]
    if normalized:
        normalized += "\n"
    return normalized


def exception_type(tb: str) -> str:
    match = re.search(
        r"^E\s+([A-Za-z_][\w.]*(?:Error|Exception|Exit|Failure))\b",
        tb,
        re.M,
    )
    if match:
        return match.group(1).split(".")[-1]
    if re.search(r"^E\s+assert\b", tb, re.M) or "AssertionError" in tb:
        return "AssertionError"
    match = re.search(r"^E\s+([A-Za-z_][\w.]*)", tb, re.M)
    if match:
        return match.group(1).split(".")[-1]
    return "Error"


def failure_signature(tb: str, repo_root: str | None = None) -> str:
    import hashlib

    normalized = normalize_traceback(tb, repo_root=repo_root)
    if not normalized.strip():
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def bound_fields(m: int, k: int, d: int, runs_to_failure: int) -> dict:
    lower = per_run_lower(m, k, d)
    empirical = Fraction(1, runs_to_failure)
    compare = "empirical>=lower" if empirical >= lower else "empirical<lower"
    return {
        "per_run_lower": str(lower),
        "formula": FORMULA,
        "empirical_runs_to_failure": runs_to_failure,
        "empirical_rate": str(empirical),
        "compare": compare,
    }


def check_bound(cert: dict) -> tuple[bool, str]:
    try:
        m = int(cert["m"])
        k = int(cert["k"])
        d = int(cert["d"])
        runs_to = int(cert["bound"]["empirical_runs_to_failure"])
        expected = bound_fields(m, k, d, runs_to)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return False, f"recompute error: {exc}"
    actual = cert["bound"]
    mismatches = []
    for key, value in expected.items():
        if actual.get(key) != value:
            mismatches.append(f"{key}: cert={actual.get(key)!r} recomputed={value!r}")
    if cert["bound"].get("formula") != FORMULA:
        mismatches.append("formula")
    if mismatches:
        return False, "; ".join(mismatches)
    return True, "recomputed"


def build_certificate(
    row: dict,
    node_id: str,
    image_digest: str,
    image_tag: str,
    pip_freeze_sha: str,
    python_version: str,
    sources: list[str],
    k: int,
    d: int,
    schedule: dict,
    order_scope: str,
    exc: str,
    sig: str,
    runs_to_failure: int,
    pytest_args: list[str],
    tb: str,
) -> dict:
    m = len(sources)
    return {
        "id": row["id"],
        "project": row["project_url"],
        "sha": row["sha"],
        "pytest_id": row["pytest_id"],
        "node_id": node_id,
        "image_digest": image_digest,
        "image_tag": image_tag,
        "pip_freeze_sha": pip_freeze_sha,
        "flakecert_version": __version__,
        "python": python_version,
        "sources": list(sources),
        "m": m,
        "k": k,
        "d": d,
        "schedule": [{"source": name, "value": schedule[name]} for name in sources],
        "order_scope": order_scope,
        "seed": SEED,
        "pytest_args": list(pytest_args),
        "expected_failure": {"exc": exc, "sig": sig, "tb_norm": normalize_traceback(tb)},
        "bound": bound_fields(m, k, d, runs_to_failure),
    }


def schedule_dict(cert: dict) -> dict:
    schedule = {}
    for item in cert["schedule"]:
        schedule[item["source"]] = item["value"]
    return schedule


def dump_cert(cert: dict) -> str:
    return json.dumps(cert, indent=2, sort_keys=False) + "\n"


def load_cert(path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
