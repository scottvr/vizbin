# Exploring vizbin

`vizbin` makes more sense once you have watched it find structure that you already know is there.

So this is not a command reference, and it is not quite a reversing tutorial. It is a guided tour: a sequence of small experiments designed to show what the tool can see, what happens when you change one assumption, and how to get from:

```text
"that looks interesting"
```

back to:

```text
"these exact bytes caused it"
```

After that, point it at something mysterious.

The central idea is simple:

> Take a blob. Pretend it is an image. Vary the lie until the truth starts to show.

The deeper idea is that almost everything you do in `vizbin` is a hypothesis.

- Width asks: "What if the data repeats every N bytes?"
- Projection asks: "What property of these bytes matters?"
- Transform chains ask: "What if I process that property further?"
- RGB composition asks: "What if I ask several questions at once?"
- Offset asks: "What if the structure actually starts here?"

You make the hypothesis, render it, and let your eyes tell you whether the result became more organized.

## 0. Make the demo data

From the repository root:

```sh
python examples/make_sample_data.py
mkdir -p examples/output
```

The generated files deliberately contain structures that `vizbin` ought to notice.

There is also an automated tour:

```sh
bash examples/demo.sh
```

But doing the following experiments by hand is more useful. The point is to see what changes when you turn each knob.

## 1. First, lie badly

Start with the fixed-record sample, but do not tell `vizbin` anything about its structure:

```sh
vizbin render examples/sample-data/records.bin
```

Open the resulting BMP.

This is the byte stream laid out in grayscale at an automatically chosen, roughly square width. One byte becomes one pixel.

No file format was inferred.

No parser ran.

No schema was consulted.

Just bytes.

Look at the texture rather than trying to "read" the image.

You may see diagonal structure, repeating bands, or something that looks frustratingly close to orderly.

That frustration is useful.

The file contains repeated records, but we have wrapped the byte stream at the wrong place.

In `vizbin`, width is not merely an image dimension.

**Width is a hypothesis about periodicity.**

## 2. Let vizbin guess the period

Ask which widths make adjacent rows unusually coherent:

```sh
vizbin suggest examples/sample-data/records.bin -v --top 6
```

One candidate should stand out:

```text
188
```

Test it:

```sh
vizbin render examples/sample-data/records.bin -w 188 -m gray
```

Open that image beside the first one.

The bytes did not change.

Their order did not change.

You merely changed where one row ends and the next begins, and previously smeared structure snaps into alignment.

That is one of the fundamental `vizbin` tricks.

A useful width may correspond to a:

- record length
- structure size
- scan line
- page width
- packet size
- filesystem block
- row of samples
- other repeating stride

A wrong width makes real structure drift.

The right width lets it stand still.

## 3. Watch the structure lock into place

A static comparison is useful.

Watching the hypothesis move is better.

```sh
vizbin animate examples/sample-data/records.bin \
    --widths 180,184,188,192,196 \
    -m gray \
    -o examples/output/records.sweep.gif
```

Play the GIF.

Watch what happens around width 188.

Structure that drifts diagonally at nearby widths should briefly lock into place when the row wrapping agrees with the underlying record size, then begin drifting again as the width moves away.

This is visual stride spectroscopy.

You are sweeping a hypothesis and watching for resonance.

For a real unknown file, search a larger range:

```sh
vizbin animate blob --from 64 --to 1024 --step 4 -m gray
```

If something interesting happens around width `W`, sweep closely around it:

```sh
vizbin animate blob --widths 500,504,508,512,516,520 -m gray
```

Things worth noticing:

- If structure becomes vertical or horizontal at one width, that width is probably meaningful.
- If it locks again near `2W`, that harmonic strengthens the case.
- If everything drifts at every width, the file may not contain a fixed-length structure there.
- If an image almost resolves but remains sheared, the width may be right while the starting offset is wrong.

We will come back to that last one.

## 4. Keep the width fixed and change the question

Now switch to the mixed sample:

```sh
vizbin contact examples/sample-data/mixed.bin \
    --modes gray,byteclass,entropy,delta \
    -w 128 \
    -o examples/output/mixed.contact.modes.bmp
```

Open the contact sheet.

Every tile contains the same bytes at the same width.

Only the projection changes.

That is the other fundamental idea:

