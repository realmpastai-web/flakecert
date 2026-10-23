#!/usr/bin/env python3.11
"""make envs: one image per effective main test, interpreter ladder logged."""

import csv
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flakecert.discover import configured_testpaths, discover_rootdir, resolve_test_file
from flakecert.effective import SWAP_FIELDS, derive, evidence_path, load_frozen, load_swaps, slug
from flakecert.hashes import upsert_image_line
from flakecert.install import (
    attempt_count,
    build_base_images,
    build_rung,
    bump_attempt,
    concise_log,
    prepare_context,
    render_install_sh,
)
from flakecert.parse import match_node
from flakecert.paths import CACHE, CERTS, ENVS, LEDGER, PY_LADDER
from flakecert.runner import cleanup_our_containers, collect_in_image, image_id, pip_freeze, python_version
from flakecert.search import sources_for_text
from flakecert.sources import detect_thread_like
from flakecert.util import freeze_sha, log, run_cmd, sha256_file
from flakecert.vcs import checkout

IST = timezone(timedelta(hours=5, minutes=30))


def _base_ready(py: str) -> bool:
    proc = run_cmd(["docker", "image", "inspect", f"flakecert-base:{py}"], timeout=60)
    return proc.returncode == 0


def _collect_match(tag: str, pytest_id: str, rel: str):
    # -q hides node ids on pytest 8+. Clear addopts first so xdist/network
    # plugins from the project ini are not required to collect.
    attempts = [
        (
            ["-p", "no:cacheprovider", "-o", "addopts=", rel],
            ["-v", "--tb=short", "-p", "no:cacheprovider", "-o", "addopts="],
        ),
        (
            ["-p", "no:cacheprovider", rel],
            ["-v", "--tb=short", "-p", "no:cacheprovider"],
        ),
    ]
    last = ""
    for collect_args, run_args in attempts:
        try:
            nodes, output = collect_in_image(tag, collect_args, timeout=240)
        except Exception as exc:
            last = str(exc)
            continue
        last = output
        node = match_node(pytest_id, nodes)
        if node:
            return node, nodes, run_args, output
    return None, [], [], last


def _suite_nodes(tag: str, root: Path, rel: str) -> tuple[list[str], str]:
    paths = configured_testpaths(root)
    target = paths[0] if paths else str(Path(rel).parent.as_posix())
    if target in ("", "."):
        return [], "test_file"
    try:
        nodes, _output = collect_in_image(tag, ["-q", "-p", "no:cacheprovider", target], timeout=180)
    except Exception:
        return [], "test_file"
    if not nodes:
        return [], "test_file"
    scope = "configured_suite" if paths else "test_directory"
    return nodes[:400], scope


