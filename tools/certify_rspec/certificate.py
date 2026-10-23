"""Certificate schema check. Extra keys are allowed; required ones are not."""

from __future__ import annotations

import re

from tools.certify_rspec.order_guard import INVALID_ORDER

HEX64 = re.compile(r"^[0-9a-f]{64}$")
VERDICTS = {"FIXED", "NOT_FIXED", "DISAGREEMENT", "POLLUTER_FAILED", INVALID_ORDER}
BRITTLE_CERTIFIED = "BRITTLE_CERTIFIED"
LABELS = {"CERTIFIED", "CONTROL", "UNRESOLVED", "REJECTED", BRITTLE_CERTIFIED}
OD_LABELS = {"CERTIFIED", "CONTROL", "UNRESOLVED", "REJECTED"}
RUN_FIELDS = (
    "exit_code",
    "example_count",
    "failure_count",
    "first_error_class",
    "first_error_message_line",
    "log_sha256",
    "failed_ids",
    "order",
)


def _err(errors: list[str], message: str) -> None:
    errors.append(message)


def _require_str(errors: list[str], obj: dict, key: str, label: str) -> None:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        _err(errors, f"{label}.{key} must be a non-empty string")


def _check_run(errors: list[str], run: object, label: str) -> None:
    if not isinstance(run, dict):
        _err(errors, f"{label} must be an object")
        return
    for field in RUN_FIELDS:
        if field not in run:
            _err(errors, f"{label}.{field} missing")
    if "exit_code" in run and not isinstance(run["exit_code"], int):
        _err(errors, f"{label}.exit_code must be an int")
    for field in ("example_count", "failure_count"):
        if field in run and not isinstance(run[field], int):
            _err(errors, f"{label}.{field} must be an int")
    digest = run.get("log_sha256")
    if isinstance(digest, str) and digest != "0" * 64 and not HEX64.match(digest):
        _err(errors, f"{label}.log_sha256 must be 64 hex chars")
    elif not isinstance(digest, str):
        _err(errors, f"{label}.log_sha256 must be a string")
    for field in ("failed_ids", "order"):
        if field in run and not isinstance(run[field], list):
            _err(errors, f"{label}.{field} must be a list")


def _check_seed_provenance(errors: list[str], cert: dict) -> None:
    provenance = cert.get("seed_provenance")
    if not isinstance(provenance, dict):
        _err(errors, "seed_provenance must be an object")
        return
    if not isinstance(provenance.get("s0"), dict):
        _err(errors, "seed_provenance.s0 must be an object")


