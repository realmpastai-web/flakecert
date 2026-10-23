"""S1-S5 pipeline. The CLI does not accept victim or polluter names."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from tools.certify_rspec import __version__
from tools.certify_rspec.certificate import validate_certificate
from tools.certify_rspec.classify import ORDER_DEPENDENT, alone_passed, classify_s2, predecessors
from tools.certify_rspec.commands import format_command, spec_commands
from tools.certify_rspec.parse_rspec import (
    example_location,
    parse_bisect,
    parse_outcome,
    polluter_ids,
)
from tools.certify_rspec.replay import write_replay_script
from tools.certify_rspec.runner import (
    argv_length,
    command_preview,
    docker_bash,
    docker_rspec,
    rspec_docker_cmd,
)
from tools.certify_rspec.sources import (
    bundle_check,
    commit_from_url,
    ensure_tarball,
    ensure_tree,
    repo_from_url,
    sha256_file,
)
from tools.certify_rspec.exit_rule import classification_exit_ok
from tools.certify_rspec.verdict import judge

REPO_ROOT = Path(__file__).resolve().parents[2]
REPS = 3


class RunLog:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._fh = path.open("a", encoding="utf-8", buffering=1)
        self._lock = threading.Lock()

    def write(self, text: str, echo: bool = False) -> None:
        if text and not text.endswith("\n"):
            text += "\n"
        with self._lock:
            self._fh.write(text)
            self._fh.flush()
        if echo:
            sys.stderr.write(text)
            sys.stderr.flush()

    def section(self, title: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.write(f"\n===== {title} {stamp} =====", echo=True)

    def close(self) -> None:
        with self._lock:
            self._fh.flush()
            self._fh.close()


def _slug(location: str) -> str:
    text = location[2:] if location.startswith("./") else location
    text = text.replace("/", "_").replace(":", "-")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    return text[:180] or "example"


def _git_sha(root: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    sha = proc.stdout.strip() if proc.returncode == 0 else "unknown"
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if dirty.stdout.strip():
        return sha + "-dirty"
    return sha


def _image_id(image: str) -> str:
    proc = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or f"image inspect failed for {image}")
    return proc.stdout.strip()


def _docker_server_version() -> str:
    proc = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip()


def _parse_versions(text: str) -> dict[str, str]:
    ruby = ""
    bundler = ""
    rspec_core = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("ruby ") and not ruby:
            ruby = stripped
        if stripped.startswith("Bundler version") and not bundler:
            bundler = stripped
        match = re.search(r"rspec-core ([0-9][^\s]*)", stripped)
        if match:
            rspec_core = match.group(1)
    return {"ruby": ruby, "bundler": bundler, "rspec_core": rspec_core}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_log(path: Path, header: str, body: str, exit_code: int) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if body and not body.endswith("\n"):
        body += "\n"
    content = f"{header}\n{body}docker_exit={exit_code}\n"
    path.write_text(content, encoding="utf-8")
    return _sha256_text(content)


def _run_rspec(
    log: RunLog,
    image: str,
    tree: Path,
    rspec_argv: list[str],
    log_path: Path,
    json_host: Path | None,
    timeout: int,
    logical: str,
    bundler: str | None = None,
    extra_mounts: list[str] | None = None,
    extra_env: list[tuple[str, str]] | None = None,
) -> dict:
    if json_host is not None:
        json_host.parent.mkdir(parents=True, exist_ok=True)
        if json_host.exists():
            json_host.unlink()
    cmd = rspec_docker_cmd(
        image,
        tree,
        rspec_argv,
        json_host,
        bundler=bundler,
        extra_mounts=extra_mounts,
        extra_env=extra_env,
    )
    header = "\n".join(
        [
            f"+ logical={logical}",
            f"+ rspec_argv_len={argv_length(rspec_argv)}",
            f"+ rspec_argv_n={len(rspec_argv)}",
            f"+ docker_argv_len={argv_length(cmd)}",
            f"+ docker_argv_n={len(cmd)}",
            "+ " + command_preview(cmd),
        ]
    )
    log.write(header, echo=False)
    log.write(
        f"run {log_path.name} rspec_argv_len={argv_length(rspec_argv)} timeout={timeout}",
        echo=True,
    )
    code, text, elapsed = docker_rspec(
        image,
        tree,
        rspec_argv,
        json_host,
        timeout,
        bundler=bundler,
        extra_mounts=extra_mounts,
        extra_env=extra_env,
    )
    header = header + f"\nelapsed_s={elapsed:.3f}"
    digest = _write_log(log_path, header, text, code)
    log.write(text, echo=False)
    log.write(f"docker_exit={code} elapsed_s={elapsed:.3f} log_sha256={digest}", echo=True)
    outcome = parse_outcome(text, code, json_host)
    outcome["log_sha256"] = digest
    outcome["log"] = str(log_path)
    outcome["elapsed_s"] = round(elapsed, 3)
    return outcome


def _json_name(stem: str) -> str:
    return stem + ".json"


def _exec_argv(args_after_rspec: list[str], json_name: str | None) -> list[str]:
    if json_name is None:
        return ["--no-color", *args_after_rspec]
    # Documentation stays on the container stdout (the evidence log). --out binds
    # only to the json formatter that follows it.
    return [
        "--format",
        "documentation",
        "--no-color",
        *args_after_rspec,
        "--format",
        "json",
        "--out",
        f"/out/{json_name}",
    ]


def _prepare_side(log: RunLog, image: str, cache: Path, url: str) -> dict:
    commit = commit_from_url(url)
    log.section(f"source {commit}")
    tarball, digest = ensure_tarball(cache, url, commit)
    log.write(f"tarball {tarball} sha256 {digest}", echo=True)
    tree = ensure_tree(cache, tarball, commit)
    log.write(f"tree {tree}", echo=True)
    lock = tree / "Gemfile.lock"
    lock_sha = sha256_file(lock)
    log.write(f"Gemfile.lock sha256 {lock_sha}", echo=True)
    code, text = bundle_check(image, tree)
    log.write(text, echo=False)
    log.write(f"bundle_check_exit={code}", echo=True)
    if code != 0:
        raise SystemExit(
            f"bundle check failed for {commit}; vendor/bundle was not reinstalled"
        )
    vcode, vtext, _elapsed = docker_bash(
        image,
        tree,
        "ruby -v; bundle -v; bundle exec rspec --version",
        180,
    )
    log.write(vtext, echo=False)
    log.write(f"version_exit={vcode}", echo=True)
    versions = _parse_versions(vtext)
    if vcode != 0 or not versions["rspec_core"]:
        raise SystemExit(f"version probe failed for {commit}")
    return {
        "commit": commit,
        "sha7": commit[:7],
        "tarball_sha256": digest,
        "tree": tree,
        "gemfile_lock_sha256": lock_sha,
        "versions": versions,
    }


def _load_examples(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    examples = data.get("examples")
    if not isinstance(examples, list):
        raise SystemExit("s1 json has no examples array")
    return examples


def _build_cert(
    meta: dict,
    victim: dict,
    polluters: list[str],
    commands: dict[str, str],
    minimal: str,
    runs: dict,
    judged: dict,
    exec_argv: dict,
) -> dict:
    return {
        "tool": {
            "name": "certify_rspec",
            "version": __version__,
            "git_sha": meta["git_sha"],
        },
        "repo": meta["repo"],
        "base": {"commit": meta["base_commit"], "tarball_sha256": meta["base_tarball"]},
        "head": {"commit": meta["head_commit"], "tarball_sha256": meta["head_tarball"]},
        "image_id": meta["image_id"],
        "ruby": meta["ruby"],
        "bundler": meta["bundler"],
        "rspec_core": meta["rspec_core"],
        "gemfile_lock_sha256": {
            "base": meta["base_lock"],
            "head": meta["head_lock"],
        },
        "seed": meta["seed"],
        "victim_id": victim["id"],
        "victim_location": victim["location"],
        "polluter_ids": polluters,
        "minimal_reproduction_command": minimal,
        "commands": commands,
        "runs": runs,
        "verdicts": judged["verdicts"],
        "plain_retry_verdict": judged["plain_retry_verdict"],
        "rep_disagreement": judged["rep_disagreement"],
        "c_passes": judged["c_passes"],
        "label": judged["label"],
        "execution": {
            "mode": "docker",
            "image": meta["image"],
            "trees": {"base": str(meta["base_tree"]), "head": str(meta["head_tree"])},
            "timeout_s": 240,
            "exec_argv": exec_argv,
        },
    }


def _summary_md(rows: list[dict]) -> str:
    lines = [
        "# PR check",
        "",
        "One line per order-dependent id. Verdicts are arm A. Plain-retry is arm B.",
        "",
        "| victim | base | head | plain-retry base | plain-retry head | polluter ids | label |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        polluters = " ".join(row.get("polluter_ids") or [])
        lines.append(
            "| {victim} | {base} | {head} | {pb} | {ph} | {polluters} | {label} |".format(
                victim=row["location"],
                base=row.get("base", ""),
                head=row.get("head", ""),
                pb=row.get("plain_base", ""),
                ph=row.get("plain_head", ""),
                polluters=polluters,
                label=row["label"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache)
    json_dir = cache / "rspec-json"
    json_dir.mkdir(parents=True, exist_ok=True)
    log = RunLog(out / "run.log")
    log.section("certify_rspec start")
    invocation = shlex.join(sys.argv)
    (out / "invocation.txt").write_text(invocation + "\n", encoding="utf-8")
    log.write("argv " + invocation, echo=True)
    image_id = _image_id(args.image)
    server = _docker_server_version()
    log.write(f"image {args.image}", echo=True)
    log.write(f"image_id {image_id}", echo=True)
    log.write(f"docker_server {server}", echo=True)
    repo = repo_from_url(args.base_url)
    head_repo = repo_from_url(args.head_url)
    if head_repo != repo:
        raise SystemExit(f"base repo {repo} and head repo {head_repo} differ")
    base = _prepare_side(log, args.image, cache, args.base_url)
    head = _prepare_side(log, args.image, cache, args.head_url)
    if base["versions"] != head["versions"]:
        log.write(
            "version strings differ between trees: "
            + json.dumps({"base": base["versions"], "head": head["versions"]}),
            echo=True,
        )
    versions = base["versions"]

    log.section("S1 discover")
    s1_json_host = json_dir / "s1.json"
    s1_argv = _exec_argv([args.suite, "--seed", str(args.seed)], "s1.json")
    s1 = _run_rspec(
        log,
        args.image,
        base["tree"],
        s1_argv,
        out / "s1.doc.log",
        s1_json_host,
        600,
        format_command(["rspec", args.suite, "--seed", str(args.seed), "--format", "json", "--out", "s1.json"]),
    )
    if not s1_json_host.is_file():
        raise SystemExit("S1 did not write json")
    (out / "s1.json").write_bytes(s1_json_host.read_bytes())
    examples = _load_examples(out / "s1.json")
    failing = []
    for index, example in enumerate(examples):
        if example.get("status") != "failed":
            continue
        failing.append(
            {
                "id": example["id"],
                "location": example_location(example),
                "index": index,
            }
        )
    log.write(f"S1 examples={len(examples)} failing={len(failing)}", echo=True)

    log.section("S2 classify")
    s2_dir = out / "s2"
    classified = []
    order_dependent = []
    for victim in failing:
        slug = _slug(victim["location"])
        flags = []
        for rep in range(1, REPS + 1):
            name = f"{slug}-r{rep}"
            argv = _exec_argv([victim["id"]], _json_name(name))
            outcome = _run_rspec(
                log,
                args.image,
                base["tree"],
                argv,
                s2_dir / f"{name}.log",
                json_dir / _json_name(name),
                180,
                format_command(["rspec", victim["id"]]),
            )
            flags.append(alone_passed(outcome))
            victim.setdefault("alone", []).append(
                {
                    "passed": flags[-1],
                    "exit_code": outcome["exit_code"],
                    "example_count": outcome["example_count"],
                    "failure_count": outcome["failure_count"],
                    "first_error_class": outcome["first_error_class"],
                }
            )
        kind = classify_s2(True, flags)
        victim["classification"] = kind
        classified.append(victim)
        if kind == ORDER_DEPENDENT:
            order_dependent.append(victim)
        log.write(f"S2 {victim['location']} {kind} alone={flags}", echo=True)
    (s2_dir / "classify.json").write_text(
        json.dumps(
            {
                "failing": [
                    {
                        "id": item["id"],
                        "location": item["location"],
                        "classification": item["classification"],
                        "alone": item.get("alone", []),
                    }
                    for item in classified
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    log.section("S3 attribute")
    s3_dir = out / "s3"
    attributed = []
    rows = []
    for victim in order_dependent:
        slug = _slug(victim["location"])
        preds = predecessors(examples, victim["id"])
        bisect_args = ["--bisect=verbose", "--seed", str(args.seed), *preds, victim["id"]]
        logical = format_command(["rspec", *bisect_args])
        argv = _exec_argv(bisect_args, None)
        log_path = s3_dir / f"{slug}-bisect.log"
        outcome = _run_rspec(
            log,
            args.image,
            base["tree"],
            argv,
            log_path,
            None,
            3600,
            logical,
        )
        parsed = parse_bisect(log_path.read_text(encoding="utf-8"))
        record = {
            **victim,
            "predecessor_count": len(preds),
            "bisect": parsed,
            "rspec_argv_len": argv_length(argv),
        }
        if not parsed["attributed"]:
            record["status"] = "UNATTRIBUTED"
            record["reason"] = parsed["reason"]
            rows.append(
                {
                    "location": victim["location"],
                    "id": victim["id"],
                    "base": "",
                    "head": "",
                    "plain_base": "",
                    "plain_head": "",
                    "polluter_ids": [],
                    "label": "UNATTRIBUTED",
                    "reason": parsed["reason"],
                }
            )
            log.write(f"S3 {victim['location']} UNATTRIBUTED {parsed['reason']}", echo=True)
            attributed.append(record)
            continue
        polluters = polluter_ids(parsed["ids"], victim["id"])
        if polluters is None:
            record["status"] = "UNATTRIBUTED"
            record["reason"] = "victim id not in repro command"
            rows.append(
                {
                    "location": victim["location"],
                    "id": victim["id"],
                    "base": "",
                    "head": "",
                    "plain_base": "",
                    "plain_head": "",
                    "polluter_ids": [],
                    "label": "UNATTRIBUTED",
                    "reason": record["reason"],
                }
            )
            log.write(f"S3 {victim['location']} UNATTRIBUTED victim id missing from repro", echo=True)
            attributed.append(record)
            continue
        record["status"] = "ATTRIBUTED"
        record["polluter_ids"] = polluters
        record["commands"] = spec_commands(args.seed, polluters, victim["id"])
        log.write(
            f"S3 {victim['location']} ATTRIBUTED polluters={len(polluters)}",
            echo=True,
        )
        attributed.append(record)

    (s3_dir / "attribution.json").write_text(
        json.dumps(
            [
                {
                    "id": item["id"],
                    "location": item["location"],
                    "status": item["status"],
                    "reason": item.get("reason"),
                    "predecessor_count": item["predecessor_count"],
                    "rspec_argv_len": item["rspec_argv_len"],
                    "polluter_ids": item.get("polluter_ids", []),
                    "minimal_reproduction_command": (item.get("bisect") or {}).get("command"),
                }
                for item in attributed
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    log.section("S4 certify")
    meta = {
        "git_sha": _git_sha(REPO_ROOT),
        "repo": repo,
        "base_commit": base["commit"],
        "head_commit": head["commit"],
        "base_tarball": base["tarball_sha256"],
        "head_tarball": head["tarball_sha256"],
        "image_id": image_id,
        "image": args.image,
        "ruby": versions["ruby"],
        "bundler": versions["bundler"],
        "rspec_core": versions["rspec_core"],
        "base_lock": base["gemfile_lock_sha256"],
        "head_lock": head["gemfile_lock_sha256"],
        "seed": args.seed,
        "base_tree": base["tree"],
        "head_tree": head["tree"],
    }
    s4_dir = out / "s4"
    cert_index = 0
    cert_paths = []
    for item in attributed:
        if item["status"] != "ATTRIBUTED":
            continue
        cert_index += 1
        commands = item["commands"]
        command_strings = {arm: format_command(commands[arm]) for arm in ("A", "B", "C")}
        runs = {"base": {}, "head": {}}
        exec_by_arm = {"base": {}, "head": {}}

        def run_side(side_name: str, side: dict) -> tuple[dict, dict]:
            side_runs = {}
            side_exec = {}
            for arm in ("A", "B", "C"):
                reps = []
                body = commands[arm][1:]
                for rep in range(1, REPS + 1):
                    stem = f"{_slug(item['location'])}-{side['sha7']}-{arm}-r{rep}"
                    json_name = _json_name(stem)
                    argv = _exec_argv(body, json_name)
                    outcome = _run_rspec(
                        log,
                        args.image,
                        side["tree"],
                        argv,
                        s4_dir / f"{stem}.log",
                        json_dir / json_name,
                        240,
                        command_strings[arm],
                    )
                    outcome["exec_argv"] = argv
                    outcome["json_host"] = str(json_dir / json_name)
                    outcome["tree_side"] = side_name
                    reps.append(outcome)
                side_runs[arm] = reps
                side_exec[arm] = [rep["exec_argv"] for rep in reps]
            return side_runs, side_exec

        with ThreadPoolExecutor(max_workers=2) as pool:
            base_future = pool.submit(run_side, "base", base)
            head_future = pool.submit(run_side, "head", head)
            runs["base"], exec_by_arm["base"] = base_future.result()
            runs["head"], exec_by_arm["head"] = head_future.result()
        judged = judge(runs["base"], runs["head"], item["id"], item["polluter_ids"])
        cert = _build_cert(
            meta,
            item,
            item["polluter_ids"],
            command_strings,
            item["bisect"]["command"],
            runs,
            judged,
            exec_by_arm,
        )
        errors = validate_certificate(cert)
        if errors:
            log.write("certificate schema errors: " + "; ".join(errors), echo=True)
            raise SystemExit("certificate failed schema validation")
        cert_path = out / f"cert-{cert_index}.json"
        cert_path.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
        script_path = out / f"replay-{cert_index}.sh"
        write_replay_script(script_path, cert_path, REPO_ROOT)
        cert_paths.append((cert_index, cert_path, script_path, item, judged))
        rows.append(
            {
                "location": item["location"],
                "id": item["id"],
                "base": judged["verdicts"]["base"],
                "head": judged["verdicts"]["head"],
                "plain_base": judged["plain_retry_verdict"]["base"],
                "plain_head": judged["plain_retry_verdict"]["head"],
                "polluter_ids": item["polluter_ids"],
                "label": judged["label"],
                "cert": cert_path.name,
            }
        )
        log.write(
            f"S4 {item['location']} {judged['label']} "
            f"base={judged['verdicts']['base']} head={judged['verdicts']['head']}",
            echo=True,
        )

    # Preserve S1 order: unattributed rows were appended during S3, certified during S4.
    # Rebuild rows in order-dependent order.
    by_location = {row["location"] + row.get("label", ""): row for row in rows}
    ordered_rows = []
    for victim in order_dependent:
        matches = [row for row in rows if row["id"] == victim["id"]]
        if matches:
            ordered_rows.append(matches[-1])
    rows = ordered_rows
    del by_location

    (out / "check-summary.md").write_text(_summary_md(rows), encoding="utf-8")

    log.section("replay")
    replay_log = out / "replay-check.log"
    replay_lines = []
    for cert_index, cert_path, script_path, item, judged in cert_paths:
        replay_lines.append(f"===== {script_path.name} {item['location']} =====")
        proc = subprocess.run(
            ["bash", str(script_path)],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        )
        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")
        replay_lines.append(stdout)
        if stderr:
            replay_lines.append(stderr)
        replay_lines.append(f"replay_exit={proc.returncode}")
        log.write(f"replay {script_path.name} exit={proc.returncode}", echo=True)
    replay_log.write_text("\n".join(replay_lines) + "\n", encoding="utf-8")

    od_ids = [item["location"] for item in order_dependent]
    attributed_ids = [item["location"] for item in attributed if item["status"] == "ATTRIBUTED"]
    certified_ids = [row["location"] for row in rows if row["label"] == "CERTIFIED"]
    control_ids = [row["location"] for row in rows if row["label"] == "CONTROL"]
    exit_ok = classification_exit_ok(rows)
    summary = {
        "od_count": len(order_dependent),
        "attributed_count": len(attributed_ids),
        "od": od_ids,
        "attributed": attributed_ids,
        "certified": certified_ids,
        "control": control_ids,
        "rows": rows,
        "exit_ok": exit_ok,
        "image_id": image_id,
        "docker_server": server,
        "ruby": versions["ruby"],
        "bundler": versions["bundler"],
        "rspec_core": versions["rspec_core"],
        "s1_examples": len(examples),
        "s1_failing": len(failing),
        "coveralls_mentions_s1_doc": (out / "s1.doc.log").read_text(encoding="utf-8").count("Coveralls"),
        "stdout_redirect_mentions_s1_doc": (out / "s1.doc.log").read_text(encoding="utf-8").count(
            "Changing stdout"
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    log.write(
        f"done od={summary['od_count']} attributed={summary['attributed_count']} exit_ok={exit_ok}",
        echo=True,
    )
    return 0 if exit_ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.certify_rspec")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--head-url", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cache", default="/tmp/flakecert-g1-1019/work")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
