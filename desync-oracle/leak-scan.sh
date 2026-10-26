#!/bin/sh
# Text scan, byte scan of every file, and the staged diff.
# Fragments are joined at runtime so this file does not store a
# contiguous forbidden literal. Gzip pins are included in the byte scan.
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
e=$(join 'c8c-' 'haproxy-' 'kestrel')
f=$(join 'flakecert-' 'archive')
g=$(join 'gh' 'p_')
h=$(join 'gh' 'o_')
i=$(join 'github_' 'pat_')
j=$(join 'Core.' 'Internal')
k=$(join 'Microsoft\.AspNetCore\.Server\.Kestrel\.[A-Za-z0-9._]*' 'Internal')

p=$(join 'S' 'KU')
q=$(join 'US' 'D')
r=$(join 'pri' 'ce')
s=$(join 'dol' 'lar')
t=$(join 'mon' 'ey')
u='\$[0-9]'

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

text_fixed_i() {
  hits=$(grep -R -I -n -i -F -e "${1}" "$here" || true)
  report "text fixed hit" "$hits"
}

byte_scan() {
  A="$a" B="$b" C="$c" D="$d" E="$e" F="$f" G="$g" H="$h" I="$i" J="$j" \
  python3 - "$here" << 'PY'
import os, pathlib, sys
root = pathlib.Path(sys.argv[1])
needles = [os.environ[name].encode() for name in list("ABCDEFGHIJ")]
bad = False
for path in root.rglob("*"):
    if not path.is_file():
        continue
    data = path.read_bytes()
    for needle in needles:
        idx = data.find(needle)
        if idx >= 0:
            rel = path.relative_to(root)
            print(f"byte hit {rel} offset {idx} len {len(needle)}")
            bad = True
sys.exit(0 if not bad else 0)
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
text_re "$k"
text_fixed "$p"
text_fixed "$q"
text_fixed_i "$r"
text_fixed_i "$s"
text_fixed_i "$t"
text_re "$u"

byte_hits=$(byte_scan || true)
report "byte scan" "$byte_hits"

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
git -C "$repo" diff --cached -- desync-oracle > "$tmp" || true

diff_one() {
  kind=${2}
  if [ "$kind" = re ]; then
    hits=$(grep -n -E -e "${1}" "$tmp" || true)
  elif [ "$kind" = i ]; then
    hits=$(grep -n -i -F -e "${1}" "$tmp" || true)
  else
    hits=$(grep -n -F -e "${1}" "$tmp" || true)
  fi
  report "staged diff hit" "$hits"
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
diff_one "$p" f
diff_one "$q" f
diff_one "$r" i
diff_one "$s" i
diff_one "$t" i
diff_one "$u" re

if [ "$fail" -ne 0 ]; then
  printf '%s\n' "leak-scan: FAIL"
  exit 1
fi

printf '%s\n' "leak-scan: scanned desync-oracle text, file bytes, and staged diff"
printf '%s\n' "leak-scan: clean"
exit 0
