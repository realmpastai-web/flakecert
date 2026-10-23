import hashlib
import os
import subprocess
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def freeze_canonical(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(sorted(lines)) + ("\n" if lines else "")


def freeze_sha(text: str) -> str:
    return sha256_text(freeze_canonical(text))


def chmod_writable(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    mode = path.stat().st_mode
    os.chmod(path, mode | 0o200)


def run_cmd(cmd, timeout=None, cwd=None, env=None, input_text=None, check=False):
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=check,
        )
    except subprocess.TimeoutExpired as exc:
        # A timed-out pytest may already have printed the target node's line.
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        note = f"FLAKECERT_TIMEOUT_EXPIRED {timeout}\n"
        return subprocess.CompletedProcess(cmd, 124, stdout, stderr + note)


def log(msg: str) -> None:
    print(msg, flush=True)