def _thread_text(root: Path, rel: str) -> str:
    parts = []
    path = root / rel
    if path.is_file():
        parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    conf = path.parent / "conftest.py"
    if conf.is_file():
        parts.append(conf.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _existing_meta(test_id: str) -> dict | None:
    if os.environ.get("FLAKECERT_REBUILD") == "1":
        return None
    path = CACHE / "meta" / f"{test_id}.json"
    if not path.exists():
        return None
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    tag = meta.get("image_tag") or ""
    if not tag or not meta.get("node_id") or not meta.get("image_digest"):
        return None
    probe = run_cmd(["docker", "image", "inspect", tag], timeout=30)
    if probe.returncode != 0:
        return None
    return meta


def _frozen_freeze_text(test_id: str) -> str | None:
    """Pip freeze captured from the image that minted this certificate, if we have one."""
    if test_id != "F08":
        return None
    path = ENVS / "F08.freeze.txt"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def apply_freeze_constraints(script: str, freeze_text: str) -> str:
    """Install with `pip install -c` built from a frozen pip freeze.

    Direct-reference lines (name @ file://...) stay constraints. Exact
    name==version lines are also installed so a later rebuild resolves to
    that freeze instead of floating unpinned requirements.
    """
    constraints: list[str] = []
    pins: list[str] = []
    local_paths: list[str] = []
    for raw in freeze_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        constraints.append(line)
        if " @ " in line:
            ref = line.split(" @ ", 1)[1].strip()
            if ref.startswith("file://"):
                ref = ref[len("file://") :]
            local_paths.append(ref)
        else:
            pins.append(line)
    constraint_body = "\n".join(constraints) + ("\n" if constraints else "")
    pin_body = "\n".join(pins) + ("\n" if pins else "")
    prelude = (
        "cat > /tmp/fc-constraints.txt << 'FC_CONSTRAINTS_END'\n"
        f"{constraint_body}"
        "FC_CONSTRAINTS_END\n"
        "cat > /tmp/fc-pins.txt << 'FC_PINS_END'\n"
        f"{pin_body}"
        "FC_PINS_END\n"
        'echo "FLAKECERT_INSTALL constraints $(grep -cve \'^[[:space:]]*$\' /tmp/fc-constraints.txt)"\n'
    )
    rewritten = []
    for line in script.splitlines(keepends=True):
        if "pip install" in line and "-c /tmp/fc-constraints.txt" not in line:
            line = line.replace("pip install", "pip install -c /tmp/fc-constraints.txt", 1)
        rewritten.append(line)
    body = "".join(rewritten)
    local_cmds = []
    for path in local_paths:
        quoted = path.replace("'", "'\\''")
        local_cmds.append(
            "python -m pip install -c /tmp/fc-constraints.txt --no-deps --no-build-isolation "
            f"'{quoted}' || echo \"FLAKECERT_INSTALL constraints_local_fail {quoted}\""
        )
    local_block = "\n".join(local_cmds)
    sync = f"""echo "FLAKECERT_INSTALL constraints_sync"
if ! python -m pip install --prefer-binary -c /tmp/fc-constraints.txt -r /tmp/fc-pins.txt; then
  echo "FLAKECERT_INSTALL constraints_sync_fail"
fi
{local_block}
python - << 'PY'
import pathlib, subprocess
wanted = {{
    ln.strip()
    for ln in pathlib.Path("/tmp/fc-constraints.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
}}
out = subprocess.check_output(["python", "-m", "pip", "freeze"], text=True)
for line in out.splitlines():
    item = line.strip()
    if item and item not in wanted:
        name = item.split("==", 1)[0].split("@", 1)[0].strip()
        print("FLAKECERT_INSTALL constraints_extra", item)
        subprocess.call(["python", "-m", "pip", "uninstall", "-y", name])
PY
echo "FLAKECERT_INSTALL constraints_sync_done"
"""
    needle = "if ! python -c 'import pytest'"
    idx = body.rfind(needle)
    if idx == -1:
        body = body + "\n" + sync
    else:
        body = body[:idx] + sync + "\n" + body[idx:]
    if body.startswith("#!"):
        first, rest = body.split("\n", 1)
        body = first + "\n" + prelude + rest
    else:
        body = prelude + body
    return body


def _drop_mismatched_cert(test_id: str, live_freeze_sha: str) -> bool:
    """Drop F08 when a constrained rebuild still does not match. Do not re-mint."""
    if test_id != "F08":
        return False
    cert_path = CERTS / "F08.json"
    if not cert_path.is_file():
        return False
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    expected = cert.get("pip_freeze_sha") or ""
    if live_freeze_sha == expected:
        log(f"F08 pip_freeze_sha matches cert {expected}")
        return False
    reason = (
        "pip_freeze_mismatch after pip install -c constraints from frozen pip freeze; "
        f"cert={expected} live={live_freeze_sha}"
    )
    LEDGER.mkdir(parents=True, exist_ok=True)
    with (LEDGER / "dropped.log").open("a", encoding="utf-8") as handle:
        handle.write(f"F08 dropped {reason}\n")
    cert_path.unlink()
    log(f"F08 dropped {reason}")
    return True


def install_one(row: dict) -> dict:
    test_id = row["id"]
    existing = _existing_meta(test_id)
    if existing:
        line = (
            f"image {test_id} tag={existing['image_tag']} python={existing.get('python', '')} "
            f"digest={existing['image_digest']} pip_freeze_sha256={existing.get('pip_freeze_sha', '')} "
            f"node_id={existing['node_id']}"
        )
        log(f"{test_id} image reused")
        return {"id": test_id, "ok": True, "line": line, "meta": existing}
    log(f"{test_id} clone {slug(row['project_url'])}@{row['sha'][:10]}")
    source = checkout(row["project_url"], row["sha"], CACHE / "src" / test_id)
    script, rels = render_install_sh(source)
    frozen = _frozen_freeze_text(test_id)
    if frozen:
        script = apply_freeze_constraints(script, frozen)
        log(f"{test_id} install uses pip install -c constraints from frozen pip freeze")
    ctx = prepare_context(test_id, source, script)
    rel = resolve_test_file(source, row["pytest_id"])
    install_log = ENVS / f"{test_id}.install.log"
    chunks = [
        f"rung files {','.join(rels) if rels else 'none'}",
        f"rung test_file {rel}",
    ]
    selected = None
    fallback = None
    collect_output = ""
    for py in PY_LADDER:
        chunks.append(f"rung python={py} start")
        code, full = build_rung(test_id, py, ctx)
        brief = concise_log(full).rstrip()
        chunks.append(brief)
        chunks.append(f"rung python={py} build_exit={code}")
        if code != 0:
            chunks.append(f"rung python={py} result=FAIL build")
            if fallback is None:
                run_cmd(["docker", "rmi", "-f", f"flakecert:{test_id}"], timeout=60)
            continue
        node, nodes, run_args, collect_output = _collect_match(f"flakecert:{test_id}", row["pytest_id"], rel)
        chunks.append(f"collect nodes={len(nodes)} matched={node or 'none'}")
        complete = "FLAKECERT_INSTALL reqs_complete yes" in full or "FLAKECERT_INSTALL reqs_complete yes" in brief
        if node and complete:
            chunks.append(f"rung python={py} result=PASS")
            selected = (py, node, nodes, run_args)
            break
        if node and fallback is None:
            chunks.append(f"rung python={py} result=KEEP incomplete requirements")
            run_cmd(
                ["docker", "tag", f"flakecert:{test_id}", f"flakecert:{test_id}-fb"],
                timeout=60,
            )
            fallback = (py, node, nodes, run_args)
            continue
        chunks.append(f"rung python={py} result=FAIL collect")
        tail = "\n".join(collect_output.splitlines()[-20:])
        chunks.append(tail)
        if fallback is None:
            run_cmd(["docker", "rmi", "-f", f"flakecert:{test_id}"], timeout=60)
    if selected is None and fallback is not None:
        selected = fallback
        run_cmd(
            ["docker", "tag", f"flakecert:{test_id}-fb", f"flakecert:{test_id}"],
            timeout=60,
        )
        chunks.append("rung selected=fallback")
    else:
        run_cmd(["docker", "rmi", "-f", f"flakecert:{test_id}-fb"], timeout=60)
    install_log.write_text("\n".join(chunks) + "\n", encoding="utf-8")
    if not selected:
        count = bump_attempt(test_id)
        return {"id": test_id, "ok": False, "attempts": count, "row": row, "log": str(install_log)}
    py, node, nodes, run_args = selected
    tag = f"flakecert:{test_id}"
    digest = image_id(tag)
    freeze = freeze_sha(pip_freeze(tag))
    if _drop_mismatched_cert(test_id, freeze):
        log(f"{test_id} certificate removed; image_digest stays informational and the cert is not re-minted")
    pyver = python_version(tag)
    suite, scope = _suite_nodes(tag, source, rel)
    thread_like, hits = detect_thread_like(_thread_text(source, rel))
    meta = {
        "id": test_id,
        "category": row["category"],
        "project_url": row["project_url"],
        "sha": row["sha"],
        "pytest_id": row["pytest_id"],
        "node_id": node,
        "test_file": rel,
        "rootdir": discover_rootdir(source, rel),
        "file_nodes": nodes,
        "suite_nodes": suite,
        "order_scope": scope,
        "image_tag": tag,
        "image_digest": digest,
        "pip_freeze_sha": freeze,
        "python": pyver,
        "ladder_python": py,
        "pytest_args": run_args,
        "sources": sources_for_text(thread_like),
        "thread_hits": hits,
        "timeout_s": 180,
    }
    meta_path = CACHE / "meta" / f"{test_id}.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    line = (
        f"image {test_id} tag={tag} python={pyver} digest={digest} "
        f"pip_freeze_sha256={freeze} node_id={node}"
    )
    return {"id": test_id, "ok": True, "line": line, "meta": meta}


