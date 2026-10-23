# Skeptic pass (before runs)
1. Two-file runs are not the suite: a pair can fail for a reason other than the named polluter (e.g. provisioning_client_spec's own portal
   login needing stubs). Guard: require the M4 message, and R_i (swapped order) must pass.
2. 'Last writer' is static; dynamic writers outside spec files (lib) were grepped: none (M6). Indirect writers via helpers not grepped
   beyond spaceship/spec + spaceship/lib -> residual risk.
3. Fix changed six files; the pair proves the fix removes THIS polluter's effect, not that #30192 fixed every order dependency
   (two_step:76 stays failing; portal/certificate:111 polluter unnamed).
4. 3 reps can't bound a rate; these pairs are expected deterministic (no RNG on path). Any rep disagreement voids the pair.
5. codeload tarballs re-downloaded twice with identical sha256 here; still not a GitHub guarantee -> the task re-checks them.
6. Nothing in F6 says flakiness in CI at large; scope is this suite, these commits, this image.
