"""Control surface shipped into each image.

This is not a pytest plugin. Order is applied by passing node ids on the
pytest command line. The other knobs are applied by sitecustomize.py, which
the image puts on PYTHONPATH, and by run_pytest.py before pytest starts.
Container-side scripts stay compatible with Python 3.7.
"""

from pathlib import Path

SITECUSTOMIZE = r'''# FlakeCert controls. Not a pytest plugin. Python 3.7 compatible.
import os
import sys

def _tolerate_duplicate_options():
    # Some repos register the same pytest option twice (conftest imported
    # twice). Collection dies before any test runs. Keep the first registration.
    try:
        from _pytest.config.argparsing import Parser
    except Exception:
        return
    if getattr(Parser.addoption, "_flakecert_wrapped", False):
        return
    original = Parser.addoption

    def addoption(self, *opts, **attrs):
        try:
            return original(self, *opts, **attrs)
        except Exception as exc:
            text = str(exc)
            if type(exc).__name__ in ("ArgumentError", "ValueError") and "conflict" in text:
                return None
            raise

    addoption._flakecert_wrapped = True
    Parser.addoption = addoption

def _apply():
    if getattr(sys, "_flakecert_applied", False):
        return
    sys._flakecert_applied = True
    _tolerate_duplicate_options()
    seed = os.environ.get("FLAKECERT_SEED", "")
    if seed != "":
        try:
            import random
            random.seed(int(seed))
        except Exception:
            pass
        try:
            import numpy
            numpy.random.seed(int(seed) % (2 ** 32 - 1))
        except Exception:
            pass
    offset = os.environ.get("FLAKECERT_TIME_OFFSET", "")
    if offset not in ("", "0", "0.0"):
        try:
            _patch_time(float(offset))
        except Exception:
            pass
    tmp = os.environ.get("FLAKECERT_TMPDIR", "")
    if tmp:
        try:
            if not os.path.isabs(tmp):
                tmp = os.path.join("/tmp", tmp)
            os.makedirs(tmp, exist_ok=True)
            os.environ["TMPDIR"] = tmp
            os.environ["TMP"] = tmp
            os.environ["TEMP"] = tmp
            import tempfile
            tempfile.tempdir = tmp
        except Exception:
            pass
    switch = os.environ.get("FLAKECERT_SWITCH_INTERVAL", "")
    if switch:
        try:
            sys.setswitchinterval(float(switch))
        except Exception:
            pass

def _patch_time(offset):
    import datetime
    import time as time_mod
    delta = datetime.timedelta(seconds=offset)
    real_time = time_mod.time
    time_mod.time = lambda: real_time() + offset
    real_localtime = time_mod.localtime

    def localtime(sec=None):
        if sec is None:
            sec = time_mod.time()
        return real_localtime(sec)

    time_mod.localtime = localtime
    real_dt = datetime.datetime

    class _ShiftedDateTime(real_dt):
        @classmethod
        def now(cls, tz=None):
            return real_dt.now(tz) + delta

        @classmethod
        def utcnow(cls):
            return real_dt.utcnow() + delta

    datetime.datetime = _ShiftedDateTime

try:
    _apply()
except Exception:
    pass
'''

COLLECT_NODES = r'''# Python 3.7 compatible node-id collector. Not used to control order.
import sys

nodes = []

def _record(items):
    if not items:
        return
    found = []
    for item in items:
        nodeid = getattr(item, "nodeid", "")
        if nodeid and nodeid not in found:
            found.append(nodeid)
    if not found:
        return
    nodes[:] = found
    try:
        handle = open("/tmp/fc-nodes.txt", "w")
        handle.write("\n".join(found) + "\n")
        handle.close()
    except Exception:
        pass

class Collector(object):
    # Explicit names. A *args hook is invoked with no arguments on
    # pytest 3.1 through 8, which made collection look empty.
    def pytest_collection_modifyitems(self, session, config, items):
        _record(items)

    def pytest_collection_finish(self, session):
        _record(getattr(session, "items", None) or [])

def _tolerate_duplicate_options():
    try:
        from _pytest.config.argparsing import Parser
    except Exception:
        return
    if getattr(Parser.addoption, "_flakecert_wrapped", False):
        return
    original = Parser.addoption

    def addoption(self, *opts, **attrs):
        try:
            return original(self, *opts, **attrs)
        except Exception as exc:
            text = str(exc)
            if type(exc).__name__ in ("ArgumentError", "ValueError") and "conflict" in text:
                return None
            raise

    addoption._flakecert_wrapped = True
    Parser.addoption = addoption

def main(argv):
    _tolerate_duplicate_options()
    import pytest
    args = list(argv)
    if "--collect-only" not in args:
        args = ["--collect-only"] + args
    rc = pytest.main(args, plugins=[Collector()])
    print("COLLECT_RC %s" % rc)
    for node in nodes:
        print("NODEID %s" % node)
    if nodes:
        return 0
    if isinstance(rc, int):
        return rc
    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''

RUN_PYTEST = r'''# Python 3.7 compatible pytest launcher. Applies sitecustomize first.
import os
import sys

def _load_controls():
    path = "/opt/flakecert/sitecustomize.py"
    if not os.path.exists(path):
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("flakecert_sitecustomize", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

def _hypothesis_seed(args):
    seed = os.environ.get("FLAKECERT_SEED", "")
    if seed == "":
        return args
    if "--hypothesis-seed" in " ".join(args):
        return args
    try:
        import hypothesis
    except Exception:
        return args
    parts = []
    for piece in getattr(hypothesis, "__version__", "0").split("."):
        if piece.isdigit():
            parts.append(int(piece))
        else:
            break
    if tuple(parts[:2]) < (4, 42):
        return args
    try:
        seed_text = str(int(seed))
    except Exception:
        return args
    return list(args) + ["--hypothesis-seed=%s" % seed_text]

def main(argv):
    _load_controls()
    args = _hypothesis_seed(list(argv))
    import pytest
    rc = pytest.main(args)
    if isinstance(rc, int):
        return rc
    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


def write_support_files(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    (dest / "collect_nodes.py").write_text(COLLECT_NODES, encoding="utf-8")
    (dest / "run_pytest.py").write_text(RUN_PYTEST, encoding="utf-8")