def _append_swap(removed: dict, replacement: dict | None, log_path: Path, reason: str) -> None:
    from flakecert.paths import SWAPS

    evidence_name = f"snap-{removed['id']}-install.log"
    dest = evidence_path(evidence_name)
    dest.write_bytes(log_path.read_bytes())
    digest = sha256_file(dest)
    ts = datetime.now(IST).strftime("%Y-%m-%dT%H:%M+05:30")
    row = {
        "swap_id": _next_swap_id(),
        "ts_ist": ts,
        "removed_id": removed["id"],
        "removed_role": removed["role"],
        "removed_category": removed["category"],
        "replacement_id": replacement["id"] if replacement else "",
        "replacement_role": "reserve->main" if replacement else "retired",
        "replacement_category": replacement["category"] if replacement else "",
        "rule": "install failure after 2 attempts",
        "reason": reason,
        "evidence_file": evidence_name,
        "evidence_sha256": digest,
    }
    with SWAPS.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SWAP_FIELDS, lineterminator="\n")
        writer.writerow(row)
    log(f"swap appended {row['swap_id']} {removed['id']} -> {row['replacement_id'] or 'retired'}")


def _next_swap_id() -> str:
    swaps = load_swaps()
    nums = []
    for swap in swaps:
        raw = swap["swap_id"]
        if raw.startswith("S") and raw[1:].isdigit():
            nums.append(int(raw[1:]))
    return "S%02d" % (max(nums) + 1 if nums else 1)


