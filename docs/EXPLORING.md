# Exploring with vizbin

This is not a tutorial with a right answer at the end. It's a field guide for
poking at a blob you don't understand yet. Grab any file — a photo, a firmware
image, a savegame, a `.pyc`, a core dump, a `.sqlite`, something you pulled off a
device and can't identify — and follow your eyes.

The whole game is: **make a hypothesis, render it, and see if the picture gets
more organized.** More organized is the signal. Keep whatever move made it
happen; back out whatever made it worse.

Throughout, replace `blob` with your file.

---

## 0. First contact

```sh
vizbin render blob
```

That gives you grayscale at a square-ish width — one byte per pixel, no
interpretation. Open the `.bmp` and just look. You're not trying to *read* it,
you're triaging texture. Ask yourself:

- Are there **horizontal bands or stripes**? That's structure with a period.
- Big **flat black** regions? Runs of `0x00` — padding, sparse tables, unused
  space. Big flat **white**? Runs of `0xff` — erased flash, fills.
- A **snowy/TV-static** area? High entropy — compressed, encrypted, or already
  random.
- A region that looks like **woven fabric or brickwork**? Repeating fixed-size
  records. Note roughly *how tall* one "brick" is; that's a width clue.

Don't over-interpret the first image. It's just the establishing shot.

---

## 1. Width is a probe

The single most powerful move. A wrong width shreds real structure into diagonal
noise; the right width snaps it into vertical/horizontal alignment.

Let the tool nominate widths:

```sh
vizbin suggest blob -v
```

The top rows are widths where adjacent rows look most alike — often exactly the
stride you want. Try the top two or three:

```sh
vizbin render blob -w <suggested> -m gray
```

Then watch structure form and dissolve as width changes:

```sh
vizbin animate blob --from 64 --to 1024 --step 4 -m gray
```

Play the GIF and **look for the moment things "lock in"** — diagonal streaks
suddenly stand upright, or a checkerboard steadies into clean columns. The width
at that frame is meaningful. Around a promising value, zoom the sweep in:

```sh
vizbin animate blob --widths 500,504,508,512,516,520 -m gray
```

- **If everything drifts diagonally no matter the width** → there may be no fixed
  stride (or it's variable-length records). Move on to projections.
- **If it locks at some W and again near 2·W** → W is probably a real record or
  row size; the harmonic confirms it.
- **If a photo-like image almost resolves but shears** → you're one or two pixels
  off the true width, *or* there's a header before the pixels (see §4).

---

## 2. Projection is a probe

Same bytes, different question. Pick the projection that matches what you
suspect, and switch freely.

```sh
vizbin contact blob --modes gray,byteclass,entropy,delta -w <good-width>
```

That one contact sheet is a great orientation. Then chase whatever tile looked
most informative:

**`byteclass`** — colors bytes by kind (nul / `0xff` / whitespace / printable
ASCII / control / high-bit). Reach for it when you suspect **mixed text and
binary**.
- *Look for* solid blocks of "printable" color → embedded strings, config,
  JSON/XML. Note where they start and end.
- *If* you see thin regular lines of one class threading through binary → those
  may be **delimiters or fixed fields**. Try a width that puts them in a straight
  column.

**`entropy`** — brightness ≈ local randomness (dark = orderly, bright = random).
Reach for it to **map regions before you read any of them**.
- *Look for* sharp brightness boundaries → section edges. A dark→bright cliff is
  often "header/tables → compressed or encrypted payload."
- *If* a region is uniformly bright *and* stays bright at every width → treat it
  as compressed/encrypted and stop trying to find a stride in it.
- *If* it's mid-bright and textured → likely code or structured binary; keep
  probing width.

**`gray`** — the honest default; best for **periodicity and padding**. If a
region looks promising in another mode, come back to `gray` at that width to read
the fine texture.

**`raw-rgb`** — three bytes per pixel, so it's colorful and busy; good for
**broad texture and section boundaries**, less for fine structure. It is
**phase-sensitive**: a one-byte shift can change everything.

```sh
vizbin contact blob --phases 0,1,2 -w <width>
```

- *If* a pattern survives all three phases → it's real structure, not a grouping
  artifact.
- *If* it only appears at one phase → probably an artifact of 3-byte grouping;
  trust it less.

**`delta`** (`|byte[i]-byte[i-1]|`) — dark where values change slowly. Reach for
it on **counters, timestamps, sample data, gradients**.
- *Look for* near-black smooth regions → slowly ramping values (audio, sensor
  logs, incrementing IDs).

**`xor --k N`** — compares each byte to the one N back. Reach for it when you
suspect a **repeat period N**.
- *If* `--k` equal to your candidate record size makes a region go **flat/dark**
  → consecutive records are nearly identical; you found the period.

**`bitplane --plane 0..7`** — one bit across all bytes.
- *Look at* plane 0 (lowest bit): structure there suggests **packed flags or
  low-bit encodings**. Plane 7 (top bit) separates ASCII from high-byte data.

**`nibble`** — high nibble → red, low nibble → green. Reach for it on
**hex-ish / BCD / packed** data; regular red/green weaves imply nibble-aligned
fields.

---

## 3. Narrow down to a region

Once a stripe or block looks interesting, stop rendering the whole file and
interrogate just that part — no need to carve it out first:

```sh
vizbin render blob --offset 0x12000 --length 65536 -w 256 -m entropy
```

Slide the `--offset` and shrink the `--length` until the interesting thing fills
the frame. Now re-run the width sweep and projections *on the region* — a local
stride is often much clearer once the surrounding noise is gone.

---

## 4. From the picture back to the bytes

When something catches your eye, find out **where it lives** so you can open a hex
editor / disassembler at the right spot:

```sh
vizbin inspect -w 256 -m gray --x 40 --y 512      # pixel -> byte offset
vizbin inspect -w 256 -m gray --offset 0x1f400    # byte offset -> pixel
```

If you rendered a windowed region, add `--base <the --offset you used>` so the
math points back into the original file. For `raw-rgb`, pass the same `--phase`
you rendered with.

---

## 5. The self-referential trick (and headers)

Feed vizbin an actual uncompressed BMP and it will draw a little burst of
garbage — the **header "scar"** — followed by a warped echo of the real image:

```sh
vizbin render photo.bmp -m raw-rgb -w <the photo's real width>
```

- *If* the echo is there but sheared or split across the frame → your width is
  off, *or* the leading header is pushing everything out of phase. Skip the
  header:

  ```sh
  vizbin render photo.bmp -m raw-rgb -w <width> --offset 54
  ```

  For a plain 24-bit BMP the pixels start at offset 54, and the original image
  tends to just fall back out (possibly flipped — BMP stores rows bottom-up).

This is the general lesson for *any* format: a small fixed **preamble before the
payload** shifts the whole picture. If a render is tantalizingly-close-but-
misaligned, try nudging `--offset` by a handful of bytes and watch it click into
place.

---

## 6. Keep it and come back

When a region is byte-exactly what you care about, the reversible BMP mode
preserves it with the offset property (payload byte *n* at file offset `54 + n`):

```sh
vizbin bmp blob blob.bmp
vizbin unbmp blob.bmp -o blob.again        # byte-identical
```

---

## A rough loop to internalize

1. `render` (gray) → triage the texture.
2. `suggest` + `animate` → find the width where it locks in.
3. `contact --modes …` → find the projection that speaks.
4. `--offset/--length` → zoom the interesting region and repeat 2–3 locally.
5. `inspect` → get the byte offset and jump there in your real tools.

The picture is never the answer. It's the thing that tells you **where to point
the answer-finding tools**.
