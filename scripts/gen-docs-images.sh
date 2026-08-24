#!/usr/bin/env bash
# Generate the images for docs/GALLERY.md.
#
# vizbin renders each tile to SVG, then rasterizes it to a crisp PNG in
# docs/images/. Going through SVG (vector, shape-rendering=crispEdges) and
# rasterizing at a large width gives sharp pixels with no upscaling blur, at a
# fraction of the size of embedding the SVG directly. Re-run any time.
#
#   bash scripts/gen-docs-images.sh
#
# Requires: vizbin on PATH (pip install -e .) and an SVG rasterizer --
# `rsvg-convert` (librsvg) or ImageMagick `magick`.

set -uo pipefail
cd "$(dirname "$0")/.."

OUT=docs/images
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT"

# -- pick an SVG rasterizer --------------------------------------------------
if command -v rsvg-convert >/dev/null 2>&1; then
  svg2png() { rsvg-convert -w "$3" "$1" -o "$2"; }
elif command -v magick >/dev/null 2>&1; then
  svg2png() { magick -background none "$1" -resize "${3}x" "$2"; }
else
  echo "error: need 'rsvg-convert' (librsvg) or ImageMagick 'magick' to rasterize SVG" >&2
  exit 1
fi

viz() { python -m vizbin "$@"; }

emit() {  # emit <label> <svg> [width]
  local label="$1" svg="$2" width="${3:-800}"
  if [ -f "$svg" ]; then
    svg2png "$svg" "$OUT/$label.png" "$width" && echo "  $OUT/$label.png"
  else
    echo "  ! skipped $label (no $svg)" >&2
  fi
}

echo "generating sample data ..."
python scripts/uat.py --outdir "$TMP/uat" >/dev/null 2>&1
MIX="$TMP/uat/mixed_regions.bin"

# a tar of vizbin's own source -> a great 'text mode' subject
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
viz render "$MIX" -m gray      -w 160 -o "$TMP/gray.svg"  --no-hints >/dev/null; emit render-gray "$TMP/gray.svg"
viz render "$MIX" -m byteclass -w 160 -o "$TMP/bc.svg"    --no-hints >/dev/null; emit render-byteclass "$TMP/bc.svg"
viz render "$MIX" -m entropy   -w 160 -o "$TMP/ent.svg"   --no-hints >/dev/null; emit render-entropy "$TMP/ent.svg"
viz render "$MIX" -m nibble    -w 160 -o "$TMP/nib.svg"   --no-hints >/dev/null; emit render-nibble "$TMP/nib.svg"
viz render "$MIX" --rgb entropy,delta,xor -w 160 -o "$TMP/rgb.svg" --no-hints >/dev/null; emit render-rgb "$TMP/rgb.svg"
viz render "$MIX" -t xor,entropy --paint magma -w 160 -o "$TMP/pipe.svg" --no-hints >/dev/null; emit render-pipe "$TMP/pipe.svg"
viz render "$TMP/src.tar" -m text --find "def to_dict" --length 6000 -w 80 \
    -o "$TMP/text.svg" --no-hints >/dev/null; emit render-text "$TMP/text.svg" 960
viz contact "$MIX" --modes gray,byteclass,entropy,delta -w 160 -o "$TMP/contact.svg" >/dev/null; emit contact "$TMP/contact.svg" 1000
viz diff "$TMP/fw_v1.bin" "$TMP/fw_v2.bin" -o "$TMP/diff.svg" -w 128 >/dev/null; emit diff "$TMP/diff.svg"

echo
echo "done -> $OUT/ (crisp PNGs rasterized from SVG)"
echo "review the images, then: git add docs/images && git commit"