**Projection is a hypothesis about what property of the bytes matters.**

`gray` asks:

```text
What are the byte values?
```

It is good for periodicity, padding, fixed fields, and fine texture.

`byteclass` asks:

```text
What kinds of bytes are here?
```

It separates things such as NUL, `0xff`, printable ASCII, whitespace, control bytes, and high-bit data.

`entropy` asks:

```text
How locally unpredictable is this region?
```

That makes it useful for seeing transitions between orderly structures and compressed, encrypted, or otherwise high-entropy data.

`delta` asks:

```text
How quickly are adjacent values changing?
```

Slow ramps, counters, samples, and similar data can suddenly become obvious.

No projection is "the correct view."

They are instruments.

Use whichever instrument makes the structure you care about easier to see.

## 5. Let text stay inside the binary

Ordinary `strings` is useful, but it removes everything around the strings.

`vizbin` can instead make printable text part of the byte map.

Try it on the README:

```sh
vizbin render README.md -m text -w 64 --scale 2
```

Printable bytes become glyphs.

Non-printable bytes remain visible as structural tiles.

On an actual binary, that becomes much more interesting:

```sh
vizbin render some-binary -m text -w 64
```

You can see strings while preserving where they live relative to:

- padding
- headers
- tables
- binary fields
- embedded payloads
- neighboring strings
- unrelated data

Think of `text` mode as a visual `strings` that refuses to throw the surrounding file away.

Because width still means bytes per row, text can also be aligned directly with other projections:

```sh
vizbin contact README.md --modes gray,text -w 64
```

Same bytes.

Same geometry.

Different question.

## 6. Point at the picture and ask what caused it

Visualization only becomes really useful if you can get back to the bytes.

That is what `inspect` does.

Without a source file, it performs geometry:

```sh
vizbin inspect -w 256 -m gray --x 40 --y 512
```

That maps a pixel back to a source offset.

Go the other direction:

```sh
vizbin inspect -w 256 -m gray --offset 0x1f400
```

Now give it the source file too:

```sh
vizbin inspect README.md -w 64 -m text --offset 260
```

`inspect` can now tell you not only where the byte is, but what that projection means there.

In text mode, that includes the character itself.

You can also ask several projections about the same coordinate:

```sh
vizbin inspect README.md \
    -w 64 \
    --modes raw-rgb,text,gray \
    --offset 260
```

One offset, several interpretations.

Depending on the mode, `inspect` can report things such as:

- the byte value
- the rendered character
- raw RGB source bytes
- XOR operands and result
- local entropy
- delta
- selected bitplane value

This closes the loop:

```text
interesting pixels
        |
        v
source offset
        |
        v
actual bytes
        |
        v
hex editor / parser / debugger / disassembler / next experiment
```

The picture is reconnaissance.

It tells you where to point the answer-finding tools.

## 7. Discover that "modes" are presets

Up to this point, `vizbin` can look like a program with a collection of rendering modes:

```text
gray
entropy
byteclass
delta
xor
bitplane
nibble
text
raw-rgb
```

That is convenient, but it is not the deeper model.

For most modes, two separate decisions are being made:

```text
bytes -> transform -> colorizer -> pixels
```

The transform decides:

```text
What do we measure?
```

The colorizer decides:

```text
How do we paint that measurement?
```

Named modes are presets for useful pairings.

For example, conceptually:

```text
gray       = identity -> gray
byteclass  = class    -> palette
entropy    = entropy  -> magma
```

But the axes are exposed, so you can mix them yourself:

```sh
vizbin render examples/sample-data/mixed.bin \
    -w 128 \
    -t xor \
    --paint magma
```

Now XOR is the measurement, but magma is the painter.

Or repaint a familiar preset:

```sh
vizbin render examples/sample-data/mixed.bin \
    -w 128 \
    -m byteclass \
    --paint gray
```

This is useful experimentally because you can vary:

```text
what is measured
```

independently from:

```text
how your eye is shown the result
```

## 8. Compose in depth

Transforms can be chained:

```sh
vizbin render examples/sample-data/mixed.bin \
    -w 128 \
    -t xor,entropy
```

Read that literally:

```text
bytes
  |
  v
xor
  |
  v
entropy
  |
  v
paint
  |
  v
pixels
```

You are looking at the local entropy of the XOR-transformed stream.

