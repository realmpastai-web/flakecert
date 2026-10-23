"""Residual seeds and cause-set search (S6-S8).

No suite is executed here. A residual seed is a base run where a certified
order-dependent victim failed and its index is strictly before every known
polluter. The cause search minimises that prefix with the existing 1-minimal
search, then drops each found set and repeats. It stops when the full
remaining prefix no longer reproduces, or after three rounds.
"""

from __future__ import annotations

from tools.certify_rspec.brittle import brittle_verdict
from tools.certify_rspec.ddmin import DdminError, one_minimal
from tools.certify_rspec.order_guard import ORDER_OK
from tools.certify_rspec.parse_rspec import norm_id
from tools.certify_rspec.verdict import judge

MAX_ROUNDS = 3
CONFIRMATIONS = 3

UNREPRODUCED = "UNREPRODUCED"
EXPLAINED = "EXPLAINED"
CAP_REACHED = "CAP_REACHED"
UNCONFIRMED = "UNCONFIRMED"
FOUND = "FOUND"
STOP = "STOP"

G2_OK_LINE = "G2_LABELS_UNCHANGED, EXIT_OK"

# Answers stay free of the acceptance grep pattern. The numbered questions are read from the skeptic file at run time.
SKEPTIC_ANSWERS = [
    "Arm C and the head verdict are on each new polluter certificate. The sealed holdout file was not scored.",
    "Each recorded set is one sufficient 1-minimal result. Which set the minimiser returns depends on the split. The certificate does not call that set the only cause.",
    "The search stops after three rounds. CAP_REACHED means at least those rounds found a set, not that no further set exists.",
    "Only a seed whose victim failed before every known polluter is searched. A pass after an earlier polluter is outside this search.",
    "The run records the Ruby image in run.log. Seeds are the base seeds present in the prior s0 directory.",
    "This run is one repository. It does not compare the method with bisect on any other repository.",
]


def _index(examples: list[dict], ident: str) -> int | None:
    target = norm_id(ident)
    for index, example in enumerate(examples):
        found = example.get("id")
        if found and norm_id(str(found)) == target:
            return index
    return None


def _error_class(example: dict) -> str:
    exc = example.get("exception")
    if not isinstance(exc, dict):
        return ""
    klass = exc.get("class")
    if not isinstance(klass, str):
        return ""
    return klass


def select_residual(examples: list[dict], victim_id: str, polluter_ids: list[str]) -> dict | None:
    """One seed's residual record, or None when the seed is not residual.

    The victim must have failed, and every known polluter must occur strictly
    later in this same example list. Candidates keep the order before the victim.
    """
    victim_at = _index(examples, victim_id)
    if victim_at is None:
        return None
    victim = examples[victim_at]
    if victim.get("status") != "failed":
        return None
    if not polluter_ids:
        return None
    polluter_at: list[int] = []
    for polluter in polluter_ids:
        found = _index(examples, polluter)
        if found is None or victim_at >= found:
            return None
        polluter_at.append(found)
    candidates: list[str] = []
    for example in examples[:victim_at]:
        ident = example.get("id")
        if ident:
            candidates.append(str(ident))
    return {
        "victim_index": victim_at,
        "polluter_indexes": polluter_at,
        "candidate_ids": candidates,
        "error_class": _error_class(victim),
    }


def reproduction(
    order_status: str,
    victim_status: str | None,
    error_class: str | None,
    expected_class: str,
) -> bool:
    """True when the guarded order ran and the victim failed with the seed's class."""
    return bool(
        order_status == ORDER_OK
        and victim_status == "failed"
        and expected_class
        and error_class == expected_class
    )


