"""FlakeCert dry-run SABOTAGE control for IvanSkainet/arena-agent#206 (not upstream code).

Copy to tests/test_000_sabotage_popen_thread.py in the pinned checkout. It leaves a daemon thread
that keeps calling subprocess.run([sys.executable, "--version"]) for the rest of the process. That
reproduces the hypothesised mechanism (H4): a concurrent in-process Popen during
test_client_start_happy_path overwrites captured_popen["args"]. Expected (sealed H3): the target fails
with argv [sys.executable, "--version"] when run after this file with -p no:randomly.
"""
import subprocess
import sys
import threading


def _loop():
    while True:
        try:
            subprocess.run([sys.executable, "--version"], capture_output=True, timeout=5)
        except Exception:  # the target's fake Popen returns a mock; ignore whatever that does here
            pass


def test_sabotage_leaves_popen_thread_running():
    threading.Thread(target=_loop, name="flakecert-sabotage", daemon=True).start()
