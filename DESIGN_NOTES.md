# vizbin Design Notes

## Working description

`vizbin` is a small, format-agnostic binary visualization tool for turning arbitrary byte streams into images and related visual artifacts.

The core idea is intentionally simple:

- impose a 2D geometry on a byte stream
- apply one or more cheap visual projections
- vary width, phase, and projection to expose structure
- let human vision do some of the first-pass reconnaissance

At its simplest, `vizbin` treats raw bytes as image data. At its most interesting, it becomes a visual stride-analysis and structure-discovery tool for:

- executables
- firmware
- unknown binary formats
- memory dumps
- database files
- logs and mixed text/binary blobs
- packet captures
- compressed or encrypted payload discovery
- embedded asset hunting

The tool should remain small, composable, and Unix-friendly.

---

## Elevator pitch

`vizbin` renders arbitrary bytes as images so that hidden structure in unknown data becomes visible.

Different widths act like different hypotheses about stride or record length. Different visual projections act like different hypotheses about meaning.

What "looks random" in one projection or width may snap into obvious structure in another.

---

## Core insights captured so far

### 1. Width is a probe

Choosing image width is not merely formatting. It is a hypothesis.

If a blob contains some repeating or aligned structure, some widths will make it visually obvious:

- fixed records
- pages
- sectors
- rows
- packet boundaries
- screen buffers
- tables
- repeated code/data motifs

### 2. Projection is a probe

A single visualization mode is not enough.

The same bytes should be viewable through multiple projections, such as:

- raw RGB grouping
- grayscale
- byte-class coloring
- entropy
- deltas
- bitplanes

Different projections reveal different classes of structure.

### 3. Motion may help

A width sweep rendered as an animation may be more revealing than any single still image.

As width changes:

- meaningless artifacts drift
- periodic structures can "lock in"
- repeated records can suddenly align
- row/column coherence can emerge

Human eyes are very good at noticing emergence under motion.

### 4. The tool should begin format-agnostic

The first version should not depend on understanding ELF, PE, Mach-O, SQLite, PNG, or any other known format.

The value lies in asking:

"What can we learn visually about this blob before we parse it?"

Format-aware overlays may come later, but should not define the initial design.

### 5. Keep the "constant-offset payload" property where useful

A particularly elegant property of the BMP-based rendering path is this:

- BMP pixel data offset is 54 bytes
- payload byte `n` appears at file offset `54 + n`

This is valuable because a visually interesting region can be mapped back to source offsets without any codec transform.

That property is especially attractive for reverse engineering.

---

## Goals

### Primary goals

- Provide a simple way to render arbitrary byte streams as images.
- Support multiple visual projections over the same source data.
- Support multiple width hypotheses.
- Support quick generation of contact sheets and animations.
- Help a user discover structure in unknown binary data.

### Secondary goals

- Preserve strong offset mapping from visualization back to source bytes.
- Be scriptable and CLI-first.
- Stay lightweight and dependency-minimal if practical.
- Produce output that is useful both for quick eyeballing and for deeper analysis.

### Non-goals, at least initially

- Full reverse engineering suite
- Disassembler
- Hex editor replacement
- Full GUI-heavy forensic workstation
- Deep format-aware interpretation in v1
- Statistical novelty for its own sake without a practical user story

---

## Guiding principles

- Small, sharp, and composable
- Image generation should be deterministic
- Output naming should be predictable
- Widths and projections should be explicit and reproducible
- Simple modes first, exotic modes later
- Default behavior should be useful without being magical
- Preserve the source bytes unchanged wherever possible
- Make it easy to correlate visual regions with source offsets

---

## Conceptual model

A `vizbin` rendering is the combination of:

1. Source bytes
2. Layout hypothesis
3. Projection mode
4. Optional phase/alignment choice
5. Optional palette or mapping parameters
6. Output format

That suggests a mental model like:

```text
source bytes
  |
  +-- layout(width, height, stride assumptions, phase)
  |
  +-- projection(raw-rgb, gray, entropy, byteclass, ...)
  |
  +-- render(output image / contact sheet / animation)
```

---

## Initial usage shape

These commands are illustrative, not final.

### Render a single image

```sh
vizbin render foo.bin
vizbin render foo.bin --width 256
vizbin render foo.bin --width 512 --mode gray
vizbin render foo.bin --width 80 --mode byteclass
vizbin render foo.bin --width 320 --mode raw-rgb --phase 1
```

### Render several widths

```sh
vizbin sweep foo.bin --widths 64,80,128,256,512
vizbin sweep foo.bin --widths common
vizbin sweep foo.bin --widths powers2 --mode gray
vizbin sweep foo.bin --widths textish --mode byteclass
```

