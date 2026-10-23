# Skeptic pass (Hark, before any run)

1. arena-agent#206 may not reproduce on Linux at all: the issue says every Linux CI cell passed. A Linux-only no-repro proves
   nothing about the flake; the next cell is a macos-latest runner on py3.12 (the issue's cell). Sealed H1/H2 predict no repro.
2. The polluter named in the issue (e2e bridge) runs its server as a child process, so it cannot touch the parent's Popen
   patch directly (O5). The real polluter may be something else in-process; the forced-order A1 tests the issue's claim, not ours.
3. Coverage addopts (--cov-fail-under=46) make every narrow run exit non-zero. Read outcomes from junitxml, add --no-cov.
4. The e2e module binds a loopback port and spawns the bridge; on a sandbox that blocks binding, the module errors at setup and
   A1 becomes "victim alone". Treat e2e setup errors as INVALID, not as PASS.
5. The sabotage control (S1) is racy by design; it shows FlakeCert can certify a thread-borne leak, not that #206 is that leak.
6. fastlane seed 48174 was pinned for the full CI run; a spaceship/spec-only run orders differently (H7). The 17-failure count is
   the issue author's local macOS run, not a CI number. Neither count is ours until our logs show it.
7. Nothing here is claimed as reproduced. Every count enters only via q-logs committed under evidence/dryrun-2026-10-19/.
