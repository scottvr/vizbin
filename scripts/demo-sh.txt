#!/usr/bin/env bash
# A quick tour of vizbin over the bundled sample data.
# Outputs land in examples/output/ (gitignored).
set -euo pipefail

cd "$(dirname "$0")/.."
VB="${VIZBIN:-vizbin}"
PY="${PYTHON:-python3}"
OUT=examples/output
mkdir -p "$OUT"

"$PY" examples/make_sample_data.py

echo
echo "== suggest widths for the record file =="
$VB suggest examples/sample-data/records.bin -v --top 6

echo
echo "== render the record file at its true stride (188) =="
$VB render examples/sample-data/records.bin -w 188 -m gray -o "$OUT/records.w188.gray.bmp"

echo
echo "== contact sheet of projections over the mixed blob =="
$VB contact examples/sample-data/mixed.bin --modes gray,byteclass,entropy,delta -w 128 \
    -o "$OUT/mixed.contact.modes.bmp"

echo
echo "== width-sweep animation around the record boundary =="
$VB animate examples/sample-data/records.bin --widths 180,184,188,192,196 -m gray \
    -o "$OUT/records.sweep.gif"

echo
echo "== reversible payload BMP round-trip =="
$VB bmp examples/sample-data/random.bin "$OUT/random.bmp"
$VB unbmp "$OUT/random.bmp" -o "$OUT/random.recovered.bin"
cmp examples/sample-data/random.bin "$OUT/random.recovered.bin" \
    && echo "round-trip OK (byte-identical)"

echo
echo "Done. See $OUT/"
