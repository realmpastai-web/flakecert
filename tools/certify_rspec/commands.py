"""The A/B/C commands from the spec, as argv lists."""

from __future__ import annotations

import shlex
from pathlib import Path

# Container path. The host file is mounted here only for the arm that requires it.
ORDERING_REQUIRE = "/flakecert/ordering.rb"
IDS_ENV = "ids"


def ordering_dir() -> Path:
    return Path(__file__).resolve().parent


def spec_commands(seed: int, polluters: list[str], victim_id: str) -> dict[str, list[str]]:
    return {
        "A": ["rspec", "--seed", str(seed), *polluters, victim_id],
        "B": ["rspec", victim_id],
        "C": ["rspec", "--require", ORDERING_REQUIRE, victim_id, *polluters],
    }


def format_command(argv: list[str]) -> str:
    return shlex.join(argv)


def ordered_spec_commands(polluters: list[str], victim_id: str) -> dict[str, list[str]]:
    """Arms A, B, and C loaded through the ordering require.

    A runs the polluter ids then the victim. C runs the victim then the polluters.
    B runs the victim alone. The process order is the ids environment, checked
    by the order guard; these argument lists name the same ids.
    """
    require = ["rspec", "--require", ORDERING_REQUIRE]
    return {
        "A": [*require, *polluters, victim_id],
        "B": [*require, victim_id],
        "C": [*require, victim_id, *polluters],
    }


def ordered_ids(arm: str, polluters: list[str], victim_id: str) -> list[str]:
    """Example ids the ordering require must reproduce for one arm."""
    if arm == "A":
        return [*polluters, victim_id]
    if arm == "B":
        return [victim_id]
    if arm == "C":
        return [victim_id, *polluters]
    raise KeyError(arm)
