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

### inspect (offset <-> pixel mapping)

```sh
vizbin inspect -w 256 -m gray --offset 0x12340
vizbin inspect -w 256 -m gray --x 12 --y 40
vizbin inspect -w 256 -m raw-rgb --phase 1 --offset 100
```

If you rendered a windowed region, pass `--base <offset>` so the math accounts
for where the render started.

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
