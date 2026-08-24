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

**See it in action:** the [gallery](docs/GALLERY.md) shows real renders — the
projections, channel composition, contact sheets, text mode, and the binary diff.

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
|-- infer      draft a record/field layout from repeating structure
|-- profile    structural fingerprint (entropy, byte classes, regions)
|-- diff       structural/visual diff of two binaries
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

New to it? Start with the [exploration guide](docs/QUICKSTART-TUTORIAL.md) — a
guided tour of small experiments that show what vizbin can see, and how changing
one assumption changes the picture.

Stay in the terminal — `--term` renders straight into the console with 24-bit
ANSI colour and Unicode half-blocks (two pixels per character cell), no file and
no image viewer. Perfect over SSH or on a headless box:

```sh
vizbin render firmware.bin -m entropy --term
vizbin render firmware.bin --rgb entropy,delta,xor --term
```

Window a region without extracting it first (great for reversing):

```sh
vizbin render mystery.bin --offset 0x12000 --length 65536 -w 256
```

#### Composing: two axes

A projection is a **transform** (`-t`/`--transform`: *what to measure* — bytes→bytes)
plus a **colorizer** (`--paint`: *how to paint* — bytes→pixels). The named modes
are just **presets** for common pairings (`gray` = `identity`+`gray`, `byteclass`
= `class`+`palette`, `entropy` = `entropy`+`magma`, …) — they don't limit what's
expressible. Mix the axes freely:

```sh
vizbin render f.bin -t xor --paint magma            # xor stream, magma-painted
vizbin render f.bin -t xor,entropy --paint palette   # chain transforms, repaint
vizbin render f.bin -t class                          # bare transform (default gray)
vizbin render f.bin -m byteclass --paint gray         # a preset, repainted
```

- **`-t/--transform`** takes a transform or mode name, or a comma-**chain** run in
  order (output feeds the next), so `xor,entropy` is "the entropy of the xor
  stream." **Order matters** (`entropy,xor` differs). `--pipe` is an alias.
- Transforms: `identity, xor, delta, bitplane, class, entropy`. Colorizers:
  `gray, magma, palette, nibble`.
- Without `--paint`, a chain paints with its **last stage's** colour (so
  `xor,entropy` stays magma), and a bare transform defaults to gray.
- **No combination is disallowed** — `palette` on non-class data just paints the
  out-of-range values black, `magma` on raw bytes is the ramp over byte values.
  We decline to police taste; the only limit is structural: `raw-rgb`/`text`
  aren't equal-length byte streams, so they can't be transforms.

Where `-t` chains transforms in *depth*, **`--rgb`** composes them in *breadth* —
up to three transforms driving R, G, B in parallel:

```sh
vizbin render f.bin --rgb entropy,delta,xor -w 256   # R=entropy, G=delta, B=xor
```

One image answering *"where is it high-entropy **and** fast-changing **and**
periodic?"* — your eye finds where the channels light up together. `inspect --rgb`
reports the three channel values at an offset, matching the rendered pixel:

```sh
vizbin inspect f.bin -w 256 --rgb entropy,delta,xor --offset 260
#   -> R(entropy)=0x19 (25)  G(delta)=0x13 (19)  B(xor)=0x12 (18)
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

The hint fires on either a mostly-printable window **or** a printable run of at
least `-n`/`--min-run` glyphs (default 6, like `strings -n`) — so it also catches
a magic string or filename embedded in binary/padding, rendering the `.` structure
around it:

```
vizbin inspect archive.tar -w 64 -m raw-rgb --offset 260
#   -> pixel 86 -> R@258=0x73 G@259=0x74 B@260=0x61 -> "sta"
#   psst: bytes [244-276] look like text: ".............ustar.00bundle-tron9"
vizbin inspect archive.tar -w 64 -m raw-rgb --offset 260 -n 20   # raise the bar; now silent
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

### infer (draft a record layout)

Where `suggest` finds the *stride* and the picture shows you records line up,
`infer` takes the next step — it **guesses the fields**. It detects the record
period by byte-autocorrelation, reshapes the file into a record grid, profiles
each byte column, and reports a draft layout with per-field evidence and
confidence (it's a starting point you verify, not ground truth):

```sh
vizbin infer firmware.bin              # auto-detect the record stride
vizbin infer logs.bin --stride 22      # or force it
```
```
logs.bin:
stride 22 bytes (period @ 22 (autocorr 0.82, 64% constant columns)); 1000 complete records

   offset  size  kind      conf  evidence
  -------  ----  --------- ----  -----------------------------------------
  0x0000     4  magic     1.00  constant "LOG1"
  0x0004     4  counter   1.00  monotonic 32-bit int (little-endian), e.g. 0..999
  0x0008     2  bytes     0.40  low-entropy varying (~2.0 bits/byte)
  0x000a     8  string    1.00  printable ASCII across records
  0x0012     4  blob      0.71  high entropy ~7.4 bits/byte (hash/compressed?)
```

It recognizes constant **magic**/reserved fields, monotonic **counters** (with
endianness), printable **strings**, and high-entropy **blobs**. It reports
honestly when there's no strong record structure (e.g. random or non-record
data), and small multi-byte counters are shown at their *observed* width (a
counter that never exceeds 65535 reads as `u16`). Adjacent constant fields can
merge — the evidence (hex/ASCII) is shown so you can split them by eye.

