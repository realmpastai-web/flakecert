"""Pure helpers for the G3 GitLab order-dependence run.

Paths, labels, and image names come from the frozen spec text and the
checkout. Nothing here names a subject spec, a polluter, or a failure mode.
"""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

from tools.certify_rspec.ddmin import DdminError, one_minimal

HEADLINE_RE = re.compile(
    r"^\d+ failures in \d+ seeded runs -> failure rate <= \d+\.\d{2}% "
    r"\(one-sided 95%, Clopper-Pearson\); seeds=\d+\.\.\d+; commit=[0-9a-f]{40}$"
)
VERDICTS = ("CERTIFIED_ORDER_DEPENDENT", "BOUNDED_CLEAN")
CATEGORY_LABELS = ("ENV_FAILURE", "ENABLER_CERTIFIED", "PASSES_ALONE", "UNRESOLVED")
FOSS_ENTRY = re.compile(r"^- '(\./spec/(?:models|lib)/[^']+)'\s*$")
FENCE = re.compile(r"```yaml\n(.*?)```", re.S)
EXCLUDED_ROW = re.compile(r"^-\s+(\S+_spec\.rb)\s+#\s*(.*?)\s*$", re.M)
SHA_LINE = re.compile(r"^([0-9a-f]{64})\s+(\S+)\s*$")
INFRA_CLASSES = {
    "LoadError",
    "Errno::ENOENT",
    "Errno::ECONNREFUSED",
    "Errno::ECONNRESET",
    "Errno::EHOSTUNREACH",
    "PG::ConnectionBad",
    "Redis::CannotConnectError",
    "SocketError",
}
INFRA_PHRASES = (
    "connection refused",
    "could not connect",
    "failed to connect",
    "cannot connect",
    "not running",
    "no such file or directory",
    "temporary failure in name resolution",
    "name or service not known",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clopper_pearson_upper(failures: int, trials: int, alpha: float = 0.05) -> float:
    """One-sided Clopper-Pearson upper bound on a binomial failure rate."""
    if trials <= 0:
        raise ValueError("trials must be positive")
    if failures < 0 or failures > trials:
        raise ValueError("failures out of range")
    if failures == 0:
        return 1.0 - alpha ** (1.0 / trials)
    lo = 0.0
    hi = 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if _binom_cdf_le(failures, trials, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def _binom_cdf_le(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    q = 1.0 - p
    log_term = n * math.log(q)
    total = math.exp(log_term)
    for i in range(k):
        log_term += math.log(n - i) - math.log(i + 1) + math.log(p) - math.log(q)
        total += math.exp(log_term)
    if total > 1.0:
        return 1.0
    return total


def format_percent(rate: float) -> str:
    return f"{rate * 100:.2f}%"


def bound_headline(failures: int, trials: int, seed_lo: int, seed_hi: int, commit: str) -> str:
    percent = format_percent(clopper_pearson_upper(failures, trials))
    return (
        f"{failures} failures in {trials} seeded runs -> "
        f"failure rate <= {percent} (one-sided 95%, Clopper-Pearson); "
        f"seeds={seed_lo}..{seed_hi}; commit={commit}"
    )


def armf_verdict(failures: int) -> str:
    if failures == 0:
        return "BOUNDED_CLEAN"
    return "CERTIFIED_ORDER_DEPENDENT"


def select_s20(todo_text: str, limit: int = 20) -> list[str]:
    """FOSS todo entries under spec/models or spec/lib, smallest sha256(path) first."""
    found = []
    for line in todo_text.splitlines():
        match = FOSS_ENTRY.match(line.strip())
        if match:
            found.append(match.group(1))
    found.sort(key=lambda path: hashlib.sha256(path.encode("utf-8")).hexdigest())
    return found[:limit]


def parse_excluded(descriptions: list[str]) -> dict[str, list[str]]:
    """Category rows from fenced yaml blocks in issue descriptions."""
    category_a: list[str] = []
    category_b1: list[str] = []
    seen_a: set[str] = set()
    seen_b1: set[str] = set()
    for description in descriptions:
        for block in FENCE.findall(description):
            for match in EXCLUDED_ROW.finditer(block):
                path, comment = match.group(1), match.group(2)
                if re.search(r"Category" + r" A\b", comment) and path not in seen_a:
                    category_a.append(path)
                    seen_a.add(path)
                if re.search(r"Category" + r" B1\b", comment) and path not in seen_b1:
                    category_b1.append(path)
                    seen_b1.add(path)
    return {"category_a": category_a, "b1": category_b1}


def first_commit(spec_text: str) -> str:
    match = re.search(r"\b([0-9a-f]{40})\b", spec_text)
    if not match:
        raise ValueError("spec text has no pinned commit")
    return match.group(1)


def check_script_rel(spec_text: str) -> str:
    match = re.search(r"(scripts/\S+)", spec_text)
    if not match:
        raise ValueError("spec text has no scripts path")
    return match.group(1).rstrip(".,)")


def absence_needle(spec_text: str) -> str:
    match = re.search(r"fails because ([A-Za-z][A-Za-z0-9_]*) is absent", spec_text)
    if not match:
        raise ValueError("spec text has no absence fallback")
    return match.group(1)


def sha_by_prefix(recon_text: str, prefix: str) -> tuple[str, str]:
    for line in recon_text.splitlines():
        match = SHA_LINE.match(line.strip())
        if match and match.group(2).startswith(prefix):
            return match.group(1), match.group(2)
    raise ValueError(f"recon log has no sha line starting with {prefix}")


def todo_relpath(script_text: str) -> str:
    match = re.search(r"TODO_YAML='([^']+)'", script_text)
    if not match:
        raise ValueError("check script has no TODO_YAML assignment")
    return match.group(1)


def slug(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


SETUP_FAIL_LIMIT = 2
SEED_TIMEOUT_FLOOR_S = 300


def cert_verdict(text: str) -> str:
    """Second non-empty line of a certificate is the verdict."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return ""
    return lines[1]


def sum_for(sums_text: str, rel: str) -> str | None:
    for line in sums_text.splitlines():
        match = SHA_LINE.match(line.strip())
        if match and match.group(2) == rel:
            return match.group(1)
    return None


def resume_action(verdict: str, actual_sha: str, expected_sha: str | None) -> str:
    """Skip a finished clean certificate only after its sha256 matches the sums file."""
    if verdict != "BOUNDED_CLEAN":
        return "run"
    if not expected_sha or actual_sha != expected_sha:
        return "sha_mismatch"
    return "skip_verified"


def seed_finished(meta: dict | None) -> bool:
    """A seed counts only when its process finished. A timeout is not finished."""
    if not isinstance(meta, dict):
        return False
    if meta.get("timeout") is True or meta.get("exit_code") == 124:
        return False
    return "exit_code" in meta


def next_resume_seed(
    seed_metas: dict[int, dict | None],
    seed_lo: int = 1,
    seed_hi: int = 30,
) -> int | None:
    for seed in range(seed_lo, seed_hi + 1):
        if not seed_finished(seed_metas.get(seed)):
            return seed
    return None


def seed_timeout_s(arm_g_elapsed_s: float, floor_s: int = SEED_TIMEOUT_FLOOR_S) -> int:
    """Per-seed limit is three times that file's arm-G time, and at least the floor."""
    scaled = math.ceil(3 * float(arm_g_elapsed_s))
    if scaled < floor_s:
        return floor_s
    return int(scaled)


def counts_as_setup_failure(
    example_count: int,
    exit_code: int,
    error_class: str,
    message: str,
    timeout: bool = False,
    needle: str = "",
) -> bool:
    if timeout or exit_code == 124:
        return False
    return is_env_failure(example_count, exit_code, error_class, message, needle)


def should_stop_setup(count: int, limit: int = SETUP_FAIL_LIMIT) -> bool:
    return count >= limit


def resume_plan(rows: list[dict]) -> dict[str, list[str]]:
    """Unfinished seeded paths first, then paths that have not started.

    A clean certificate is omitted. The caller runs the excluded set and the
    single reverse-order path between those two groups.
    """
    skip: list[str] = []
    continue_paths: list[str] = []
    later: list[str] = []
    for row in rows:
        path = row["path"]
        verdict = str(row.get("verdict") or "NOT_RUN")
        trials = int(row.get("arm_f_trials") or 0)
        if verdict == "BOUNDED_CLEAN" and row.get("cert"):
            skip.append(path)
        elif verdict == "INCOMPLETE" and (trials > 0 or row.get("arm_g_log")):
            continue_paths.append(path)
        else:
            later.append(path)
    return {"skip": skip, "continue": continue_paths, "later": later}


def not_run_row(path: str) -> dict:
    return {
        "path": path,
        "slug": slug(path),
        "arm_g_pass": None,
        "arm_g_log": "",
        "arm_f_failures": 0,
        "arm_f_trials": 0,
        "verdict": "NOT_RUN",
        "headline": "",
        "cert": "",
        "seed_timeout_s": None,
    }


def is_expectation(error_class: str) -> bool:
    return error_class.endswith("ExpectationNotMetError")


def is_env_failure(
    example_count: int,
    exit_code: int,
    error_class: str,
    message: str,
    needle: str = "",
) -> bool:
    if exit_code == 0:
        return False
    if example_count == 0:
        return True
    if error_class in INFRA_CLASSES:
        return True
    blob = f"{error_class}\n{message}".lower()
    if any(phrase in blob for phrase in INFRA_PHRASES):
        return True
    if needle and needle.lower() in blob and any(
        word in blob for word in ("absent", "missing", "not found", "not running")
    ):
        return True
    return False


def classify_category_a(
    alone_passed: bool,
    siblings_target_passed: bool,
    env_failure: bool,
    enabler_certified: bool,
) -> str:
    if alone_passed:
        return "PASSES_ALONE"
    if siblings_target_passed and enabler_certified:
        return "ENABLER_CERTIFIED"
    if env_failure and not siblings_target_passed:
        return "ENV_FAILURE"
    return "UNRESOLVED"


def armg_pass_armf_fail(rows: list[dict]) -> list[str]:
    chosen = []
    for row in rows:
        if row.get("arm_g_pass") and int(row.get("arm_f_failures") or 0) > 0:
            chosen.append(row["path"])
    return chosen


def same_file(ids: list[str], target_file: str) -> bool:
    if not ids:
        return False
    target = _norm_path(target_file)
    for ident in ids:
        if _norm_path(ident.split("[", 1)[0]) != target:
            return False
    return True


def _norm_path(path: str) -> str:
    text = path[2:] if path.startswith("./") else path
    return text


def file_of_example(example: dict) -> str:
    raw = example.get("file_path") or example.get("id") or ""
    return _norm_path(str(raw).split("[", 1)[0])


def summarize_rspec(data: dict | None, exit_code: int) -> dict:
    examples = []
    if isinstance(data, dict):
        raw = data.get("examples")
        if isinstance(raw, list):
            examples = raw
    failed_ids = []
    error_class = ""
    message = ""
    for example in examples:
        if example.get("status") != "failed":
            continue
        ident = example.get("id")
        if ident:
            failed_ids.append(str(ident))
        if error_class:
            continue
        exc = example.get("exception") or {}
        if isinstance(exc, dict):
            error_class = str(exc.get("class") or "")
            text = exc.get("message") or ""
            message = str(text).splitlines()[0] if text else ""
    summary = data.get("summary") if isinstance(data, dict) else None
    if not isinstance(summary, dict):
        summary = {}
    example_count = summary.get("example_count")
    failure_count = summary.get("failure_count")
    if not isinstance(example_count, int):
        example_count = len(examples)
    if not isinstance(failure_count, int):
        failure_count = len(failed_ids)
    return {
        "exit_code": exit_code,
        "example_count": example_count,
        "failure_count": failure_count,
        "failed_ids": failed_ids,
        "error_class": error_class,
        "message": message,
        "examples": examples,
        "passed": exit_code == 0 and failure_count == 0 and example_count > 0,
    }


def target_examples_passed(summary: dict, target_file: str) -> bool:
    target = _norm_path(target_file)
    seen = [example for example in summary["examples"] if file_of_example(example) == target]
    if not seen:
        return False
    return all(example.get("status") == "passed" for example in seen)


def sibling_names(names: list[str]) -> list[str]:
    return sorted(name for name in names if name.endswith("_spec.rb"))


def minimal_enablers(others: list[str], test) -> list[str] | None:
    if not others:
        return None
    try:
        return one_minimal(list(others), test)
    except DdminError:
        return None


def _quoted_vars(text: str) -> dict[str, str]:
    found = {}
    for line in text.splitlines():
        match = re.match(r"^\s+([A-Z0-9_]+):\s+\"([^\"]*)\"\s*$", line)
        if match:
            found[match.group(1)] = match.group(2)
    return found


def _substitute(template: str, variables: dict[str, str]) -> str:
    previous = None
    current = template
    while current != previous:
        previous = current
        current = re.sub(
            r"\$\{([A-Z0-9_]+)\}",
            lambda match: variables.get(match.group(1), match.group(0)),
            previous,
        )
    if "${" in current:
        missing = sorted(set(re.findall(r"\$\{([A-Z0-9_]+)\}", current)))
        raise ValueError("unresolved image variables: " + ",".join(missing))
    return current


def redis_cluster_version(global_text: str, pg_version: str) -> str:
    pattern = rf'PG_VERSION: "{re.escape(pg_version)}"\n\s+REDIS_CLUSTER_VERSION: "([^"]+)"'
    match = re.search(pattern, global_text)
    if not match:
        raise ValueError("global CI has no redis cluster version for this postgres")
    return match.group(1)


def postgres_command(global_text: str) -> list[str]:
    match = re.search(r"\.db-services:\n(?:.*\n){0,6}?\s+command:\s+\[([^\]]+)\]", global_text)
    if not match:
        raise ValueError("global CI has no .db-services command")
    parts = re.findall(r'"([^"]+)"', match.group(1))
    if not parts or parts[0] != "postgres":
        raise ValueError(".db-services command is not postgres")
    return parts


def resolve_images(version_text: str, gitlab_ci_text: str, global_text: str) -> dict:
    variables = {}
    variables.update(_quoted_vars(version_text))
    variables.update(_quoted_vars(gitlab_ci_text))
    # The default-branch pipeline uses the default Ruby anchor. A later
    # next-ruby assignment in the same file must not win.
    if "RUBY_VERSION_DEFAULT" in variables:
        variables["RUBY_VERSION"] = variables["RUBY_VERSION_DEFAULT"]
    pg_version = variables["PG_VERSION"]
    variables["REDIS_CLUSTER_VERSION"] = redis_cluster_version(global_text, pg_version)
    image_template = variables["DEFAULT_CI_IMAGE"]
    registry = variables["REGISTRY_HOST"]
    group = variables["REGISTRY_GROUP"]
    prefix = f"{registry}/{group}/gitlab-build-images"
    redis_name = ""
    for line in global_text.splitlines():
        if "redis:" in line and "alpine" in line and "name:" in line:
            redis_name = line.split("name:", 1)[1].strip()
            break
    if not redis_name:
        raise ValueError("global CI has no redis image")
    return {
        "ci_image": _substitute(image_template, variables),
        "postgres_image": f"{prefix}:postgres-{pg_version}",
        "redis_image": redis_name,
        "redis_cluster_image": f"{prefix}:redis-cluster-{variables['REDIS_CLUSTER_VERSION']}",
        "pg_version": pg_version,
        "redis_cluster_version": variables["REDIS_CLUSTER_VERSION"],
        "postgres_command": postgres_command(global_text),
        "ruby_version": variables["RUBY_VERSION"],
    }


def certificate_text(headline: str, verdict: str, body: dict) -> str:
    import json

    return headline + "\n" + verdict + "\n" + json.dumps(body, indent=2, sort_keys=True) + "\n"


def bisect_command(text: str) -> str | None:
    from tools.certify_rspec.parse_rspec import parse_bisect, strip_ansi

    parsed = parse_bisect(text)
    command = parsed.get("command")
    if command:
        return command
    clean = strip_ansi(text)
    match = re.search(r"Rerun with:\s*(.+)", clean)
    if match:
        return match.group(1).strip()
    return None


def descriptions_from_sources(source_dir: Path) -> list[str]:
    import json

    texts = []
    for path in sorted(source_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        description = data.get("description") if isinstance(data, dict) else None
        if isinstance(description, str) and "```yaml" in description:
            texts.append(description)
    return texts
