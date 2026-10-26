#!/bin/sh
# Scan desync-pilot text, file bytes, file names, and diffs.
# Fragments are joined at runtime so this file does not store a
# contiguous forbidden literal.
set -eu

here=$(CDPATH= cd -- "$(dirname "${0}")" && pwd)
repo=$(git -C "$here" rev-parse --show-toplevel)

join() {
  printf '%s' "$@"
}

a=$(join 'de' 'compil')
b=$(join '.de' 'compiled' '.cs')
c=$(join 'c5-' 'kestrel')
d=$(join 'c8b-' 'conformance')
e=$(join 'c8c-' 'haproxy')
f=$(join 'flakecert-' 'archive')
g=$(join 'gh' 'p_')
h=$(join 'gh' 'o_')
i=$(join 'github_' 'pat_')
j=$(join 'Core.' 'Internal')
k=$(join 'Microsoft\.AspNetCore\.Server\.Kestrel\.[A-Za-z0-9._]*' 'Internal')
n1=$(join 'Port' 'Swigger')
n2=$(join 'Tena' 'ble')
n3=$(join 'Rapi' 'd7')
n4=$(join 'Detec' 'tify')
n5=$(join 'Tetra' 'te')
n6=$(join 'Cloud' 'flare')
n7=$(join 'Http' 'Parser')

fail=0

report() {
  hits=${2}
  if [ -n "$hits" ]; then
    printf '%s\n' "${1}"
    printf '%s\n' "$hits"
    fail=1
  fi
}

text_fixed() {
  hits=$(grep -R -I -n -F -e "${1}" "$here" || true)
  report "text fixed hit" "$hits"
}

text_re() {
  hits=$(grep -R -I -n -E -e "${1}" "$here" || true)
  report "text regex hit" "$hits"
}

byte_scan() {
  python3 - "$here" "$a" "$b" "$c" "$d" "$e" "$f" "$g" "$h" "$i" "$j" "$n1" "$n2" "$n3" "$n4" "$n5" "$n6" "$n7" << 'PY'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
needles = [item.encode() for item in sys.argv[2:]]
bad = False
for path in root.rglob("*"):
    rel = str(path.relative_to(root))
    rel_b = rel.encode()
    data = b""
    if path.is_file():
        data = path.read_bytes()
    for needle in needles:
        if needle in rel_b:
            print(f"name hit {rel} len {len(needle)}")
            bad = True
        if data and needle in data:
            print(f"byte hit {rel} offset {data.find(needle)} len {len(needle)}")
            bad = True
sys.exit(0)
PY
}

text_fixed "$a"
text_fixed "$b"
text_fixed "$c"
text_fixed "$d"
text_fixed "$e"
text_fixed "$f"
text_fixed "$g"
text_fixed "$h"
text_fixed "$i"
text_fixed "$j"
text_fixed "$n1"
text_fixed "$n2"
text_fixed "$n3"
text_fixed "$n4"
text_fixed "$n5"
text_fixed "$n6"
text_fixed "$n7"
text_re "$k"

byte_hits=$(byte_scan || true)
report "byte scan" "$byte_hits"

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
{
  git -C "$repo" diff -- desync-pilot || true
  git -C "$repo" diff --cached -- desync-pilot || true
} > "$tmp"

diff_one() {
  kind=${2}
  if [ "$kind" = re ]; then
    hits=$(grep -n -E -e "${1}" "$tmp" || true)
  else
    hits=$(grep -n -F -e "${1}" "$tmp" || true)
  fi
  report "diff hit" "$hits"
}

diff_one "$a" f
diff_one "$b" f
diff_one "$c" f
diff_one "$d" f
diff_one "$e" f
diff_one "$f" f
diff_one "$g" f
diff_one "$h" f
diff_one "$i" f
diff_one "$j" f
diff_one "$k" re
diff_one "$n1" f
diff_one "$n2" f
diff_one "$n3" f
diff_one "$n4" f
diff_one "$n5" f
diff_one "$n6" f
diff_one "$n7" f

if [ "$fail" -ne 0 ]; then
  printf '%s\n' "leak-scan: FAIL"
  exit 1
fi

printf '%s\n' "leak-scan: scanned desync-pilot text, file bytes, file names, and diffs"
printf '%s\n' "leak-scan: company-name needles joined at runtime: 6 unpublished-planning names, plus the private-pack path tokens"
printf '%s\n' "leak-scan: clean"
exit 0
