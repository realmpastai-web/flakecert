# Method

This runner follows the two-team clean-room recorded in `REA_CLEANROOM.md`.

The standing file read for this package is `/workspace/rea-fleet/REA_CLEANROOM.md`. Its sha256 is `03f868715b574e7998d91f658b79aec968a6a429a6cd9478edc7bcda4600de5f`. That digest matches the published prefix `03f86871` and suffix `4600de5f`. The Oxomen path named in the task was not mounted in this checkout. The hash is the identity of the method file.

The inspect side and the build side of this package are the same session. `SPEC.md` is the hand-off. The runner implements that spec and does not add a rule the spec did not cite from `desync-oracle/`.

## Two-team order

1. **Evidence-cited spec first.** `SPEC.md` names the published files, the two profile ids, the verdict function, and the checks that must pass before a file is written.
2. **Build only from that spec.** `runner/audit.py` replays the sealed tables. It does not open a tarball member and it does not score a new row.
3. **Check against the artifact's public behaviour.** Before writing, the runner sha256-checks every line of `desync-oracle/FREEZES.txt`, recounts the 25-row table, and requires the mapped word to equal `SCORE-SUMMARY.md` and `VERDICT.md`.
4. **Frozen baseline.** `desync-oracle/FREEZES.txt` is the baseline. `desync-pilot/FREEZES.txt` freezes this package after the dry-run. Neither freeze file lists itself.
5. **Sealed holdout, scored once.** The holdout is the 25 rule identifiers already scored in `desync-oracle/SCORE-SUMMARY.md`. This package does not score them again. A dry-run that disagreed with that file would exit 1 and write nothing.
6. **Skeptic pass.** `SKEPTIC.md` tries to knock the replay down. It does not edit the sealed score.

## What a run is allowed to do

Read `desync-oracle/` and hash the files named in `FREEZES.txt`. Write `desync-pilot/out/<profile>/`. Print the counts it just checked.

## What a run is not

A socket client. A server. A tarball walker. A second holdout. A place to put origin implementation text.

## Operator check

From the repository root, after a dry-run:

```bash
python3 desync-pilot/runner/audit.py --all --dry-run
( cd desync-oracle && sha256sum -c FREEZES.txt )
( cd desync-pilot && sha256sum -c FREEZES.txt )
desync-pilot/leak-scan.sh
```

The first command is the replay. The oracle `sha256sum -c` re-checks the baseline the runner already checked. The pilot `sha256sum -c` re-checks this package. `leak-scan.sh` exits 1 if a forbidden token is present.
