"""S6-S10 residual seeds and cause sets.

The CLI takes the prior evidence directory, base and head tarball URLs, and an
image. It does not take a victim, a polluter, or a seed. S6 reads the prior s0
JSON only. Later stages run example ids through the ordering require.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tools.certify_rspec import __version__
from tools.certify_rspec.cause import (
    CAP_REACHED,
    CONFIRMATIONS,
    EXPLAINED,
    G2_OK_LINE,
    MAX_ROUNDS,
    SKEPTIC_ANSWERS,
    UNREPRODUCED,
    format_polluter_line,
    format_residual_line,
    format_seed_line,
    recompute_certificate_label,
    reproduction,
    search_cause,
    select_residual,
    victim_token_matches,
)
from tools.certify_rspec.certificate import validate_certificate
from tools.certify_rspec.commands import IDS_ENV, ORDERING_REQUIRE, format_command, ordered_ids, ordered_spec_commands
from tools.certify_rspec.exit_rule import classification_exit_ok
from tools.certify_rspec.order_guard import order_guard
from tools.certify_rspec.parse_rspec import norm_id, parse_outcome
from tools.certify_rspec.pipeline import (
    REPO_ROOT,
    RunLog,
    _build_cert,
    _docker_server_version,
    _exec_argv,
    _git_sha,
    _image_id,
    _parse_versions,
    _run_rspec,
)
from tools.certify_rspec.pipeline_g2 import (
    PATH_VALUE,
    _bundled_with,
    _exit_code,
    _expected_tarballs,
    _grep,
    _image_digest,
    _load_examples,
    _write_sums,
)
from tools.certify_rspec.replay import write_replay_script
from tools.certify_rspec.runner import docker_bash, docker_rspec
from tools.certify_rspec.sources import commit_from_url, ensure_tarball, ensure_tree, repo_from_url, sha256_file
from tools.certify_rspec.verdict import judge

SPEC_PATH = REPO_ROOT / "inputs" / "dryrun-2026-10-19-g2-2" / "SPEC-G2-2.md"
SKEPTIC_PATH = REPO_ROOT / "inputs" / "dryrun-2026-10-19-g2-2" / "SKEPTIC-G2-2.md"
RECON_AXN = REPO_ROOT / "inputs" / "dryrun-2026-10-19-g2" / "reverse" / "recon-axn.log"
SEED_MIN = 1
SEED_MAX = 30
REPS = 3
SETTLED_SEED = {EXPLAINED, UNREPRODUCED, CAP_REACHED}


def _rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _acceptance_pattern(spec_text: str) -> str:
    match = re.search(r"grep -RInE '([^']+)'", spec_text)
    if not match:
        raise SystemExit("spec has no acceptance grep pattern")
    return match.group(1)


def _acceptance_token(spec_text: str) -> str:
    match = re.search(r"CERTIFIED for (\S+), with residual-seed provenance", spec_text)
    if not match:
        raise SystemExit("spec has no acceptance victim token")
    return match.group(1).rstrip(".")


def _light_examples(examples: list) -> list[dict]:
    light = []
    for example in examples:
        if not isinstance(example, dict):
            continue
        item = {"id": example.get("id"), "status": example.get("status")}
        exc = example.get("exception")
        if isinstance(exc, dict):
            item["exception"] = {"class": exc.get("class")}
        light.append(item)
    return light


def _victim_fields(examples: list[dict], victim_id: str) -> tuple[str | None, str | None]:
    target = norm_id(victim_id)
    for example in examples:
        ident = example.get("id")
        if not ident or norm_id(str(ident)) != target:
            continue
        status = example.get("status")
        exc = example.get("exception") if isinstance(example.get("exception"), dict) else {}
        klass = exc.get("class") if isinstance(exc, dict) else None
        return (status if isinstance(status, str) else None, klass if isinstance(klass, str) else None)
    return None, None


def _skeptic_points(text: str) -> list[str]:
    points: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\d+\. ", line):
            if current:
                points.append("\n".join(current).strip())
            current = [line]
        elif current:
            current.append(line)
    if current:
        points.append("\n".join(current).strip())
    return points


class CauseRun:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.out = Path(args.out)
        self.prior = Path(args.prior)
        self.cache = Path(args.cache)
        self.jobs = max(1, int(args.jobs))
        self.image = args.image
        self.suite = args.suite
        self.log = RunLog(self.out / "run.log")
        self.started = time.monotonic()
        self.mounts: list[str] = []
        self.env: list[tuple[str, str]] = []
        self.bundler_version = ""
        self.versions: dict[str, str] = {}
        self.base: dict = {}
        self.head: dict = {}
        self.image_id = ""
        self.image_digest = ""
        self.server = ""
        self.git_sha = ""
        self._confirm_lock = threading.Lock()
        self._confirm_n: dict[tuple[str, int], int] = {}
        self.base_trees: queue.Queue[Path] = queue.Queue()

    def _next_confirm(self, victim_id: str, seed: int) -> int:
        key = (victim_id, seed)
        with self._confirm_lock:
            value = self._confirm_n.get(key, 0) + 1
            self._confirm_n[key] = value
            return value

    def _side_env(self) -> None:
        bundle = self.cache / "bundle"
        gems = self.cache / "gems"
        bundle.mkdir(parents=True, exist_ok=True)
        gems.mkdir(parents=True, exist_ok=True)
        self.mounts = ["-v", f"{bundle.resolve()}:/bundle", "-v", f"{gems.resolve()}:/gems"]
        self.env = [
            ("GEM_HOME", "/gems"),
            ("PATH", PATH_VALUE),
            ("BUNDLE_PATH", "/bundle"),
            ("BUNDLE_SILENCE_ROOT_WARNING", "1"),
        ]

    def _prepare(self, url: str, expected: str) -> dict:
        commit = commit_from_url(url)
        self.log.section(f"source {commit}")
        tarball, digest = ensure_tarball(self.cache, url, commit)
        self.log.write(f"tarball {tarball} sha256 {digest}", echo=True)
        if digest != expected:
            if tarball.is_file():
                tarball.unlink()
            tarball, digest = ensure_tarball(self.cache, url, commit)
            self.log.write(f"re-fetched tarball sha256 {digest}", echo=True)
        if digest != expected:
            raise SystemExit(f"tarball sha256 {digest} != recon {expected} for {commit}")
        tree = ensure_tree(self.cache, tarball, commit)
        self.log.write(f"tree {tree}", echo=True)
        lock = tree / "Gemfile.lock"
        lock_sha = sha256_file(lock)
        self.log.write(f"Gemfile.lock sha256 {lock_sha}", echo=True)
        version = _bundled_with(lock.read_text(encoding="utf-8"))
        return {
            "commit": commit,
            "sha7": commit[:7],
            "tarball_sha256": digest,
            "tree": tree,
            "gemfile_lock_sha256": lock_sha,
            "bundler": version,
        }

    def _version_probe(self, side: dict) -> dict[str, str]:
        version = side["bundler"]
        script = "\n".join(
            [
                "set -euo pipefail",
                "ruby -v",
                f"bundle _{version}_ -v",
                f"bundle _{version}_ exec rspec --version",
            ]
        )
        code, text, elapsed = docker_bash(self.image, side["tree"], script, 300, self.mounts, self.env)
        self.log.write(text, echo=False)
        self.log.write(f"version_probe exit={code} elapsed_s={elapsed:.3f}", echo=True)
        if code != 0:
            install = "\n".join(
                [
                    "set -euo pipefail",
                    f"gem install bundler -v {version} --no-document",
                    f"bundle _{version}_ install --jobs 4",
                    f"bundle _{version}_ check",
                    "ruby -v",
                    f"bundle _{version}_ -v",
                    f"bundle _{version}_ exec rspec --version",
                ]
            )
            self.log.write(f"+ bundle install bundler {version}", echo=True)
            code, text, elapsed = docker_bash(self.image, side["tree"], install, 1800, self.mounts, self.env)
            self.log.write(text, echo=False)
            self.log.write(f"bundle_install_exit={code} elapsed_s={elapsed:.3f}", echo=True)
            if code != 0:
                raise SystemExit(f"bundle install failed for {side['commit']}")
        parsed = _parse_versions(text)
        if not parsed.get("rspec_core"):
            raise SystemExit(f"version probe did not report rspec-core for {side['commit']}")
        return parsed

    def _worker_trees(self, side_name: str, side: dict) -> list[Path]:
        trees = []
        for slot in range(self.jobs):
            dest = self.cache / "workers" / f"{side_name}-{slot}"
            marker = dest / "Gemfile.lock"
            if not marker.is_file():
                if dest.exists():
                    shutil.rmtree(dest)
                self.log.write(f"copy tree {side['tree']} -> {dest}", echo=True)
                shutil.copytree(side["tree"], dest, symlinks=True)
            trees.append(dest)
        return trees

    def _certified_victims(self) -> list[dict]:
        summary = json.loads((self.prior / "summary.json").read_text(encoding="utf-8"))
        victims = []
        for row in summary.get("rows") or []:
            if row.get("classification") != "ORDER-DEPENDENT" or row.get("label") != "CERTIFIED":
                continue
            cert_name = row.get("cert")
            if not isinstance(cert_name, str):
                continue
            cert = json.loads((self.prior / cert_name).read_text(encoding="utf-8"))
            if cert.get("label") != "CERTIFIED":
                continue
            victim_id = cert.get("victim_id")
            polluters = cert.get("polluter_ids")
            if not isinstance(victim_id, str) or not isinstance(polluters, list):
                raise SystemExit(f"{cert_name} has no victim or polluter list")
            if row.get("id") != victim_id:
                raise SystemExit(f"{cert_name} victim does not match the summary row")
            victims.append(
                {
                    "victim_id": victim_id,
                    "victim_location": cert.get("victim_location") or row.get("location") or victim_id,
                    "cert_name": cert_name,
                    "known_polluter_ids": [item for item in polluters if isinstance(item, str)],
                    "residual_seeds": [],
                }
            )
        return victims

    def _residual(self, victims: list[dict]) -> list[dict]:
        records = []
        for seed in range(SEED_MIN, SEED_MAX + 1):
            path = self.prior / "s0" / f"base-seed-{seed:02d}.json"
            if not path.is_file():
                raise SystemExit(f"missing prior s0 file {path}")
            data = json.loads(path.read_text(encoding="utf-8"))
            examples = _light_examples(data.get("examples") or [])
            del data
            for victim in victims:
                found = select_residual(examples, victim["victim_id"], victim["known_polluter_ids"])
                if found is None:
                    continue
                digest = _sha256_text("\n".join(found["candidate_ids"]))
                record = {
                    "victim_id": victim["victim_id"],
                    "victim_location": victim["victim_location"],
                    "cert_name": victim["cert_name"],
                    "known_polluter_ids": list(victim["known_polluter_ids"]),
                    "seed": seed,
                    "error_class": found["error_class"],
                    "victim_index": found["victim_index"],
                    "polluter_indexes": found["polluter_indexes"],
                    "candidate_sha256": digest,
                    "candidate_ids": found["candidate_ids"],
                    "s0": _rel(path),
                }
                victim["residual_seeds"].append(
                    {
                        "seed": seed,
                        "error_class": found["error_class"],
                        "victim_index": found["victim_index"],
                        "polluter_indexes": found["polluter_indexes"],
                        "candidate_sha256": digest,
                        "candidate_ids": found["candidate_ids"],
                        "s0": _rel(path),
                    }
                )
                records.append(record)
        document = {
            "prior": _rel(self.prior),
            "s0": _rel(self.prior / "s0"),
            "note": "Selected from prior base s0 JSON only. No suite run.",
            "victims": [
                {
                    "victim_id": victim["victim_id"],
                    "victim_location": victim["victim_location"],
                    "cert": victim["cert_name"],
                    "known_polluter_ids": victim["known_polluter_ids"],
                    "residual_seeds": victim["residual_seeds"],
                }
                for victim in victims
            ],
        }
        dest = self.out / "s6" / "residual-seeds.json"
        dest.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        self.log.write(f"wrote {_rel(dest)}", echo=True)
        for victim in victims:
            seeds = [item["seed"] for item in victim["residual_seeds"]]
            self.log.write(format_residual_line(victim["victim_id"], seeds), echo=True)
        return records

    def _cache_dir(self, digest: str, round_index: int) -> Path:
        folder = "s7" if round_index == 1 else "s8"
        return self.out / folder / "by-hash" / digest

    def _cached_probe(self, digest: str, expected_class: str) -> dict | None:
        for folder in ("s7", "s8"):
            path = self.out / folder / "by-hash" / digest / "result.json"
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not data.get("complete"):
                continue
            log_path = REPO_ROOT / str(data.get("log") or "")
            json_path = REPO_ROOT / str(data.get("json") or "")
            if not log_path.is_file() or not json_path.is_file():
                continue
            data["reproduced"] = reproduction(
                str(data.get("order_status") or ""),
                data.get("victim_status"),
                data.get("victim_error_class"),
                expected_class,
            )
            return data
        return None

    def _probe(
        self,
        record: dict,
        tree: Path,
        ids: list[str],
        phase: str,
        round_index: int,
        confirm_index: int,
    ) -> dict:
        victim_id = record["victim_id"]
        seed = int(record["seed"])
        expected = str(record["error_class"])
        material = "\n".join([phase, str(confirm_index), victim_id, str(seed), *ids])
        digest = _sha256_text(material)
        cached = self._cached_probe(digest, expected)
        if cached is not None:
            self.log.write(
                f"resume probe seed={seed} round={round_index} phase={phase} n={cached.get('n_ids')} reproduced={cached['reproduced']}",
                echo=False,
            )
            return cached
        intended = [*ids, victim_id]
        directory = self._cache_dir(digest, round_index)
        directory.mkdir(parents=True, exist_ok=True)
        ids_path = directory / "ids.txt"
        ids_path.write_text("\n".join(intended) + "\n", encoding="utf-8")
        ids_sha = sha256_file(ids_path)
        log_path = directory / "probe.log"
        json_path = directory / "rspec.json"
        timeout = 900 if len(intended) >= 800 else 300
        argv = [
            "--format",
            "json",
            "--out",
            f"/out/{json_path.name}",
            "--require",
            ORDERING_REQUIRE,
            *intended,
        ]
        # The id list is a file inside the mounted probe directory. One environment
        # value cannot hold the longer prefixes.
        env = [*self.env, ("ids_file", f"/out/{ids_path.name}")]
        last_error = "no examples"
        code = 1
        text = ""
        elapsed = 0.0
        examples: list[dict] | None = None
        for attempt in (1, 2):
            status_file = tree / ".rspec_status"
            if status_file.exists():
                status_file.unlink()
            if json_path.exists():
                json_path.unlink()
            code, text, elapsed = docker_rspec(
                self.image,
                tree,
                argv,
                json_path,
                timeout,
                bundler=self.bundler_version,
                extra_mounts=self.mounts,
                extra_env=env,
            )
            header = "\n".join(
                [
                    f"+ phase={phase}",
                    f"+ seed={seed}",
                    f"+ round={round_index}",
                    f"+ confirm={confirm_index}",
                    f"+ ids_n={len(intended)}",
                    f"+ ids_sha256={ids_sha}",
                    f"+ ids_file={_rel(ids_path)}",
                    f"+ attempt={attempt}",
                    f"elapsed_s={elapsed:.3f}",
                ]
            )
            body = text if text.endswith("\n") or not text else text + "\n"
            log_path.write_text(f"{header}\n{body}docker_exit={code}\n", encoding="utf-8")
            timed_out = code == 124
            examples = _load_examples(json_path)
            if not timed_out and examples:
                break
            last_error = "timed out" if timed_out else f"attempt {attempt} produced no examples"
            self.log.write(f"retry probe seed={seed} round={round_index} {last_error}", echo=True)
            examples = None
        if not examples:
            raise SystemExit(f"probe failed twice seed={seed} round={round_index} phase={phase}: {last_error}")
        order_status = order_guard(examples, intended)
        victim_status, error_class = _victim_fields(examples, victim_id)
        reproduced = reproduction(order_status, victim_status, error_class, expected)
        result = {
            "complete": True,
            "reproduced": reproduced,
            "order_status": order_status,
            "victim_status": victim_status,
            "victim_error_class": error_class,
            "expected_error_class": expected,
            "log": _rel(log_path),
            "json": _rel(json_path),
            "ids": _rel(ids_path),
            "ids_sha256": ids_sha,
            "n_ids": len(intended),
            "elapsed_s": round(elapsed, 3),
            "exit_code": code,
            "phase": phase,
            "round": round_index,
            "seed": seed,
        }
        (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        self.log.write(
            f"probe seed={seed} round={round_index} phase={phase} n={len(intended)} "
            f"reproduced={reproduced} order={order_status} elapsed_s={elapsed:.3f} exit={code}",
            echo=True,
        )
        return result

    def _done_path(self, record: dict) -> Path:
        digest = hashlib.sha256(record["victim_id"].encode("utf-8")).hexdigest()[:8]
        return self.out / "s7" / "done" / f"s{int(record['seed']):02d}-{digest}.json"

    def _load_done(self, record: dict) -> dict | None:
        path = self._done_path(record)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if data.get("candidate_sha256") != record["candidate_sha256"]:
            return None
        if data.get("error_class") != record["error_class"]:
            return None
        for round_info in data.get("rounds") or []:
            for probe in round_info.get("probes") or []:
                log_path = REPO_ROOT / str(probe.get("log") or "")
                if not log_path.is_file():
                    return None
        return data

    def _search_one(self, record: dict) -> dict:
        done = self._load_done(record)
        if done is not None:
            self.log.write(
                f"resume seed={record['seed']} victim_sha={self._done_path(record).name} status={done.get('status')}",
                echo=True,
            )
            return done
        tree = self.base_trees.get()
        try:
            started = time.monotonic()

            def run(ids: list[str], phase: str, round_index: int, record: dict = record, tree: Path = tree) -> dict:
                confirm_index = 0
                if phase == "confirm":
                    confirm_index = self._next_confirm(record["victim_id"], int(record["seed"]))
                return self._probe(record, tree, ids, phase, round_index, confirm_index)

            found = search_cause(record["candidate_ids"], run, MAX_ROUNDS, CONFIRMATIONS)
            found["victim_id"] = record["victim_id"]
            found["victim_location"] = record["victim_location"]
            found["cert_name"] = record["cert_name"]
            found["known_polluter_ids"] = list(record["known_polluter_ids"])
            found["seed"] = record["seed"]
            found["error_class"] = record["error_class"]
            found["candidate_sha256"] = record["candidate_sha256"]
            found["elapsed_s"] = round(time.monotonic() - started, 3)
            path = self._done_path(record)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
            self.log.write(
                f"seed={record['seed']} status={found['status']} rounds={len(found['rounds'])} elapsed_s={found['elapsed_s']}",
                echo=True,
            )
            return found
        finally:
            self.base_trees.put(tree)

    def _complete_arm(self, log_path: Path, json_path: Path, logical: str) -> tuple[dict, list[dict]] | None:
        if not log_path.is_file() or not json_path.is_file():
            return None
        text = log_path.read_text(encoding="utf-8", errors="replace")
        first = text.splitlines()[0] if text.splitlines() else ""
        if first != f"+ logical={logical}":
            return None
        code = _exit_code(text)
        if code is None or code == 124:
            return None
        examples = _load_examples(json_path)
        if not examples:
            return None
        outcome = parse_outcome(text, code, json_path)
        outcome["log_sha256"] = sha256_file(log_path)
        outcome["log"] = _rel(log_path)
        return outcome, examples

    def _arm(
        self,
        side_name: str,
        side: dict,
        body: list[str],
        intended: list[str],
        stem: str,
        victim_id: str,
    ) -> dict:
        log_path = self.out / "s9" / f"{stem}.log"
        json_path = self.out / "s9" / f"{stem}.json"
        logical = format_command(["rspec", *body])
        run_env = [*self.env, (IDS_ENV, " ".join(intended))]
        cached = self._complete_arm(log_path, json_path, logical)
        if cached is None:
            outcome = _run_rspec(
                self.log,
                self.image,
                side["tree"],
                _exec_argv(body, json_path.name),
                log_path,
                json_path,
                240,
                logical,
                bundler=self.bundler_version,
                extra_mounts=self.mounts,
                extra_env=run_env,
            )
            examples = _load_examples(json_path) or []
        else:
            outcome, examples = cached
            self.log.write(f"resume {log_path.name} docker_exit={outcome.get('exit_code')}", echo=True)
        outcome["order_status"] = order_guard(examples, intended)
        status, _klass = _victim_fields(examples, victim_id)
        outcome["victim_status"] = status
        outcome["exec_argv"] = _exec_argv(body, json_path.name)
        outcome["tree_side"] = side_name
        outcome["json_host"] = _rel(json_path)
        outcome["log"] = _rel(log_path)
        outcome["extra_env"] = [list(item) for item in run_env]
        return outcome

    def _certify_group(self, index: int, victim: dict, polluters: list[str], provenance_rows: list[dict]) -> dict:
        commands = ordered_spec_commands(polluters, victim["victim_id"])
        command_strings = {arm: format_command(commands[arm]) for arm in ("A", "B", "C")}
        runs: dict[str, dict[str, list]] = {"base": {}, "head": {}}
        exec_by_arm: dict[str, dict[str, list]] = {"base": {}, "head": {}}
        sides = {"base": self.base, "head": self.head}
        for arm in ("A", "B", "C"):
            body = commands[arm][1:]
            intended = ordered_ids(arm, polluters, victim["victim_id"])
            for rep in range(1, REPS + 1):

                def run_one(
                    side_name: str,
                    arm: str = arm,
                    rep: int = rep,
                    body: list[str] = body,
                    intended: list[str] = intended,
                ) -> dict:
                    side = sides[side_name]
                    stem = f"cause-{index}-{side['sha7']}-{arm}-r{rep}"
                    return self._arm(side_name, side, body, intended, stem, victim["victim_id"])

                with ThreadPoolExecutor(max_workers=2) as pool:
                    base_outcome = pool.submit(run_one, "base").result()
                    head_outcome = pool.submit(run_one, "head").result()
                runs["base"].setdefault(arm, []).append(base_outcome)
                runs["head"].setdefault(arm, []).append(head_outcome)
        for side_name in ("base", "head"):
            for arm in ("A", "B", "C"):
                exec_by_arm.setdefault(side_name, {})[arm] = [rep["exec_argv"] for rep in runs[side_name][arm]]
        judged = judge(runs["base"], runs["head"], victim["victim_id"], polluters)
        seeds = sorted({int(item["seed"]) for item in provenance_rows})
        rounds = [{"seed": int(item["seed"]), "round": int(item["round"])} for item in provenance_rows]
        provenance = {
            "seed": seeds[0],
            "seeds_failed": seeds,
            "s0": {"seed": seeds[0], "source": f"s0/base-seed-{seeds[0]:02d}.json"},
            "seeds": seeds,
            "rounds": rounds,
            "candidate_source": "s6/residual-seeds.json",
        }
        versions = self.versions
        meta = {
            "git_sha": self.git_sha,
            "repo": self.base["repo"],
            "base_commit": self.base["commit"],
            "head_commit": self.head["commit"],
            "base_tarball": self.base["tarball_sha256"],
            "head_tarball": self.head["tarball_sha256"],
            "image_id": self.image_id,
            "image": self.image,
            "ruby": versions.get("ruby", ""),
            "bundler": versions.get("bundler", ""),
            "rspec_core": versions.get("rspec_core", ""),
            "base_lock": self.base["gemfile_lock_sha256"],
            "head_lock": self.head["gemfile_lock_sha256"],
            "seed": seeds[0],
            "base_tree": self.base["tree"],
            "head_tree": self.head["tree"],
        }
        cert = _build_cert(
            meta,
            {"id": victim["victim_id"], "location": victim["victim_location"]},
            polluters,
            command_strings,
            command_strings["A"],
            runs,
            judged,
            exec_by_arm,
        )
        cert["kind"] = "ORDER-DEPENDENT"
        cert["seed_provenance"] = provenance
        cert["tool"]["version"] = __version__
        cert["execution"] = {
            "mode": "docker",
            "image": self.image,
            "trees": {"base": str(self.base["tree"]), "head": str(self.head["tree"])},
            "timeout_s": 240,
            "bundler": self.bundler_version,
            "extra_mounts": list(self.mounts),
            "extra_env": [list(item) for item in self.env],
            "clear_status": True,
            "exec_argv": exec_by_arm,
        }
        errors = validate_certificate(cert)
        if errors:
            raise SystemExit("cause certificate failed schema validation: " + "; ".join(errors))
        cert_path = self.out / f"cause-{index}.json"
        cert_path.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
        replay_path = self.out / f"replay-{index}.sh"
        write_replay_script(replay_path, cert_path, REPO_ROOT)
        self.log.write(f"S9 cause-{index} {judged['label']} seeds={seeds}", echo=True)
        return {
            "victim_id": victim["victim_id"],
            "polluter_ids": list(polluters),
            "verdicts": judged["verdicts"],
            "plain_retry_verdict": judged["plain_retry_verdict"],
            "label": judged["label"],
            "seed_provenance": {
                "seeds": seeds,
                "rounds": rounds,
                "candidate_source": "s6/residual-seeds.json",
            },
            "replay": replay_path.name,
            "cert": cert_path.name,
        }

    def _groups(self, victims: list[dict], results: list[dict]) -> list[tuple[dict, list[str], list[dict]]]:
        by_id = {victim["victim_id"]: victim for victim in victims}
        order = {victim["victim_id"]: index for index, victim in enumerate(victims)}
        grouped: dict[tuple[str, tuple[str, ...]], list[dict]] = {}
        for result in results:
            known = tuple(norm_id(item) for item in result.get("known_polluter_ids") or [])
            for round_info in result.get("rounds") or []:
                ids = [item for item in round_info.get("set") or [] if isinstance(item, str)]
                if not ids:
                    continue
                if tuple(norm_id(item) for item in ids) == known:
                    continue
                key = (result["victim_id"], tuple(ids))
                grouped.setdefault(key, []).append({"seed": result["seed"], "round": round_info["round"]})
        items = sorted(grouped.items(), key=lambda item: (order.get(item[0][0], 10**9), item[0][1]))
        return [(by_id[victim_id], list(ids), rows) for (victim_id, ids), rows in items]

    def _write_victim_certs(self, victims: list[dict], entries: list[dict]) -> None:
        by_victim: dict[str, list[dict]] = {}
        for entry in entries:
            by_victim.setdefault(entry["victim_id"], []).append(entry)
        for path in sorted(self.prior.glob("cert-*.json")):
            cert = json.loads(path.read_text(encoding="utf-8"))
            victim_id = cert.get("victim_id")
            if (
                cert.get("kind") == "ORDER-DEPENDENT"
                and cert.get("label") == "CERTIFIED"
                and isinstance(victim_id, str)
            ):
                cert["cause_set"] = by_victim.get(victim_id, [])
            errors = validate_certificate(cert)
            if errors:
                raise SystemExit(f"{path.name} failed schema validation: " + "; ".join(errors))
            dest = self.out / path.name
            dest.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
        self.log.write("updated certificates written", echo=True)

    def _replay(self) -> None:
        self.log.section("replay")
        lines = []
        scripts = sorted(self.out.glob("replay-*.sh"), key=lambda path: int(path.stem.split("-", 1)[1]))
        for label, key in (("first", "first_replay_exit"), ("second", "replay_exit")):
            for script in scripts:
                lines.append(f"===== {label} {script.name} =====")
                started = time.monotonic()
                proc = subprocess.run(["bash", str(script)], cwd=REPO_ROOT, capture_output=True, check=False)
                stdout = proc.stdout.decode("utf-8", errors="replace")
                stderr = proc.stderr.decode("utf-8", errors="replace")
                if stdout:
                    lines.append(stdout.rstrip("\n"))
                if stderr:
                    lines.append(stderr.rstrip("\n"))
                lines.append(f"{key}={proc.returncode}")
                elapsed = time.monotonic() - started
                self.log.write(
                    f"replay {label} {script.name} exit={proc.returncode} elapsed_s={elapsed:.3f}",
                    echo=True,
                )
        (self.out / "replay-check.log").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _log_mismatches(self, cert: dict) -> list[str]:
        mismatches = []
        runs = cert.get("runs") or {}
        if not isinstance(runs, dict):
            return ["runs missing"]
        for side, block in runs.items():
            if not isinstance(block, dict):
                continue
            for arm, reps in block.items():
                if not isinstance(reps, list):
                    continue
                for run in reps:
                    if not isinstance(run, dict):
                        continue
                    raw = run.get("log")
                    if not isinstance(raw, str) or not raw:
                        mismatches.append(f"{side} {arm} missing log")
                        continue
                    path = Path(raw)
                    if not path.is_absolute():
                        path = REPO_ROOT / path
                    if not path.is_file():
                        mismatches.append(f"missing {raw}")
                        continue
                    digest = sha256_file(path)
                    if digest != run.get("log_sha256"):
                        mismatches.append(f"sha {raw}")
        return mismatches

    def _rejudge(self) -> dict:
        self.log.section("S10 rejudge prior")
        summary_path = self.prior / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        lines = [f"prior {_rel(self.prior)}", f"summary_exit_ok {summary.get('exit_ok')}"]
        rows = []
        mismatches: list[str] = []
        unchanged = True
        for row in summary.get("rows") or []:
            cert_name = row["cert"]
            cert = json.loads((self.prior / cert_name).read_text(encoding="utf-8"))
            recomputed = recompute_certificate_label(cert)
            stored = cert.get("label")
            same = recomputed == stored == row.get("label")
            if not same:
                unchanged = False
            bad = self._log_mismatches(cert)
            mismatches.extend(f"{cert_name} {item}" for item in bad)
            lines.append(f"{cert_name} stored={stored} summary={row.get('label')} recomputed={recomputed}")
            rows.append(
                {
                    "id": row.get("id"),
                    "label": recomputed,
                    "reason": row.get("reason") or cert.get("reason") or "",
                    "base": row.get("base"),
                    "head": row.get("head"),
                }
            )
        exit_ok = classification_exit_ok(rows) and summary.get("exit_ok") is True
        lines.append(f"unchanged {unchanged}")
        lines.append(f"exit_ok {exit_ok}")
        lines.append(f"log_mismatches {len(mismatches)}")
        lines.extend(mismatches)
        dest = self.out / "s10" / "rejudge.log"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.log.write(f"S10 unchanged={unchanged} exit_ok={exit_ok} log_mismatches={len(mismatches)}", echo=True)
        return {
            "unchanged": unchanged and not mismatches,
            "exit_ok": exit_ok,
            "rows": rows,
            "log": _rel(dest),
        }

    def _check_summary(self, victims: list[dict], results: list[dict], entries: list[dict], rejudge: dict) -> None:
        lines = [
            "# G2.2 residual seeds and cause sets",
            "",
            f"Prior evidence: `{_rel(self.prior)}`.",
            "S6 list: `s6/residual-seeds.json`.",
            "Probe logs: `s7/` and `s8/`. Arm logs: `s9/`.",
            "Prior rejudge: `s10/rejudge.log`.",
            "",
            "| victim | seed | status | rounds |",
            "| --- | --- | --- | --- |",
        ]
        order = {victim["victim_id"]: index for index, victim in enumerate(victims)}
        for result in sorted(results, key=lambda item: (order.get(item["victim_id"], 10**9), item["seed"])):
            round_bits = []
            for round_info in result["rounds"]:
                shown = ",".join(round_info["set"]) if round_info["set"] else "-"
                round_bits.append(f"r{round_info['round']}:{shown}")
            lines.append(
                f"| {result['victim_id']} | {result['seed']} | {result['status']} | {'; '.join(round_bits)} |"
            )
        lines.extend(
            [
                "",
                "| polluter ids | label | seeds | replay |",
                "| --- | --- | --- | --- |",
            ]
        )
        for entry in entries:
            seeds = ",".join(str(seed) for seed in entry["seed_provenance"]["seeds"])
            lines.append(
                f"| {' '.join(entry['polluter_ids'])} | {entry['label']} | {seeds} | {entry['replay']} |"
            )
        lines.extend(["", "## Skeptic pass", ""])
        points = _skeptic_points(SKEPTIC_PATH.read_text(encoding="utf-8"))
        for index, point in enumerate(points):
            lines.append(point)
            lines.append("")
            if index < len(SKEPTIC_ANSWERS):
                lines.append(SKEPTIC_ANSWERS[index])
                lines.append("")
        if len(points) != len(SKEPTIC_ANSWERS):
            lines.append(f"Skeptic points and answers differ in length ({len(points)} and {len(SKEPTIC_ANSWERS)}).")
            lines.append("")
        lines.extend(
            [
                "## Rejudge",
                "",
                "Labels were recomputed from the prior certificates and compared with the stored labels.",
                "Log sha256 values were checked against the files named by those certificates.",
                "The prior directory was not rewritten.",
                "",
                f"unchanged: {rejudge['unchanged']}",
                f"exit_ok: {rejudge['exit_ok']}",
                "",
            ]
        )
        (self.out / "check-summary.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_g22(
        self,
        victims: list[dict],
        results: list[dict],
        entries: list[dict],
        rejudge: dict,
        acceptance: dict[str, bool],
        go: bool,
        pattern: str,
        tool_code: int,
        tool_out: str,
        inv_code: int,
        inv_out: str,
    ) -> None:
        versions = self.versions
        ruby = versions.get("ruby", "")
        if ruby and not ruby.startswith("ruby "):
            ruby = "ruby " + ruby
        lines = [
            f"image_id {self.image_id}",
            f"image_digest {self.image_digest}",
            f"docker_server {self.server}",
            ruby,
            versions.get("bundler", ""),
            f"rspec-core {versions.get('rspec_core', '')}",
            f"wall_s {round(time.monotonic() - self.started, 3)}",
            "",
        ]
        for victim in victims:
            seeds = [item["seed"] for item in victim["residual_seeds"]]
            lines.append(format_residual_line(victim["victim_id"], seeds))
        order = {victim["victim_id"]: index for index, victim in enumerate(victims)}
        for result in sorted(results, key=lambda item: (order.get(item["victim_id"], 10**9), item["seed"])):
            for round_info in result["rounds"]:
                lines.append(
                    format_seed_line(
                        int(result["seed"]),
                        int(round_info["round"]),
                        list(round_info["set"]),
                        len(round_info["probes"]),
                        str(result["status"]),
                    )
                )
        for entry in entries:
            lines.append(format_polluter_line(entry["polluter_ids"], entry["label"]))
        if rejudge["unchanged"] and rejudge["exit_ok"]:
            lines.append(G2_OK_LINE)
        else:
            lines.append(f"G2_LABELS_UNCHANGED {rejudge['unchanged']}")
            lines.append(f"EXIT_OK {rejudge['exit_ok']}")
        lines.extend(
            [
                f"ACCEPTANCE_1 {acceptance['1']}",
                f"ACCEPTANCE_2 {acceptance['2']}",
                f"ACCEPTANCE_3 {acceptance['3']}",
                f"ACCEPTANCE_4 {acceptance['4']}",
                f"GO {go}",
                "===== acceptance 1 grep =====",
                f"+ grep -RInE {pattern!r} tools/certify_rspec",
                tool_out.rstrip("\n"),
                f"grep_exit={tool_code}",
                f"+ grep -nE {pattern!r} {_rel(self.out / 'invocation.txt')}",
                inv_out.rstrip("\n"),
                f"grep_exit={inv_code}",
            ]
        )
        (self.out / "g2-2.log").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(self) -> int:
        self.out.mkdir(parents=True, exist_ok=True)
        for name in ("s6", "s7", "s8", "s9", "s10"):
            (self.out / name).mkdir(parents=True, exist_ok=True)
        invocation = shlex.join(sys.argv)
        (self.out / "invocation.txt").write_text(invocation + "\n", encoding="utf-8")
        self.git_sha = _git_sha(REPO_ROOT)
        self.log.section("certify_rspec cause")
        self.log.write("argv " + invocation, echo=True)
        self.log.write(f"suite {self.suite}", echo=True)
        self.log.write(f"prior {_rel(self.prior)}", echo=True)
        self.log.write(f"git_sha {self.git_sha}", echo=True)
        self.image_id = _image_id(self.image)
        self.image_digest = _image_digest(self.image)
        self.server = _docker_server_version()
        self.log.write(f"image {self.image}", echo=True)
        self.log.write(f"image_id {self.image_id}", echo=True)
        self.log.write(f"image_digest {self.image_digest}", echo=True)
        self.log.write(f"docker_server {self.server}", echo=True)
        prior_summary = json.loads((self.prior / "summary.json").read_text(encoding="utf-8"))
        if self.image_digest != prior_summary.get("image_digest"):
            raise SystemExit(
                f"image digest {self.image_digest} != prior {prior_summary.get('image_digest')}"
            )
        if self.image_id != prior_summary.get("image_id"):
            raise SystemExit(f"image id {self.image_id} != prior {prior_summary.get('image_id')}")
        expected = _expected_tarballs(RECON_AXN.read_text(encoding="utf-8"))
        repo = repo_from_url(self.args.base_url)
        if repo_from_url(self.args.head_url) != repo:
            raise SystemExit("base and head repos differ")
        self._side_env()
        self.base = self._prepare(self.args.base_url, expected["base.tgz"])
        self.head = self._prepare(self.args.head_url, expected["merge.tgz"])
        self.base["repo"] = repo
        self.head["repo"] = repo
        if self.base["gemfile_lock_sha256"] != self.head["gemfile_lock_sha256"]:
            raise SystemExit("base and head Gemfile.lock hashes differ")
        if self.base["bundler"] != self.head["bundler"]:
            raise SystemExit("base and head BUNDLED WITH versions differ")
        self.bundler_version = self.base["bundler"]
        self.versions = self._version_probe(self.base)
        head_versions = self._version_probe(self.head)
        if head_versions != self.versions:
            self.log.write(
                "version strings differ: " + json.dumps({"base": self.versions, "head": head_versions}),
                echo=True,
            )
        self.log.section("S6 residual seeds")
        victims = self._certified_victims()
        records = self._residual(victims)
        self.log.section("S7 S8 cause search")
        for tree in self._worker_trees("base", self.base):
            self.base_trees.put(tree)
        results: list[dict] = []
        if records:
            with ThreadPoolExecutor(max_workers=self.jobs) as pool:
                results = list(pool.map(self._search_one, records))
        self.log.section("S9 certify new sets")
        entries = []
        for index, (victim, polluters, rows) in enumerate(self._groups(victims, results), start=1):
            entries.append(self._certify_group(index, victim, polluters, rows))
        self._write_victim_certs(victims, entries)
        self._replay()
        rejudge = self._rejudge()
        spec_text = SPEC_PATH.read_text(encoding="utf-8")
        pattern = _acceptance_pattern(spec_text)
        token = _acceptance_token(spec_text)
        tool_code, tool_out = _grep(pattern, REPO_ROOT / "tools" / "certify_rspec", True)
        inv_code, inv_out = _grep(pattern, self.out / "invocation.txt", False)
        acceptance_1 = tool_code == 1 and inv_code == 1 and tool_out == "" and inv_out == ""
        acceptance_2 = any(
            entry["label"] == "CERTIFIED"
            and victim_token_matches(entry["victim_id"], token)
            and entry["seed_provenance"]["seeds"]
            for entry in entries
        )
        acceptance_3 = True
        if len(results) != len(records):
            acceptance_3 = False
        for result in results:
            if result.get("status") not in SETTLED_SEED:
                acceptance_3 = False
            probes = [probe for round_info in result.get("rounds") or [] for probe in round_info.get("probes") or []]
            if not probes:
                acceptance_3 = False
            for probe in probes:
                if not (REPO_ROOT / str(probe.get("log") or "")).is_file():
                    acceptance_3 = False
        replay_text = (self.out / "replay-check.log").read_text(encoding="utf-8") if (self.out / "replay-check.log").is_file() else ""
        first = re.findall(r"^first_replay_exit=(\d+)$", replay_text, re.M)
        second = re.findall(r"^replay_exit=(\d+)$", replay_text, re.M)
        scripts = list(self.out.glob("replay-*.sh"))
        replay_ok = (
            len(scripts) == len(first) == len(second)
            and all(item == "0" for item in first)
            and all(item == "0" for item in second)
        )
        self.log.section("pytest")
        pytest = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        (self.out / "pytest.log").write_text(pytest.stdout + pytest.stderr, encoding="utf-8")
        self.log.write(pytest.stdout + pytest.stderr, echo=False)
        self.log.write(f"pytest_exit={pytest.returncode}", echo=True)
        acceptance_4 = replay_ok and rejudge["unchanged"] and rejudge["exit_ok"] and pytest.returncode == 0
        acceptance = {"1": acceptance_1, "2": acceptance_2, "3": acceptance_3, "4": acceptance_4}
        go = all(acceptance.values())
        summary = {
            "prior": _rel(self.prior),
            "base_commit": self.base["commit"],
            "head_commit": self.head["commit"],
            "base_tarball_sha256": self.base["tarball_sha256"],
            "head_tarball_sha256": self.head["tarball_sha256"],
            "image_id": self.image_id,
            "image_digest": self.image_digest,
            "docker_server": self.server,
            "ruby": self.versions.get("ruby", ""),
            "bundler": self.versions.get("bundler", ""),
            "rspec_core": self.versions.get("rspec_core", ""),
            "git_sha": self.git_sha,
            "residual_seeds": [
                {
                    "victim_id": result["victim_id"],
                    "seed": result["seed"],
                    "status": result["status"],
                    "rounds": [
                        {
                            "round": round_info["round"],
                            "set": round_info["set"],
                            "probes": len(round_info["probes"]),
                            "round_status": round_info.get("round_status"),
                        }
                        for round_info in result["rounds"]
                    ],
                }
                for result in results
            ],
            "cause_set": entries,
            "g2_labels_unchanged": rejudge["unchanged"],
            "g2_exit_ok": rejudge["exit_ok"],
            "acceptance": acceptance,
            "go": go,
            "wall_s": round(time.monotonic() - self.started, 3),
        }
        (self.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        self._check_summary(victims, results, entries, rejudge)
        self._write_g22(
            victims,
            results,
            entries,
            rejudge,
            acceptance,
            go,
            pattern,
            tool_code,
            tool_out,
            inv_code,
            inv_out,
        )
        self.log.write(f"GO={go} wall_s={summary['wall_s']}", echo=True)
        self.log.close()
        _write_sums(self.out)
        return 0 if go else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.certify_rspec cause")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--head-url", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--prior", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cache", default="/tmp/flakecert-g2-1019/probe")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args(argv)
    return CauseRun(args).run()