This is composition in **depth**.

One transform feeds another.

Order matters:

```sh
vizbin render examples/sample-data/mixed.bin -w 128 -t xor,entropy
vizbin render examples/sample-data/mixed.bin -w 128 -t entropy,xor
```

Those are different experiments because:

```text
xor -> entropy
```

is not the same operation as:

```text
entropy -> xor
```

At this point, the mental model has grown from:

```text
bytes -> mode -> picture
```

into:

```text
bytes -> transform -> transform -> ... -> paint -> pixels
```

But there is another axis.

## 9. Compose in breadth

Depth asks several questions in sequence.

Breadth asks several questions of the same bytes in parallel.

Try:

```sh
vizbin render examples/sample-data/mixed.bin \
    -w 128 \
    --rgb entropy,delta,xor
```

Now the same source stream drives three independent transforms:

```text
                 +-> entropy -> R
                 |
bytes -----------+-> delta   -> G ---> RGB pixel
                 |
                 +-> xor     -> B
```

This is composition in **breadth**.

You are asking three questions simultaneously:

```text
R: Is this region locally high-entropy?
G: Are neighboring values changing rapidly?
B: Does XOR reveal periodic difference structure?
```

One image can therefore answer something like:

> Where is the data high-entropy AND fast-changing AND periodic?

On the mixed demo data, look for the regions to separate visually.

A zero-filled region should tend toward black because all three measurements are low.

Pseudo-random data can drive several channels high at once and produce a bright mixed color.

Periodic or structured regions produce their own characteristic texture because the three measurements respond differently.

The exact color is not itself a semantic label.

The important part is the relationship among the channels.

`--rgb` is a visual coincidence detector.

It lets human color vision look for places where several measurements agree, disagree, or change together.

You can also provide only one or two transforms:

```sh
vizbin render blob --rgb entropy
vizbin render blob --rgb entropy,delta
```

Missing channels remain zero.

And the channel names may be transform names or compatible mode names.

So now the composition model has two independent directions:

```text
                         DEPTH
                           |
                           v

bytes -> transform -> transform -> ... -> paint -> pixels
            -t a,b,c


                         BREADTH

                 +-> transform A -> R
                 |
bytes -----------+-> transform B -> G ---> pixels
                 |
                 +-> transform C -> B

                      --rgb A,B,C
```

Depth processes one signal through several stages.

Breadth processes the same signal several ways at once.

## 10. Interrogate a composite pixel

The RGB composite is not a decorative visualization.

It remains inspectable.

Use the same composition with `inspect`:

```sh
vizbin inspect examples/sample-data/mixed.bin \
    -w 128 \
    --rgb entropy,delta,xor \
    --offset 260
```

You will get values corresponding to the three rendered channels:

```text
R(entropy)=...
G(delta)=...
B(xor)=...
```

Those values are the measurements that produced the rendered pixel.

So the symmetry is:

```text
render --rgb entropy,delta,xor
              |
              v
         RGB pixel
              |
              v
inspect --rgb entropy,delta,xor
              |
              v
 R(entropy)  G(delta)  B(xor)
```

The visualization can therefore remain exploratory without becoming mysterious.

You can point at a composite color and ask:

```text
Why is this pixel this color?
```

and recover the measurements behind it.

That matters especially once you start composing more elaborate hypotheses.

A picture may suggest the anomaly.

`inspect` lets you audit it.

## 11. Zoom into the part that deserves attention

Once one region becomes interesting, stop forcing the entire file into every experiment.

Render only that region:

```sh
vizbin render blob \
    --offset 0x12000 \
    --length 65536 \
    -w 256 \
    -m entropy
```

Then repeat the earlier process locally:

```text
suggest
animate
contact
render
inspect
```

A local record structure may be almost invisible when surrounded by unrelated sections and obvious once isolated.

If you inspect a windowed render, tell `inspect` where that window began:

```sh
vizbin inspect blob \
    -w 256 \
    -m gray \
    --base 0x12000 \
    --x 40 \
    --y 100
```

The result then maps back into the original file.

The same principle applies to transform and RGB readouts: calculations are relative to the rendered region, so use the same base and mode parameters when you want inspect results to match the image exactly.

## 12. Make bytes into an image without losing a byte

