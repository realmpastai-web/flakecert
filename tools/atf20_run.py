"""Run the four pinned cases and write out/RUNLOG.json.

atf20 reps are three runs of the case command. FlakeCert reps are the F6
pair and the reverse order at that case's commit. This does not score a
sealed file.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tools.atf20_f6 import judge_commit, parse_run
from tools.certify_rspec import __version__ as TOOL_VERSION

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
IMAGE = "flakecert-dryrun-fastlane:ruby31"
PREFIX = "76eeb3f9352a657fd979ae00e89e49a388729e30"
FIX = "148c1c9b4c041b1659ea633f2632dd47eef8cb04"
TARBALL_SHA = {
    PREFIX: "078c5e59b1765b88d829d9878b29deffb66e85122301a1f65d90b714bc81abaa",
    FIX: "db53c7bc72519a447c11961956516a240472457042b28a6ea12f7138968390d5",
}
RSPEC_SHA = "155b54480f28e2b2813185077fe435c2d663031616360ed3b179a9d6a55d2551"
SRC = {
    PREFIX: Path(f"/tmp/flakecert-f6-1019/src/fastlane-{PREFIX}"),
    FIX: Path(f"/tmp/flakecert-f6-1019/src/fastlane-{FIX}"),
}
TARBALL = {
    PREFIX: Path(f"/tmp/flakecert-f6-1019/tarballs/fastlane-{PREFIX}.tar.gz"),
    FIX: Path(f"/tmp/flakecert-f6-1019/tarballs/fastlane-{FIX}.tar.gz"),
}
WEBHOOK = "./spaceship/spec/connect_api/models/webhook_spec.rb"
VICTIM = "./spaceship/spec/connect_api/models/build_beta_detail_spec.rb:5"
TWO = "./spaceship/spec/two_step_or_factor_client_spec.rb"

CASES = [
    {
        "case": "H1",
        "commit": PREFIX,
        "files": [VICTIM],
        "rspec": ["--order", "defined", VICTIM],
        "target": "build_beta_detail_spec.rb:5",
        "kind": "A",
    },
    {
        "case": "H2",
        "commit": PREFIX,
        "files": [WEBHOOK, VICTIM],
        "rspec": ["--order", "defined", WEBHOOK, VICTIM],
        "target": "build_beta_detail_spec.rb:5",
        "kind": "A",
    },
    {
        "case": "H3",
        "commit": FIX,
        "files": [WEBHOOK, VICTIM],
        "rspec": ["--order", "defined", WEBHOOK, VICTIM],
        "target": "build_beta_detail_spec.rb:5",
        "kind": "A",
    },
    {
        "case": "H4",
        "commit": FIX,
        "files": [TWO + ":76"],
        "rspec": [TWO + ":76"],
        "target": "two_step_or_factor_client_spec.rb:76",
        "kind": "B",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_sha(path: Path, expected: str, label: str) -> None:
    actual = sha256_file(path)
    print(f"{label} {actual} {path}")
    if actual != expected:
        raise SystemExit(f"sha256 mismatch for {path}: {actual} != {expected}")


def git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def image_id() -> str:
    return subprocess.check_output(
        ["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
        text=True,
    ).strip()


def write_script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def docker_bash(src: Path, script_rel: str, env: dict[str, str], hook: bool) -> subprocess.CompletedProcess[str]:
    argv = ["docker", "run", "--rm", "-e", "BUNDLE_APP_CONFIG=/src/.bundle", "-e", "BUNDLE_SILENCE_ROOT_WARNING=1"]
    for key, value in env.items():
        argv.extend(["-e", f"{key}={value}"])
    if hook:
        argv.extend(["-e", "RUBYOPT=-r/src/atf20/argv_prelude.rb"])
    argv.extend(
        [
            "-v",
            f"{src}:/src",
            "-v",
            f"{ROOT / 'atf20'}:/src/atf20:ro",
            "-v",
            f"{OUT}:/evidence",
            "-w",
            "/src",
            IMAGE,
            "bash",
            f"/evidence/{script_rel}",
        ]
    )
    return subprocess.run(argv, text=True, capture_output=True, check=False, timeout=300)


def header(title: str, commit: str, argv: list[str]) -> str:
    tarball = TARBALL[commit]
    lines = [
        f"===== {title} {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} =====",
        f"+ sha256sum {tarball}",
        f"{TARBALL_SHA[commit]}  {tarball}",
        "+ " + " ".join(argv),
        "",
    ]
    return "\n".join(lines)


def run_logged(title: str, commit: str, script_rel: str, env: dict[str, str], hook: bool, log_path: Path) -> str:
    src = SRC[commit]
    proc = docker_bash(src, script_rel, env, hook)
    script_text = (OUT / script_rel).read_text(encoding="utf-8")
    text = header(title, commit, ["docker", "run", "bash", f"/evidence/{script_rel}"])
    text += "----- script -----\n" + script_text + "----- output -----\n"
    text += proc.stdout
    if proc.stderr:
        text += proc.stderr
    text += f"\ndocker_exit={proc.returncode}\n"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(text, encoding="utf-8")
    print(f"{title} docker_exit={proc.returncode} bytes={log_path.stat().st_size}")
    if proc.returncode not in (0, 1):
        raise SystemExit(f"{title} docker exit {proc.returncode}")
    if "ruby 3.1.7p261" not in text or "Bundler version 2.6.9" not in text:
        raise SystemExit(f"{title} missing ruby or bundler version")
    if TARBALL_SHA[commit] not in text:
        raise SystemExit(f"{title} missing tarball sha256")
    return text


def bash_quote(token: str) -> str:
    return "'" + token.replace("'", "'\\''") + "'"


def atf_script(case: dict, rep: int) -> str:
    name = f"{case['case']}-r{rep}"
    out_json = f"/evidence/atf20/{name}.json"
    out_audit = f"/evidence/atf20/{name}.audit.json"
    args_json = json.dumps(case["files"])
    rspec = [
        "bundle",
        "exec",
        "rspec",
        "--format",
        "documentation",
        "--no-color",
        "--require",
        "./atf20/atf20_hook.rb",
        "--atf-n",
        "20",
        "--atf-case",
        case["case"],
        "--atf-commit",
        case["commit"],
        "--atf-tarball",
        TARBALL_SHA[case["commit"]],
        "--atf-target",
        case["target"],
        "--atf-out",
        out_json,
        "--atf-audit",
        out_audit,
        "--atf-args",
        args_json,
        *case["rspec"],
    ]
    quoted = " ".join(bash_quote(item) for item in rspec)
    return "\n".join(
        [
            "#!/bin/bash",
            "ruby -v",
            "bundle -v",
            'printf "TARBALL_SHA256:%s\\n" "$ATF_TARBALL_SHA256"',
            'printf "COMMIT:%s\\n" "$ATF_COMMIT"',
            quoted,
            "ec=$?",
            f"chmod a+r {bash_quote(out_json)} {bash_quote(out_audit)} || true",
            'echo "RSPEC_EXIT:$ec"',
            "exit $ec",
            "",
        ]
    )


def f6_script(case: dict, arm: str, rep: int) -> str:
    if case["kind"] == "A":
        args = ["--order", "defined", WEBHOOK, VICTIM] if arm == "pair" else ["--order", "defined", VICTIM, WEBHOOK]
    else:
        both = TWO + ":76:94"
        args = ["--seed", "48174", both] if arm == "pair" else ["--order", "defined", both]
    rspec = ["bundle", "exec", "rspec", "--format", "documentation", "--no-color", *args]
    quoted = " ".join(bash_quote(item) for item in rspec)
    return "\n".join(
        [
            "#!/bin/bash",
            "ruby -v",
            "bundle -v",
            'printf "TARBALL_SHA256:%s\\n" "$TARBALL_SHA256"',
            'printf "COMMIT:%s\\n" "$COMMIT"',
            quoted,
            "ec=$?",
            'echo "RSPEC_EXIT:$ec"',
            "exit $ec",
            "",
        ]
    )


def forbid_verdict(path: Path, payload: dict) -> None:
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    if "seed" in lowered or "order" in lowered:
        raise SystemExit(f"{path} contains a forbidden token")
    if payload.get("verdict") not in ("PASS", "FAIL"):
        raise SystemExit(f"{path} verdict {payload.get('verdict')}")
    for row in payload["executions"]:
        if set(row) != {"i", "status", "exception_class", "first_line"}:
            raise SystemExit(f"{path} execution keys {sorted(row)}")


def run_case(case: dict) -> dict:
    label = case["case"]
    commit = case["commit"]
    env_base = {
        "ATF_CASE": label,
        "ATF_COMMIT": commit,
        "ATF_TARBALL_SHA256": TARBALL_SHA[commit],
        "ATF_TARGET": case["target"],
        "ATF_N": "20",
        "ATF_ARGS": json.dumps(case["files"]),
    }
    reps = []
    for rep in (1, 2, 3):
        name = f"{label}-r{rep}"
        script_rel = f"cmd/atf20-{name}.sh"
        write_script(OUT / script_rel, atf_script(case, rep))
        env = dict(env_base)
        env["ATF_OUT"] = f"/evidence/atf20/{name}.json"
        env["ATF_AUDIT"] = f"/evidence/atf20/{name}.audit.json"
        run_logged(f"atf20 {name}", commit, script_rel, env, True, OUT / "atf20" / f"{name}.log")
        verdict_path = OUT / "atf20" / f"{name}.json"
        if not verdict_path.is_file():
            raise SystemExit(f"missing {verdict_path}")
        payload = json.loads(verdict_path.read_text(encoding="utf-8"))
        forbid_verdict(verdict_path, payload)
        audit_path = OUT / "atf20" / f"{name}.audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if audit.get("audit_only") is not True or "order" not in audit:
            raise SystemExit(f"{audit_path} is not an audit record")
        reps.append(payload)
        print(f"{name} verdict={payload['verdict']} executions={len(payload['executions'])}")

    signatures = []
    for payload in reps:
        statuses = tuple(row["status"] for row in payload["executions"])
        signatures.append((payload["verdict"], statuses))
    if all(item == signatures[0] for item in signatures):
        atf_verdict = signatures[0][0]
    else:
        atf_verdict = "INCONCLUSIVE"

    f6_texts = {"pair": [], "reverse": []}
    f6_runs = {"pair": [], "reverse": []}
    f6_logs = {"pair": [], "reverse": []}
    for arm in ("pair", "reverse"):
        for rep in (1, 2, 3):
            name = f"{label}-{arm}-r{rep}"
            script_rel = f"cmd/f6-{name}.sh"
            write_script(OUT / script_rel, f6_script(case, arm, rep))
            env = {"TARBALL_SHA256": TARBALL_SHA[commit], "COMMIT": commit}
            text = run_logged(
                f"flakecert {name}",
                commit,
                script_rel,
                env,
                False,
                OUT / "flakecert" / f"{name}.log",
            )
            parsed = parse_run(text, 1)
            parsed["log"] = f"flakecert/{name}.log"
            parsed["log_sha256"] = sha256_file(OUT / "flakecert" / f"{name}.log")
            f6_texts[arm].append(text)
            f6_runs[arm].append(parsed)
            f6_logs[arm].append(f"flakecert/{name}.log")

    if case["kind"] == "A":
        victim_id = VICTIM
        polluter_ids = [WEBHOOK]
        polluter_marker = "Spaceship::ConnectAPI::Webhook"
        victim_marker = "#get_build_beta_details"
        message = "request_client"
    else:
        victim_id = TWO + ":76"
        polluter_ids = [TWO + ":94"]
        polluter_marker = "when running interactive"
        victim_marker = "when running non-interactive"
        message = "2FA can only be performed in interactive mode"
    flakecert_verdict = judge_commit(
        f6_runs["pair"],
        f6_runs["reverse"],
        f6_texts["pair"],
        f6_texts["reverse"],
        victim_id,
        polluter_ids,
        polluter_marker,
        victim_marker,
        message_contains=message,
    )
    cert = {
        "tool": {"name": "certify_rspec", "version": TOOL_VERSION, "git_sha": git_sha()},
        "hook_sha256": sha256_file(ROOT / "atf20" / "atf20_hook.rb"),
        "case": label,
        "commit": commit,
        "tarball_sha256": TARBALL_SHA[commit],
        "rules": "F6",
        "victim_id": victim_id,
        "polluter_ids": polluter_ids,
        "verdict": flakecert_verdict,
        "pair_logs": f6_logs["pair"],
        "reverse_logs": f6_logs["reverse"],
        "pair_runs": f6_runs["pair"],
        "reverse_runs": f6_runs["reverse"],
    }
    cert_path = OUT / "flakecert" / f"{label}.cert.json"
    cert_path.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
    print(f"{label} atf20={atf_verdict} flakecert={flakecert_verdict}")
    return {
        "case": label,
        "atf20_verdict": atf_verdict,
        "atf20_reps": [payload["verdict"] for payload in reps],
        "flakecert_verdict": flakecert_verdict,
        "flakecert_cert_sha256": sha256_file(cert_path),
    }


def gate_gb() -> None:
    lines = ["G-b Gemfile.lock datadog-ci scan", ""]
    for commit in (PREFIX, FIX):
        path = SRC[commit] / "Gemfile.lock"
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = [line for line in text.splitlines() if "datadog-ci" in line]
        lines.append(f"file {path}")
        lines.append(f"commit {commit}")
        lines.append(f"sha256 {sha256_file(path)}")
        lines.append(f"datadog-ci-hits {len(hits)}")
        lines.extend(hits)
        lines.append("")
    (OUT / "gate-gb.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def tree_sanity() -> None:
    prefix = (SRC[PREFIX] / "spaceship/spec/spec_helper.rb").read_text(encoding="utf-8")
    fix = (SRC[FIX] / "spaceship/spec/spec_helper.rb").read_text(encoding="utf-8")
    if "Spaceship::Portal.login" in prefix:
        raise SystemExit("prefix tree looks like the fix tree")
    if "Spaceship::Portal.login" not in fix or "Spaceship::ConnectAPI.client = nil" not in fix:
        raise SystemExit("fix tree is missing the shared-example reset")
    print("tree_sanity prefix_has_portal_login=no fix_has_portal_login=yes")


def preflight() -> None:
    for commit in (PREFIX, FIX):
        require_sha(TARBALL[commit], TARBALL_SHA[commit], "tarball")
        gem = SRC[commit] / "vendor/bundle/ruby/3.1.0/cache/rspec-core-3.12.2.gem"
        require_sha(gem, RSPEC_SHA, "rspec-core")
    tree_sanity()
    print(image_id())
    gate_gb()


def ensure_out() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for folder in ("atf20", "flakecert", "cmd"):
        path = OUT / folder
        path.mkdir(parents=True, exist_ok=True)
        try:
            path.chmod(0o777)
        except PermissionError:
            subprocess.check_call(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{OUT}:/evidence",
                    IMAGE,
                    "chmod",
                    "-R",
                    "a+rwX",
                    f"/evidence/{folder}",
                ]
            )


def main() -> None:
    ensure_out()
    preflight()
    by_commit = {PREFIX: [], FIX: []}
    for case in CASES:
        by_commit[case["commit"]].append(case)

    def run_commit(commit: str) -> list[dict]:
        return [run_case(case) for case in by_commit[commit]]

    with ThreadPoolExecutor(max_workers=2) as pool:
        groups = list(pool.map(run_commit, (PREFIX, FIX)))
    rows = {item["case"]: item for group in groups for item in group}
    ordered = [rows[case["case"]] for case in CASES]
    (OUT / "RUNLOG.json").write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")
    env = {
        "git_sha": git_sha(),
        "hook_sha256": sha256_file(ROOT / "atf20" / "atf20_hook.rb"),
        "image": IMAGE,
        "image_id": image_id(),
        "tarball_sha256": TARBALL_SHA,
        "rspec_core_sha256": RSPEC_SHA,
        "ruby": "ruby 3.1.7p261",
        "bundler": "2.6.9",
    }
    (OUT / "ENV.json").write_text(json.dumps(env, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(ordered, indent=2))


if __name__ == "__main__":
    main()
