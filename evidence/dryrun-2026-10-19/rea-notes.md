# REA notes (static, before any pytest or rspec)

Read from codeload trees under `/tmp/flakecert-dryrun-1019/src/` after `sha256sum -c` on the arena `TARBALL.sha256` files (see `q0.log`). Nothing under `inputs/dryrun-2026-10-19/` was edited. `HOLDOUT.sha256` was not opened past the checksum file that `sha256sum -c` already verified. No `predictions.json`.

`cmp` of tarball vs frozen evidence copies: victim test, `arena/mcp_client/client.py`, `tests/e2e/test_bridge_live.py`, and `tests/e2e/conftest.py` are identical at eb925fa and aec7800, and identical to the evidence copies. `tests/conftest.py` is absent at eb925fa and 793 lines at aec7800. `spaceship.rb` at downloaded 76eeb3f, downloaded 148c1c9, evidence 3a4fc36, and evidence 148c1c9 are one byte-identical file.

## Part 1 — arena-agent#206 order dependency

Victim assertion, pinned `tests/test_mcp_client_parity_v4_169_39.py` (same bytes at both shas):

```152:169:tests/test_mcp_client_parity_v4_169_39.py
def _fake_popen(args, **kwargs):
    captured_popen["args"] = args
    captured_popen["kwargs"] = kwargs
    return mock_proc

monkeypatch.setattr(mcp_mod.subprocess, "Popen", _fake_popen)
...
assert captured_popen["args"] == ["node", "server.js"]
```

Line numbers in the extracted file: `_fake_popen` assigns `captured_popen["args"]` at 153 and `kwargs` at 154; the patch is at 157; the assertion is at 169. Every `Popen` during the test overwrites the dict, so the last call in the window is what line 169 sees (spec O3).

`arena/mcp_client/client.py:31` is `import subprocess`. `McpStdioClient.start` calls that module at 110:

```110:111:arena/mcp_client/client.py
self.proc = subprocess.Popen(
    [self.command] + self.args,
```

`mcp_mod.subprocess` is the process-global stdlib module (spec O2), so the monkeypatch is visible to every later `subprocess.Popen` / `subprocess.run` in this interpreter. CPython 3.11.17 `subprocess.run` (image `python:3.11`, file `/usr/local/lib/python3.11/subprocess.py`) defines `run` at line 506 and calls `with Popen(*popenargs, **kwargs) as process` at line 548. A concurrent in-process `subprocess.run([..., "--version"])` is recorded as the victim's argv (spec O4).

The issue names `tests/e2e/test_bridge_live.py` as the polluter. The bridge fixture is module-scoped and starts a child:

```112:127:tests/e2e/test_bridge_live.py
@pytest.fixture(scope="module")
def bridge(tmp_path_factory):
    ...
    proc = subprocess.Popen(
        argv, cwd=str(tmp_path_factory.mktemp("bridge-cwd")),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
```

That `Popen` is in the parent, but it runs when the e2e module sets up, which is outside the victim's monkeypatch window. The child's own `Popen` calls cannot see the parent's patched `subprocess` (spec O5). The only `--version` in this file is an HTTP body, not a parent argv: line 449 iterates `("git status --short", "python3 --version", "echo allowlisted")` and posts it to the child bridge. Which in-process caller would leave `['/Users/runner...', '--version']` in `captured_popen` is unproven from these files.

`tests/e2e/conftest.py` does not spawn anything. Lines 20-27 load `test_bridge_live.py` by path and re-export `bridge`.

`tests/conftest.py` at aec7800 (793 lines) is the network guard and the `ARENA_*` leak guard. The autouse fixture `_no_outbound_network` is at line 786 and patches `socket`, not `subprocess`. It is absent at eb925fa.

`pyproject.toml` addopts at both shas include `--cov=arena` and `--cov-fail-under=46` (eb925fa lines 111-118; aec7800 line 118). A narrow run exits non-zero on the coverage floor unless `--no-cov` is passed (spec O6). Both locks pin `pytest-randomly==4.1.0`. Runs pass `-p no:randomly` and do not pass `--randomly-seed` (spec O7).

## Part 2 — fastlane#30184 singleton leak

`spaceship/lib/spaceship/connect_api/spaceship.rb` is unchanged between 3a4fc36, 76eeb3f, and 148c1c9. The class singleton holds the client:

```9:28:spaceship/lib/spaceship/connect_api/spaceship.rb
attr_accessor :client
...
def client
  # Always look for a client set explicitly by the client first
  return @client if @client
  ...
  return nil if Spaceship::Tunes.client.nil? && Spaceship::Portal.client.nil?

  implicit_client = ConnectAPI::Client.new(tunes_client: Spaceship::Tunes.client, portal_client: Spaceship::Portal.client)
```

`@client` is class-level state. A later example that reaches `ConnectAPI.client` reuses it (line 21) or, when it is nil, builds a client from `Spaceship::Portal.client` (line 28). That is the line the issue names for `#<Double "portal_client"> ... has leaked into another example`.

At 76eeb3f, `spaceship/spec/connect_api/spaceship_spec.rb:2-6` clears `ConnectAPI.client`, `Tunes.client`, and `Portal.client` only in `before(:all)`. The same file defines `double('portal_client')` at line 12 and stubs `Spaceship::Portal.client` to return it (lines 33 and 44). Explicit-client examples assign `ConnectAPI.client` through `auth` / `login` (lines 67-68 and 80-81) and nothing in that file clears `@client` per example.

At 148c1c9 the same spec file clears those three clients in `before(:each)` (lines 7-11) and `after(:each)` (lines 20-24). The comment at lines 13-19 says an explicit-client example's double otherwise survives the example and the next caller gets "has leaked into another example". `spaceship.rb` itself is not in the fix. Other spec-only diffs at 148c1c9: `spaceship/spec/spec_helper.rb`, `client_spec.rb`, `spaceauth_spec.rb`, `tunes/tunes_client_spec.rb`.

Gemfile and Gemfile.lock match at 76eeb3f and 148c1c9. `fastlane.gemspec` has `required_ruby_version = '>= 3.1'`. CI `.github/workflows/ci.yml` ubuntu cell is `ruby: '3.1'` on `ubuntu-24.04`. Lock says `BUNDLED WITH 2.6.9`.