### Create animation across widths

```sh
vizbin animate foo.bin --from 64 --to 1024 --step 4
vizbin animate foo.bin --from 64 --to 1024 --step 4 --mode raw-rgb
vizbin animate foo.bin --widths common --mode entropy
```

### Generate a contact sheet

```sh
vizbin contact foo.bin --widths 64,80,128,256,512
vizbin contact foo.bin --widths suggest
vizbin contact foo.bin --widths screenish --mode gray
```

### Ask for candidate widths

```sh
vizbin suggest foo.bin
vizbin suggest foo.bin --top 20
vizbin suggest foo.bin --families powers2,textish,storage
vizbin suggest foo.bin --score rowcorr
```

### Inspect or map offsets

```sh
vizbin inspect foo.bin --width 256 --x 12 --y 40
vizbin inspect foo.bin --width 256 --offset 0x12340
```

These would help answer questions like:

- What source offset corresponds to this pixel?
- What pixel corresponds to this byte offset?
- What byte range corresponds to this visible block?

### Reversible BMP mode

```sh
vizbin bmp foo.bin
vizbin bmp foo.bin --output foo.bmp
vizbin unbmp foo.bmp > foo.bin
```

This mode is especially useful if the constant-offset payload property is preserved.

---

## Suggested command structure

A rough CLI shape:

```text
vizbin
|-- render
|-- sweep
|-- contact
|-- animate
|-- suggest
|-- inspect
|-- bmp
`-- unbmp
```

### Subcommand roles

#### `render`
Render one or more images from a source file using a single width or small set of widths.

#### `sweep`
Generate multiple frames/images across an explicit width list or family.

#### `contact`
Generate a contact sheet from a width sweep and/or projection sweep.

#### `animate`
Generate animation from an ordered set of widths and possibly phases/projections.

#### `suggest`
Suggest widths likely to be informative.

#### `inspect`
Map between visual coordinates and byte offsets.

#### `bmp`
Produce direct BMP visualization using the payload-as-pixel-data technique.

#### `unbmp`
Recover payload from a reversible BMP form, if supported.

---

## Projection taxonomy

The tool should treat projections as first-class concepts.

### Tier 1: Core projections

These should be simple, cheap, and highly practical.

#### `raw-rgb`
Interpret successive bytes as B, G, R triplets.

Properties:
- visually rich
- zero transform on payload in BMP mode
- highly alignment-sensitive
- good for spotting broad structure

Good for:
- mixed-content blobs
- visual "texture"
- section boundaries
- repeating motifs

#### `gray`
Interpret each byte as one grayscale pixel intensity.

Properties:
- 1 byte per pixel
- preserves byte granularity
- avoids RGB grouping artifacts
- simple and robust

Good for:
- raw periodicity
- textual regions
- sparse or padded areas
- quick inspection

#### `byteclass`
Map bytes to semantic classes.

Example classing:
- `0x00`
- `0xff`
- whitespace
- printable ASCII
- control chars
- high-bit bytes
- "other"

Properties:
- makes text/padding/control structure obvious
- strongly useful for mixed text/binary formats

Good for:
- strings
- config blobs
- delimiter-heavy formats
- spotting NUL padding

### Tier 2: Statistical projections

These require light local computation.

#### `entropy`
Compute local Shannon entropy over a sliding window and map to brightness or color.

Good for distinguishing:
- zero/padding
- structured data
- text
- compressed data
- encrypted data

#### `delta`
Map `byte[i] - byte[i-1]` or absolute delta.

Good for:
- slowly varying sequences
- repeated runs
- periodic trends
- highlighting transitions

#### `frequency`
Map bytes according to local or global frequency.

Good for:
- repeated marker bytes
- dominance of certain values
- spotting unusual distributions

### Tier 3: Structural/bit-level projections

#### `bitplane`
Render one bitplane at a time, or all 8 separately.

Good for:
- masks
- flag fields
- low-bit structure
- packed formats

#### `nibble`
Map high nibble and low nibble separately to channels or classes.

Good for:
- packed hex-like patterns
- BCD-ish or encoded structures
- compactly encoded fields

#### `xor`
Render `byte[i] XOR byte[i-k]` for selectable `k`.

Good for:
- periodicity and repetition
- repeated records
- rolling structure

### Tier 4: Heuristic projections

More experimental, possibly useful later.

#### `utf8-ish`
Color valid UTF-8 lead bytes and continuation bytes differently.

#### `pointer-ish`
Highlight aligned 32-bit or 64-bit values that resemble pointers.

#### `opcode-ish`
Crude heuristic coloring for common machine-code byte patterns.

#### `alignment`
Visually distinguish byte position modulo 2/4/8/16.

These may prove useful, but should come after the core modes.

---

## Width families

`vizbin` should probably support symbolic width families.

### `square`
Near-square width inferred from file size.

### `powers2`
Machine-ish widths:
- 16
- 32
- 64
- 128
- 256
- 512
- 1024
- 2048
- 4096

### `storage`
Common storage/page/block widths:
- 512
- 1024
- 2048
- 4096
- 8192
- 16384

### `textish`
Human/text-oriented widths:
- 40
- 64
- 72
- 80
- 96
- 120
- 132
- 160

### `screenish`
Common display widths:
- 160
- 320
- 640
- 800
- 1024
- 1280
- 1920

### `records`
Likely record sizes:
- 12
- 16
- 20
- 24
- 32
- 40
- 48
- 64
- 96
- 128
- 188
- 256
- 512

### `common`
A curated set mixing the above.

---

## Phase and alignment

Some projections are phase-sensitive, especially `raw-rgb`.

`vizbin` should support:

- `--phase 0`
- `--phase 1`
- `--phase 2`

This is especially important for any 3-byte grouping scheme.

A one-byte shift can radically alter visual appearance. If a pattern persists across phases, it is more likely to reflect true structure rather than grouping artifacts.

Later, phase may also matter for:
- multi-byte grouping projections
- alignment-sensitive heuristics
- record-oriented views

---

## The `suggest` command

This deserves to be a first-class feature.

### Purpose

Suggest widths likely to reveal meaningful structure in the file.

### Why it matters

A user often does not know what widths are likely to be informative. `suggest` should offer a reasonable set of candidate widths based on:

- file size
- width families
- simple structural scoring
- common conventions

### Initial v1 behavior

Start simple and deterministic.

Return:
- square-ish width
- powers of two around the square-ish width
- common widths from curated families
- likely block/page sizes
- maybe a few human-oriented widths

Example:

```sh
$ vizbin suggest foo.bin
Suggested widths for foo.bin:
  80      textish
  128     powers2
  188     records
  256     powers2
  320     screenish
  512     storage
  640     screenish
  1024    powers2
