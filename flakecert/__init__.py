"""FlakeCert PoC harness (v0.2).

Controls live outside pytest plugins: node-id order on the command line,
and seeds, PYTHONHASHSEED, time offset, tmpdir, and switch interval via
environment plus sitecustomize.py.
"""

__version__ = "0.2.0"
