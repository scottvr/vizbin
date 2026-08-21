# vizbin

**Take a blob. Pretend it is an image. Vary the lie until the truth starts to show.**

`vizbin` is a small, format-agnostic tool that renders arbitrary byte streams as
images so that hidden structure in unknown data becomes visible. It's useful for
poking at executables, firmware, memory dumps, database files, packet captures,
compressed/encrypted payloads, and any other blob you don't have a parser for
yet.

Two ideas drive it:

- **Width is a probe.** Choosing an image width is really a *hypothesis* about
  stride, record length, page size, or row width. The right width makes repeated
  records, tables, and section boundaries snap into alignment.
- **Projection is a probe.** The same bytes viewed as grayscale, RGB, entropy,
  byte-class, deltas, or bitplanes reveal different classes of structure.

Vary both and let human vision do the first pass of reconnaissance.

It grew out of a shell one-liner that `cat`'d a file's bytes into a hand-built
BMP header. That trick survives here as the reversible `bmp` mode, where payload
byte *n* lands at file offset `54 + n` — so an interesting region in the picture
maps straight back to a source offset.

## Design goals & dependencies

**Zero runtime dependencies.** The whole tool is pure Python standard library:
BMP is written by hand, and the animated GIF encoder (LZW and all) is
implemented from scratch. `ffmpeg` is used *only* if you ask for `--format mp4`,
and is entirely optional.

## Install

```sh
python -m venv .venv && source .venv/bin/activate
pip install -e .            # console script: vizbin
# or run without installing:
python -m vizbin --help
```

Requires Python 3.9+.

## Commands

```
vizbin
|-- render     one image at a chosen width/mode
|-- sweep      many widths, one file each
|-- contact    a labelled grid of widths / modes / phases
|-- animate    a width sweep as an animated GIF (or mp4 via ffmpeg)
|-- suggest    candidate widths, ranked by row coherence
|-- inspect    map between byte offsets and pixel coordinates
|-- bmp        reversible "payload as pixels" BMP
`-- unbmp      recover the payload from a bmp
```

### render

```sh
vizbin render foo.bin                          # grayscale, square-ish width
vizbin render foo.bin -w 256 -m gray
vizbin render foo.bin -w 320 -m raw-rgb --phase 1
vizbin render foo.bin -w 128 -m byteclass
vizbin render foo.bin -w 128 -m entropy --window 512
```

New to it? Start with the [exploration field guide](docs/EXPLORING.md) — a
suggestive "look for / if this then try that" walkthrough for poking at a blob
(or an image) you don't understand yet.

Window a region without extracting it first (great for reversing):

```sh
vizbin render mystery.bin --offset 0x12000 --length 65536 -w 256
```

### sweep

```sh
vizbin sweep foo.bin --widths 64,80,128,256,512
vizbin sweep foo.bin --widths powers2 -m gray --outdir out/
vizbin sweep foo.bin --widths records -m byteclass
```

### contact sheet

Compare many widths, or many modes, or many phases, side by side:

```sh
vizbin contact foo.bin --widths 64,128,256,512 -m gray
vizbin contact foo.bin --modes gray,byteclass,entropy,delta -w 256
vizbin contact foo.bin --phases 0,1,2 -w 320
```

### animate

Watch structure emerge as width changes:

```sh
vizbin animate foo.bin --from 64 --to 1024 --step 4 -m gray
vizbin animate foo.bin --widths 180,184,188,192 -m gray
vizbin animate foo.bin --from 64 --to 512 --format mp4     # needs ffmpeg
```

### suggest

Rank candidate widths by adjacent-row coherence (a cheap structural score):

```sh
vizbin suggest foo.bin
vizbin suggest foo.bin -v --top 20
```

```
Width  Family     Score   Why
-----  ---------  ------  ----------------------------------------
188    records    0.95    likely fixed-record size; strong adjacent-row coherence
256    powers2    0.81    machine-ish power of two; strong adjacent-row coherence
512    storage    0.78    common page/block size; strong adjacent-row coherence
```

When the input is substantially printable, `suggest` adds an advisory line
pointing at the `text` mode (it never switches mode for you — you pick the
hypothesis):

```
hint: ~100% of bytes are printable/whitespace -- this looks like text; try  -m text
```

### inspect (offset <-> pixel mapping)

```sh
vizbin inspect -w 256 -m gray --offset 0x12340
vizbin inspect -w 256 -m gray --x 12 --y 40
vizbin inspect -w 256 -m raw-rgb --phase 1 --offset 100
```

If you rendered a windowed region, pass `--base <offset>` so the math accounts
for where the render started.

For `text` mode each byte is an `8*scale`-pixel cell rather than a single pixel,
so pass the same `--scale` you rendered with. `inspect` then reports the cell's
pixel box (offset -> cell) and resolves any pixel inside a cell back to its byte:

```sh
vizbin inspect -w 64 -m text --scale 3 --offset 260   # -> cell col=4, row=4 (pixels x=[96,120) y=[96,120))
vizbin inspect -w 64 -m text --scale 3 --x 110 --y 110 # -> 1 byte at offset 260
```

#### Mode-specific readouts

Pass the **source file** and `inspect` also reports what the coordinate *means*
in the chosen mode — the character in `text`, the RGB source bytes in `raw-rgb`,
the XOR operands and result in `xor`, the selected bit in `bitplane`, the local
entropy window in `entropy`, the delta in `delta`, and so on. Without a file it
stays pure geometry.

```sh
vizbin inspect archive.tar -w 64 -m text    --offset 260   # -> byte 0x61 (97) = 'a'
vizbin inspect archive.tar -w 64 -m entropy --offset 260   # -> entropy 1.42 bits over 256-byte window [5-260]
vizbin inspect archive.tar -w 64 -m xor     --offset 260 --k 4  # -> byte 0x61 (97) XOR @256 0x00 (0) = 0x61 (97)
vizbin inspect archive.tar -w 64 -m raw-rgb --offset 260   # -> pixel 86 -> R@258=0x73 G@259=0x74 B@260=0x61 -> "sta"
```

`raw-rgb` readouts add an inline ASCII gloss (`-> "sta"`) when the pixel's three
bytes are all printable — colour channels are often hex for a string.

When you inspect a non-`text` mode and the bytes around the offset look like text,
`inspect` whispers what they spell (and `render` nudges you toward `-m text` when
the whole region is printable). It's advisory only, and `--no-hints` silences it:

```
  psst: bytes [84-116] look like text: " __future__ import annotations..i"
