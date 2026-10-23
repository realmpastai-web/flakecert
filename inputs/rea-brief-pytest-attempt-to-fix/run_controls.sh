#!/bin/bash
# Works from any cwd. Expect: self-check 0, tampered sdist 1, synthetic-good 0, every results mutant 1.
set -u
cd "$(dirname "$0")" || exit 2
r(){ python3 -B gate_pytest_attempt_to_fix.py "$@" > /tmp/patf.$$ ; e=$?; grep -E "^(FAIL|INFO|GATE)" /tmp/patf.$$ | cut -c1-170; echo "exit=$e"; return $e; }
echo "== S0 self-check: expect 0"; r; s0=$?
echo "== T1 tampered rerunfailures sdist (seed line added): expect 1"; r --rea-dir controls/rea-tampered; t1=$?
echo "== G1 synthetic-good (gate-logic fixture, not pytest): expect 0"; r --results controls/synthetic-good-results.json; g1=$?
bad=0
for m in mutant-wrong-fix-accepted mutant-plain-retry-only mutant-schedule-drift mutant-real-fix-edits-app mutant-omitted-env-and-seed mutant-rerun-plugin-installed mutant-fabricated-sig; do
  echo "== $m: expect 1"; r --results controls/$m.json; [ $? -eq 1 ] || bad=1
done
rm -f /tmp/patf.$$
[ $s0 -eq 0 ] && [ $t1 -eq 1 ] && [ $g1 -eq 0 ] && [ $bad -eq 0 ] && { echo "CONTROLS OK"; exit 0; }; echo "CONTROLS BROKEN"; exit 1
