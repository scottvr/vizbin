#!/usr/bin/env bash
# A guided tour of vizbin over the bundled sample data.
# Images/gifs land in examples/output/ (gitignored); text output prints here.
#
#   bash scripts/demo.sh
#
# Override the binary or python with VIZBIN=... PYTHON=... if needed.
set -euo pipefail

cd "$(dirname "$0")/.."
VB="${VIZBIN:-vizbin}"
PY="${PYTHON:-python3}"
OUT=examples/output
SD=examples/sample-data
mkdir -p "$OUT"

"$PY" examples/make_sample_data.py

section() { echo; echo "== $* =="; }

# --- structure discovery ---------------------------------------------------

section "suggest: rank candidate record widths"
$VB suggest "$SD/records.bin" -v --top 6

section "infer: draft a record layout (0x47 sync + counter), then emit a parser"
$VB infer "$SD/records.bin"
$VB infer "$SD/records.bin" --format struct
$VB infer "$SD/records.bin" --json > "$OUT/records.layout.json"
echo "  (full JSON layout in $OUT/records.layout.json)"

section "profile: fingerprint + entropy-band regions (a heterogeneous blob)"
$VB profile "$SD/mixed.bin"

# --- projections & composition ---------------------------------------------

# --- image artifacts (files) ----------------------------------------------

section "render at the true 188-byte stride (BMP)"
$VB render "$SD/records.bin" -w 188 -m gray -o "$OUT/records.w188.gray.bmp"

section "SVG output: crisp, scalable, browser-ready (-o *.svg)"
$VB render "$SD/mixed.bin" -m byteclass -w 128 -o "$OUT/mixed.byteclass.svg"

section "contact sheet: four projections side by side (BMP)"
$VB contact "$SD/mixed.bin" --modes gray,byteclass,entropy,delta -w 128 \
    -o "$OUT/mixed.contact.bmp"

section "width-sweep animation around the record boundary (GIF)"
$VB animate "$SD/records.bin" --widths 180,184,188,192,196 -m gray \
    -o "$OUT/records.sweep.gif"

# --- the colourful part: rendered straight into the terminal ---------------

section "entropy, in the terminal (no viewer)"
$VB render "$SD/mixed.bin" -m entropy --term

section "byte classes, in the terminal"
$VB render "$SD/mixed.bin" -m byteclass --term

section "--rgb: entropy/delta/xor as R/G/B, in the terminal"
$VB render "$SD/mixed.bin" --rgb entropy,delta,xor --term

section "compose: the entropy of the xor stream, magma-painted"
$VB render "$SD/mixed.bin" -t xor,entropy --paint magma --term

section "text mode + find: window on 'CONFIG', readable glyphs in the terminal"
$VB render "$SD/mixed.bin" -m text --find "CONFIG" --length 1024 --term

# --- pinpoint & inspect ----------------------------------------------------

section "inspect: what one coordinate means, across modes"
$VB inspect "$SD/records.bin" -w 188 --modes gray,byteclass --offset 1
$VB inspect "$SD/records.bin" -w 188 --rgb entropy,delta,xor --offset 1

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
# --block 16 keeps the tail block-aligned across the insertion, so the diff stays
# clean (one replace + one insert) instead of smearing -- see docs for the caveat.
$VB diff "$SD/records.bin" "$OUT/records_v2.bin" --block 16
echo "  (the diff image, in the terminal:)"
$VB diff "$SD/records.bin" "$OUT/records_v2.bin" --block 16 --term

# --- reversible -----------------------------------------------------------

section "reversible payload BMP round-trip"
$VB bmp "$SD/random.bin" "$OUT/random.bmp"
$VB unbmp "$OUT/random.bmp" -o "$OUT/random.recovered.bin"
cmp "$SD/random.bin" "$OUT/random.recovered.bin" && echo "round-trip OK (byte-identical)"

echo
echo "Done. Images in $OUT/"
