"""Parse pytest console output from pytest 3.1 through current."""

import re

from flakecert.cert import exception_type, failure_signature, normalize_traceback

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# pytest 3.7 prints "node <- defining_file STATUS" for tests inherited
# from another module. The node id itself has no spaces.
OUTCOME_LINE = re.compile(
    r"^(?P<node>\S+)(?:\s+<-\s+\S+)?"
    r"\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)"
    r"(?:\s+\([^)\n]*\))?(?:\s+\[[^\]]*\])?\s*$"
)
STATUS_MAP = {
    "PASSED": "passed",
    "FAILED": "failed",
    "ERROR": "error",
    "SKIPPED": "skipped",
    "XFAIL": "skipped",
    "XPASS": "failed",
}


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))


def _node_match(reported: str, node_id: str) -> bool:
    reported_n = _norm_node(reported)
    node_n = _norm_node(node_id)
    if reported == node_id or reported_n == node_n:
        return True
    if reported_n.endswith("/" + node_n) or node_n.endswith("/" + reported_n):
        return True
    if reported_n.endswith(node_n) or node_n.endswith(reported_n):
        return True
    rep_file, _, rep_rest = reported_n.partition("::")
    want_file, _, want_rest = node_n.partition("::")
    if rep_rest and rep_rest == want_rest and rep_file.split("/")[-1] == want_file.split("/")[-1]:
        return True
    return False


def find_outcome(output: str, node_id: str) -> str | None:
    output = strip_ansi(output)
    found = []
    for line in output.splitlines():
        match = OUTCOME_LINE.match(line.strip())
        if not match:
            continue
        if _node_match(match.group("node"), node_id):
            found.append(STATUS_MAP[match.group("status")])
    if not found:
        return None
    # A node listed twice (NIO: the same test run again in one session) keeps
    # the failure when either execution failed.
    for status in reversed(found):
        if status in {"failed", "error"}:
            return status
    return found[-1]


def extract_failure(output: str, node_id: str) -> str:
    output = strip_ansi(output)
    chunks = []
    for kind in ("FAILURES", "ERRORS"):
        for match in re.finditer(
            rf"=+\s*{kind}\s*=+\n(.*?)(?=\n=+\s|\Z)",
            output,
            re.S,
        ):
            chunks.append(match.group(1))
    blob = "\n".join(chunks).strip()
    if not blob:
        return ""
    parts = re.split(r"\n(?=_{10,}[^\n]*_{5,}\n)", "\n" + blob)
    parts = [part.strip() for part in parts if part.strip()]
    short = node_id.split("::")[-1] if node_id else ""
    exact = [part for part in parts if node_id and node_id in part]
    if exact:
        return "\n".join(exact).strip() + "\n"
    named = [part for part in parts if short and short in part]
    if named:
        return "\n".join(named).strip() + "\n"
    return "\n".join(parts).strip() + "\n"


def interpret(output: str, node_id: str, returncode: int | None) -> dict:
    outcome = find_outcome(output, node_id)
    tb = ""
    exc = "-"
    sig = "-"
    if outcome in {"failed", "error", None}:
        tb = extract_failure(output, node_id)
        if tb.strip():
            exc = exception_type(tb)
            sig = failure_signature(tb) or "-"
            if outcome is None:
                outcome = "failed"
    if outcome is None:
        if returncode == 124:
            outcome = "timeout"
        elif returncode not in (0, None):
            outcome = "error"
        else:
            outcome = "missing"
    if outcome == "timeout":
        exc = "Timeout"
        sig = "-"
    return {
        "outcome": outcome,
        "exc": exc or "-",
        "sig": sig or "-",
        "traceback": normalize_traceback(tb) if tb else "",
    }


def parse_nodeids(output: str) -> list[str]:
    output = strip_ansi(output)
    nodes = []
    collecting = False
    for line in output.splitlines():
        if line.startswith("COLLECT_FILE_BEGIN"):
            collecting = True
            continue
        if line.startswith("COLLECT_FILE_END"):
            collecting = False
            continue
        if line.startswith("NODEID "):
            nodes.append(line[len("NODEID ") :].strip())
            continue
        if collecting and line.strip():
            nodes.append(line.strip())
    if nodes:
        return _unique(nodes)
    for line in output.splitlines():
        stripped = line.strip()
        if "::" in stripped and " " not in stripped and not stripped.startswith("#"):
            nodes.append(stripped)
    return _unique(nodes)


def _unique(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _norm_node(node: str) -> str:
    # pytest 3.x unittest ids look like Class::()::method.
    return node.replace("::()::", "::")


def match_node(pytest_id: str, nodes: list[str]) -> str | None:
    found = _match_node(pytest_id, nodes)
    if found:
        return found
    normalized = [_norm_node(node) for node in nodes]
    found = _match_node(_norm_node(pytest_id), normalized)
    if not found:
        return None
    for node in nodes:
        if _norm_node(node) == found:
            return node
    return found


def _match_node(pytest_id: str, nodes: list[str]) -> str | None:
    if pytest_id in nodes:
        return pytest_id
    suffix = "/" + pytest_id
    suffixed = [node for node in nodes if node.endswith(suffix) or node.endswith(pytest_id)]
    if len(suffixed) == 1:
        return suffixed[0]
    if suffixed:
        suffixed.sort(key=len)
        return suffixed[0]
    file_part, sep, rest = pytest_id.partition("::")
    base = file_part.split("/")[-1]
    loose = []
    for node in nodes:
        node_file, node_sep, node_rest = node.partition("::")
        if node_sep and node_file.split("/")[-1] == base and node_rest == rest:
            loose.append(node)
    if loose:
        loose.sort(key=len)
        return loose[0]
    return None
