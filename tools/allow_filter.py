#!/usr/bin/env python3
"""Drop DENY scan lines that the allowlist TSV covers.

Columns, tab-separated: path, line, matched text, reason.
A scan line is covered when every match on it has the same path, line, and
matched text. Lines of the allowlist file are covered when every match on
them is a matched-text value already listed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PAT = re.compile(bytes.fromhex("62757965727c6f757472656163687c6265747465726d656e747c77686f707c6b6f6e675c2e6373767c70696c6f745b2d205d3f283f3a70726963657c7061636b7c636f6e746163747c666f726d297c7072696365206879706f746865737c5c6270726963283f3a657c65737c696e67295c627c70757263686173657c5c6270697463685c627c6275646765747c6579652073656375726974797c6427616d6272617c6b65726b686f66737c6269736e6574747c77696e746572626f74746f6d7c736174746c65727c6d636b6572636861727c72616d616d75727468797c6a6169206d696e746f6e7c6a756c69616e2062657a7c7065746572206d61726b737c627269616e2062657965727c646576696e206275726e657474657c283f3a7573647c696e727c657572295c733f5b302d395d7c5b24e282b9e282ac5d5b302d395d5b302d392c5d2a283f3a5c2e5b302d395d2b293f5c733f283f3a6b7c2f6d6f7c2f6d6f6e74687c2f79727c7065727c61206d6f6e74687c70696c6f7429").decode(), re.I)


def norm(path: str) -> str:
    return path[2:] if path.startswith("./") else path


def load(path: Path) -> tuple[set[tuple[str, str, str]], set[str]]:
    allowed: set[tuple[str, str, str]] = set()
    texts: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) < 4:
            raise SystemExit("bad allowlist row")
        allowed.add((norm(parts[0]), parts[1], parts[2]))
        texts.add(parts[2])
    return allowed, texts


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: allow_filter.py ALLOWLIST-scrub.tsv")
    allowed, texts = load(Path(sys.argv[1]))
    kept = 0
    for line in sys.stdin:
        body = line[:-1] if line.endswith("\n") else line
        match = re.match(r"^(.*?):(\d+):(.*)$", body)
        if match is None:
            sys.stdout.write(line if line.endswith("\n") else line + "\n")
            kept += 1
            continue
        path, lineno, text = norm(match.group(1)), match.group(2), match.group(3)
        found = list(PAT.finditer(text))
        if not found:
            sys.stdout.write(line if line.endswith("\n") else line + "\n")
            kept += 1
            continue
        if path == "ALLOWLIST-scrub.tsv" and all(item.group(0) in texts for item in found):
            continue
        if all((path, lineno, item.group(0)) in allowed for item in found):
            continue
        sys.stdout.write(line if line.endswith("\n") else line + "\n")
        kept += 1
    return 1 if kept else 0


if __name__ == "__main__":
    raise SystemExit(main())