```

### Later v2 behavior

Add scoring.

Possible scoring ideas:

#### Row correlation
For a candidate width:
- split stream into rows
- compare adjacent rows
- rank widths with strong row similarity

#### Column variance/coherence
Widths that produce unusually coherent columns may align with natural structure.

#### Autocorrelation-like scoring
Look for repeating row motifs or periodic similarity.

#### Entropy transitions
Widths that concentrate strong entropy boundaries may be informative.

### Output of `suggest`

Could be either plain or verbose:

```sh
vizbin suggest foo.bin --verbose
```

Example verbose shape:

```text
Width  Family     Score   Why
-----  ---------  ------  ------------------------------------
80     textish    0.42    common textual layout width
128    powers2    0.66    row correlation spike
188    records    0.73    suspicious periodicity candidate
256    powers2    0.81    strong adjacent-row coherence
512    storage    0.78    common page/block size
```

---

## Contact sheets and animation

These are not just "nice to have". They are central to the concept.

### Contact sheets

Use case:
- compare several widths side-by-side
- compare several projections side-by-side
- compare phases side-by-side

Suggested command shapes:

```sh
vizbin contact foo.bin --widths common --mode gray
vizbin contact foo.bin --widths 64,128,256,512 --modes gray,byteclass,entropy
vizbin contact foo.bin --width 256 --phases 0,1,2
```

### Animation

Use case:
- watch structure emerge as width changes
- identify widths at which patterns "lock in"

Suggested command shapes:

```sh
vizbin animate foo.bin --from 64 --to 1024 --step 4 --mode gray
vizbin animate foo.bin --widths suggest --mode raw-rgb
```

Possible outputs:
- GIF
- MP4
- sequence of PNGs

---

## Offset mapping and inspection

This seems worth capturing early.

### Why it matters

A visually useful region should be mappable back to source offsets.

The user may want to answer:

- what offset is this interesting patch?
- what file range corresponds to this visible stripe?
- if a region looks compressed or string-heavy, where is it in the source?

### Simple mapping for grayscale mode

If width is `W`, then:

- byte offset `n`
- pixel coordinate:
  - `x = n % W`
  - `y = n // W`

### For `raw-rgb`

If successive byte triplets form one pixel:
- pixel index `p = n // 3`
- channel `c = n % 3`
- `x = p % W`
- `y = p // W`

This is one reason the constant-offset BMP mode is so attractive.

---

