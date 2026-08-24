#!/usr/bin/env bash
# Generate the images for docs/GALLERY.md.
#
# vizbin is an imaging tool, so its docs should show pictures. This renders a
# curated set of BMPs from deterministic sample data and converts them to PNG in
# docs/images/. Re-run any time to refresh the gallery.
#
#   bash scripts/gen-docs-images.sh
#
# Requires: vizbin on PATH (pip install -e .) and an image converter --
# `sips` (built in on macOS) or ImageMagick `magick`/`convert`.

set -uo pipefail
cd "$(dirname "$0")/.."

OUT=docs/images
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT"

# -- pick an image converter -------------------------------------------------
if command -v sips >/dev/null 2>&1; then
  to_png() { sips -s format png "$1" --out "$2" >/dev/null 2>&1; }
elif command -v magick >/dev/null 2>&1; then
  to_png() { magick "$1" "$2"; }
elif command -v convert >/dev/null 2>&1; then
  to_png() { convert "$1" "$2"; }
else
  echo "error: need 'sips' (macOS) or ImageMagick ('magick'/'convert') to make PNGs" >&2
  exit 1
fi

viz() { python -m vizbin "$@"; }

emit() {  # emit <label> <bmp>  -> docs/images/<label>.png
  if [ -f "$2" ]; then
    to_png "$2" "$OUT/$1.png" && echo "  $OUT/$1.png"
  else
    echo "  ! skipped $1 (no $2)" >&2
  fi
}

echo "generating sample data ..."
# mixed_regions.bin etc. (deterministic) via the UAT harness
python scripts/uat.py --outdir "$TMP/uat" >/dev/null 2>&1
MIX="$TMP/uat/mixed_regions.bin"

# a tar of vizbin's own source -> a great 'text mode' subject (readable code +
# tar headers + NUL padding)
tar -cf "$TMP/src.tar" src/vizbin/*.py 2>/dev/null

# two "firmware versions" for the diff demo: an in-place patch + an insertion
python - "$TMP" <<'PY'
import random, sys
tmp = sys.argv[1]
r = random.Random(7)
base = bytes(r.randrange(256) for _ in range(8192))
open(f"{tmp}/fw_v1.bin", "wb").write(base)
v2 = bytearray(base)
v2[0x400:0x440] = bytes(r.randrange(256) for _ in range(0x40))  # in-place change
v2[0x1000:0x1000] = b"INSERTED_16BYTES"                          # insertion (shift)
open(f"{tmp}/fw_v2.bin", "wb").write(bytes(v2))
PY

echo "rendering ..."
viz render "$MIX" -m gray      -w 160 -o "$TMP/gray.bmp"      --no-hints >/dev/null; emit render-gray "$TMP/gray.bmp"
viz render "$MIX" -m byteclass -w 160 -o "$TMP/bc.bmp"       --no-hints >/dev/null; emit render-byteclass "$TMP/bc.bmp"
viz render "$MIX" -m entropy   -w 160 -o "$TMP/ent.bmp"      --no-hints >/dev/null; emit render-entropy "$TMP/ent.bmp"
viz render "$MIX" -m nibble    -w 160 -o "$TMP/nib.bmp"      --no-hints >/dev/null; emit render-nibble "$TMP/nib.bmp"
viz render "$MIX" --rgb entropy,delta,xor -w 160 -o "$TMP/rgb.bmp" --no-hints >/dev/null; emit render-rgb "$TMP/rgb.bmp"
viz render "$MIX" -t xor,entropy --paint magma -w 160 -o "$TMP/pipe.bmp" --no-hints >/dev/null; emit render-pipe "$TMP/pipe.bmp"
# text mode: window on a readable code section via --find (stable, not a hardcoded
# offset) instead of rendering the whole tar (~1.8MB image)
viz render "$TMP/src.tar" -m text --find "def to_dict" --length 6000 -w 80 \
    -o "$TMP/text.bmp" --no-hints >/dev/null; emit render-text "$TMP/text.bmp"
viz contact "$MIX" --modes gray,byteclass,entropy,delta -w 160 -o "$TMP/contact.bmp" >/dev/null; emit contact "$TMP/contact.bmp"
viz diff "$TMP/fw_v1.bin" "$TMP/fw_v2.bin" -o "$TMP/diff.bmp" -w 128 >/dev/null; emit diff "$TMP/diff.bmp"

echo
echo "done -> $OUT/"
echo "review the images, then: git add docs/images && git commit"