There is another, deliberately literal interpretation of "pretend the bytes are an image."

```sh
vizbin bmp examples/sample-data/random.bin \
    examples/output/random.bmp
```

That BMP is not merely a visualization.

It contains the payload reversibly.

Recover it:

```sh
vizbin unbmp examples/output/random.bmp \
    -o examples/output/random.recovered.bin
```

Prove the round-trip:

```sh
cmp examples/sample-data/random.bin \
    examples/output/random.recovered.bin \
    && echo "round-trip OK: byte-identical"
```

In this mode, payload byte `n` lives at:

```text
BMP offset 54 + n
```

The original payload length is preserved too, so recovery remains exact even when the file ends in NUL bytes.

The oldest stupid trick in `vizbin` survived because it turned out to be a useful stupid trick.

## 13. Make vizbin look at an image

This experiment explains several ideas at once.

Take an ordinary uncompressed BMP and forget that it is an image file.

Treat it as an arbitrary byte stream:

```sh
vizbin render photo.bmp \
    -m raw-rgb \
    -w <the-photo-width>
```

You should see some garbage produced by the BMP header followed by a warped echo of the original image.

That garbage is evidence.

It tells you that structure exists, but something precedes it.

For a simple 24-bit BMP, try skipping the 54-byte header:

```sh
vizbin render photo.bmp \
    -m raw-rgb \
    -w <the-photo-width> \
    --offset 54
```

The image payload should align much more cleanly.

This illustrates a general lesson.

If a render looks tantalizingly close but remains shifted, sheared, or phase-wrong, do not assume the width is wrong.

The structure may simply start later.

Try moving the offset:

```text
width  = hypothesis about stride
offset = hypothesis about origin
phase  = hypothesis about grouping
```

They are independent knobs.

## 14. Now turn it loose on something you do not understand

Grab anything:

```text
firmware image
savegame
sqlite database
packet capture
core dump
executable
pyc file
compressed archive
disk fragment
memory image
mystery blob from an old project
```

Start cheap:

```sh
vizbin render blob
vizbin suggest blob -v
```

Try promising widths:

```sh
vizbin render blob -w W -m gray
```

Watch width vary:

```sh
vizbin animate blob --from 64 --to 1024 --step 4 -m gray
```

Compare several questions:

```sh
vizbin contact blob \
    --modes gray,byteclass,entropy,delta,text \
    -w W
```

If one region catches your eye:

```sh
vizbin render blob \
    --offset OFFSET \
    --length LENGTH \
    -w W \
    -m entropy
```

If one pixel catches your eye:

```sh
vizbin inspect blob \
    -w W \
    -m gray \
    --offset OFFSET
```

If one measurement suggests another, compose in depth:

```sh
vizbin render blob -w W -t xor,entropy
```

If several measurements seem relevant at once, compose in breadth:

```sh
vizbin render blob \
    -w W \
    --rgb entropy,delta,xor
```

Then inspect the same hypothesis numerically:

```sh
vizbin inspect blob \
    -w W \
    --rgb entropy,delta,xor \
    --offset OFFSET
```

And repeat.

There is no winning render.

There is only a render that causes you to form a better hypothesis.

## The model to internalize

At first, `vizbin` looks like this:

```text
bytes -> picture
```

Then:

```text
bytes -> projection -> picture
```

Then:

```text
width is a hypothesis
projection is a hypothesis
offset is a hypothesis
```

And eventually:

```text
                              DEPTH
                                |
                                v

bytes -> transform -> transform -> ... -> paint -> pixels
            -t a,b,c


                              BREADTH

                    +-> transform A -> R
                    |
bytes --------------+-> transform B -> G ---> pixels
                    |
                    +-> transform C -> B

                         --rgb A,B,C
```

The practical exploration loop is still simple:

```text
render
  |
  v
notice structure
  |
  v
change width / projection / transform / offset
  |
  v
structure gets clearer?
  |             |
 yes            no
  |             |
  v             +---- back out
inspect
  |
  v
actual measurements and bytes
  |
  v
new hypothesis
  |
  +-----------------------------+
                                |
                                v
                              render
```

`vizbin` does not tell you what an unknown file is.

It gives human vision a cheap way to interrogate structure before you know enough to write the parser.

The picture is never the answer.

It tells you where to ask the next question.