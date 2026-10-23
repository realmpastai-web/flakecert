"""Controlled sources. Each source is a logged knob with a fixed ladder of levels.

Empty string means the variable is unset (the plain-rerun default).
"""

SOURCE_ORDER = "order"
SOURCE_SEED = "seed"
SOURCE_HASH = "pythonhashseed"
SOURCE_TIME = "time_offset"
SOURCE_TMP = "tmpdir"
SOURCE_SWITCH = "switch_interval"

SEED_LEVELS = ["", "0", "1", "42", "20261017"]
HASH_LEVELS = ["", "0", "1", "42", "20261017"]
TIME_LEVELS = ["", "0", "86400", "-86400", "3600"]
TMP_LEVELS = ["", "fc-a", "fc-b", "fc-c", "fc-d"]
SWITCH_LEVELS = ["", "0.005", "0.001", "0.0001", "0.05"]

CORE_SOURCES = [SOURCE_ORDER, SOURCE_SEED, SOURCE_HASH, SOURCE_TIME, SOURCE_TMP]


def active_sources(thread_like: bool) -> list[str]:
    sources = list(CORE_SOURCES)
    if thread_like:
        sources.append(SOURCE_SWITCH)
    return sources


def default_schedule(order: list[str], sources: list[str]) -> dict:
    schedule = {
        SOURCE_ORDER: list(order),
        SOURCE_SEED: "",
        SOURCE_HASH: "",
        SOURCE_TIME: "",
        SOURCE_TMP: "",
        SOURCE_SWITCH: "",
    }
    return {key: schedule[key] for key in sources}


def detect_thread_like(text: str) -> tuple[bool, list[str]]:
    hits = []
    for token in ("threading", "asyncio", "concurrent.futures", "Thread(", "get_event_loop"):
        if token in text:
            hits.append(token)
    return bool(hits), hits
