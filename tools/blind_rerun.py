#!/usr/bin/env python3.11
"""Blind replay. The only input is one certificate JSON path."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakecert.cert import load_cert, schedule_dict
from flakecert.runner import Session, pip_freeze, python_version, run_schedule
from flakecert.util import freeze_sha


def main() -> int:
    if len(sys.argv) != 2:
        print("FAIL")
        print("-")
        print("harness_error")
        print("usage")
        return 2
    cert = load_cert(sys.argv[1])
    try:
        live_freeze = freeze_sha(pip_freeze(cert["image_tag"]))
        live_python = python_version(cert["image_tag"])
    except Exception as exc:
        print("FAIL")
        print("-")
        print("harness_error")
        print(type(exc).__name__)
        return 1
    # image_digest is informational. A rebuilt image with the same freeze replays.
    if live_freeze != cert["pip_freeze_sha"]:
        print("FAIL")
        print("-")
        print("harness_error")
        print("pip_freeze_mismatch")
        return 1
    if live_python != cert.get("python"):
        print("FAIL")
        print("-")
        print("harness_error")
        print("python_mismatch")
        return 1
    schedule = schedule_dict(cert)
    try:
        with Session(cert["id"], cert["image_tag"]) as session:
            result = run_schedule(
                session,
                cert["node_id"],
                schedule,
                list(cert.get("pytest_args") or ["-v", "--tb=short", "-p", "no:cacheprovider"]),
                int(cert.get("timeout_s") or 300),
            )
    except Exception as exc:
        print("FAIL")
        print("-")
        print("harness_error")
        print(type(exc).__name__)
        return 1
    expected = cert["expected_failure"]["sig"]
    ok = result.outcome in {"failed", "error"} and result.sig == expected
    print("PASS" if ok else "FAIL")
    print(result.sig)
    print(result.outcome)
    print(result.exc)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