## Possible repository shape

A rough `tree -F`-style layout:

```text
vizbin/
|-- README.md
|-- QUICKSTART.md
|-- REFERENCE.md
|-- DESIGN.md
|-- LICENSE
|-- pyproject.toml
|-- requirements.txt
|-- examples/
|   |-- sample-data/
|   |   |-- hello.txt
|   |   |-- random.bin
|   |   |-- pe-sample.bin
|   |   `-- firmware-sample.bin
|   |-- output/
|   |   |-- contact-sheets/
|   |   |-- renders/
|   |   `-- animations/
|   `-- notebooks/
|-- docs/
|   |-- projections.md
|   |-- width-families.md
|   |-- suggest.md
|   `-- reversing-use-cases.md
|-- scripts/
|   |-- demo-contact-sheet.sh
|   |-- demo-sweep.sh
|   `-- demo-animate.sh
|-- tests/
|   |-- test_layout.py
|   |-- test_bmp.py
|   |-- test_projections.py
|   |-- test_suggest.py
|   `-- test_cli.py
`-- src/
    `-- vizbin/
        |-- __init__.py
        |-- cli.py
        |-- commands/
        |   |-- __init__.py
        |   |-- render.py
        |   |-- sweep.py
        |   |-- contact.py
        |   |-- animate.py
        |   |-- suggest.py
        |   |-- inspect.py
        |   |-- bmp.py
        |   `-- unbmp.py
        |-- layout/
        |   |-- __init__.py
        |   |-- geometry.py
        |   |-- widths.py
        |   `-- phases.py
        |-- projections/
        |   |-- __init__.py
        |   |-- raw_rgb.py
        |   |-- gray.py
        |   |-- byteclass.py
        |   |-- entropy.py
        |   |-- delta.py
        |   |-- bitplane.py
        |   `-- helpers.py
        |-- render/
        |   |-- __init__.py
        |   |-- image_writer.py
        |   |-- contact_sheet.py
        |   `-- animation.py
        |-- analysis/
        |   |-- __init__.py
        |   |-- suggest.py
        |   |-- scoring.py
        |   `-- correlation.py
        |-- formats/
        |   |-- __init__.py
        |   `-- bmp.py
        `-- util/
            |-- __init__.py
            |-- io.py
            |-- naming.py
            `-- palette.py
```

This may be more structure than needed on day one, but it captures natural boundaries.

A leaner first pass would be fine.

---

## Minimal internal architecture

A compact mental model for the code:

### 1. Layout layer
Responsible for:
- width selection
- height calculation
- row construction
- phase handling
- offset mapping

### 2. Projection layer
Responsible for:
- turning bytes into pixels or scalar values
- applying classes/palettes
- statistical windows when needed

### 3. Rendering layer
Responsible for:
- writing PNG/BMP or image sequences
- generating contact sheets
- generating animations

### 4. Analysis layer
Responsible for:
- candidate width generation
- scoring and ranking
- suggestion logic

### 5. CLI layer
Responsible for:
- subcommands
- argument parsing
- output naming
- reproducible defaults

---

## Output naming ideas

Output names should probably encode enough context to be useful.

Examples:

```text
foo.w256.gray.png
foo.w256.rawrgb.phase0.png
foo.w80.byteclass.png
foo.contact.common.gray.png
foo.anim.64-1024-step4.rawrgb.gif
foo.bmp
```

This makes casual CLI use much nicer.

---

## Roadmap

### Phase 1: Tiny but real

Goal: working prototype with obvious utility.

Implement:
- `render`
- `bmp`
- `gray`
- `raw-rgb`
- `byteclass`
- explicit width selection
- square-ish width default
- `--phase` for RGB grouping
- offset mapping helpers
- basic PNG output
- reversible BMP mode if easy enough

Deliverable:
- user can render one file in a few modes and widths
- user can start noticing structure

### Phase 2: Comparison workflows

Goal: make width exploration practical.

Implement:
- `sweep`
- `contact`
- width family presets
- simple `suggest` with curated width families only
- deterministic output naming

Deliverable:
- user can compare many widths quickly
- user does not have to guess entirely blind

### Phase 3: Animation and richer projections

Goal: support visual emergence and more analytical views.

Implement:
- `animate`
- `entropy`
- `delta`
- `bitplane`
- optional nibble/frequency projections
- image sequence to GIF/MP4 pipeline

Deliverable:
- user can discover patterns through motion
- more kinds of structure become visible

### Phase 4: Width scoring and smarter `suggest`

Goal: introduce first-pass analysis.

Implement:
- row-correlation scoring
- column coherence scoring
- ranking candidate widths
- verbose `suggest`
- "top candidate widths" output