```

The readout is computed to match exactly what that projection rendered
(predecessors, windows, and phase are taken **region-relative to `--base`**), and
it reads only a bounded window around the offset, so it stays a cheap point query.
Pass the mode's parameter when it has one: `--k` (xor), `--window` (entropy),
`--plane` (bitplane), `--phase` (raw-rgb).

Stack several modes for one coordinate with `--modes` — each projection is an
independent view of the same offset, so the readouts are additive:

```sh
vizbin inspect archive.tar -w 64 --modes raw-rgb,text,gray --offset 260
#   offset 0x104 (260) [w=64]
#     [raw-rgb] pixel 86 -> R@258=0x73 G@259=0x74 B@260=0x61 -> "sta"
#     [text   ] byte 0x61 (97) = 'a'
#     [gray   ] byte 0x61 (97) -> gray 97
```

### bmp / unbmp (reversible payload mode)

```sh
vizbin bmp foo.bin foo.bmp        # payload byte n is at file offset 54 + n
vizbin unbmp foo.bmp -o foo.bin   # byte-for-byte recovery
vizbin unbmp foo.bmp > foo.bin
```

The original length is stashed in the BMP header's reserved field, so recovery is
exact even when the payload ends in `NUL` bytes. Width must be divisible by 4 in
this mode (so BMP's row padding never breaks the contiguous-payload property);
the default width is chosen automatically.

The self-referential experiment from the design notes works too:

```sh
vizbin render IMG_0001.BMP -m raw-rgb --width <w>            # header "scar" + echo of the image
vizbin render IMG_0001.BMP -m raw-rgb --width <w> --offset 54   # skip the 54-byte header
```

## Projections

| mode        | bytes/pixel | what it shows |
|-------------|-------------|---------------|
| `gray`      | 1 | raw byte periodicity, text, padding |
| `raw-rgb`   | 3 | broad texture, section boundaries (phase-sensitive) |
| `byteclass` | 1 | nul / 0xff / whitespace / ascii / control / high-bit |
| `entropy`   | 1 | padding vs text vs code vs compressed/encrypted |
| `delta`     | 1 | slowly varying runs, transitions |
| `xor`       | 1 | periodicity / repeated records (`--k` lag) |
| `bitplane`  | 1 | a single bit across all bytes (`--plane 0..7`) |
| `nibble`    | 1 | high nibble -> red, low nibble -> green |
| `text`      | 1 cell | printable ASCII as glyphs, non-text bytes as class tiles |

### text mode

`text` (aliases `ascii`, `txt`) is a *grid* renderer rather than a
one-byte-one-pixel projection: each byte becomes an 8x8 cell. Printable ASCII is
drawn as its glyph so text regions are literally readable, while everything else
(NUL, controls, tab/newline, high-bit, `0xFF`) is painted as a solid tile in its
`byteclass` colour — so the binary structure wrapped around the text still pops.
Think of it as a visual `strings` that keeps the surrounding scaffolding visible.

```bash
vizbin render archive.tar -m text -w 64            # 64 bytes per row
vizbin render archive.tar -m text -w 64 --scale 3  # 3x magnified glyphs
vizbin render firmware.bin -m text --mono-text     # non-printables left blank
```

Good on tar members, PEM/cert blobs, embedded scripts, and the
`.rodata`/`.rdata` string tables of executables (not `.text` — that is machine
code and renders as a wall of colour, which is itself a useful tell). `--width`
is bytes-per-row just like the 1-byte modes, so `contact --modes gray,text -w 64`
lines the two up byte-for-byte. The glyphs come from a vendored public-domain
8x8 font (`font8x8.py`), so vizbin stays pure-stdlib.

## Width families

`square`, `common`, and the named families `powers2`, `storage`, `textish`,
`screenish`, `records`. Use them anywhere a `--widths` argument is accepted, or
give an explicit comma list (values may be hex, e.g. `0x200`).

## Output naming

Outputs encode their parameters so casual CLI use stays tidy:

```
foo.w256.gray.bmp
foo.w320.rawrgb.phase1.bmp
foo.contact.gray.widths.bmp
foo.anim.gray.64-1024.gif
```

## Development

```sh
pip install -e '.[dev]'
pytest
```

## ACKNOWLEDGEMENTS
the 8x8 bitmap font used for text rendering is from https://github.com/dhepper/font8x8
which itself borrowed from some old IBM assembly code:
```
Credits
=======
These header files are directly derived from an assembler file fetched from:
http://dimensionalrift.homelinux.net/combuster/mos3/?p=viewsource&file=/modules/gfx/font8_8.asm

Original header:

; Summary: font8_8.asm
; 8x8 monochrome bitmap fonts for rendering
;
; Author:
;     Marcel Sondaar
;     International Business Machines (public domain VGA fonts)
;
; License:
;     Public Domain
;
```

It's pixels all the way down.
