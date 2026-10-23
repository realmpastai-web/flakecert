#!/bin/bash
# Works from any cwd. Expect: self-check 0, tampered sdist 1, synthetic-good 0, every results mutant 1, real PR #7 results 1.
set -u
cd "$(dirname "$0")" || exit 2
G=gate_pytest_attempt_to_fix_v2.py
r(){ python3 -B $G "$@" > /tmp/patf2.$$ ; e=$?; grep -E "^(FAIL|INFO|GATE)" /tmp/patf2.$$ | cut -c1-170; echo "exit=$e"; return $e; }
echo "== S0 self-check: expect 0"; r; s0=$?
echo "== T1 tampered rerunfailures sdist (v1 control dir): expect 1"; r --rea-dir ../rea-brief-pytest-attempt-to-fix/controls/rea-tampered; t1=$?
echo "== G1 synthetic-good (gate-logic fixture, not pytest; wrong_fix carries its own line-7 sig): expect 0"; r --results controls/synthetic-good-results.json; g1=$?
bad=0
for m in mutant-wrong-fix-accepted mutant-plain-retry-only mutant-schedule-drift mutant-real-fix-edits-app mutant-omitted-env-and-seed mutant-rerun-plugin-installed mutant-fabricated-sig \
         v2-m1-tb-norm-not-hashing-to-sig v2-m2-wrong-fix-copies-cert-sig v2-m3a-line-moved-different-exception v2-m3b-line-moved-different-message \
         v2-m4-non-test-frame-changed v2-m5-real-fix-still-fails v2-m6-line-shift-wrong-size pr7-3ec5eb8-results-no-tb-norm; do
  echo "== $m: expect 1"; r --results controls/$m.json; [ $? -eq 1 ] || bad=1
done
rm -f /tmp/patf2.$$
[ $s0 -eq 0 ] && [ $t1 -eq 1 ] && [ $g1 -eq 0 ] && [ $bad -eq 0 ] && { echo "CONTROLS OK"; exit 0; }; echo "CONTROLS BROKEN"; exit 1
