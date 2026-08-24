#!/usr/bin/env bash
# A guided tour of vizbin over the bundled sample data.
# Images/gifs land in examples/output/ (gitignored); text output prints here.
#
#   bash scripts/demo.sh            # pauses between steps (great for screen-recording)
#   NOPAUSE=1 bash scripts/demo.sh  # run straight through, no pauses
#
# Override the binary or python with VIZBIN=... PYTHON=... if needed.
set -euo pipefail

cd "$(dirname "$0")/.."
VB="${VIZBIN:-vizbin}"
PY="${PYTHON:-python3}"
OUT=./examples/output
SD=./examples/sample-data
mkdir -p "$OUT"

# Pause between steps so a screen recording can breathe. Auto-skipped when stdin
# isn't a terminal (piped/redirected/CI) or when NOPAUSE is set.
pause() {
  if [ -t 0 ] && [ -z "${NOPAUSE:-}" ]; then
    printf '\n\033[2m  -- press a key to continue --\033[0m'
    read -rsn1 _ 2>/dev/null || true
    printf '\n'
  fi
}

# Echo a command (as you'd type it), then run it -- so the recording has context.
run() { printf '\033[1m$ %s\033[0m\n' "$*"; "$@"; }

_first=1
section() {
  [ -n "${_first:-}" ] || pause
  _first=
  printf '\n\033[36m== %s ==\033[0m\n' "$*"   # cyan section headers
}

section "generating ${SD} files"
"$PY" examples/make_sample_data.py

# --- structure discovery ---------------------------------------------------

section "suggest: rank candidate record widths"
run $VB suggest "$SD/records.bin" -v --top 6

section "infer: draft a record layout (0x47 sync + counter), then emit a parser"
run $VB infer "$SD/records.bin"
run $VB infer "$SD/records.bin" --format struct

# --- image artifacts (files) ----------------------------------------------

section "render at the true 188-byte stride (BMP)"
run $VB render "$SD/records.bin" -w 188 -m gray -o "$OUT/records.w188.gray.bmp"

section "width-sweep animation around the record boundary (GIF)"
run $VB animate "$SD/records.bin" --widths 176,180,184,188,192,196,200 -m gray --fps 3 \
    -o "$OUT/records.sweep.gif"

section "profile: fingerprint + entropy-band regions (a heterogeneous blob)"
run $VB profile "$SD/mixed.bin"

section "SVG output: crisp, scalable, browser-ready (-o *.svg)"
run $VB render "$SD/mixed.bin" -m byteclass -w 128 -o "$OUT/mixed.byteclass.svg"

section "contact sheet: four projections side by side (BMP)"
run $VB contact "$SD/mixed.bin" --modes gray,byteclass,entropy,delta -w 128 -o "$OUT/mixed.contact.bmp"

# --- the colourful part: rendered straight into the terminal ---------------

section "entropy, in the terminal (no viewer)"
run $VB render "$SD/mixed.bin" -m entropy --term

section "byte classes, in the terminal"
run $VB render "$SD/mixed.bin" -m byteclass --term

section "--rgb: entropy/delta/xor as R/G/B, in the terminal"
run $VB render "$SD/mixed.bin" --rgb entropy,delta,xor --term

section "compose: the entropy of the xor stream, magma-painted"
run $VB render "$SD/mixed.bin" -t xor,entropy --paint magma --term

section "text mode + find: window on 'CONFIG', readable glyphs in the terminal"
run $VB render "$SD/mixed.bin" -m text --find "CONFIG" --length 1024 --term

# --- pinpoint & inspect ----------------------------------------------------

section "inspect: what one coordinate means, across modes"
run $VB inspect "$SD/records.bin" -w 188 --modes gray,byteclass --offset 1
run $VB inspect "$SD/records.bin" -w 188 --rgb entropy,delta,xor --offset 1

# --- diff ------------------------------------------------------------------

section "diff: shift-tolerant structural diff of two versions"
cp "$SD/records.bin" "$OUT/records_v2.bin"
"$PY" - "$OUT/records_v2.bin" <<'PY'
import sys
p = sys.argv[1]
d = bytearray(open(p, "rb").read())
d[0x400:0x410] = b"\x00" * 16          # an in-place patch (16 bytes)
d[0x1000:0x1000] = b"PATCHED_16BYTES!"  # a 16-byte insertion -> shifts the tail
open(p, "wb").write(bytes(d))
PY
run $VB diff "$SD/records.bin" "$OUT/records_v2.bin" --block 16
run $VB diff "$SD/records.bin" "$OUT/records_v2.bin" --block 16 --term

# --- reversible -----------------------------------------------------------

section "reversible payload BMP round-trip"
run $VB bmp "$SD/random.bin" "$OUT/random.bmp"
run $VB unbmp "$OUT/random.bmp" -o "$OUT/random.recovered.bin"
cmp "$SD/random.bin" "$OUT/random.recovered.bin" && echo "  round-trip OK (byte-identical)"

pause
echo
echo "Done. Images in $OUT/"