def _next_reserve(rows, swaps) -> dict | None:
    _mains, reserves = derive(rows, swaps)
    by_id = {row["id"]: row for row in rows}
    if not reserves:
        return None
    return by_id[reserves[0]]


def main() -> int:
    os.environ.setdefault("DOCKER_BUILDKIT", "1")
    cleanup_our_containers()
    for py in PY_LADDER:
        if os.environ.get("FLAKECERT_REBUILD_BASE") == "1" or not _base_ready(py):
            build_base_images()
            break
    else:
        log("base images present")
    # If any base is missing, build_base_images builds all. If the loop broke, done.
    missing = [py for py in PY_LADDER if not _base_ready(py)]
    if missing:
        build_base_images()
    rows = load_frozen()
    swaps = load_swaps()
    by_id = {row["id"]: row for row in rows}
    mains, _reserves = derive(rows, swaps)
    jobs = int(os.environ.get("FLAKECERT_BUILD_JOBS", "4"))
    results = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(install_one, by_id[item]): item for item in mains}
        for future in as_completed(futures):
            test_id = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                log(f"{test_id} HARNESS ERROR {exc}")
                results.append({"id": test_id, "ok": False, "attempts": attempt_count(test_id), "error": str(exc)})
    matched = 32
    for result in sorted(results, key=lambda item: item["id"]):
        if result.get("ok"):
            upsert_image_line(result["line"], matched)
            log(result["line"])
        else:
            log(f"{result['id']} install failed attempts={result.get('attempts')}")
            attempts = int(result.get("attempts") or 0)
            if attempts >= 2 and result.get("row") and result.get("log"):
                swaps = load_swaps()
                replacement = _next_reserve(rows, swaps)
                _append_swap(
                    result["row"],
                    replacement,
                    Path(result["log"]),
                    "install ladder failed twice (3.11, 3.9, 3.8, 3.7)",
                )
                if replacement:
                    log(f"promoted {replacement['id']} is not built in this pass")
    ok = sum(1 for result in results if result.get("ok"))
    log(f"envs built {ok}/{len(mains)}")
    cleanup_our_containers()
    return 0


if __name__ == "__main__":
    sys.exit(main())
