"""baseline/HASHES: frozen hashes plus image lines. frozen-set.csv stays untouched."""

from flakecert.paths import (
    FROZEN_SHA256,
    HASHES,
    IDOFT_COMMIT,
    IDOFT_SHA256,
)
from flakecert.util import chmod_writable


def core_lines(matched: int) -> list[str]:
    return [
        f"frozen-set.csv sha256 {FROZEN_SHA256}",
        f"idoft py-data.csv commit {IDOFT_COMMIT} sha256 {IDOFT_SHA256}",
        f"idoft-rows-matched {matched}",
    ]


def read_image_lines() -> list[str]:
    if not HASHES.exists():
        return []
    lines = []
    for line in HASHES.read_text(encoding="utf-8").splitlines():
        if line.startswith("image ") or line.startswith("install "):
            lines.append(line)
    return lines


def write_hashes(matched: int, image_lines: list[str] | None = None) -> None:
    if image_lines is None:
        image_lines = read_image_lines()
    text = "\n".join(core_lines(matched) + image_lines).rstrip() + "\n"
    HASHES.parent.mkdir(parents=True, exist_ok=True)
    chmod_writable(HASHES.parent)
    chmod_writable(HASHES)
    HASHES.write_text(text, encoding="utf-8")


def upsert_image_line(line: str, matched: int) -> None:
    ident = line.split()[1]
    kept = []
    for old in read_image_lines():
        parts = old.split()
        if len(parts) >= 2 and parts[1] == ident and old.startswith("image "):
            continue
        if old.startswith("install ") and len(parts) >= 2 and parts[1] == ident:
            continue
        kept.append(old)
    kept.append(line)
    write_hashes(matched, kept)
