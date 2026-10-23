"""S0-S5 seed discovery and BRITTLE enabler search.

The CLI takes base and head tarball URLs, a suite path, and an image.
It does not take a victim, a polluter, or a seed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tools.certify_rspec import __version__
from tools.certify_rspec.brittle import brittle_verdict
from tools.certify_rspec.certificate import validate_certificate
from tools.certify_rspec.classify import (
    BRITTLE,
    ORDER_DEPENDENT,
    OTHER,
    alone_passed,
    classify_discovered,
    predecessors,
)
from tools.certify_rspec.commands import IDS_ENV, format_command, spec_commands
from tools.certify_rspec.order_guard import INVALID_ORDER, order_guard
from tools.certify_rspec.ddmin import DdminError, one_minimal
from tools.certify_rspec.exit_rule import classification_exit_ok
from tools.certify_rspec.parse_rspec import example_location, norm_id, parse_bisect, parse_outcome, polluter_ids
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
    _slug,
)
from tools.certify_rspec.replay import write_replay_script
from tools.certify_rspec.runner import docker_bash
from tools.certify_rspec.seeds import primary_seed, union_failing
from tools.certify_rspec.sources import (
    commit_from_url,
    ensure_tarball,
    ensure_tree,
    repo_from_url,
    sha256_file,
)
from tools.certify_rspec.verdict import judge

SPEC_PATH = REPO_ROOT / "inputs" / "dryrun-2026-10-19-g2" / "SPEC-certify-rspec-G2.md"
RECON_LOG = REPO_ROOT / "inputs" / "dryrun-2026-10-19-g2" / "reverse" / "recon-axn.log"
G1_SUMMARY = REPO_ROOT / "evidence" / "certify-rspec-g1" / "summary.json"
SEED_MIN = 1
SEED_MAX = 30
REPS = 3
PATH_VALUE = "/gems/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def example_stem(location: str, ident: str) -> str:
    """File stem unique per example id.

    Two examples can share one file and line when a shared group is included
    more than once. The id hash keeps their logs apart.
    """
    digest = hashlib.sha256(ident.encode("utf-8")).hexdigest()[:8]
    return _slug(f"{location}-{digest}")


def _bundled_with(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "BUNDLED WITH" and index + 1 < len(lines):
            version = lines[index + 1].strip()
            if version:
                return version
    raise SystemExit("Gemfile.lock has no BUNDLED WITH")


def _expected_tarballs(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    in_block = False
    for line in text.splitlines():
        if line.startswith("## sha256"):
            in_block = True
            continue
        if in_block and line.startswith("## "):
            break
        if not in_block or not line.strip():
            continue
        digest, name = line.split()
        found[name] = digest
    for name in ("base.tgz", "merge.tgz"):
        if name not in found:
            raise SystemExit(f"recon log has no sha256 for {name}")
    return found


def _acceptance_pattern(spec_text: str) -> str:
    match = re.search(r"grep -RInE '([^']+)'", spec_text)
    if not match:
        raise SystemExit("spec has no acceptance grep pattern")
    return match.group(1)


def _image_digest(image: str) -> str:
    proc = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{index .RepoDigests 0}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip()


def _exit_code(text: str) -> int | None:
    found = re.findall(r"^docker_exit=(\d+)$", text, re.M)
    if not found:
        return None
    return int(found[-1])


def _load_examples(path: Path) -> list[dict] | None:
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    examples = data.get("examples")
    if not isinstance(examples, list):
        return None
    return examples


def _failing_ids(examples: list[dict]) -> list[str]:
    return [example["id"] for example in examples if example.get("status") == "failed" and example.get("id")]


def _passed_ids(examples: list[dict]) -> set[str]:
    return {example["id"] for example in examples if example.get("status") == "passed" and example.get("id")}


def _example_index(examples: list[dict], ident: str) -> int | None:
    target = norm_id(ident)
    for index, example in enumerate(examples):
        found = example.get("id")
        if found and norm_id(str(found)) == target:
            return index
    return None


def _victim_status(examples: list[dict], victim_id: str) -> str | None:
    target = norm_id(victim_id)
    for example in examples:
        ident = example.get("id")
        if ident and norm_id(str(ident)) == target:
            status = example.get("status")
            return status if isinstance(status, str) else None
    return None


def _ids_before(examples: list[dict], victim_id: str) -> list[str]:
    target = norm_id(victim_id)
    index = None
    for position, example in enumerate(examples):
        ident = example.get("id")
        if ident and norm_id(str(ident)) == target:
            index = position
            break
    if index is None:
        raise KeyError(victim_id)
    chosen = []
    for example in examples[:index]:
        ident = example.get("id")
        if ident:
            chosen.append(ident)
    return chosen


def _file_of(identifier: str) -> str:
    text = identifier[2:] if identifier.startswith("./") else identifier
    text = text.split("[", 1)[0]
    leaf = text.rsplit("/", 1)[-1]
    if ":" in leaf:
        text = text.rsplit(":", 1)[0]
    return text


def _differing_spec_files(base: Path, head: Path) -> list[str]:
    def listing(root: Path) -> dict[str, str]:
        spec = root / "spec"
        found = {}
        if not spec.is_dir():
            return found
        for path in spec.rglob("*"):
            if path.is_file():
                found[path.relative_to(root).as_posix()] = sha256_file(path)
        return found

    base_files = listing(base)
    head_files = listing(head)
    names = sorted(set(base_files) | set(head_files))
    return [name for name in names if base_files.get(name) != head_files.get(name)]


def _grep(pattern: str, target: Path, recursive: bool) -> tuple[int, str]:
    argv = ["grep", "-RInE" if recursive else "-nE", pattern, str(target)]
    proc = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout


def _write_sums(out: Path) -> None:
    rels = []
    for path in out.rglob("*"):
        if path.is_file() and path.name != "SHA256SUMS":
            rels.append("./" + path.relative_to(out).as_posix())
    lines = []
    for rel in sorted(rels):
        lines.append(f"{sha256_file(out / rel[2:])}  {rel}")
    (out / "SHA256SUMS").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _summary_md(rows: list[dict]) -> str:
    lines = [
        "# PR check",
        "",
        "One line per id in the seed-search union. OD verdicts use arm A.",
        "",
        "| id | class | label | detail |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {id} | {kind} | {label} | {detail} |".format(
                id=row["location"],
                kind=row.get("classification", ""),
                label=row.get("label", ""),
                detail=row.get("detail", ""),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _skeptic() -> str:
    lines = [
        "## Skeptic pass",
        "",
        "What else could move a verdict:",
        "- Seeds searched are 1..30. An id that never fails in that range is not shown to be order-safe.",
        "- The primary seed is the qualifying seed with the most base failures. Ties take the smallest seed. A different seed can fail a different set.",
        "- An order-dependent certificate names one sufficient polluter set from rspec --bisect on the first seed where that id failed. Another sufficient set would not by itself change the cross-commit label.",
        "- Bisect keeps one sufficient set when several exist. The certificate claims sufficiency of the recorded set.",
        "- A brittle certificate names a 1-minimal enabler under defined order. Another sufficient set can exist. It does not claim to be the set a defined-order CI run relied on.",
        "- The enabler search uses the predecessor ids from this base defined-order run. A different definition order would change that list.",
        "- This run is Ruby 3.3 only. A pass here does not speak for the other CI Rubies.",
        "- Alone results that are not 3/3 stay OTHER and are not a certificate.",
        "- One order-dependent rep whose failed ids include a polluter id rejects that certificate.",
        "- The message line is not part of the signature.",
        "- An order-dependent id can be NOT_FIXED at base and FIXED at head and still stay UNRESOLVED when arm C does not pass 3/3 at both commits. Arm C passing at both commits would move that id to CERTIFIED. The same victim-only failure on arm C at head would move it toward CONTROL.",
        "- Arm C requires tools/certify_rspec/ordering.rb and names the victim id before the polluter ids in ENV ids. The JSON example order is compared with that list. A mismatch is INVALID_ORDER and is not a pass or a fail, so the verdict cannot use it.",
        "- At 5603142, arm C passed --order defined and listed the victim first. For two ids the JSON still ran the polluter id first. Those runs are ARM_C_INVALID_ORDER_BEFORE and are not certificates. A later arm C that matches the named order is a new measurement.",
        "- A full-suite seed can run the victim before the recorded polluter and still fail, because other examples ran earlier. s0/victim-first-crosscheck.txt lists those seeds from the existing base json. It is not the isolated arm C pair.",
        "- An id that never fails in the searched seeds is absent from the union. Absence is not evidence that the diff did nothing.",
        "- Finding an enabler by search is not a market-novelty claim. No prior-art search was done.",
        "- Star count on the subject repo is not evidence of demand. This run is a method proof.",
        "",
    ]
    return "\n".join(lines)


class Discovery:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.out = Path(args.out)
        self.cache = Path(args.cache)
        self.log = RunLog(self.out / "run.log")
        self.started = time.monotonic()
        self.image = args.image
        self.suite = args.suite
        self.bundler = ""
        self.mounts: list[str] = []
        self.env: list[tuple[str, str]] = []
        self.locations: dict[str, str] = {}
        self.base: dict = {}
        self.head: dict = {}
        self.versions: dict[str, str] = {}
        self.image_id = ""
        self.image_digest = ""
        self.server = ""
        self.invalid_before = 0
        self.invalid_after = 0
        self.prior_labels: dict[str, str] = {}
        self.label_changes: list[str] = []

    def _side_env(self) -> tuple[list[str], list[tuple[str, str]]]:
        bundle = self.cache / "bundle"
        gems = self.cache / "gems"
        bundle.mkdir(parents=True, exist_ok=True)
        gems.mkdir(parents=True, exist_ok=True)
        mounts = ["-v", f"{bundle.resolve()}:/bundle", "-v", f"{gems.resolve()}:/gems"]
        env = [
            ("GEM_HOME", "/gems"),
            ("PATH", PATH_VALUE),
            ("BUNDLE_PATH", "/bundle"),
            ("BUNDLE_SILENCE_ROOT_WARNING", "1"),
        ]
        return mounts, env

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

    def _bundle(self, side: dict) -> None:
        version = side["bundler"]
        script = "\n".join(
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
        code, text, elapsed = docker_bash(
            self.image,
            side["tree"],
            script,
            1800,
            self.mounts,
            self.env,
        )
        self.log.write(text, echo=False)
        self.log.write(f"bundle_install_exit={code} elapsed_s={elapsed:.3f}", echo=True)
        if code != 0:
            raise SystemExit(f"bundle install failed for {side['commit']}")
        side["versions"] = _parse_versions(text)

    def _remember(self, examples: list[dict], side_name: str) -> None:
        # Base and head can put the same id on different lines. Log stems use
        # that line, so the first writer must be base or a rerun looks for a
        # different file. Head still runs; it does not name the example.
        if side_name != "base":
            return
        for example in examples:
            ident = example.get("id")
            if ident and ident not in self.locations:
                self.locations[ident] = example_location(example)

    def _complete_log(self, path: Path) -> str | None:
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        code = _exit_code(text)
        if code is None or code == 124:
            return None
        return text

    def _annotate_order(
        self,
        outcome: dict,
        examples: list[dict],
        intended: list[str] | None,
        run_env: list[tuple[str, str]] | None,
        log_path: Path,
    ) -> None:
        if run_env is not None:
            outcome["extra_env"] = [list(item) for item in run_env]
        if intended is None:
            return
        status = order_guard(examples, intended)
        outcome["order_status"] = status
        if status == INVALID_ORDER:
            self.log.write(
                f"INVALID_ORDER {log_path.name} order={outcome.get('order')} intended={intended}",
                echo=True,
            )

    def _execute(
        self,
        side_name: str,
        side: dict,
        rspec_args: list[str],
        log_path: Path,
        json_path: Path | None,
        timeout: int,
        logical: str,
        victim_id: str | None,
        intended: list[str] | None = None,
        run_env: list[tuple[str, str]] | None = None,
    ) -> tuple[dict, list[dict]]:
        status = side["tree"] / ".rspec_status"
        env = self.env if run_env is None else run_env
        cached = self._complete_log(log_path)
        if cached is not None:
            first = cached.splitlines()[0] if cached.splitlines() else ""
            if first != f"+ logical={logical}":
                cached = None
        examples = _load_examples(json_path) if json_path is not None else None
        if cached is not None and (json_path is None or examples is not None):
            code = _exit_code(cached) or 0
            outcome = parse_outcome(cached, code, json_path)
            outcome["log_sha256"] = _sha256_text(cached)
            outcome["log"] = str(log_path)
            outcome["exec_argv"] = _exec_argv(rspec_args, json_path.name if json_path is not None else None)
            outcome["tree_side"] = side_name
            if json_path is not None:
                outcome["json_host"] = str(json_path)
            if victim_id and examples is not None:
                outcome["victim_status"] = _victim_status(examples, victim_id)
            self._annotate_order(outcome, examples or [], intended, run_env, log_path)
            self.log.write(f"resume {log_path.name} docker_exit={code}", echo=True)
            if examples is None:
                examples = []
            self._remember(examples, side_name)
            return outcome, examples
        if status.exists():
            status.unlink()
        json_name = json_path.name if json_path is not None else None
        argv = _exec_argv(rspec_args, json_name)
        last_error = "no json"
        for attempt in (1, 2):
            outcome = _run_rspec(
                self.log,
                self.image,
                side["tree"],
                argv,
                log_path,
                json_path,
                timeout,
                logical,
                bundler=self.bundler,
                extra_mounts=self.mounts,
                extra_env=env,
            )
            outcome["exec_argv"] = argv
            outcome["tree_side"] = side_name
            if json_path is not None:
                outcome["json_host"] = str(json_path)
            examples = _load_examples(json_path) if json_path is not None else []
            timed_out = _exit_code(log_path.read_text(encoding="utf-8", errors="replace")) == 124
            if not timed_out and (json_path is None or examples is not None):
                if victim_id and examples is not None:
                    outcome["victim_status"] = _victim_status(examples, victim_id)
                self._annotate_order(outcome, examples or [], intended, run_env, log_path)
                if examples:
                    self._remember(examples, side_name)
                return outcome, examples or []
            last_error = "timed out" if timed_out else f"attempt {attempt} produced no examples"
            self.log.write(f"retry {log_path.name} {last_error}", echo=True)
            if log_path.exists():
                log_path.unlink()
            if json_path is not None and json_path.exists():
                json_path.unlink()
        raise SystemExit(f"{logical} failed twice: {last_error}")

    def _suite(self, side_name: str, side: dict, stem: str, order_args: list[str], timeout: int) -> list[dict]:
        logical = format_command(["rspec", self.suite, *order_args])
        log_path = self.out / "s0" / f"{side_name}-{stem}.log"
        json_path = self.out / "s0" / f"{side_name}-{stem}.json"
        _outcome, examples = self._execute(
            side_name,
            side,
            [self.suite, *order_args],
            log_path,
            json_path,
            timeout,
            logical,
            None,
        )
        failing = _failing_ids(examples)
        self.log.write(
            f"S0 {side_name} {stem} examples={len(examples)} failing={len(failing)}",
            echo=True,
        )
        return examples

    def _pair(self, stem: str, order_args: list[str], timeout: int) -> tuple[list[dict], list[dict]]:
        with ThreadPoolExecutor(max_workers=2) as pool:
            base_future = pool.submit(self._suite, "base", self.base, stem, order_args, timeout)
            head_future = pool.submit(self._suite, "head", self.head, stem, order_args, timeout)
            return base_future.result(), head_future.result()

    def _alone(self, side_name: str, side: dict, victim_id: str, directory: str, stem: str) -> dict:
        logical = format_command(["rspec", victim_id])
        log_path = self.out / directory / f"{stem}.log"
        json_path = self.out / directory / f"{stem}.json"
        outcome, _examples = self._execute(
            side_name,
            side,
            [victim_id],
            log_path,
            json_path,
            240,
            logical,
            victim_id,
            intended=[victim_id],
        )
        return outcome

    def _enabled(self, side: dict, enablers: list[str], victim_id: str, stem: str) -> dict:
        args = ["--order", "defined", *enablers, victim_id]
        logical = format_command(["rspec", *args])
        log_path = self.out / "s4" / f"{stem}.log"
        json_path = self.out / "s4" / f"{stem}.json"
        outcome, _examples = self._execute(
            "base",
            side,
            args,
            log_path,
            json_path,
            900,
            logical,
            victim_id,
            intended=[*enablers, victim_id],
        )
        return outcome

    def _provenance(self, seed: int, record: dict, seeds_failed: list[int]) -> dict:
        return {"seed": seed, "seeds_failed": list(seeds_failed), "s0": record}

    def _execution(self, exec_by_arm: dict, timeout: int) -> dict:
        return {
            "mode": "docker",
            "image": self.image,
            "trees": {"base": str(self.base["tree"]), "head": str(self.head["tree"])},
            "timeout_s": timeout,
            "bundler": self.bundler,
            "extra_mounts": list(self.mounts),
            "extra_env": [list(item) for item in self.env],
            "clear_status": True,
            "exec_argv": exec_by_arm,
        }

    def _meta(self, seed: int) -> dict:
        versions = self.base.get("versions") or self.versions
        return {
            "git_sha": _git_sha(REPO_ROOT),
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
            "seed": seed,
            "base_tree": self.base["tree"],
            "head_tree": self.head["tree"],
        }

    def _write_cert(self, index: int, cert: dict) -> Path:
        errors = validate_certificate(cert)
        if errors:
            self.log.write("certificate schema errors: " + "; ".join(errors), echo=True)
            raise SystemExit("certificate failed schema validation")
        path = self.out / f"cert-{index}.json"
        path.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
        write_replay_script(self.out / f"replay-{index}.sh", path, REPO_ROOT)
        return path

    def _od_reason(self, ident: str, label: str) -> str:
        if label == "REJECTED":
            return "polluter id failed"
        if label == "CERTIFIED" and self.prior_labels.get(ident) == "UNRESOLVED":
            return "arm C ran the named victim-then-polluter order and passed 3/3 at base and head"
        return ""

    def _remember_prior_labels(self) -> None:
        path = self.out / "summary.json"
        if not path.is_file():
            return
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        for row in prior.get("rows") or []:
            ident = row.get("id")
            label = row.get("label")
            if isinstance(ident, str) and isinstance(label, str):
                self.prior_labels[ident] = label

    def _snapshot_arm_c_before(self) -> None:
        path = self.out / "s4" / "arm-c-order-before.txt"
        if path.is_file() and path.stat().st_size > 0:
            return
        by_name: dict[str, tuple[str, list[str], str, str, int]] = {}
        certs = sorted(self.out.glob("cert-*.json"), key=lambda item: item.name)
        for cert_path in certs:
            try:
                cert = json.loads(cert_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if cert.get("kind") == "BRITTLE":
                continue
            victim = cert.get("victim_id")
            polluters = cert.get("polluter_ids")
            if not isinstance(victim, str) or not isinstance(polluters, list):
                continue
            intended = [victim, *[item for item in polluters if isinstance(item, str)]]
            runs = cert.get("runs") or {}
            for side in ("base", "head"):
                block = (runs.get(side) or {}).get("C") or []
                for index, run in enumerate(block, start=1):
                    if not isinstance(run, dict):
                        continue
                    host = run.get("json_host")
                    if not isinstance(host, str) or not host:
                        continue
                    by_name[Path(host).name] = (victim, intended, cert_path.name, side, index)
        lines = []
        invalid = 0
        total = 0
        victims: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        json_files = sorted((self.out / "s4").glob("*-C-r*.json"))
        for json_path in json_files:
            meta = by_name.get(json_path.name)
            if meta is None:
                continue
            victim, intended, cert_name, side, index = meta
            examples = _load_examples(json_path) or []
            order = [example.get("id") for example in examples if example.get("id")]
            total += 1
            bad = order != intended
            if bad:
                invalid += 1
                for polluter in intended[1:]:
                    key = (victim, polluter)
                    if key not in seen:
                        seen.add(key)
                        victims.append(key)
            status = INVALID_ORDER if bad else "OK"
            lines.append(f"{json_path.name} {cert_name} {side} C r{index} {status} order={order}")
        header = [f"ARM_C_INVALID_ORDER_BEFORE {invalid}", f"ARM_C_RUNS {total}"]
        for victim, polluter in victims:
            header.append(f"invalid_victim {victim} polluter {polluter}")
        path.write_text("\n".join(header + lines) + "\n", encoding="utf-8")

    def _before_count(self) -> int:
        path = self.out / "s4" / "arm-c-order-before.txt"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("ARM_C_INVALID_ORDER_BEFORE "):
                return int(line.rsplit(" ", 1)[1])
        raise SystemExit(f"{path} has no ARM_C_INVALID_ORDER_BEFORE line")

    def _invalid_pairs(self) -> list[tuple[str, str]]:
        path = self.out / "s4" / "arm-c-order-before.txt"
        pairs = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("invalid_victim "):
                continue
            rest = line[len("invalid_victim ") :]
            victim, marker, polluter = rest.partition(" polluter ")
            if marker and victim and polluter:
                pairs.append((victim, polluter))
        return pairs

    def _write_crosscheck(self) -> None:
        lines = [
            "source existing s0 json only; no new runs",
            "a seed is listed when the victim index is lower than the polluter index in the base json",
            "status is the victim status in that base json; head_status is the same seed at head",
            "",
        ]
        for victim, polluter in self._invalid_pairs():
            lines.append(f"victim {victim}")
            lines.append(f"polluter {polluter}")
            for seed in range(SEED_MIN, SEED_MAX + 1):
                base_examples = _load_examples(self.out / "s0" / f"base-seed-{seed:02d}.json") or []
                head_examples = _load_examples(self.out / "s0" / f"head-seed-{seed:02d}.json") or []
                victim_at = _example_index(base_examples, victim)
                polluter_at = _example_index(base_examples, polluter)
                if victim_at is None or polluter_at is None or victim_at >= polluter_at:
                    continue
                status = _victim_status(base_examples, victim) or "absent"
                head_status = _victim_status(head_examples, victim) or "absent"
                lines.append(
                    f"seed {seed} status={status} head_status={head_status} "
                    f"victim_index={victim_at} polluter_index={polluter_at} "
                    f"source=s0/base-seed-{seed:02d}.json"
                )
            lines.append("")
        text = "\n".join(lines).rstrip() + "\n"
        (self.out / "s0" / "victim-first-crosscheck.txt").write_text(text, encoding="utf-8")

    def run(self) -> int:
        self.out.mkdir(parents=True, exist_ok=True)
        for name in ("s0", "s1", "s2", "s3", "s4"):
            (self.out / name).mkdir(parents=True, exist_ok=True)
        self._remember_prior_labels()
        self._snapshot_arm_c_before()
        self.invalid_before = self._before_count()
        self._write_crosscheck()
        invocation = shlex.join(sys.argv)
        (self.out / "invocation.txt").write_text(invocation + "\n", encoding="utf-8")
        self.log.section("certify_rspec discover")
        self.log.write("argv " + invocation, echo=True)
        self.image_id = _image_id(self.image)
        self.image_digest = _image_digest(self.image)
        self.server = _docker_server_version()
        self.log.write(f"image {self.image}", echo=True)
        self.log.write(f"image_id {self.image_id}", echo=True)
        self.log.write(f"image_digest {self.image_digest}", echo=True)
        self.log.write(f"docker_server {self.server}", echo=True)
        expected = _expected_tarballs(RECON_LOG.read_text(encoding="utf-8"))
        repo = repo_from_url(self.args.base_url)
        head_repo = repo_from_url(self.args.head_url)
        if head_repo != repo:
            raise SystemExit(f"base repo {repo} and head repo {head_repo} differ")
        self.mounts, self.env = self._side_env()
        self.base = self._prepare(self.args.base_url, expected["base.tgz"])
        self.head = self._prepare(self.args.head_url, expected["merge.tgz"])
        self.base["repo"] = repo
        self.head["repo"] = repo
        if self.base["gemfile_lock_sha256"] != self.head["gemfile_lock_sha256"]:
            raise SystemExit("base and head Gemfile.lock hashes differ")
        if self.base["bundler"] != self.head["bundler"]:
            raise SystemExit("base and head BUNDLED WITH versions differ")
        self.bundler = self.base["bundler"]
        self._bundle(self.base)
        self._bundle(self.head)
        self.versions = self.base["versions"]
        if self.head.get("versions") != self.versions:
            self.log.write(
                "version strings differ between trees: "
                + json.dumps({"base": self.versions, "head": self.head.get("versions")}),
                echo=True,
            )
        if not self.versions.get("rspec_core"):
            raise SystemExit("version probe did not report rspec-core")

        self.log.section("S0 seed discovery")
        defined_base, defined_head = self._pair("defined", ["--order", "defined"], 900)
        defined_passed = _passed_ids(defined_base)
        records = []
        for seed in range(SEED_MIN, SEED_MAX + 1):
            base_examples, head_examples = self._pair(f"seed-{seed:02d}", ["--seed", str(seed)], 900)
            records.append(
                {
                    "seed": seed,
                    "base_failing_ids": _failing_ids(base_examples),
                    "head_failing_ids": _failing_ids(head_examples),
                }
            )
        chosen = primary_seed(records)
        union = union_failing(records)
        seeds_doc = {
            "defined": {
                "base_failing_ids": _failing_ids(defined_base),
                "head_failing_ids": _failing_ids(defined_head),
            },
            "seeds": records,
            "primary_seed": chosen,
            "union": union,
        }
        (self.out / "s0" / "seeds.json").write_text(json.dumps(seeds_doc, indent=2) + "\n", encoding="utf-8")
        self.log.write(
            f"S0 primary={chosen} union={len(union)} defined_base_failing={len(seeds_doc['defined']['base_failing_ids'])}",
            echo=True,
        )
        by_seed = {int(record["seed"]): record for record in records}

        self.log.section("S2 classify")
        classified = []
        for item in union:
            victim_id = item["id"]
            slug = example_stem(self.locations.get(victim_id, victim_id), victim_id)
            flags = []
            alone_runs = []
            for rep in range(1, REPS + 1):
                outcome = self._alone("base", self.base, victim_id, "s2", f"{slug}-r{rep}")
                flags.append(alone_passed(outcome))
                alone_runs.append(outcome)
            kind = classify_discovered(flags, victim_id in defined_passed)
            record = {
                "id": victim_id,
                "location": self.locations.get(victim_id, victim_id),
                "seeds": list(item["seeds"]),
                "classification": kind,
                "alone": flags,
                "alone_runs": alone_runs,
            }
            classified.append(record)
            self.log.write(f"S2 {record['location']} {kind} alone={flags}", echo=True)
        (self.out / "s2" / "classify.json").write_text(
            json.dumps(
                [
                    {
                        "id": item["id"],
                        "location": item["location"],
                        "seeds": item["seeds"],
                        "classification": item["classification"],
                        "alone": item["alone"],
                    }
                    for item in classified
                ],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        rows = []
        cert_index = 0
        self.log.section("S3 attribute")
        for item in classified:
            kind = item["classification"]
            if kind == OTHER:
                rows.append(
                    {
                        "id": item["id"],
                        "location": item["location"],
                        "classification": OTHER,
                        "label": OTHER,
                        "seeds": item["seeds"],
                        "detail": "alone=" + ",".join("pass" if flag else "fail" for flag in item["alone"]),
                        "reason": "alone results are not 3/3 pass or 3/3 fail in defined order",
                    }
                )
                continue
            first = int(item["seeds"][0])
            s0_line = by_seed[first]
            if kind == ORDER_DEPENDENT:
                examples = _load_examples(self.out / "s0" / f"base-seed-{first:02d}.json") or []
                try:
                    preds = predecessors(examples, item["id"])
                except KeyError:
                    rows.append(self._unattributed(item, "victim id missing from the seed run"))
                    continue
                bisect_args = ["--bisect=verbose", "--seed", str(first), *preds, item["id"]]
                logical = format_command(["rspec", *bisect_args])
                log_path = self.out / "s3" / f"{example_stem(item['location'], item['id'])}-bisect.log"
                self._execute(
                    "base",
                    self.base,
                    bisect_args,
                    log_path,
                    None,
                    3600,
                    logical,
                    None,
                )
                parsed = parse_bisect(log_path.read_text(encoding="utf-8", errors="replace"))
                if not parsed["attributed"]:
                    rows.append(self._unattributed(item, parsed["reason"] or "bisect failed"))
                    self.log.write(f"S3 {item['location']} UNATTRIBUTED {parsed['reason']}", echo=True)
                    continue
                polluters = polluter_ids(parsed["ids"], item["id"])
                if polluters is None:
                    rows.append(self._unattributed(item, "victim id not in repro command"))
                    continue
                item["polluter_ids"] = polluters
                item["commands"] = spec_commands(first, polluters, item["id"])
                item["minimal"] = parsed["command"]
                item["seed"] = first
                item["s0"] = s0_line
                self.log.write(f"S3 {item['location']} ATTRIBUTED polluters={len(polluters)}", echo=True)
                continue
            examples = _load_examples(self.out / "s0" / "base-defined.json") or []
            try:
                candidates = _ids_before(examples, item["id"])
            except KeyError:
                rows.append(self._unattributed(item, "victim id missing from the defined-order run"))
                continue
            enablers, probes = self._enablers(item, candidates)
            probe_path = self.out / "s3" / f"{example_stem(item['location'], item['id'])}-enabler.json"
            probe_path.write_text(json.dumps({"probes": probes}, indent=2) + "\n", encoding="utf-8")
            if not enablers:
                reason = probes[-1]["reason"] if probes and probes[-1].get("reason") else "no 1-minimal enabler"
                rows.append(self._unattributed(item, reason))
                self.log.write(f"S3 {item['location']} UNATTRIBUTED {reason}", echo=True)
                continue
            item["enabler_ids"] = enablers
            item["seed"] = first
            item["s0"] = s0_line
            self.log.write(f"S3 {item['location']} enablers={len(enablers)} probes={len(probes)}", echo=True)

        self.log.section("S4 certify")
        for item in classified:
            if item["classification"] == ORDER_DEPENDENT and item.get("polluter_ids") is not None:
                cert_index += 1
                cert, row = self._certify_od(cert_index, item)
                self._write_cert(cert_index, cert)
                rows.append(row)
                self.log.write(f"S4 {item['location']} {row['label']}", echo=True)
            elif item["classification"] == BRITTLE and item.get("enabler_ids"):
                cert_index += 1
                cert, row = self._certify_brittle(cert_index, item)
                self._write_cert(cert_index, cert)
                rows.append(row)
                self.log.write(f"S4 {item['location']} {row['label']}", echo=True)

        order = {item["id"]: index for index, item in enumerate(classified)}
        rows.sort(key=lambda row: order.get(row["id"], 10**9))
        (self.out / "check-summary.md").write_text(_summary_md(rows) + "\n" + _skeptic(), encoding="utf-8")
        self._replay(rows)
        self._finish(rows, records, chosen, union, classified)
        return 0 if classification_exit_ok(rows) else 1

    def _unattributed(self, item: dict, reason: str) -> dict:
        return {
            "id": item["id"],
            "location": item["location"],
            "classification": item["classification"],
            "label": "UNATTRIBUTED",
            "reason": reason,
            "seeds": item["seeds"],
            "detail": reason,
        }

    def _enablers(self, item: dict, candidates: list[str]) -> tuple[list[str], list[dict]]:
        probes: list[dict] = []
        slug = example_stem(item["location"], item["id"])

        def test(subset: list[str]) -> bool:
            key = hashlib.sha256("\n".join(subset).encode("utf-8")).hexdigest()[:16]
            stem = f"{slug}-enabler-{key}"
            args = ["--order", "defined", *subset, item["id"]]
            logical = format_command(["rspec", *args])
            log_path = self.out / "s3" / f"{stem}.log"
            json_path = self.out / "s3" / f"{stem}.json"
            outcome, _examples = self._execute(
                "base",
                self.base,
                args,
                log_path,
                json_path,
                900,
                logical,
                item["id"],
            )
            passed = outcome.get("victim_status") == "passed"
            reason = ""
            if not passed and not subset:
                reason = "empty predecessor set does not pass the victim"
            probes.append(
                {
                    "ids": list(subset),
                    "victim_passed": passed,
                    "log": str(log_path),
                    "reason": reason,
                }
            )
            return passed

        try:
            found = one_minimal(candidates, test)
        except DdminError:
            if not probes:
                probes.append(
                    {
                        "ids": list(candidates),
                        "victim_passed": False,
                        "reason": "full predecessor set does not pass the victim",
                    }
                )
            elif not probes[-1].get("reason"):
                probes[-1]["reason"] = "full predecessor set does not pass the victim"
            return [], probes
        return found, probes

    def _certify_od(self, index: int, item: dict) -> tuple[dict, dict]:
        commands = item["commands"]
        command_strings = {arm: format_command(commands[arm]) for arm in ("A", "B", "C")}
        runs = {"base": {}, "head": {}}
        exec_by_arm = {"base": {}, "head": {}}
        sides = {"base": self.base, "head": self.head}
        for arm in ("A", "B", "C"):
            body = commands[arm][1:]
            if arm == "A":
                intended = [*item["polluter_ids"], item["id"]]
            elif arm == "B":
                intended = [item["id"]]
            else:
                intended = [item["id"], *item["polluter_ids"]]
            run_env = None
            if arm == "C":
                run_env = [*self.env, (IDS_ENV, " ".join(intended))]
            for rep in range(1, REPS + 1):
                def run_one(
                    side_name: str,
                    arm=arm,
                    rep=rep,
                    body=body,
                    intended=intended,
                    run_env=run_env,
                ) -> dict:
                    side = sides[side_name]
                    stem = f"{example_stem(item['location'], item['id'])}-{side['sha7']}-{arm}-r{rep}"
                    logical = command_strings[arm]
                    log_path = self.out / "s4" / f"{stem}.log"
                    json_path = self.out / "s4" / f"{stem}.json"
                    outcome, _examples = self._execute(
                        side_name,
                        side,
                        body,
                        log_path,
                        json_path,
                        240,
                        logical,
                        item["id"],
                        intended=intended,
                        run_env=run_env,
                    )
                    return outcome

                with ThreadPoolExecutor(max_workers=2) as pool:
                    base_future = pool.submit(run_one, "base")
                    head_future = pool.submit(run_one, "head")
                    base_outcome = base_future.result()
                    head_outcome = head_future.result()
                runs["base"].setdefault(arm, []).append(base_outcome)
                runs["head"].setdefault(arm, []).append(head_outcome)
        for side_name in ("base", "head"):
            for rep in runs[side_name].get("C") or []:
                if rep.get("order_status") == INVALID_ORDER:
                    self.invalid_after += 1
        for side_name in ("base", "head"):
            for arm in ("A", "B", "C"):
                exec_by_arm.setdefault(side_name, {})[arm] = [rep["exec_argv"] for rep in runs[side_name][arm]]
        judged = judge(runs["base"], runs["head"], item["id"], item["polluter_ids"])
        cert = _build_cert(
            self._meta(item["seed"]),
            {"id": item["id"], "location": item["location"]},
            item["polluter_ids"],
            command_strings,
            item.get("minimal") or "",
            runs,
            judged,
            exec_by_arm,
        )
        cert["kind"] = "ORDER-DEPENDENT"
        cert["seed_provenance"] = self._provenance(item["seed"], item["s0"], item["seeds"])
        cert["tool"]["version"] = __version__
        cert["execution"] = self._execution(exec_by_arm, 240)
        row = {
            "id": item["id"],
            "location": item["location"],
            "classification": ORDER_DEPENDENT,
            "label": judged["label"],
            "base": judged["verdicts"]["base"],
            "head": judged["verdicts"]["head"],
            "polluter_ids": item["polluter_ids"],
            "seeds": item["seeds"],
            "cert": f"cert-{index}.json",
            "detail": f"polluters={len(item['polluter_ids'])} seed={item['seed']}",
            "reason": self._od_reason(item["id"], judged["label"]),
        }
        return cert, row

    def _certify_brittle(self, index: int, item: dict) -> tuple[dict, dict]:
        enablers = list(item["enabler_ids"])
        alone_cmd = format_command(["rspec", item["id"]])
        enabled_cmd = format_command(["rspec", "--order", "defined", *enablers, item["id"]])
        base_enabled = []
        head_alone = []
        for rep in range(1, REPS + 1):
            with ThreadPoolExecutor(max_workers=2) as pool:
                enabled_future = pool.submit(
                    self._enabled,
                    self.base,
                    enablers,
                    item["id"],
                    f"{example_stem(item['location'], item['id'])}-{self.base['sha7']}-enabled-r{rep}",
                )
                alone_future = pool.submit(
                    self._alone,
                    "head",
                    self.head,
                    item["id"],
                    "s4",
                    f"{example_stem(item['location'], item['id'])}-{self.head['sha7']}-alone-r{rep}",
                )
                base_enabled.append(enabled_future.result())
                head_alone.append(alone_future.result())
        verdict = brittle_verdict(item["alone_runs"], base_enabled, head_alone, item["id"])
        runs = {
            "base": {"alone": item["alone_runs"], "enabled": base_enabled},
            "head": {"alone": head_alone},
        }
        versions = self.base.get("versions") or self.versions
        cert = {
            "tool": {"name": "certify_rspec", "version": __version__, "git_sha": _git_sha(REPO_ROOT)},
            "repo": self.base["repo"],
            "base": {"commit": self.base["commit"], "tarball_sha256": self.base["tarball_sha256"]},
            "head": {"commit": self.head["commit"], "tarball_sha256": self.head["tarball_sha256"]},
            "image_id": self.image_id,
            "ruby": versions.get("ruby", ""),
            "bundler": versions.get("bundler", ""),
            "rspec_core": versions.get("rspec_core", ""),
            "gemfile_lock_sha256": {
                "base": self.base["gemfile_lock_sha256"],
                "head": self.head["gemfile_lock_sha256"],
            },
            "seed": item["seed"],
            "seed_provenance": self._provenance(item["seed"], item["s0"], item["seeds"]),
            "victim_id": item["id"],
            "victim_location": item["location"],
            "kind": "BRITTLE",
            "enabler_ids": enablers,
            "commands": {"alone": alone_cmd, "enabled": enabled_cmd},
            "runs": runs,
            "label": verdict["label"],
            "reason": verdict["reason"],
            "error_class": verdict["error_class"],
            "execution": self._execution({}, 900),
        }
        row = {
            "id": item["id"],
            "location": item["location"],
            "classification": BRITTLE,
            "label": verdict["label"],
            "reason": verdict["reason"],
            "enabler_ids": enablers,
            "seeds": item["seeds"],
            "cert": f"cert-{index}.json",
            "detail": f"enablers={len(enablers)} seed={item['seed']}",
        }
        return cert, row

    def _replay(self, rows: list[dict]) -> None:
        self.log.section("replay")
        lines = []
        scripts = sorted(self.out.glob("replay-*.sh"), key=lambda path: int(path.stem.split("-", 1)[1]))
        for label, key in (("first", "first_replay_exit"), ("second", "replay_exit")):
            for script in scripts:
                lines.append(f"===== {label} {script.name} =====")
                proc = subprocess.run(["bash", str(script)], cwd=REPO_ROOT, capture_output=True, check=False)
                stdout = proc.stdout.decode("utf-8", errors="replace")
                stderr = proc.stderr.decode("utf-8", errors="replace")
                if stdout:
                    lines.append(stdout.rstrip("\n"))
                if stderr:
                    lines.append(stderr.rstrip("\n"))
                lines.append(f"{key}={proc.returncode}")
                self.log.write(f"replay {label} {script.name} exit={proc.returncode}", echo=True)
        (self.out / "replay-check.log").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _finish(self, rows, records, chosen, union, classified) -> None:
        spec_text = SPEC_PATH.read_text(encoding="utf-8")
        pattern = _acceptance_pattern(spec_text)
        tool_code, tool_out = _grep(pattern, REPO_ROOT / "tools" / "certify_rspec", True)
        invocation = self.out / "invocation.txt"
        inv_code, inv_out = _grep(pattern, invocation, False)
        acceptance_1 = tool_code == 1 and inv_code == 1 and tool_out == "" and inv_out == ""
        certified_rows = [row for row in rows if row["label"] in ("CERTIFIED", "BRITTLE_CERTIFIED")]
        changed = set(_differing_spec_files(self.base["tree"], self.head["tree"]))
        covered = {_file_of(row["location"]) for row in certified_rows}
        acceptance_2 = len(certified_rows) >= 3 and len(covered & changed) >= 2
        replay_text = (self.out / "replay-check.log").read_text(encoding="utf-8")
        second = re.findall(r"^replay_exit=(\d+)$", replay_text, re.M)
        scripts = list(self.out.glob("replay-*.sh"))
        g1 = json.loads(G1_SUMMARY.read_text(encoding="utf-8"))
        g1_labels = [row["label"] for row in g1["rows"]]
        g1_ok = (
            g1.get("exit_ok") is True
            and g1_labels.count("CERTIFIED") == 4
            and g1_labels.count("REJECTED") == 1
            and g1_labels.count("CONTROL") == 1
        )
        replay_ok = len(second) == len(scripts) and all(item == "0" for item in second)
        acceptance_3 = replay_ok and g1_ok
        pytest = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        (self.out / "pytest.log").write_text(pytest.stdout + pytest.stderr, encoding="utf-8")
        acceptance_4 = pytest.returncode == 0
        go = acceptance_1 and acceptance_2 and acceptance_3 and acceptance_4
        self.label_changes = []
        for row in rows:
            old = self.prior_labels.get(row["id"])
            if old is not None and old != row["label"]:
                self.label_changes.append(f"LABEL_CHANGED {row['id']} {old} {row['label']}")
        exit_ok = classification_exit_ok(rows)
        certified_ids = [row["id"] for row in rows if row["label"] == "CERTIFIED"]
        brittle_ids = [row["id"] for row in rows if row["label"] == "BRITTLE_CERTIFIED"]
        rejected_ids = [row["id"] for row in rows if row["label"] == "REJECTED"]
        od_n = sum(1 for item in classified if item["classification"] == ORDER_DEPENDENT)
        brittle_n = sum(1 for item in classified if item["classification"] == BRITTLE)
        failing_base = sum(1 for record in records if record["base_failing_ids"])
        failing_head = sum(1 for record in records if record["head_failing_ids"])
        versions = self.base.get("versions") or self.versions
        summary = {
            "seeds_searched": SEED_MAX - SEED_MIN + 1,
            "seeds_failing_base": failing_base,
            "seeds_failing_head": failing_head,
            "primary_seed": chosen,
            "union": [item["id"] for item in union],
            "od_count": od_n,
            "brittle_count": brittle_n,
            "certified": certified_ids,
            "brittle_certified": brittle_ids,
            "rejected": rejected_ids,
            "rows": [{key: value for key, value in row.items() if key != "alone_runs"} for row in rows],
            "exit_ok": exit_ok,
            "acceptance": {
                "1": acceptance_1,
                "2": acceptance_2,
                "3": acceptance_3,
                "4": acceptance_4,
            },
            "go": go,
            "changed_spec_files": sorted(changed),
            "covered_spec_files": sorted(covered),
            "image_id": self.image_id,
            "image_digest": self.image_digest,
            "docker_server": self.server,
            "ruby": versions.get("ruby", ""),
            "bundler": versions.get("bundler", ""),
            "rspec_core": versions.get("rspec_core", ""),
            "wall_s": round(time.monotonic() - self.started, 3),
            "arm_c_invalid_order_before": self.invalid_before,
            "arm_c_invalid_order_after": self.invalid_after,
        }
        (self.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        self._write_g2(
            summary,
            pattern,
            tool_code,
            tool_out,
            inv_code,
            inv_out,
        )
        self.log.write(
            f"done union={len(union)} od={od_n} brittle={brittle_n} exit_ok={exit_ok} GO={go} wall_s={summary['wall_s']}",
            echo=True,
        )
        self.log.close()
        _write_sums(self.out)

    def _write_g2(
        self,
        summary: dict,
        pattern: str,
        tool_code: int,
        tool_out: str,
        inv_code: int,
        inv_out: str,
    ) -> None:
        versions = summary
        ruby = versions["ruby"]
        if ruby and not ruby.startswith("ruby "):
            ruby = "ruby " + ruby
        lines = [
            f"image_id {summary['image_id']}",
            f"image_digest {summary['image_digest']}",
            f"docker_server {summary['docker_server']}",
            ruby,
            versions["bundler"],
            f"rspec-core {summary['rspec_core']}",
            f"wall_s {summary['wall_s']}",
            f"exit_ok {summary['exit_ok']}",
            "",
        ]
        for row in summary["rows"]:
            lines.append(
                f"{row['label']} {row['location']} class={row.get('classification', '')} {row.get('detail', '')}"
            )
        primary = summary["primary_seed"]
        primary_text = "none" if primary is None else str(primary)
        lines.extend(
            [
                "",
                f"SEEDS_SEARCHED {summary['seeds_searched']}",
                f"SEEDS_FAILING_BASE {summary['seeds_failing_base']}",
                f"SEEDS_FAILING_HEAD {summary['seeds_failing_head']}",
                f"PRIMARY_SEED {primary_text}",
                f"UNION {len(summary['union'])}",
                f"OD {summary['od_count']}",
                f"BRITTLE {summary['brittle_count']}",
                "CERTIFIED " + ",".join(summary["certified"]),
                "BRITTLE_CERTIFIED " + ",".join(summary["brittle_certified"]),
                "REJECTED " + ",".join(summary["rejected"]),
                f"ARM_C_INVALID_ORDER_BEFORE {summary['arm_c_invalid_order_before']}",
                f"ARM_C_INVALID_ORDER_AFTER {summary['arm_c_invalid_order_after']}",
            ]
        )
        for row in summary["rows"]:
            reason = row.get("reason") or ""
            suffix = f" reason={reason}" if reason else ""
            lines.append(f"VICTIM {row['id']} {row['label']}{suffix}")
        lines.extend(self.label_changes)
        lines.extend(
            [
                f"ACCEPTANCE_1 {summary['acceptance']['1']}",
                f"ACCEPTANCE_2 {summary['acceptance']['2']}",
                f"ACCEPTANCE_3 {summary['acceptance']['3']}",
                f"ACCEPTANCE_4 {summary['acceptance']['4']}",
                f"GO {summary['go']}",
                "===== acceptance 1 grep =====",
                f"+ grep -RInE {pattern!r} tools/certify_rspec",
                tool_out.rstrip("\n"),
                f"grep_exit={tool_code}",
                f"+ grep -nE {pattern!r} {(self.out / 'invocation.txt').resolve().relative_to(REPO_ROOT.resolve()).as_posix()}",
                inv_out.rstrip("\n"),
                f"grep_exit={inv_code}",
            ]
        )
        (self.out / "g2.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.certify_rspec discover")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--head-url", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cache", default="/tmp/flakecert-g2-1019/work")
    args = parser.parse_args(argv)
    return Discovery(args).run()