def _validate_brittle(cert: dict) -> list[str]:
    errors: list[str] = []
    for key in (
        "tool",
        "repo",
        "base",
        "head",
        "image_id",
        "ruby",
        "bundler",
        "rspec_core",
        "gemfile_lock_sha256",
        "seed",
        "victim_id",
        "enabler_ids",
        "commands",
        "runs",
        "label",
        "seed_provenance",
    ):
        if key not in cert:
            _err(errors, f"missing {key}")
    tool = cert.get("tool")
    if isinstance(tool, dict):
        for key in ("name", "version", "git_sha"):
            _require_str(errors, tool, key, "tool")
    else:
        _err(errors, "tool must be an object")
    if not isinstance(cert.get("repo"), str) or not cert.get("repo"):
        _err(errors, "repo must be a non-empty string")
    for side in ("base", "head"):
        block = cert.get(side)
        if not isinstance(block, dict):
            _err(errors, f"{side} must be an object")
            continue
        _require_str(errors, block, "commit", side)
        digest = block.get("tarball_sha256")
        if not isinstance(digest, str) or not HEX64.match(digest):
            _err(errors, f"{side}.tarball_sha256 must be 64 hex chars")
    for key in ("image_id", "ruby", "bundler", "rspec_core"):
        if not isinstance(cert.get(key), str) or not cert.get(key):
            _err(errors, f"{key} must be a non-empty string")
    locks = cert.get("gemfile_lock_sha256")
    if not isinstance(locks, dict):
        _err(errors, "gemfile_lock_sha256 must be an object")
    else:
        for side in ("base", "head"):
            digest = locks.get(side)
            if not isinstance(digest, str) or not HEX64.match(digest):
                _err(errors, f"gemfile_lock_sha256.{side} must be 64 hex chars")
    enablers = cert.get("enabler_ids")
    if not isinstance(enablers, list) or not enablers or not all(isinstance(item, str) and item for item in enablers):
        _err(errors, "enabler_ids must be a non-empty list of strings")
    commands = cert.get("commands")
    if not isinstance(commands, dict):
        _err(errors, "commands must be an object")
    else:
        for arm in ("alone", "enabled"):
            value = commands.get(arm)
            if not isinstance(value, str) or not value.startswith("rspec"):
                _err(errors, f"commands.{arm} must be an rspec command string")
    runs = cert.get("runs")
    if not isinstance(runs, dict):
        _err(errors, "runs must be an object")
    else:
        expected = {"base": ("alone", "enabled"), "head": ("alone",)}
        for side, arms in expected.items():
            block = runs.get(side)
            if not isinstance(block, dict):
                _err(errors, f"runs.{side} must be an object")
                continue
            for arm in arms:
                reps = block.get(arm)
                if not isinstance(reps, list) or len(reps) != 3:
                    _err(errors, f"runs.{side}.{arm} must be 3 runs")
                    continue
                for index, run in enumerate(reps, start=1):
                    _check_run(errors, run, f"runs.{side}.{arm}[{index}]")
    if cert.get("label") not in {BRITTLE_CERTIFIED, "REJECTED", "UNRESOLVED"}:
        _err(errors, "brittle label must be BRITTLE_CERTIFIED, REJECTED, or UNRESOLVED")
    if "seed_provenance" in cert:
        _check_seed_provenance(errors, cert)
    if not isinstance(cert.get("seed"), int):
        _err(errors, "seed must be an int")
    if not isinstance(cert.get("victim_id"), str) or not cert.get("victim_id"):
        _err(errors, "victim_id must be a non-empty string")
    return errors


def validate_cause_set(cause_set: object) -> list[str]:
    """Each entry names one polluter set, its verdicts, where it was found, and a replay script."""
    errors: list[str] = []
    if not isinstance(cause_set, list):
        return ["cause_set must be a list"]
    for index, item in enumerate(cause_set):
        label = f"cause_set[{index}]"
        if not isinstance(item, dict):
            _err(errors, f"{label} must be an object")
            continue
        polluters = item.get("polluter_ids")
        if (
            not isinstance(polluters, list)
            or not polluters
            or not all(isinstance(value, str) and value for value in polluters)
        ):
            _err(errors, f"{label}.polluter_ids must be a non-empty list of strings")
        verdicts = item.get("verdicts")
        if not isinstance(verdicts, dict):
            _err(errors, f"{label}.verdicts must be an object")
        else:
            for side in ("base", "head"):
                if verdicts.get(side) not in VERDICTS:
                    _err(errors, f"{label}.verdicts.{side} must be one of {sorted(VERDICTS)}")
        provenance = item.get("seed_provenance")
        if not isinstance(provenance, dict):
            _err(errors, f"{label}.seed_provenance must be an object")
        else:
            seeds = provenance.get("seeds")
            if not isinstance(seeds, list) or not seeds or not all(isinstance(seed, int) for seed in seeds):
                _err(errors, f"{label}.seed_provenance.seeds must be a non-empty list of ints")
        replay = item.get("replay")
        if not isinstance(replay, str) or not replay:
            _err(errors, f"{label}.replay must be a non-empty string")
    return errors


def _attach_cause_set(errors: list[str], cert: dict) -> list[str]:
    if "cause_set" in cert:
        errors.extend(validate_cause_set(cert.get("cause_set")))
    return errors


