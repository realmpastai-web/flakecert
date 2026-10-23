#!/usr/bin/env python3
"""flakecert-ingest gate (Hark, frozen 2026-10-18). Offline. It reads only the files in this folder.
Question: can a Buildkite, CircleCI or GitLab user's existing test output feed a FlakeCert certificate, and which cert fields must FlakeCert supply itself?
Cert spec (inputs/flakecert/CURSOR_TASK_flakecert-poc.md step 6): {id, project, sha, pytest_id, node_id, image_digest, pip_freeze_sha, flakecert_version,
  sources[], m, k, d, schedule[], seed, expected_failure{exc, sig=sha256(normalized traceback)}, bound{per_run_lower, formula}}.
Usage: python3 gate_flakecert_ingest.py   (exit 0 = every expectation in FIELD_MAP holds on the frozen samples)"""
import json, re, sys, hashlib, xml.etree.ElementTree as ET
from pathlib import Path
H = Path(__file__).resolve().parent; S = H / "samples"
SHA = "f711ef3b9426b92e2e73691439bf6d4dbaa6e341"   # commit of the sample repo, exported as BUILDKITE_COMMIT for pytest runs
bad = []
def say(tag, ok, msg):
    print(("PASS" if ok else "FAIL") + f"\t{tag}\t{msg}")
    if not ok: bad.append(tag)

def junit(path):
    root = ET.parse(path).getroot(); out = {}
    keys = set()
    for el in root.iter():
        keys |= {f"{el.tag}@{a}" for a in el.attrib}
        if el.tag == "property": keys.add("property:" + el.get("name", ""))
    for tc in root.iter("testcase"):
        f = tc.find("failure"); sk = tc.find("skipped")
        text = None if f is None else ((f.get("message") or "") + "\n" + (f.text or ""))
        out[tc.get("name")] = {"result": "failed" if f is not None else "skipped" if sk is not None else "passed", "text": text, "attrs": dict(tc.attrib)}
    return out, keys, Path(path).read_text()
def collector(path):
    data = json.loads(Path(path).read_text()); out = {}; keys = set()
    for d in data:
        keys |= set(d)
        text = None
        if d.get("result") == "failed":
            text = d.get("failure_reason", "") + "\n" + "\n".join("\n".join(x.get("expanded", [])) for x in d.get("failure_expanded", []))
        out[d["name"]] = {"result": d["result"], "text": text, "attrs": d}
    return out, keys, Path(path).read_text(), data

F = {  # format -> (fail-seed file, rerun of same seed, pass-seed file, flaky test name, deterministic-fail name)
 "pytest-junit": ("pytest-junit-seed1.xml", "pytest-junit-seed1-rerun.xml", "pytest-junit-seed0.xml", "test_flaky_seeded", "test_fail_deterministic"),
 "jest-junit": ("jest-junit-seed1.xml", "jest-junit-seed1-rerun.xml", "jest-junit-seed2.xml", " flaky seeded", " fail deterministic"),
 "gotestsum-junit": ("gotestsum-junit-seed2.xml", "gotestsum-junit-seed2-rerun.xml", "gotestsum-junit-seed0.xml", "TestFlakySeeded", "TestFailDeterministic"),
 "buildkite-collector-json": ("buildkite-collector-seed1.json", "buildkite-collector-seed1-rerun.json", "buildkite-collector-seed0.json", "test_flaky_seeded", "test_fail_deterministic"),
}
def load(fmt, name):
    return collector(S / name)[:3] if fmt.startswith("buildkite") else junit(S / name)

# Normalizer the CURSOR TASK must implement (and nothing more is assumed here)
def normalize(t):
    t = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", t)                      # CPython object addresses (pytest repr)
    t = re.sub(r"(/[^\s:()]+)*/(node_modules/[^\s:()]+)", r"<dep>/\2", t)  # absolute dep paths
    t = re.sub(r"/[^\s:()]*/(proj/[^\s:()]+)", r"<repo>/\1", t)       # absolute repo paths -> repo-relative
    t = re.sub(r"\(\d+\.\d+s\)", "(Ts)", t)                           # go durations
    t = re.sub(r"\d+\.\d{3,}", "<float>", t)                          # drawn values / timings
    return "\n".join(l.rstrip() for l in t.strip().splitlines())
sig = lambda t: hashlib.sha256(normalize(t).encode()).hexdigest()
raw = lambda t: hashlib.sha256(t.encode()).hexdigest()