Stride detection has two engines: byte-autocorrelation for records with several
fixed fields, plus a **sparse-marker** scan for records whose *only* fixed byte
is a periodic sync/marker in otherwise-opaque payload (e.g. an MPEG-TS `0x47`
sync every 188 bytes) — a case where the autocorrelation stays flat.

**Export the guess into a real parser** with `--format` (or `--json`) — this is
the point: go from a picture of an unknown format to something you can compile.

```sh
vizbin infer logs.bin --json              # structured, for pipelines/tooling
vizbin infer logs.bin --format kaitai     # a Kaitai Struct .ksy stub
vizbin infer logs.bin --format struct     # a Python struct format + field names
```
```yaml
# --format kaitai
meta:
  id: logs
seq:
  - id: magic
    contents: [0x4c, 0x4f, 0x47, 0x31]
  - id: count
    type: u4le
  - id: text
    type: str
    size: 8
    encoding: ASCII
```
```python
# --format struct
format = "<4sI2x8s4s"
fields = ['magic', 'count', 'text', 'data']
```

The `struct` format always accounts for every byte (`struct.calcsize(format) ==
stride`), so it round-trips; `kaitai` gives per-field endianness and fixed-magic
`contents`.

### profile (structural fingerprint)

`profile` distills a file into a compact fingerprint — overall entropy, byte-class
mix, a coarse **region** map (adjacent windows merged by entropy class), the
`head` magic bytes, and a detected record stride. It reads **one or more** files,
so you can fingerprint a whole corpus at once:

```sh
vizbin profile firmware.bin                     # human summary
vizbin profile *.bin --json --no-stride         # JSONL, one object per file
```

The region map turns vizbin into a *sensor*, not just a lens — it makes
**heterogeneous** blobs (a file with several differently-structured parts) fall
right out:

```
mystery.bin:  13120 bytes
  entropy 5.86 bits/byte   printable 54%   distinct 256/256   head 6465662068656c6c
  byte-classes: nul 23%  whitespace 5%  ascii 49%  control 4%  high 19%
  regions (6):
    0x00000000      2048  text       entropy 3.85
    0x00000800      2048  sparse     entropy 0.00
    0x00001000      1024  binary     entropy 2.07
    0x00001400      4096  compressed entropy 7.81
    0x00002400      1024  code       entropy 6.74
    0x00002800      2880  text       entropy 2.00
```

`--json` emits one object per line (JSONL) with a fixed-length `entropy_profile`
vector plus the `byte_classes` fractions — a ready-made feature vector for
clustering / triage / anomaly-detection across thousands of files in the
terminal, something interactive visualizers can't do:

```sh
# which files stand out? cluster by their region composition
vizbin profile corpus/*.bin --json | \
  jq -r '[(.regions|map(.kind)|unique|join("+")), .source] | @tsv'
```

### diff (structural / visual binary diff)

`diff` compares two binaries at the **block** level (via `difflib`), so it
survives insertions and deletions the way `cmp` can't — a few bytes added near
the top of `firmware_v2` won't paint the whole rest of the file as "changed":

```sh
vizbin diff firmware_v1.bin firmware_v2.bin
```
```
firmware_v1.bin (8192 bytes) vs firmware_v2.bin (8208 bytes)
  99.0% identical (block 8); 2 changed region(s)
    replace  A:0x00000400-0x00000440  B:0x00000400-0x00000440  (64 bytes)
    insert   A:                  —  B:0x00001000-0x00001010  (+16 bytes)
```

It reports `replace` (changed in place), `insert` (added in v2), and `delete`
(removed from v1) with offsets in **both** files. Add `-o diff.bmp` or `--term`
for a **diff image** over the new file — identical bytes dimmed, changes lit
(red = replaced, green = inserted) — so the changed regions jump out at a glance:

```sh
vizbin diff firmware_v1.bin firmware_v2.bin --term        # or -o diff.bmp
vizbin diff a.bin b.bin --json                            # machine-readable
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
