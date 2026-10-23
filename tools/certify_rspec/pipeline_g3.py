"""Run the G3 sample against a GitLab checkout in the CI image.

The invocation names an input directory and a checkout. Subject paths are
read from those trees at runtime.
"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import shlex
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from tools.certify_rspec.g3lib import (
    HEADLINE_RE,
    SEED_TIMEOUT_FLOOR_S,
    absence_needle,
    armf_verdict,
    armg_pass_armf_fail,
    bisect_command,
    bound_headline,
    cert_verdict,
    certificate_text,
    check_script_rel,
    classify_category_a,
    counts_as_setup_failure,
    descriptions_from_sources,
    first_commit,
    is_env_failure,
    minimal_enablers,
    next_resume_seed,
    not_run_row,
    parse_excluded,
    resolve_images,
    resume_action,
    resume_plan,
    same_file,
    seed_finished,
    seed_timeout_s,
    select_s20,
    sha256_file,
    sha_by_prefix,
    should_stop_setup,
    sibling_names,
    slug,
    sum_for,
    summarize_rspec,
    target_examples_passed,
    todo_relpath,
)
from tools.certify_rspec.parse_rspec import locations_from_repro

SEED_LO = 1
SEED_HI = 30
WALL_LIMIT_S = 4 * 60 * 60
STOP_RESERVE_S = 18 * 60
DB_NAMES = ("gitlabhq_test_sec", "gitlabhq_test_ci", "gitlabhq_test")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _quote(value: str) -> str:
    return shlex.quote(value)


def _slim_report(data: dict) -> dict:
    examples = []
    for item in data.get("examples") or []:
        exc = item.get("exception") or {}
        message = str(exc.get("message") or "").splitlines()
        examples.append(
            {
                "id": item.get("id"),
                "file_path": item.get("file_path"),
                "status": item.get("status"),
                "exception": {
                    "class": exc.get("class"),
                    "message": message[0] if message else "",
                }
                if exc
                else None,
            }
        )
    summary = data.get("summary") or {}
    return {
        "examples": examples,
        "summary": {
            key: summary.get(key)
            for key in (
                "example_count",
                "failure_count",
                "pending_count",
                "errors_outside_of_examples_count",
            )
        },
    }


class RunLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def line(self, message: str) -> None:
        text = f"{_now()} {message}\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(text)
        print(text, end="", flush=True)


class Runner:
    def __init__(self, args: argparse.Namespace, log: RunLog):
        self.args = args
        self.log = log
        self.gitlab = Path(args.gitlab_dir)
        self.evidence = Path(args.evidence_dir)
        self.inputs = Path(args.input_dir)
        self.container = args.container
        self.postgres = args.postgres
        self.todo_lock = threading.Lock()
        self.clock_name = "resume_started_at" if getattr(args, "resume", False) else "started_at"
        self.setup_failures = 0
        self.stop_reason = ""
        self.evidence.mkdir(parents=True, exist_ok=True)
        spec = (self.inputs / "SPEC-G3.md").read_text(encoding="utf-8")
        amended = (self.inputs / "SPEC-G3.1.md").read_text(encoding="utf-8")
        self.spec_text = spec
        self.amended = amended
        self.commit = first_commit(spec)
        self.needle = absence_needle(amended)
        self.check_rel = check_script_rel(spec)
        self.recon = (self.inputs / "reverse" / "recon-gitlab.log").read_text(encoding="utf-8")

    def docker(self, script: str, log_path: Path, timeout: int, env: dict[str, str]) -> tuple[int, str, float]:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        inner = f"timeout --signal=TERM {int(timeout)} bash -lc {_quote(script)}"
        cmd = ["docker", "exec", "-w", "/gitlab"]
        merged = {"CI": "true", "RAILS_ENV": "test", "MALLOC_ARENA_MAX": "2"}
        merged.update(env)
        for key, value in merged.items():
            cmd.extend(["-e", f"{key}={value}"])
        cmd.extend([self.container, "bash", "-lc", inner])
        started = time.time()
        self.log.line(f"BEGIN timeout={timeout}s log={log_path}")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout + 60,
                check=False,
            )
            text = proc.stdout.decode("utf-8", errors="replace")
            text += proc.stderr.decode("utf-8", errors="replace")
            rc = proc.returncode
        except subprocess.TimeoutExpired as exc:
            text = (exc.stdout or b"").decode("utf-8", errors="replace")
            text += (exc.stderr or b"").decode("utf-8", errors="replace")
            text += "\nHOST_TIMEOUT\n"
            rc = 124
        elapsed = time.time() - started
        log_path.write_text(text, encoding="utf-8")
        self.log.line(f"END rc={rc} elapsed_s={elapsed:.1f} log={log_path}")
        return rc, text, elapsed

    def psql(self, sql: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", "exec", self.postgres, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-c", sql],
            capture_output=True,
            text=True,
            check=False,
        )

    def note_record(self, record: dict) -> None:
        if not self.args.resume:
            return
        failed = counts_as_setup_failure(
            int(record.get("example_count") or 0),
            int(record.get("exit_code") or 0),
            str(record.get("error_class") or ""),
            str(record.get("message") or ""),
            bool(record.get("timeout")),
            self.needle,
        )
        if not failed:
            return
        self.setup_failures += 1
        self.log.line(f"ENV_SETUP_FAILURE count={self.setup_failures}")
        if should_stop_setup(self.setup_failures):
            self.stop_reason = "ENV_SETUP"
            self.log.line("STOP env setup failure limit")

    def prepare_databases(self) -> None:
        limit = 2 if self.args.resume else 1
        last: SystemExit | None = None
        for _attempt in range(1, limit + 1):
            try:
                self._prepare_databases_once()
                return
            except SystemExit as exc:
                last = exc
                self.setup_failures += 1
                self.log.line(f"ENV_SETUP_FAILURE prepare count={self.setup_failures} detail={exc}")
                if self.setup_failures >= limit:
                    self.stop_reason = "ENV_SETUP"
                    raise
        if last is not None:
            self.stop_reason = "ENV_SETUP"
            raise last

    def _prepare_databases_once(self) -> None:
        yml = self.gitlab / "config" / "database.yml"
        if not yml.is_file():
            raise SystemExit("database.yml is missing; setup has not finished")
        text = yml.read_text(encoding="utf-8")
        if "G3_DB_SUFFIX" not in text:
            updated = text
            for name in DB_NAMES:
                updated = updated.replace(
                    f"database: {name}\n",
                    "database: " + name + "<%= ENV['G3_DB_SUFFIX'] %>\n",
                )
            yml.write_text(updated, encoding="utf-8")
            self.log.line("patched database.yml with a suffix for a second schema clone")
        for base in DB_NAMES:
            clone = base + "2"
            exists = self.psql(f"SELECT 1 FROM pg_database WHERE datname = '{clone}'")
            if exists.returncode == 0 and "1" in exists.stdout:
                self.log.line(f"database {clone} already present")
                continue
            self.psql(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{base}' AND pid <> pg_backend_pid()"
            )
            created = self.psql(f"CREATE DATABASE {clone} TEMPLATE {base}")
            self.log.line(f"create {clone} rc={created.returncode} {created.stderr.strip()[:200]}")
            if created.returncode != 0:
                raise SystemExit(f"could not clone {base}")

    def pristine_todo(self, todo_rel: str) -> None:
        destination = self.gitlab / "tmp" / "g3-todo-pristine.yml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = self.gitlab / todo_rel.lstrip("./")
        destination.write_bytes(source.read_bytes())
        self.log.line(f"saved pristine todo bytes={destination.stat().st_size}")

    def run_rspec(
        self,
        rel_files: list[str],
        order: str,
        seed: int | None,
        log_path: Path,
        json_name: str,
        timeout: int,
        db_suffix: str,
    ) -> dict:
        meta_path = log_path.with_suffix(".meta.json")
        if meta_path.is_file():
            cached = json.loads(meta_path.read_text(encoding="utf-8"))
            if (not self.args.resume) or seed_finished(cached):
                self.note_record(cached)
                return cached
            self.log.line(f"RESUME rerun unfinished seed={seed} log={log_path.name}")
        json_rel = f"tmp/g3-out/{json_name}"
        host_json = self.gitlab / json_rel
        host_json.parent.mkdir(parents=True, exist_ok=True)
        if host_json.exists():
            host_json.unlink()
        files = " ".join(_quote(item) for item in rel_files)
        seed_arg = f"--seed {int(seed)} " if seed is not None else ""
        script = "\n".join(
            [
                "set -o pipefail",
                "cd /gitlab",
                "mkdir -p tmp/g3-out",
                f"export RSPEC_ORDER={_quote(order)}",
                (
                    "bin/rspec "
                    + seed_arg
                    + f"--format json --out {_quote(json_rel)} --format documentation {files}"
                ),
            ]
        )
        rc, text, elapsed = self.docker(
            script,
            log_path,
            timeout,
            {"G3_DB_SUFFIX": db_suffix, "MALLOC_ARENA_MAX": "2"},
        )
        data = None
        if host_json.is_file():
            raw = host_json.read_bytes()
            evidence_json = log_path.with_suffix(".json")
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                evidence_json.write_text(json.dumps(_slim_report(data)), encoding="utf-8")
            else:
                evidence_json.write_bytes(raw)
            host_json.unlink(missing_ok=True)
        summary = summarize_rspec(data, rc)
        summary["elapsed_s"] = round(elapsed, 3)
        summary["log"] = str(log_path.relative_to(self.evidence))
        summary["json"] = str(log_path.with_suffix(".json").relative_to(self.evidence)) if data else ""
        summary["timeout"] = rc == 124
        summary["order"] = order
        summary["seed"] = seed
        summary["db_suffix"] = db_suffix
        stored = {key: value for key, value in summary.items() if key != "examples"}
        stored["examples"] = summary["examples"]
        meta_path.write_text(json.dumps(stored), encoding="utf-8")
        self.note_record(stored)
        return stored

    def run_arm_g(self, path: str, log_path: Path, db_suffix: str, timeout: int = 1800) -> dict:
        meta_path = log_path.with_suffix(".meta.json")
        if meta_path.is_file():
            cached = json.loads(meta_path.read_text(encoding="utf-8"))
            reuse = (not self.args.resume) or (
                bool(cached.get("passed"))
                and not cached.get("timeout")
                and cached.get("exit_code") != 124
            )
            if reuse:
                return cached
            self.log.line(f"RESUME rerun arm log={log_path.name}")
        listed = path[2:] if path.startswith("./") else path
        script = "\n".join(
            [
                "set -o pipefail",
                "cd /gitlab",
                f"cp -a tmp/g3-todo-pristine.yml {_quote(self.todo_rel)}",
                "set +e",
                f"{_quote(self.check_rel)} {_quote(listed)}",
                "rc=$?",
                "set -e",
                f"cp -a tmp/g3-todo-pristine.yml {_quote(self.todo_rel)}",
                "exit $rc",
            ]
        )
        with self.todo_lock:
            rc, _text, elapsed = self.docker(
                script,
                log_path,
                timeout,
                {"G3_DB_SUFFIX": db_suffix, "MALLOC_ARENA_MAX": "2"},
            )
        record = {
            "exit_code": rc,
            "passed": rc == 0,
            "elapsed_s": round(elapsed, 3),
            "log": str(log_path.relative_to(self.evidence)),
            "timeout": rc == 124,
        }
        meta_path.write_text(json.dumps(record), encoding="utf-8")
        return record

    def _pool(self, jobs: list, workers: int) -> list:
        suffixes = [""] if workers <= 1 else ["", "2"]
        slots: queue.Queue[str] = queue.Queue()
        for suffix in suffixes[: max(workers, 1)]:
            slots.put(suffix)

        def wrap(job):
            suffix = slots.get()
            try:
                return job(suffix)
            finally:
                slots.put(suffix)

        with ThreadPoolExecutor(max_workers=len(suffixes)) as pool:
            futures = [pool.submit(wrap, job) for job in jobs]
            return [future.result() for future in futures]

    def certify_file(self, path: str) -> dict:
        digest = slug(path)
        arm_g_log = self.evidence / "arm-g" / f"{digest}.log"

        def arm_g(suffix: str) -> dict:
            return self.run_arm_g(path, arm_g_log, suffix)

        # Arm G is submitted alone per file from the caller so the pool can
        # overlap it with other files. This method runs both arms itself.
        g_record = arm_g("")
        failures = 0
        finished = 0
        seed_logs = []
        for seed in range(SEED_LO, SEED_HI + 1):
            log_path = self.evidence / "arm-f" / digest / f"seed-{seed:02d}.log"
            json_name = f"{digest}-seed-{seed:02d}.json"

            def run_seed(suffix: str, seed=seed, log_path=log_path, json_name=json_name) -> dict:
                return self.run_rspec(
                    [path[2:] if path.startswith("./") else path],
                    "random",
                    seed,
                    log_path,
                    json_name,
                    1200,
                    suffix,
                )

            record = run_seed("2" if self.args.workers > 1 else "")
            seed_logs.append(record["log"])
            if record.get("timeout"):
                continue
            finished += 1
            if not record.get("passed"):
                failures += 1
        verdict = armf_verdict(failures) if finished == SEED_HI else "INCOMPLETE"
        headline = ""
        cert_rel = ""
        if finished:
            headline = bound_headline(failures, finished, SEED_LO, SEED_LO + finished - 1, self.commit)
            body = {
                "path": path,
                "commit": self.commit,
                "arm_g_passed": g_record["passed"],
                "arm_g_log": g_record["log"],
                "failures": failures,
                "finished_runs": finished,
                "seed_logs": seed_logs,
                "verdict": verdict,
            }
            cert_path = self.evidence / "certificates" / f"{digest}.txt"
            cert_path.parent.mkdir(parents=True, exist_ok=True)
            if verdict in ("BOUNDED_CLEAN", "CERTIFIED_ORDER_DEPENDENT") and finished == SEED_HI:
                text = certificate_text(headline, verdict, body)
            else:
                text = headline + "\n" + verdict + "\n" + json.dumps(body, indent=2, sort_keys=True) + "\n"
            cert_path.write_text(text, encoding="utf-8")
            cert_rel = str(cert_path.relative_to(self.evidence))
        return {
            "path": path,
            "slug": digest,
            "arm_g_pass": bool(g_record["passed"]),
            "arm_g_log": g_record["log"],
            "arm_f_failures": failures,
            "arm_f_trials": finished,
            "verdict": verdict,
            "headline": headline,
            "cert": cert_rel,
        }

    def run_s20(self, paths: list[str]) -> list[dict]:
        # Two workers. Each file's seeds stay on one suffix so a file does not
        # hop databases, and arm G for that file uses the same suffix.
        def job(path: str):
            def run(suffix: str) -> dict:
                digest = slug(path)
                left = int(WALL_LIMIT_S - STOP_RESERVE_S - _wall(self.evidence, self.clock_name))
                floor = SEED_TIMEOUT_FLOOR_S if self.args.resume else 180
                if self.stop_reason or left < floor:
                    self.log.line(
                        f"STOP budget before path={path} left_s={left} reason={self.stop_reason or 'budget'}"
                    )
                    if self.args.resume:
                        return not_run_row(path)
                    return {
                        "path": path,
                        "slug": digest,
                        "arm_g_pass": False,
                        "arm_g_log": "",
                        "arm_f_failures": 0,
                        "arm_f_trials": 0,
                        "verdict": "INCOMPLETE",
                        "headline": "",
                        "cert": "",
                    }
                g_record = self.run_arm_g(
                    path,
                    self.evidence / "arm-g" / f"{digest}.log",
                    suffix,
                    timeout=min(1800, max(left, 1)),
                )
                planned_timeout = None
                if self.args.resume:
                    planned_timeout = seed_timeout_s(float(g_record.get("elapsed_s") or 0))
                    self.log.line(
                        f"SEED_TIMEOUT seconds={planned_timeout} "
                        f"arm_g_elapsed_s={g_record.get('elapsed_s')} path={path}"
                    )
                failures = 0
                finished = 0
                seed_logs = []
                seed = SEED_LO
                while seed <= SEED_HI:
                    if self.stop_reason or _past_stop(self.evidence, self.clock_name):
                        self.log.line(
                            f"STOP budget path={path} before seed={seed} reason={self.stop_reason or 'budget'}"
                        )
                        break
                    if self.args.resume:
                        left_seed = int(
                            WALL_LIMIT_S - STOP_RESERVE_S - _wall(self.evidence, self.clock_name)
                        )
                        if left_seed < SEED_TIMEOUT_FLOOR_S:
                            self.log.line(f"STOP budget path={path} before seed={seed} left_s={left_seed}")
                            break
                    timeout_s = self._seed_limit(g_record)
                    log_path = self.evidence / "arm-f" / digest / f"seed-{seed:02d}.log"
                    record = self.run_rspec(
                        [path[2:] if path.startswith("./") else path],
                        "random",
                        seed,
                        log_path,
                        f"{digest}-seed-{seed:02d}.json",
                        timeout_s,
                        suffix,
                    )
                    seed_logs.append(record["log"])
                    if self.args.resume and counts_as_setup_failure(
                        int(record.get("example_count") or 0),
                        int(record.get("exit_code") or 0),
                        str(record.get("error_class") or ""),
                        str(record.get("message") or ""),
                        bool(record.get("timeout")),
                        self.needle,
                    ):
                        preserve = log_path.with_name(
                            f"{log_path.stem}.setup-{self.setup_failures}{log_path.suffix}"
                        )
                        if log_path.is_file():
                            preserve.write_bytes(log_path.read_bytes())
                        log_path.with_suffix(".meta.json").unlink(missing_ok=True)
                        if self.stop_reason:
                            break
                        continue
                    if record.get("timeout"):
                        seed += 1
                        continue
                    finished += 1
                    if not record.get("passed"):
                        failures += 1
                    seed += 1
                verdict = armf_verdict(failures) if finished == SEED_HI else "INCOMPLETE"
                headline = ""
                cert_rel = ""
                if finished:
                    headline = bound_headline(
                        failures, finished, SEED_LO, SEED_LO + finished - 1, self.commit
                    )
                    body = {
                        "path": path,
                        "commit": self.commit,
                        "arm_g_passed": g_record["passed"],
                        "arm_g_log": g_record["log"],
                        "failures": failures,
                        "finished_runs": finished,
                        "seed_logs": seed_logs,
                        "verdict": verdict,
                    }
                    cert_path = self.evidence / "certificates" / f"{digest}.txt"
                    cert_path.parent.mkdir(parents=True, exist_ok=True)
                    cert_path.write_text(
                        certificate_text(headline, verdict, body)
                        if verdict in ("BOUNDED_CLEAN", "CERTIFIED_ORDER_DEPENDENT")
                        else headline + "\n" + verdict + "\n" + json.dumps(body, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    cert_rel = str(cert_path.relative_to(self.evidence))
                self.log.line(f"FILE {path} G={g_record['passed']} F={verdict} failures={failures}/{finished}")
                row = {
                    "path": path,
                    "slug": digest,
                    "arm_g_pass": bool(g_record["passed"]),
                    "arm_g_log": g_record["log"],
                    "arm_f_failures": failures,
                    "arm_f_trials": finished,
                    "verdict": verdict,
                    "headline": headline,
                    "cert": cert_rel,
                }
                if self.args.resume:
                    row["seed_timeout_s"] = planned_timeout
                return row

            return run

        return self._pool([job(path) for path in paths], self.args.workers)

    def _seed_limit(self, g_record: dict) -> int:
        left = int(WALL_LIMIT_S - STOP_RESERVE_S - _wall(self.evidence, self.clock_name))
        if not self.args.resume:
            return min(480, max(60, left))
        planned = seed_timeout_s(float(g_record.get("elapsed_s") or 0))
        if left < SEED_TIMEOUT_FLOOR_S:
            return max(left, 1)
        return min(planned, left)

    def category_file(self, path: str) -> dict:
        if self.stop_reason:
            self.log.line(f"STOP skip excluded path={path} reason={self.stop_reason}")
            return _idle_categories([path])[0]
        digest = slug(path)
        alone = self.run_rspec(
            [path],
            "defined",
            None,
            self.evidence / "cat-a" / f"{digest}-alone.log",
            f"{digest}-alone.json",
            1200,
            "",
        )
        if self.stop_reason:
            siblings = {
                "passed": False,
                "log": "",
                "examples": [],
                "example_count": 0,
                "exit_code": 1,
                "error_class": "",
                "message": "",
            }
            files = []
        else:
            directory = (self.gitlab / path).parent
            names = sibling_names([item.name for item in directory.glob("*_spec.rb")])
            rel_dir = path.rsplit("/", 1)[0]
            files = [f"{rel_dir}/{name}" for name in names]
            siblings = self.run_rspec(
                files,
                "defined",
                None,
                self.evidence / "cat-a" / f"{digest}-siblings.log",
                f"{digest}-siblings.json",
                3600,
                "",
            )
        alone_pass = bool(alone.get("passed"))
        siblings_pass = target_examples_passed(siblings, path)
        env_fail = is_env_failure(
            int(alone.get("example_count") or 0),
            int(alone.get("exit_code") or 1),
            str(alone.get("error_class") or ""),
            str(alone.get("message") or ""),
            self.needle,
        )
        enablers: list[str] | None = None
        ddmin_log = self.evidence / "cat-a" / f"{digest}-ddmin.log"
        if (not alone_pass) and siblings_pass:
            others = [item for item in files if item != path]

            def test(subset: list[str]) -> bool:
                chosen = set(subset) | {path}
                ordered = [item for item in files if item in chosen]
                record = self.run_rspec(
                    ordered,
                    "defined",
                    None,
                    self.evidence / "cat-a" / digest / f"ddmin-{slug(' '.join(ordered))}.log",
                    f"{digest}-ddmin-{slug(' '.join(ordered))}.json",
                    1800,
                    "",
                )
                return target_examples_passed(record, path)

            enablers = minimal_enablers(others, test)
            ddmin_log.write_text(
                json.dumps({"enablers": enablers}, indent=2) + "\n",
                encoding="utf-8",
            )
        certified = False
        replay = ""
        if enablers:
            chosen = set(enablers) | {path}
            ordered = [item for item in files if item in chosen]
            first = self.run_rspec(
                ordered,
                "defined",
                None,
                self.evidence / "cat-a" / f"{digest}-replay1.log",
                f"{digest}-replay1.json",
                1800,
                "",
            )
            second = self.run_rspec(
                ordered,
                "defined",
                None,
                self.evidence / "cat-a" / f"{digest}-replay2.log",
                f"{digest}-replay2.json",
                1800,
                "",
            )
            certified = target_examples_passed(first, path) and target_examples_passed(second, path)
            replay = self._write_replay(
                self.evidence / f"replay-enabler-{digest}.sh",
                ordered,
                "defined",
                0,
            )
        label = classify_category_a(alone_pass, siblings_pass, env_fail, certified)
        self.log.line(f"CAT path={path} label={label}")
        return {
            "path": path,
            "label": label,
            "alone_log": alone.get("log"),
            "siblings_log": siblings.get("log"),
            "alone_passed": alone_pass,
            "siblings_target_passed": siblings_pass,
            "enablers": enablers or [],
            "enabler_replay": replay,
            "ddmin_log": str(ddmin_log.relative_to(self.evidence)) if ddmin_log.is_file() else "",
        }

    def _write_replay(self, path: Path, files: list[str], order: str, expected: int) -> str:
        listed = " ".join(_quote(item) for item in files)
        body = "\n".join(
            [
                "#!/bin/bash",
                "set -uo pipefail",
                "set +e",
                "docker exec -w /gitlab "
                f"-e CI=true -e RSPEC_ORDER={_quote(order)} -e G3_DB_SUFFIX= -e MALLOC_ARENA_MAX=2 "
                f"{_quote(self.container)} "
                f"bash -lc {_quote('cd /gitlab && bin/rspec --format documentation ' + listed)}",
                "rc=$?",
                "set -e",
                f'test "$rc" -eq {int(expected)}',
                'echo REPLAY_OK',
                "",
            ]
        )
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return str(path.relative_to(self.evidence))

    def run_b1(self, path: str) -> dict:
        if self.stop_reason:
            self.log.line(f"STOP skip reverse-order path={path} reason={self.stop_reason}")
            return _idle_b1(path)
        digest = slug(path)
        defined = self.run_rspec(
            [path],
            "defined",
            None,
            self.evidence / "b1" / "defined.log",
            f"{digest}-defined.json",
            1200,
            "",
        )
        reverse = self.run_rspec(
            [path],
            "reverse",
            None,
            self.evidence / "b1" / "reverse.log",
            f"{digest}-reverse.json",
            1200,
            "",
        )
        bisect_log = self.evidence / "b1" / "bisect.log"
        bisect_meta = bisect_log.with_suffix(".meta.json")
        if bisect_meta.is_file():
            bisect = json.loads(bisect_meta.read_text(encoding="utf-8"))
        else:
            script = "\n".join(
                [
                    "set +e",
                    "cd /gitlab",
                    "unset RSPEC_ORDER",
                    f"bin/rspec --bisect {_quote(path)}",
                    "exit $?",
                ]
            )
            rc, text, elapsed = self.docker(script, bisect_log, 2400, {"G3_DB_SUFFIX": "", "MALLOC_ARENA_MAX": "2"})
            command = bisect_command(text)
            bisect = {
                "exit_code": rc,
                "elapsed_s": round(elapsed, 3),
                "log": str(bisect_log.relative_to(self.evidence)),
                "command": command,
                "ids": locations_from_repro(command) if command else [],
            }
            bisect_meta.write_text(json.dumps(bisect), encoding="utf-8")
        ids = [example.get("id") for example in reverse.get("examples") or [] if example.get("id")]
        failed = [example.get("id") for example in reverse.get("examples") or [] if example.get("status") == "failed" and example.get("id")]
        ddmin_set: list[str] = []
        victim = failed[0] if failed else ""
        if victim and ids and victim in ids:
            before = ids[: ids.index(victim)]

            def test(subset: list[str]) -> bool:
                ordered = list(subset) + [victim]
                record = self._run_ids(ordered, self.evidence / "b1" / "ddmin" / f"{slug(' '.join(ordered))}.log")
                return victim in record.get("failed_ids", [])

            found = minimal_enablers(before, test)
            ddmin_set = (found or []) + [victim] if found is not None else []
        (self.evidence / "b1" / "ddmin.log").write_text(
            json.dumps({"victim": victim, "set": ddmin_set, "bisect_ids": bisect.get("ids")}, indent=2) + "\n",
            encoding="utf-8",
        )
        reported = ddmin_set or bisect.get("ids") or []
        replay_rel = ""
        replay_ok = False
        if reported:
            replay_rel = self._write_id_replay(self.evidence / "replay-b1.sh", reported, "global")
            replay_ok = self._script_passes_twice(self.evidence / "replay-b1.sh")
        elif defined.get("passed"):
            replay_rel = self._write_replay(self.evidence / "replay-b1.sh", [path], "defined", 0)
            replay_ok = self._script_passes_twice(self.evidence / "replay-b1.sh")
        same = same_file(reported, path) if reported else False
        if reverse.get("passed") and defined.get("passed"):
            label = "PASSES_ALONE"
        elif reported and replay_ok:
            label = "ENABLER_CERTIFIED" if not reverse.get("passed") else "PASSES_ALONE"
        elif is_env_failure(
            int(defined.get("example_count") or 0),
            int(defined.get("exit_code") or 1),
            str(defined.get("error_class") or ""),
            str(defined.get("message") or ""),
            self.needle,
        ):
            label = "ENV_FAILURE"
        else:
            label = "UNRESOLVED"
        # A reverse-order failure with a replayed set is the order result.
        if (not reverse.get("passed")) and reported and replay_ok:
            label = "ENABLER_CERTIFIED"
        self.log.line(f"B1 path={path} label={label} same_file={same} replay_twice={replay_ok}")
        return {
            "path": path,
            "label": label,
            "defined_log": defined.get("log"),
            "reverse_log": reverse.get("log"),
            "bisect_log": bisect.get("log"),
            "ddmin_log": "b1/ddmin.log",
            "set": reported,
            "same_file": same,
            "replay_twice": replay_ok,
            "replay": replay_rel,
            "defined_passed": bool(defined.get("passed")),
            "reverse_passed": bool(reverse.get("passed")),
        }

    def _run_ids(self, ids: list[str], log_path: Path) -> dict:
        meta = log_path.with_suffix(".meta.json")
        if meta.is_file():
            return json.loads(meta.read_text(encoding="utf-8"))
        joined = " ".join(ids)
        script = "\n".join(
            [
                "set -o pipefail",
                "cd /gitlab",
                "export RSPEC_ORDER=global",
                f"export ids={_quote(joined)}",
                "bin/rspec --require /tmp/ordering.rb --format json --out tmp/g3-out/b1-ids.json "
                + " ".join(_quote(item) for item in ids),
            ]
        )
        rc, _text, elapsed = self.docker(
            script,
            log_path,
            1200,
            {"G3_DB_SUFFIX": "", "MALLOC_ARENA_MAX": "2"},
        )
        host_json = self.gitlab / "tmp" / "g3-out" / "b1-ids.json"
        data = None
        if host_json.is_file():
            try:
                data = json.loads(host_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                log_path.with_suffix(".json").write_text(json.dumps(_slim_report(data)), encoding="utf-8")
            else:
                log_path.with_suffix(".json").write_bytes(host_json.read_bytes())
            host_json.unlink(missing_ok=True)
        summary = summarize_rspec(data, rc)
        summary["elapsed_s"] = round(elapsed, 3)
        summary["log"] = str(log_path.relative_to(self.evidence))
        meta.write_text(json.dumps({key: value for key, value in summary.items()}), encoding="utf-8")
        return summary

    def _write_id_replay(self, path: Path, ids: list[str], order: str) -> str:
        joined = " ".join(ids)
        args = " ".join(_quote(item) for item in ids)
        script = " ".join(
            [
                "cd /gitlab &&",
                "export RSPEC_ORDER=global &&",
                f"export ids={_quote(joined)} &&",
                "bin/rspec --require /tmp/ordering.rb --format documentation",
                args,
            ]
        )
        body = "\n".join(
            [
                "#!/bin/bash",
                "set -uo pipefail",
                "set +e",
                "docker exec -w /gitlab "
                f"-e CI=true -e RSPEC_ORDER={_quote(order)} -e G3_DB_SUFFIX= -e MALLOC_ARENA_MAX=2 "
                f"-e ids={_quote(joined)} "
                f"{_quote(self.container)} bash -lc {_quote(script)}",
                "rc=$?",
                "set -e",
                'test "$rc" -ne 0',
                'echo REPLAY_OK',
                "",
            ]
        )
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return str(path.relative_to(self.evidence))

    def _script_passes_twice(self, script: Path) -> bool:
        log_path = self.evidence / "replay-check.log"
        ok = True
        lines = []
        if log_path.is_file():
            lines.append(log_path.read_text(encoding="utf-8"))
        for index in (1, 2):
            proc = subprocess.run(["bash", str(script)], capture_output=True, text=True, check=False)
            lines.append(f"PASS {index} script={script.name} rc={proc.returncode}")
            lines.append(proc.stdout)
            lines.append(proc.stderr)
            if proc.returncode != 0:
                ok = False
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.log.line(f"REPLAY {script.name} twice_ok={ok}")
        return ok

    def mention(self, log_rel: str) -> bool:
        path = self.evidence / log_rel
        if not path.is_file():
            return False
        blob = path.read_text(encoding="utf-8", errors="replace").lower()
        return self.needle.lower() in blob and any(
            word in blob for word in ("absent", "missing", "not found", "not running")
        )


def _image_record(tag: str) -> dict:
    raw = subprocess.check_output(["docker", "image", "inspect", tag], text=True)
    data = json.loads(raw)[0]
    return {"tag": tag, "id": data.get("Id"), "repo_digests": data.get("RepoDigests") or []}


def _wall(evidence: Path, clock_name: str = "started_at") -> float:
    started = (evidence / clock_name).read_text(encoding="utf-8").strip()
    stamp = datetime.fromisoformat(started.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - stamp).total_seconds()


def _past_stop(evidence: Path, clock_name: str = "started_at") -> bool:
    return _wall(evidence, clock_name) >= (WALL_LIMIT_S - STOP_RESERVE_S)


def _idle_categories(paths: list[str]) -> list[dict]:
    return [
        {
            "path": path,
            "label": "NOT_RUN",
            "alone_log": "",
            "siblings_log": "",
            "enablers": [],
            "enabler_replay": "",
            "replay_twice": None,
        }
        for path in paths
    ]


def _idle_b1(path: str) -> dict:
    return {
        "path": path,
        "label": "NOT_RUN",
        "defined_log": "",
        "reverse_log": "",
        "bisect_log": "",
        "ddmin_log": "",
        "set": [],
        "same_file": False,
        "replay_twice": False,
    }


def _verify_skips(runner: Runner, evidence: Path, by_path: dict, skip_paths: list[str]) -> list[dict]:
    sums_text = (evidence / "SHA256SUMS").read_text(encoding="utf-8")
    kept = []
    for path in skip_paths:
        row = dict(by_path[path])
        cert_rel = str(row.get("cert") or "")
        cert_path = evidence / cert_rel
        if not cert_rel or not cert_path.is_file():
            raise SystemExit(f"resume certificate missing cert={cert_rel}")
        actual = sha256_file(cert_path)
        expected = sum_for(sums_text, cert_rel)
        action = resume_action(cert_verdict(cert_path.read_text(encoding="utf-8")), actual, expected)
        runner.log.line(f"RESUME cert action={action} sha256={actual} cert={cert_rel}")
        if action != "skip_verified":
            raise SystemExit(f"resume certificate check failed action={action} cert={cert_rel}")
        row["sha256_verified"] = actual
        gmeta = evidence / "arm-g" / f"{row['slug']}.meta.json"
        if gmeta.is_file():
            elapsed = float(json.loads(gmeta.read_text(encoding="utf-8")).get("elapsed_s") or 0)
            row["seed_timeout_s"] = seed_timeout_s(elapsed)
        kept.append(row)
    return kept


def _log_continue(runner: Runner, evidence: Path, by_path: dict, paths: list[str]) -> None:
    for path in paths:
        row = by_path[path]
        digest = str(row.get("slug") or slug(path))
        metas = {}
        for seed in range(SEED_LO, SEED_HI + 1):
            meta_path = evidence / "arm-f" / digest / f"seed-{seed:02d}.meta.json"
            if meta_path.is_file():
                metas[seed] = json.loads(meta_path.read_text(encoding="utf-8"))
        runner.log.line(f"RESUME continue from_seed={next_resume_seed(metas)} path={path}")


def _resume_tail(runner: Runner, evidence: Path, excluded: dict, later_paths: list[str]):
    clock = runner.clock_name
    idle_b1 = _idle_b1(excluded["b1"][0] if excluded["b1"] else "")
    if runner.stop_reason or _past_stop(evidence, clock):
        runner.log.line(f"STOP before excluded set reason={runner.stop_reason or 'budget'}")
        return (
            _idle_categories(excluded["category_a"]),
            idle_b1,
            [not_run_row(path) for path in later_paths],
        )
    categories = []
    for path in excluded["category_a"]:
        if runner.stop_reason or _past_stop(evidence, clock):
            categories.extend(_idle_categories([path]))
            continue
        categories.append(runner.category_file(path))
    if runner.stop_reason or _past_stop(evidence, clock):
        runner.log.line(f"STOP before reverse-order path reason={runner.stop_reason or 'budget'}")
        return categories, idle_b1, [not_run_row(path) for path in later_paths]
    b1_rows = [runner.run_b1(path) for path in excluded["b1"]]
    b1 = b1_rows[0] if b1_rows else {}
    if runner.stop_reason or _past_stop(evidence, clock):
        runner.log.line(f"STOP before remaining sample reason={runner.stop_reason or 'budget'}")
        return categories, b1, [not_run_row(path) for path in later_paths]
    runner.log.line(f"RESUME remaining sample paths={len(later_paths)}")
    later_rows = runner.run_s20(later_paths) if later_paths else []
    return categories, b1, later_rows


def _acceptance(names: list[str], roots: list[str]) -> tuple[int, str]:
    rc = 1
    chunks = []
    for name in names:
        if not name:
            continue
        proc = subprocess.run(
            ["grep", "-RInF", "-e", name, *roots],
            capture_output=True,
            text=True,
            check=False,
        )
        chunks.append(f"grep -RInF -e {name!r} {' '.join(roots)} -> {proc.returncode}")
        if proc.returncode == 0:
            rc = 0
            chunks.append(proc.stdout)
        elif proc.returncode not in (0, 1):
            rc = proc.returncode
            chunks.append(proc.stderr)
    return rc, "\n".join(chunks) + "\n"


def _write_sums(evidence: Path) -> None:
    sums = evidence / "SHA256SUMS"
    lines = []
    for path in sorted(evidence.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        rel = path.relative_to(evidence).as_posix()
        lines.append(f"{sha256_file(path)}  {rel}")
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _check_summary(evidence: Path, payload: dict) -> None:
    skeptic = Path(payload["skeptic_path"]).read_text(encoding="utf-8")
    rows = payload["s20"]
    labels = payload["category_a"]
    b1 = payload["b1"]
    lines = [
        "# G3 check summary",
        "",
        "Counts below are copied from the logs named on each line.",
        "",
        "## Sample",
        "",
        f"- S20 paths: `s20.txt` ({len(rows)} lines).",
        f"- Category paths: `cat_a.txt`.",
        f"- B1 path: `b1.txt`.",
        "",
        "## Arm results",
        "",
        "| path | arm G | arm F verdict | failures | certificate |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['path']}` | {'PASS' if row['arm_g_pass'] else 'FAIL'} `{row['arm_g_log']}` | "
            f"{row['verdict']} | {row['arm_f_failures']}/{row['arm_f_trials']} | `{row['cert']}` |"
        )
    lines.extend(
        [
            "",
            "Files that pass arm G and fail arm F: "
            + (", ".join(f"`{item}`" for item in payload["cross"]) if payload["cross"] else "none")
            + ". Source rows are the arm table above.",
            "",
            "## Category labels",
            "",
        ]
    )
    for item in labels:
        lines.append(
            f"- `{item['path']}` {item['label']} alone=`{item['alone_log']}` siblings=`{item['siblings_log']}`"
        )
    lines.extend(
        [
            "",
            "## B1",
            "",
            f"- path `{b1.get('path')}` label `{b1.get('label')}`",
            f"- set `{b1.get('set')}` same_file={b1.get('same_file')} replay_twice={b1.get('replay_twice')}",
            f"- logs `{b1.get('defined_log')}` `{b1.get('reverse_log')}` `{b1.get('bisect_log')}` `{b1.get('ddmin_log')}`",
            "",
            "## Skeptic pass",
            "",
            "The questions are the frozen `SKEPTIC-G3.md`. Answers use this run's logs.",
            "",
            "```",
            skeptic.rstrip(),
            "```",
            "",
            "1. This subject is a proving ground for the method.",
            "2. Enabler labels are the category list above. A zero enabler count is what `cat_a` logs support, not a prediction.",
            "3. Removal totals stay in `inputs/dryrun-2026-10-19-g3/reverse/recon-gitlab.log` under T1 and T2. Notes were not read.",
            "4. Setup noise is an `ENV_FAILURE` label only when the alone log matches the structural rule in that file's meta.",
            "5. Each S20 certificate's first line is the Clopper-Pearson bound. `BOUNDED_CLEAN` means zero failures inside that bound, not the absence of flakes.",
            "6. `s20.txt` is only the models/lib FOSS slice from the frozen spec. It does not represent request or feature specs.",
            "7. This run is a method proof; it tests no commercial claim.",
            "",
            f"Holdout seal file `HOLDOUT-G3.sha256` was not opened as a predictions document. "
            f"Its digest is recorded in `summary.json`. Q3 stays N/A under the amendment because the full-suite arm was dropped. "
            f"The dated question stays for its own date.",
            "",
        ]
    )
    (evidence / "check-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_checkout(runner: Runner) -> str:
    head = subprocess.check_output(["git", "-C", str(runner.gitlab), "rev-parse", "HEAD"], text=True).strip()
    if head != runner.commit:
        raise SystemExit(f"checkout {head} != spec {runner.commit}")
    todo_sha, _name = sha_by_prefix(runner.recon, "todo-")
    script_sha, _script_name = sha_by_prefix(runner.recon, "check-")
    script_path = runner.gitlab / runner.check_rel
    runner.todo_rel = todo_relpath(script_path.read_text(encoding="utf-8"))
    todo_path = runner.gitlab / runner.todo_rel.lstrip("./")
    got_todo = sha256_file(todo_path)
    got_script = sha256_file(script_path)
    runner.log.line(f"todo sha256 {got_todo} expected {todo_sha}")
    runner.log.line(f"check sha256 {got_script} expected {script_sha}")
    if got_todo != todo_sha or got_script != script_sha:
        raise SystemExit("pinned todo or check script hash mismatch")
    return runner.todo_rel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--gitlab-dir", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--container", default="g3runner")
    parser.add_argument("--postgres", default="g3pg")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--setup-log", default="")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip a clean certificate after its sha256 matches, and continue unfinished seeds",
    )
    args = parser.parse_args(argv)
    evidence = Path(args.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=True)
    if args.resume:
        (evidence / "resume_started_at").write_text(_now() + "\n", encoding="utf-8")
    if not (evidence / "started_at").is_file():
        (evidence / "started_at").write_text(_now() + "\n", encoding="utf-8")
    invoke = evidence / "invoke.txt"
    recorded = argv if argv is not None else sys.argv[1:]
    invoke.write_text(
        " ".join(shlex.quote(item) for item in ["python3", "-m", "tools.certify_rspec.pipeline_g3", *recorded])
        + "\n",
        encoding="utf-8",
    )
    log = RunLog(evidence / "run.log")
    runner = Runner(args, log)
    log.line(f"commit {runner.commit}")
    todo_rel = verify_checkout(runner)
    version = (runner.gitlab / ".gitlab" / "ci" / "version.yml").read_text(encoding="utf-8")
    gitlab_ci = (runner.inputs / "reverse" / "gitlab-ci-8004fe1c.yml").read_text(encoding="utf-8")
    global_ci = (runner.inputs / "reverse" / "global.gitlab-ci-8004fe1c.yml").read_text(encoding="utf-8")
    images = resolve_images(version, gitlab_ci, global_ci)
    records = {
        "ci": _image_record(images["ci_image"]),
        "postgres": _image_record(images["postgres_image"]),
        "redis": _image_record(images["redis_image"]),
        "redis_cluster": _image_record(images["redis_cluster_image"]),
    }
    prior_env_path = evidence / "env.json"
    if args.resume and prior_env_path.is_file():
        prior_env = json.loads(prior_env_path.read_text(encoding="utf-8"))
        prior_digest = (prior_env.get("images") or {}).get("ci", {}).get("repo_digests")
        if prior_digest != records["ci"]["repo_digests"]:
            raise SystemExit("CI image digest changed since the partial run")
    env_doc = {
        "images": records,
        "postgres_command": images["postgres_command"],
        "gdk_fallback": False,
        "simplecov": "false",
        "enable_spring": False,
        "cache_classes": True,
        "spring_probe": "ENABLE_SPRING=1 with CACHE_CLASSES=false hit a 70s host timeout before examples finished, so the campaign uses a fresh process per run",
        "decomposed_db": True,
        "sec_decomposed_db": True,
        "rails_env": "test",
    }
    (evidence / "env.json").write_text(json.dumps(env_doc, indent=2) + "\n", encoding="utf-8")
    if args.setup_log:
        source = Path(args.setup_log)
        if source.is_file():
            (evidence / "setup.log").write_bytes(source.read_bytes())
    runner.prepare_databases()
    runner.pristine_todo(todo_rel)
    subprocess.run(
        ["docker", "cp", str(Path(__file__).resolve().parent / "ordering.rb"), f"{runner.container}:/tmp/ordering.rb"],
        check=True,
    )
    todo_text = (runner.gitlab / todo_rel.lstrip("./")).read_text(encoding="utf-8")
    s20 = select_s20(todo_text, 20)
    (evidence / "s20.txt").write_text("\n".join(s20) + "\n", encoding="utf-8")
    log.line(f"wrote s20.txt lines={len(s20)}")
    excluded = parse_excluded(descriptions_from_sources(runner.inputs / "sources"))
    (evidence / "cat_a.txt").write_text("\n".join(excluded["category_a"]) + "\n", encoding="utf-8")
    (evidence / "b1.txt").write_text("\n".join(excluded["b1"]) + "\n", encoding="utf-8")
    log.line(f"wrote cat_a.txt lines={len(excluded['category_a'])} b1.txt lines={len(excluded['b1'])}")
    prior_payload: dict = {}
    if args.resume:
        summary_path = evidence / "summary.json"
        if summary_path.is_file():
            prior_payload = json.loads(summary_path.read_text(encoding="utf-8"))
        by_path = {row["path"]: row for row in prior_payload.get("s20") or []}
        ordered_rows = [by_path.get(path) or not_run_row(path) for path in s20]
        plan = resume_plan(ordered_rows)
        kept = _verify_skips(runner, evidence, by_path, plan["skip"])
        _log_continue(runner, evidence, by_path, plan["continue"])
        log.line(
            f"RESUME order continue={len(plan['continue'])} "
            f"excluded={len(excluded['category_a'])} "
            f"reverse={len(excluded['b1'])} "
            f"later={len(plan['later'])}"
        )
        continued = runner.run_s20(plan["continue"]) if plan["continue"] else []
        categories, b1, later_rows = _resume_tail(runner, evidence, excluded, plan["later"])
        updates = {row["path"]: row for row in kept}
        updates.update({row["path"]: row for row in continued})
        updates.update({row["path"]: row for row in later_rows})
        rows = [updates.get(path) or by_path.get(path) or not_run_row(path) for path in s20]
    else:
        rows = runner.run_s20(s20)
        if _past_stop(evidence):
            log.line("STOP budget before category and B1")
            categories = _idle_categories(excluded["category_a"])
            b1 = _idle_b1(excluded["b1"][0] if excluded["b1"] else "")
        else:
            categories = [runner.category_file(path) for path in excluded["category_a"]]
            b1_rows = [runner.run_b1(path) for path in excluded["b1"]]
            b1 = b1_rows[0] if b1_rows else {}
    gdk = False
    for row in rows:
        if runner.mention(row["arm_g_log"]):
            gdk = True
    if gdk:
        log.line("absence needle matched an arm G log; fallback flag set")
    env_doc["gdk_fallback"] = gdk
    (evidence / "env.json").write_text(json.dumps(env_doc, indent=2) + "\n", encoding="utf-8")
    extra_replays = []
    for item in categories:
        if item.get("enabler_replay"):
            script = evidence / item["enabler_replay"]
            item["replay_twice"] = runner._script_passes_twice(script)
            extra_replays.append(item["replay_twice"])
        else:
            item["replay_twice"] = None
    cross = armg_pass_armf_fail(rows)
    headlines_ok = True
    for row in rows:
        if not row["cert"]:
            headlines_ok = False
            continue
        first = (evidence / row["cert"]).read_text(encoding="utf-8").splitlines()[0]
        if not HEADLINE_RE.match(first):
            headlines_ok = False
    labels_ok = all(item.get("label") and item.get("alone_log") for item in categories) and bool(b1.get("label"))
    replay_ok = bool(b1.get("replay_twice")) and all(value is not False for value in extra_replays)
    names = [row["path"] for row in rows]
    names.extend(item["path"] for item in categories)
    names.extend(excluded["b1"])
    for item in categories:
        names.extend(item.get("enablers") or [])
    names.extend(b1.get("set") or [])
    grep_rc, grep_text = _acceptance(names, ["tools", str(invoke)])
    (evidence / "acceptance-grep.log").write_text(grep_text, encoding="utf-8")
    wall = _wall(evidence, runner.clock_name)
    exit_ok = (
        headlines_ok
        and labels_ok
        and replay_ok
        and grep_rc == 1
        and wall <= WALL_LIMIT_S
        and all(row["verdict"] in ("BOUNDED_CLEAN", "CERTIFIED_ORDER_DEPENDENT") for row in rows)
    )
    reason = ""
    if not exit_ok:
        if runner.stop_reason == "ENV_SETUP":
            reason = "ENV_SETUP"
        elif wall > WALL_LIMIT_S or _past_stop(evidence, runner.clock_name):
            reason = "WALL_CLOCK"
        elif grep_rc != 1:
            reason = "ACCEPTANCE_GREP"
        else:
            reason = "INCOMPLETE"
    holdout = runner.inputs / "HOLDOUT-G3.sha256"
    payload = {
        "base_sha": "611e80fb0e5e390b0f4d4f1e814f844beacdf1ab",
        "inputs_commit": "af6029fdf0f462f15fde2bb85a53f6be0e09094a",
        "gitlab_commit": runner.commit,
        "exit_ok": exit_ok,
        "reason": reason,
        "gdk_fallback": gdk,
        "wall_clock_s": round(wall, 1),
        "s20": rows,
        "cross": cross,
        "category_a": categories,
        "b1": b1,
        "acceptance_grep_exit": grep_rc,
        "headlines_ok": headlines_ok,
        "holdout_sha256_file": sha256_file(holdout),
        "skeptic_path": str(runner.inputs / "SKEPTIC-G3.md"),
        "resume": bool(args.resume),
        "setup_failures": runner.setup_failures,
        "seed_timeout_rule": "max(300, ceil(3 * arm_g_elapsed_s))",
    }
    if args.resume:
        for key, value in prior_payload.items():
            payload.setdefault(key, value)
    (evidence / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _check_summary(evidence, payload)
    g3_lines = []
    for role, record in records.items():
        digest = record["repo_digests"][0] if record["repo_digests"] else record["id"]
        g3_lines.append(f"{role}_image={record['tag']}")
        g3_lines.append(f"{role}_digest={digest}")
    g3_lines.append(f"GDK_FALLBACK={str(gdk).lower()}")
    g3_lines.append(f"S20_COUNT={len(s20)} source=s20.txt")
    for row in rows:
        g3_lines.append(
            f"ARM path={row['path']} G={'PASS' if row['arm_g_pass'] else 'FAIL'} "
            f"G_LOG={row['arm_g_log']} F={row['verdict']} "
            f"F_FAILURES={row['arm_f_failures']}/{row['arm_f_trials']} F_CERT={row['cert']}"
        )
    g3_lines.append("ARMG_PASS_ARMF_FAIL=" + (",".join(cross) if cross else "none"))
    for item in categories:
        g3_lines.append(
            f"CAT_A path={item['path']} label={item['label']} "
            f"alone_log={item['alone_log']} siblings_log={item['siblings_log']}"
        )
    g3_lines.append(
        "B1 path={path} label={label} set={set} same_file={same_file} replay_twice={replay_twice} "
        "defined_log={defined_log} reverse_log={reverse_log} bisect_log={bisect_log} ddmin_log={ddmin_log}".format(
            **b1
        )
    )
    g3_lines.append(f"WALL_CLOCK={wall:.1f}")
    g3_lines.append(f"resume={str(bool(args.resume)).lower()}")
    g3_lines.append(f"setup_failures={runner.setup_failures}")
    g3_lines.append("seed_timeout_rule=max(300, ceil(3 * arm_g_elapsed_s))")
    for row in rows:
        if row.get("seed_timeout_s") is not None:
            g3_lines.append(f"SEED_TIMEOUT path={row['path']} seconds={row['seed_timeout_s']}")
    g3_lines.append(f"exit_ok={str(exit_ok).lower()}")
    if reason:
        g3_lines.append(f"reason={reason}")
        g3_lines.append(f"stop_reserve_s={STOP_RESERVE_S}")
    g3_lines.append(f"acceptance_grep_exit={grep_rc}")
    (evidence / "g3.log").write_text("\n".join(g3_lines) + "\n", encoding="utf-8")
    _write_sums(evidence)
    log.line(f"exit_ok={exit_ok} reason={reason} wall={wall:.1f}")
    return 0 if exit_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