def validate_certificate(cert: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(cert, dict):
        return ["certificate must be an object"]
    if cert.get("kind") == "BRITTLE":
        return _attach_cause_set(_validate_brittle(cert), cert)
    for key in (
        "tool",
        "repo",
        "base",
        "head",
        "image_id",
        "ruby",
        "bundler",
        "rspec_core",
        "gemfile_lock_sha256",
        "seed",
        "victim_id",
        "polluter_ids",
        "commands",
        "runs",
        "verdicts",
        "plain_retry_verdict",
        "label",
    ):
        if key not in cert:
            _err(errors, f"missing {key}")
    tool = cert.get("tool")
    if not isinstance(tool, dict):
        _err(errors, "tool must be an object")
    else:
        for key in ("name", "version", "git_sha"):
            _require_str(errors, tool, key, "tool")
    if not isinstance(cert.get("repo"), str) or not cert.get("repo"):
        _err(errors, "repo must be a non-empty string")
    for side in ("base", "head"):
        block = cert.get(side)
        if not isinstance(block, dict):
            _err(errors, f"{side} must be an object")
            continue
        _require_str(errors, block, "commit", side)
        digest = block.get("tarball_sha256")
        if not isinstance(digest, str) or not HEX64.match(digest):
            _err(errors, f"{side}.tarball_sha256 must be 64 hex chars")
    if not isinstance(cert.get("image_id"), str) or not cert.get("image_id"):
        _err(errors, "image_id must be a non-empty string")
    for key in ("ruby", "bundler", "rspec_core"):
        if not isinstance(cert.get(key), str) or not cert.get(key):
            _err(errors, f"{key} must be a non-empty string")
    locks = cert.get("gemfile_lock_sha256")
    if not isinstance(locks, dict):
        _err(errors, "gemfile_lock_sha256 must be an object")
    else:
        for side in ("base", "head"):
            digest = locks.get(side)
            if not isinstance(digest, str) or not HEX64.match(digest):
                _err(errors, f"gemfile_lock_sha256.{side} must be 64 hex chars")
    if not isinstance(cert.get("seed"), int):
        _err(errors, "seed must be an int")
    if not isinstance(cert.get("victim_id"), str) or not cert.get("victim_id"):
        _err(errors, "victim_id must be a non-empty string")
    polluters = cert.get("polluter_ids")
    if not isinstance(polluters, list) or not all(isinstance(item, str) for item in polluters or []):
        _err(errors, "polluter_ids must be a list of strings")
    commands = cert.get("commands")
    if not isinstance(commands, dict):
        _err(errors, "commands must be an object")
    else:
        for arm in ("A", "B", "C"):
            value = commands.get(arm)
            if not isinstance(value, str) or not value.startswith("rspec"):
                _err(errors, f"commands.{arm} must be an rspec command string")
    runs = cert.get("runs")
    if not isinstance(runs, dict):
        _err(errors, "runs must be an object")
    else:
        for side in ("base", "head"):
            block = runs.get(side)
            if not isinstance(block, dict):
                _err(errors, f"runs.{side} must be an object")
                continue
            for arm in ("A", "B", "C"):
                reps = block.get(arm)
                if not isinstance(reps, list) or len(reps) != 3:
                    _err(errors, f"runs.{side}.{arm} must be 3 runs")
                    continue
                for index, run in enumerate(reps, start=1):
                    _check_run(errors, run, f"runs.{side}.{arm}[{index}]")
    for key in ("verdicts", "plain_retry_verdict"):
        block = cert.get(key)
        if not isinstance(block, dict):
            _err(errors, f"{key} must be an object")
            continue
        for side in ("base", "head"):
            if block.get(side) not in VERDICTS:
                _err(errors, f"{key}.{side} must be one of {sorted(VERDICTS)}")
    if cert.get("label") not in OD_LABELS:
        _err(errors, "label must be CERTIFIED, CONTROL, UNRESOLVED, or REJECTED")
    return _attach_cause_set(errors, cert)
