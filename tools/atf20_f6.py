"""F6 pair verdict at one commit.

FIXED, NOT_FIXED, or INCONCLUSIVE. The pair arm is polluter then victim.
The reverse arm is victim then polluter and must pass. Reps that disagree
are INCONCLUSIVE.
"""

from __future__ import annotations

import re

from tools.certify_rspec.parse_rspec import parse_documentation
from tools.certify_rspec.verdict import FIXED, NOT_FIXED, stable_outcome_verdict

INCONCLUSIVE = "INCONCLUSIVE"
EXIT_LINE = re.compile(r"^RSPEC_EXIT:(\d+)\s*$", re.M)


def exit_code_from_log(text: str, fallback: int) -> int:
    found = EXIT_LINE.findall(text)
    if not found:
        return fallback
    return int(found[-1])


def doc_before_summary(text: str) -> str:
    for marker in ("\nFailures:\n", "\nFinished in"):
        index = text.find(marker)
        if index >= 0:
            return text[:index]
    return text


def polluter_before_victim(text: str, polluter_marker: str, victim_marker: str) -> bool:
    body = doc_before_summary(text)
    polluter_at = body.find(polluter_marker)
    victim_at = body.find(victim_marker)
    return polluter_at >= 0 and victim_at >= 0 and polluter_at < victim_at


def parse_run(text: str, fallback_exit: int) -> dict:
    return parse_documentation(text, exit_code_from_log(text, fallback_exit))


def judge_commit(
    pair_runs: list[dict],
    reverse_runs: list[dict],
    pair_texts: list[str],
    reverse_texts: list[str],
    victim_id: str,
    polluter_ids: list[str],
    polluter_marker: str,
    victim_marker: str,
    message_contains: str | None = None,
) -> str:
    if len(pair_runs) != 3 or len(reverse_runs) != 3:
        return INCONCLUSIVE
    if not all(polluter_before_victim(text, polluter_marker, victim_marker) for text in pair_texts):
        return INCONCLUSIVE
    if any(polluter_before_victim(text, polluter_marker, victim_marker) for text in reverse_texts):
        return INCONCLUSIVE
    if stable_outcome_verdict(reverse_runs, victim_id, polluter_ids) != FIXED:
        return INCONCLUSIVE
    pair_verdict = stable_outcome_verdict(pair_runs, victim_id, polluter_ids)
    if pair_verdict == FIXED:
        return FIXED
    if pair_verdict != NOT_FIXED:
        return INCONCLUSIVE
    if message_contains:
        for run in pair_runs:
            line = run.get("first_error_message_line") or ""
            if message_contains not in line:
                return INCONCLUSIVE
    return NOT_FIXED