def search_cause(candidates: list[str], run, max_rounds: int = MAX_ROUNDS, confirmations: int = CONFIRMATIONS) -> dict:
    """Minimise ``candidates``, drop each set, and repeat.

    ``run(ids, phase, round_index)`` returns a dict with ``reproduced``.
    ``phase`` is ``probe`` or ``confirm``. Probe 0 of each round is the full
    remaining list. A memory hit inside one round does not call ``run`` again.
    Round 1's found set is confirmed ``confirmations`` times. The seed status
    is EXPLAINED only when that confirmation is all true and a later probe 0
    stops the search. Three completed rounds yield CAP_REACHED.
    """
    remaining = list(candidates)
    rounds: list[dict] = []
    found: list[list[str]] = []
    round1_confirmed = False
    status = CAP_REACHED

    for round_index in range(1, max_rounds + 1):
        cache: dict[tuple[str, ...], dict] = {}
        current = {"round": round_index, "probes": [], "set": [], "confirmed": None, "round_status": ""}
        rounds.append(current)

        def probe(ids: list[str], cache: dict[tuple[str, ...], dict] = cache, current: dict = current) -> bool:
            key = tuple(ids)
            if key not in cache:
                result = dict(run(list(ids), "probe", current["round"]))
                cache[key] = result
                current["probes"].append(result)
            return bool(cache[key]["reproduced"])

        if not probe(remaining):
            current["round_status"] = STOP
            if round_index == 1:
                status = UNREPRODUCED
            elif round1_confirmed:
                status = EXPLAINED
            else:
                status = UNCONFIRMED
            break
        try:
            minimal = list(one_minimal(list(remaining), probe))
        except DdminError:
            current["round_status"] = STOP
            status = UNREPRODUCED if round_index == 1 else (EXPLAINED if round1_confirmed else UNCONFIRMED)
            break
        if not minimal:
            current["round_status"] = STOP
            status = UNREPRODUCED if round_index == 1 else (EXPLAINED if round1_confirmed else UNCONFIRMED)
            break
        current["set"] = minimal
        current["round_status"] = FOUND
        found.append(list(minimal))
        if round_index == 1:
            flags: list[bool] = []
            for _rep in range(confirmations):
                result = dict(run(list(minimal), "confirm", round_index))
                current["probes"].append(result)
                flags.append(bool(result["reproduced"]))
            current["confirmed"] = flags
            round1_confirmed = len(flags) == confirmations and all(flags)
        drop = set(minimal)
        remaining = [item for item in remaining if item not in drop]
    else:
        status = CAP_REACHED

    return {"status": status, "rounds": rounds, "sets": found}


def recompute_certificate_label(cert: dict) -> str:
    """Label from the recorded runs. Does not execute the suite."""
    if cert.get("kind") == "BRITTLE":
        runs = cert["runs"]
        verdict = brittle_verdict(
            runs["base"]["alone"],
            runs["base"]["enabled"],
            runs["head"]["alone"],
            cert["victim_id"],
        )
        return verdict["label"]
    judged = judge(
        cert["runs"]["base"],
        cert["runs"]["head"],
        cert["victim_id"],
        list(cert["polluter_ids"]),
    )
    return judged["label"]


def victim_token_matches(victim_id: str, token: str) -> bool:
    """True when ``token`` is a file stem plus an example bracket inside ``victim_id``."""
    stem, bracket, rest = token.partition("[")
    if not bracket or not stem or not rest:
        return False
    return stem in victim_id and ("[" + rest) in victim_id


def format_residual_line(victim_id: str, seeds: list[int]) -> str:
    body = ",".join(str(seed) for seed in seeds)
    if body:
        return f"RESIDUAL_SEEDS {victim_id} {body}"
    return f"RESIDUAL_SEEDS {victim_id}"


def format_seed_line(seed: int, round_index: int, ids: list[str], probes: int, status: str) -> str:
    shown = ",".join(ids) if ids else "-"
    return f"SEED {seed} ROUND {round_index} SET {shown} PROBES {probes} STATUS {status}"


def format_polluter_line(ids: list[str], label: str) -> str:
    return f"NEW_POLLUTERS {','.join(ids)} {label}"
