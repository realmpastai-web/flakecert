"""Deterministic controlled-search plan within the run budget."""

import json
import random

from flakecert.paths import SEED
from flakecert.sources import (
    HASH_LEVELS,
    SEED_LEVELS,
    SOURCE_HASH,
    SOURCE_ORDER,
    SOURCE_SEED,
    SOURCE_SWITCH,
    SOURCE_TIME,
    SOURCE_TMP,
    SWITCH_LEVELS,
    TIME_LEVELS,
    TMP_LEVELS,
    default_schedule,
)


def _dedupe(orders: list[list[str]]) -> list[list[str]]:
    seen = set()
    out = []
    for order in orders:
        key = tuple(order)
        if key in seen or not order:
            continue
        seen.add(key)
        out.append(list(order))
    return out


def order_candidates(target: str, file_nodes: list[str], suite_nodes: list[str]) -> list[list[str]]:
    file_nodes = list(file_nodes)
    if target not in file_nodes and target:
        file_nodes = [target] + [node for node in file_nodes if node != target]
    others = [node for node in file_nodes if node != target]
    # Alone, then the same node twice (NIO), then file and suite orders.
    # Pair prefixes are how an OD-Vic polluter is reached without a plugin.
    candidates = [[target], [target, target], list(file_nodes), list(reversed(file_nodes))]
    if others:
        candidates.append(others + [target])
        candidates.append([target] + others)
    # Pair prefixes are how an OD-Vic polluter is reached. Keep them inside
    # the run budget; build_plan stops adding once the budget is full.
    for other in others[:150]:
        candidates.append([other, target])
        candidates.append([other, target, target])
    suite_others = [node for node in suite_nodes if node != target and node not in set(file_nodes)]
    for other in suite_others[:220]:
        candidates.append([other, target])
    return _dedupe(candidates)


def _canonical(schedule: dict) -> str:
    return json.dumps(schedule, sort_keys=True, default=str)


def build_plan(
    target: str,
    file_nodes: list[str],
    suite_nodes: list[str],
    sources: list[str],
    budget: int,
    test_id: str,
) -> tuple[list[dict], int]:
    orders = order_candidates(target, file_nodes, suite_nodes)
    plan: list[dict] = []
    seen = set()

    def add(schedule: dict) -> None:
        if len(plan) >= budget:
            return
        schedule = {key: schedule[key] for key in sources}
        key = _canonical(schedule)
        if key in seen:
            return
        seen.add(key)
        plan.append(schedule)

    for order in orders:
        add(default_schedule(order, sources))
        if len(plan) >= budget:
            return plan, len(plan)

    focus = orders[:3] or [[target]]
    for order in focus:
        base = default_schedule(order, sources)
        if SOURCE_SEED in sources:
            for level in SEED_LEVELS:
                trial = dict(base)
                trial[SOURCE_SEED] = level
                add(trial)
        if SOURCE_HASH in sources:
            for level in HASH_LEVELS:
                trial = dict(base)
                trial[SOURCE_HASH] = level
                add(trial)
        if SOURCE_TIME in sources:
            for level in TIME_LEVELS:
                trial = dict(base)
                trial[SOURCE_TIME] = level
                add(trial)
        if SOURCE_TMP in sources:
            for level in TMP_LEVELS:
                trial = dict(base)
                trial[SOURCE_TMP] = level
                add(trial)
        if SOURCE_SWITCH in sources:
            for level in SWITCH_LEVELS:
                trial = dict(base)
                trial[SOURCE_SWITCH] = level
                add(trial)

    # NOD flakes are often a seed, and a handful of fixed levels can miss it.
    # Sweep the target alone before calling the plan structured.
    if SOURCE_SEED in sources and target:
        sweep = random.Random(SEED + int(test_id[1:]) + 17)
        alone = default_schedule([target], sources)
        for _ in range(64):
            trial = dict(alone)
            trial[SOURCE_SEED] = str(sweep.randrange(0, 1000000))
            add(trial)

    structured = len(plan)
    rng = random.Random(SEED + int(test_id[1:]))
    seed_choices = SEED_LEVELS if SOURCE_SEED in sources else [""]
    hash_choices = HASH_LEVELS if SOURCE_HASH in sources else [""]
    time_choices = TIME_LEVELS if SOURCE_TIME in sources else [""]
    tmp_choices = TMP_LEVELS if SOURCE_TMP in sources else [""]
    switch_choices = SWITCH_LEVELS if SOURCE_SWITCH in sources else [""]
    guard = 0
    while len(plan) < budget and orders and guard < budget * 20:
        guard += 1
        order = orders[rng.randrange(len(orders))]
        schedule = default_schedule(order, sources)
        if SOURCE_SEED in sources:
            schedule[SOURCE_SEED] = seed_choices[rng.randrange(len(seed_choices))]
        if SOURCE_HASH in sources:
            schedule[SOURCE_HASH] = hash_choices[rng.randrange(len(hash_choices))]
        if SOURCE_TIME in sources:
            schedule[SOURCE_TIME] = time_choices[rng.randrange(len(time_choices))]
        if SOURCE_TMP in sources:
            schedule[SOURCE_TMP] = tmp_choices[rng.randrange(len(tmp_choices))]
        if SOURCE_SWITCH in sources:
            schedule[SOURCE_SWITCH] = switch_choices[rng.randrange(len(switch_choices))]
        add(schedule)
    return plan, structured


def observed_k(schedules: list[dict], sources: list[str]) -> int:
    if not schedules:
        return 1
    counts = []
    for source in sources:
        values = set()
        for schedule in schedules:
            value = schedule.get(source, "")
            if isinstance(value, list):
                value = tuple(value)
            values.add(value)
        counts.append(len(values))
    return max(counts) if counts else 1
