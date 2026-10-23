#!/bin/bash
# Run from inputs/flakecert-attempt-to-fix. Expect: self-check 0, synthetic-good 0, every mutant 1.
set -u
r(){ python3 -B gate_attempt_to_fix.py "$@" > /tmp/atf.$$ ; e=$?; grep -E "^(FAIL|INFO|GATE)" /tmp/atf.$$ | cut -c1-170; echo "exit=$e"; return $e; }
echo "== S0 self-check: expect 0"; r; s0=$?
echo "== G1 synthetic-good (gate-logic fixture, not Ruby): expect 0"; r --results controls/synthetic-good-results.json; g1=$?
bad=0
for m in mutant-wrong-fix-accepted mutant-plain-retry-only mutant-schedule-drift mutant-real-fix-edits-model; do
  echo "== $m: expect 1"; r --results controls/$m.json; [ $? -eq 1 ] || bad=1
done
rm -f /tmp/atf.$$
[ $s0 -eq 0 ] && [ $g1 -eq 0 ] && [ $bad -eq 0 ] && { echo "CONTROLS OK"; exit 0; }; echo "CONTROLS BROKEN"; exit 1