# What each format carries for each cert field: computed from the samples, then compared with FIELD_MAP.md
EXPECT = {  # field -> {format: present?}
 "test_identity":      {"pytest-junit": True,  "jest-junit": True,  "gotestsum-junit": True,  "buildkite-collector-json": True},
 "file":               {"pytest-junit": False, "jest-junit": True,  "gotestsum-junit": False, "buildkite-collector-json": True},
 "line":               {"pytest-junit": False, "jest-junit": False, "gotestsum-junit": False, "buildkite-collector-json": True},
 "failure_text":       {"pytest-junit": True,  "jest-junit": True,  "gotestsum-junit": True,  "buildkite-collector-json": True},
 "duration":           {"pytest-junit": True,  "jest-junit": True,  "gotestsum-junit": True,  "buildkite-collector-json": True},
 "commit_sha":         {"pytest-junit": False, "jest-junit": False, "gotestsum-junit": False, "buildkite-collector-json": False},
 "seed":               {"pytest-junit": False, "jest-junit": False, "gotestsum-junit": False, "buildkite-collector-json": False},
 "image_digest":       {"pytest-junit": False, "jest-junit": False, "gotestsum-junit": False, "buildkite-collector-json": False},
 "dep_lock_hash":      {"pytest-junit": False, "jest-junit": False, "gotestsum-junit": False, "buildkite-collector-json": False},
 "failure_sig":        {"pytest-junit": False, "jest-junit": False, "gotestsum-junit": False, "buildkite-collector-json": False},
 "toolchain_version":  {"pytest-junit": False, "jest-junit": False, "gotestsum-junit": True,  "buildkite-collector-json": False},
}
def present(field, fmt, keys, text, cases):
    k = {x.lower() for x in keys}
    if field == "test_identity": return all(n for n in cases)
    if field == "file": return any(x.endswith("@file") for x in k) or "file_name" in k
    if field == "line": return any(x.endswith("@line") for x in k) or ("location" in k and all(re.search(r":\d+$", c["attrs"].get("location", "")) for c in cases.values()))
    if field == "failure_text": return any(c["text"] for c in cases.values())
    if field == "duration": return any(x.endswith("@time") for x in k) or "history" in k
    if field == "commit_sha": return SHA in text
    if field == "seed": return any("seed" in x for x in k)
    if field == "image_digest": return "sha256:" in text or any("digest" in x or "image" in x for x in k)
    if field == "dep_lock_hash": return any(w in x for x in k for w in ("freeze", "lock", "requirements"))
    if field == "failure_sig": return any(w in x for x in k for w in ("sig", "fingerprint", "hash"))
    if field == "toolchain_version": return any(x.startswith("property:") and "version" in x for x in k) or "version" in k

for fmt, (ff, rr, pp, flaky, det) in F.items():
    fc, fk, ft = load(fmt, ff); rc, rk, rt = load(fmt, rr); pc, pk, ptxt = load(fmt, pp)
    say(f"{fmt}.G1.outcomes", fc[flaky]["result"] == "failed" and rc[flaky]["result"] == "failed" and pc[flaky]["result"] == "passed"
        and all(c[det]["result"] == "failed" for c in (fc, rc, pc)),
        f"{ff}: flaky={fc[flaky]['result']} rerun={rc[flaky]['result']} | {pp}: flaky={pc[flaky]['result']}; deterministic fails in all 3 -> same-commit flip observable")
    keys = fk | pk; text = ft + ptxt
    got = {f: present(f, fmt, keys, text, fc) for f in EXPECT}
    for f, exp in EXPECT.items():
        say(f"{fmt}.G2.{f}", got[f] == exp[fmt], f"{'present' if got[f] else 'MISSING'} (expected {'present' if exp[fmt] else 'missing'})")
    r_eq = raw(fc[flaky]["text"]) == raw(rc[flaky]["text"]); n_eq = sig(fc[flaky]["text"]) == sig(rc[flaky]["text"])
    say(f"{fmt}.G3.sig_stable", n_eq and sig(fc[flaky]["text"]) != sig(fc[det]["text"]),
        f"flaky failure raw-text sha equal across same-seed reruns: {r_eq}; normalized sig equal: {n_eq}; sig={sig(fc[flaky]['text'])[:16]}; != deterministic sig")

# G4 collector specifics, from shipped source (wheel e2c5013b...) and RunEnvBuilder output
src = (H / "collector-src/buildkite_plugin.py").read_text(); renv = (H / "collector-src/run_env.py").read_text(); pay = (H / "collector-src/payload.py").read_text()
say("collector.G4.local_json_drops_run_env", 'data = list(self.payload.as_json()["data"])' in src and isinstance(json.loads((S / "buildkite-collector-seed1.json").read_text()), list),
    "--json writes payload['data'] only; run_env (commit_sha, branch, CI) exists only in the uploaded payload (payload.py \"run_env\": self.run_env.as_json())")
say("collector.G4.upload_payload_keys", '"run_env": self.run_env.as_json()' in pay and '"format": "json"' in pay, "upload = {format, run_env, data[, tags]}")
re_ = json.loads((S / "collector-run-env.json").read_text())
say("collector.G4.ci_detection", re_["buildkite"]["run_env"].get("commit_sha") == SHA and re_["circleci"]["run_env"].get("commit_sha") == SHA
    and re_["gitlab"]["run_env"]["CI"] == "generic" and "commit_sha" not in re_["gitlab"]["run_env"] and "GITLAB" not in renv and "CI_COMMIT_SHA" not in renv,
    "Buildkite + CircleCI -> commit_sha set; GitLab env -> CI=generic, no commit_sha (run_env.py has no GitLab detector)")
a = {d["name"]: d["id"] for d in json.loads((S / "buildkite-collector-seed1.json").read_text())}
b = {d["name"]: d["id"] for d in json.loads((S / "buildkite-collector-seed1-rerun.json").read_text())}
say("collector.G4.id_not_stable", all(a[n] != b[n] for n in a) and all(re.fullmatch(r"[0-9a-f-]{36}", i) for i in a.values()),
    "per-execution id is a fresh uuid4 each run, so it can't key a test; use scope::name (or file_name+name)")
jn = ET.parse(S / "jest-junit-seed1.xml").getroot().find("testsuite")
say("jest.G4.identity_quirk", jn.get("name") == "undefined" and all(tc.get("name").startswith(" ") for tc in jn.iter("testcase")),
    "jest-junit 16 defaults: testsuite name=\"undefined\", testcase names have a leading space with no describe(); ingest must strip, and key on file+name")
print("VERDICT ingest: JUnit/collector output gives identity, outcome, failure text and duration; the cert's sha, seed, image_digest, pip_freeze_sha and sig must come from FlakeCert's own run (or CI env), not the reports"
      if not bad else f"VERDICT ingest: {len(bad)} expectation(s) failed: {bad}")
sys.exit(1 if bad else 0)