Deliverable:
- the tool begins to guide the user toward interesting widths

### Phase 5: Deeper inspection and optional overlays

Goal: bridge from visualization to analysis workflow.

Implement:
- richer `inspect`
- clickable or coordinate-based offset lookup
- extraction of regions/ranges
- optional later format-aware overlays for known formats
- maybe side-by-side image plus hex snippet output

Deliverable:
- visualization becomes more actionable for reversing work

---

## Open questions

### 1. Image formats
Should the default output be:
- PNG
- BMP
- both depending on mode

BMP is elegant for the direct-payload trick. PNG is convenient and compact for general projections.

### 2. Dependency budget
Should image writing depend on:
- Pillow
- pure Python BMP/PPM for early versions
- external tools optionally for GIF/MP4 generation

A low-dependency core would be attractive.

### 3. Projection defaults
What should `vizbin render foo.bin` do by default?
Candidates:
- grayscale at square-ish width
- raw-rgb at square-ish width
- emit both
- maybe a mini contact sheet of a few core modes

### 4. Width defaults
Should default width be:
- square-ish
- suggested best candidate
- family-based composite

### 5. Performance and large files
How should the tool handle very large inputs?
Possibilities:
- full render
- cap size
- downsample
- chunked or windowed views
- tiled output

### 6. Terminal UI or GUI later
Not a v1 need, but perhaps later:
- a TUI for cycling widths and projections
- cursor-based offset inspection
- maybe a tiny web UI or notebook helper

### 7. Steganographic/reversible use cases
Is the reversible BMP mode a side feature, or a first-class pillar?
It may deserve to remain first-class because it preserves the elegant offset property.

---

## Immediate practical first cut

If development begins soon, the first useful prototype could be just this:

- one Python CLI
- `render`
- `gray`
- `raw-rgb`
- `byteclass`
- `--width`
- `--phase`
- square-ish default
- PNG output
- one contact-sheet helper
- maybe a tiny `suggest` that just returns curated width families

That alone may already be enough to validate the core idea.

---

## Closing summary

`vizbin` should start life as a small CLI tool that helps a user visually inspect arbitrary binary data by rendering it under multiple width and projection hypotheses.

The major conceptual pillars are:

- width as a structural probe
- projection as a semantic probe
- contact sheets and animation as discovery tools
- format-agnostic first-pass analysis
- strong mapping from visible structure back to source offsets

The project has room to grow into something genuinely useful for reverse engineering and binary reconnaissance, but its strength will come from preserving the simplicity of the original idea rather than smothering it with heavyweight features too early.

Or more bluntly:

Take a blob.
Pretend it is an image.
Vary the lie until the truth starts to show.


## extra thooughts... transcript
I just had an amusing thought that maybe should have been so amusing to me because it is obvious, but it took me by surprise.. The thought was of the sort: vizbin render IMG_0001.BMP and it made me chuckle after puzzling at my own thought.

Yes. And the funniest part is that it is not merely recursive nonsense - it could produce something visually intelligible.

For a plain uncompressed 24-bit BMP, the file is approximately:

[BMP header][BGR pixel bytes]

So:

vizbin render IMG_0001.BMP --mode raw-rgb

means:

"Please interpret this image file, including the instructions saying how to interpret the image file, as an image."

The header becomes a little burst of garbage/color at the beginning, and then the original pixel data begins. If you happened to choose the original bitmap's width, you could get a distorted echo of the source image after the header: shifted by the header bytes, wrapped across scanlines, perhaps vertically flipped because of BMP's usual bottom-up storage, and affected by any source row padding.

There is something delightfully self-referential about:

            +----------------------+
BMP file -> | metadata about image | --+
            +----------------------+   |
            | image                 |   |
            +----------------------+   |
                                       v
                              treated as image

And it suggests a useful diagnostic experiment:

vizbin render IMG_0001.BMP --width <actual-width> --mode raw-rgb

versus:

vizbin render IMG_0001.BMP --offset 54 --width <actual-width> --mode raw-rgb

For the right kind of BMP, that second command would make the original image more or less just fall back out of the byte stream.

Which gives us another feature that I don't think we explicitly captured:

--offset N
--length N

Those are extremely natural for reversing anyway.

Then you can say:

vizbin render mystery.bin --offset 0x12000 --length 65536 --width 256

and visually interrogate a region without extracting it first.

And, naturally:

vizbin render "$(vizbin render ...)"

is where we begin irresponsibly studying the visual phenomenology of images contemplating themselves.

The first 54 bytes becoming a literal visible "header scar" also feels very on-brand for the project.
