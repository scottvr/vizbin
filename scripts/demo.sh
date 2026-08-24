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

section "render at the true 188-byte stride"
$VB render "$SD/records.bin" -w 188 -m gray -o "$OUT/records.w188.gray.bmp"

section "contact sheet: four projections of the mixed blob"
$VB contact "$SD/mixed.bin" --modes gray,byteclass,entropy,delta -w 128 \
    -o "$OUT/mixed.contact.bmp"

section "compose axes: any transform x any colorizer"
$VB render "$SD/mixed.bin" -t xor --paint magma           -o "$OUT/mixed.xor-magma.bmp"
$VB render "$SD/mixed.bin" -t xor,entropy --paint palette -o "$OUT/mixed.pipe.bmp"  # order matters

section "--rgb: three structural measures (entropy/delta/xor) in one image"
$VB render "$SD/mixed.bin" --rgb entropy,delta,xor -w 128 -o "$OUT/mixed.rgb.bmp"

section "text mode: readable ASCII glyphs, non-text as class tiles"
$VB render "$SD/hello.txt" -m text -w 48 -o "$OUT/hello.text.bmp"

section "width-sweep animation around the record boundary"
$VB animate "$SD/records.bin" --widths 180,184,188,192,196 -m gray \
    -o "$OUT/records.sweep.gif"

# --- pinpoint & inspect ----------------------------------------------------

section "find: window the render on a string (no offset-hunting)"
$VB render "$SD/hello.txt" -m text --find "pretend" --length 512 -o "$OUT/hello.find.bmp"

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

# --- reversible + terminal -------------------------------------------------

section "reversible payload BMP round-trip"
$VB bmp "$SD/random.bin" "$OUT/random.bmp"
$VB unbmp "$OUT/random.bmp" -o "$OUT/random.recovered.bin"
cmp "$SD/random.bin" "$OUT/random.recovered.bin" && echo "round-trip OK (byte-identical)"

section "--term: render straight into the terminal (no image viewer)"
$VB render "$SD/mixed.bin" --rgb entropy,delta,xor --term

echo
echo "Done. Images in $OUT/"
