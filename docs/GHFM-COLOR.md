# vizbin, drawn with math

*An easter egg. Not a real feature. Yet.*

GitHub-Flavoured Markdown renders LaTeX math via MathJax — and MathJax will draw a
`\rule{w}{h}`: a filled rectangle of exact dimensions. Give each rectangle a
`\color`, run-length-encode a row of pixels into a few coloured rules, put one row
per Markdown bullet (bullets pack tighter vertically than blank-line-separated math),
and you can draw a **vizbin render straight into a Markdown page — no image file.**

This is the pixel-grid sequel to a thing done once before with *text* over in
[phart's GHM-LATEX experiment](https://github.com/scottvr/phart/blob/main/docs/GHM-LATEX.md)
— that one fought MathJax's not-actually-monospace `\mathtt` font with a
tilde-space-ratio fudge factor. This one sidesteps glyphs entirely (rules are
geometry, not letters) — but MathJax gets the last laugh anyway. More below.

## Exhibit A — `entropy`, which behaves

`vizbin render mixed_regions.bin -m entropy` is horizontal entropy bands: text (dark),
zero padding (near-black), a compressed block (bright magma), a periodic tail. Each
row is nearly one colour, so RLE gives ~one rule per row and the rows line up:

- ${\color{#000004}\rule{0.55ex}{1.1ex}}{\color{#46176e}\rule{0.55ex}{1.1ex}}{\color{#6c216d}\rule{0.55ex}{1.1ex}}{\color{#71226d}\rule{0.55ex}{1.1ex}}{\color{#80266c}\rule{0.55ex}{1.1ex}}{\color{#8b296c}\rule{0.55ex}{1.1ex}}{\color{#8d2a6c}\rule{0.55ex}{1.1ex}}{\color{#8b296c}\rule{0.55ex}{1.1ex}}{\color{#8d2a6c}\rule{0.55ex}{1.1ex}}{\color{#89286c}\rule{0.55ex}{1.1ex}}{\color{#8b296c}\rule{0.55ex}{1.1ex}}{\color{#8d2a6c}\rule{1.65ex}{1.1ex}}{\color{#8e2a6c}\rule{0.55ex}{1.1ex}}{\color{#8b296c}\rule{0.55ex}{1.1ex}}{\color{#8d2a6c}\rule{2.20ex}{1.1ex}}{\color{#8e2a6c}\rule{0.55ex}{1.1ex}}{\color{#8b296c}\rule{0.55ex}{1.1ex}}{\color{#8d2a6c}\rule{1.10ex}{1.1ex}}$
- ${\color{#8d2a6c}\rule{13.20ex}{1.1ex}}$
- ${\color{#8d2a6c}\rule{13.20ex}{1.1ex}}$
- ${\color{#8e2a6c}\rule{0.55ex}{1.1ex}}{\color{#902a6c}\rule{0.55ex}{1.1ex}}{\color{#912b6c}\rule{0.55ex}{1.1ex}}{\color{#922b6c}\rule{0.55ex}{1.1ex}}{\color{#912b6c}\rule{1.10ex}{1.1ex}}{\color{#902a6c}\rule{0.55ex}{1.1ex}}{\color{#8e2a6c}\rule{0.55ex}{1.1ex}}{\color{#8d2a6c}\rule{1.10ex}{1.1ex}}{\color{#8a296c}\rule{0.55ex}{1.1ex}}{\color{#89286c}\rule{0.55ex}{1.1ex}}{\color{#86286c}\rule{0.55ex}{1.1ex}}{\color{#84276c}\rule{0.55ex}{1.1ex}}{\color{#82276c}\rule{0.55ex}{1.1ex}}{\color{#80266c}\rule{0.55ex}{1.1ex}}{\color{#7d256d}\rule{0.55ex}{1.1ex}}{\color{#7a256d}\rule{0.55ex}{1.1ex}}{\color{#78246d}\rule{0.55ex}{1.1ex}}{\color{#75236d}\rule{0.55ex}{1.1ex}}{\color{#71226d}\rule{0.55ex}{1.1ex}}{\color{#6e216d}\rule{0.55ex}{1.1ex}}{\color{#6b216d}\rule{0.55ex}{1.1ex}}{\color{#68206d}\rule{0.55ex}{1.1ex}}$
- ${\color{#000004}\rule{13.20ex}{1.1ex}}$
- ${\color{#000004}\rule{13.20ex}{1.1ex}}$
- ${\color{#000004}\rule{13.20ex}{1.1ex}}$
- ${\color{#000004}\rule{13.20ex}{1.1ex}}$
- ${\color{#f3b47b}\rule{4.95ex}{1.1ex}}{\color{#f3b67d}\rule{2.20ex}{1.1ex}}{\color{#f3b87e}\rule{2.75ex}{1.1ex}}{\color{#f4ba80}\rule{1.65ex}{1.1ex}}{\color{#f3b87e}\rule{1.65ex}{1.1ex}}$
- ${\color{#f3b87e}\rule{2.20ex}{1.1ex}}{\color{#f3b67d}\rule{5.50ex}{1.1ex}}{\color{#f3b87e}\rule{0.55ex}{1.1ex}}{\color{#f3b67d}\rule{0.55ex}{1.1ex}}{\color{#f3b87e}\rule{2.20ex}{1.1ex}}{\color{#f4ba80}\rule{0.55ex}{1.1ex}}{\color{#f3b87e}\rule{1.65ex}{1.1ex}}$
- ${\color{#f3b67d}\rule{4.40ex}{1.1ex}}{\color{#f3b47b}\rule{2.20ex}{1.1ex}}{\color{#f2b279}\rule{1.65ex}{1.1ex}}{\color{#f2b178}\rule{2.20ex}{1.1ex}}{\color{#f2b279}\rule{0.55ex}{1.1ex}}{\color{#f2b178}\rule{0.55ex}{1.1ex}}{\color{#f2b279}\rule{1.10ex}{1.1ex}}{\color{#f2b178}\rule{0.55ex}{1.1ex}}$
- ${\color{#f3b47b}\rule{0.55ex}{1.1ex}}{\color{#f3b67d}\rule{0.55ex}{1.1ex}}{\color{#f3b47b}\rule{1.65ex}{1.1ex}}{\color{#f3b67d}\rule{1.65ex}{1.1ex}}{\color{#f3b47b}\rule{3.85ex}{1.1ex}}{\color{#f3b67d}\rule{0.55ex}{1.1ex}}{\color{#f3b47b}\rule{1.10ex}{1.1ex}}{\color{#f2b279}\rule{1.65ex}{1.1ex}}{\color{#f2b178}\rule{1.10ex}{1.1ex}}{\color{#f2b279}\rule{0.55ex}{1.1ex}}$
- ${\color{#f3b47b}\rule{1.10ex}{1.1ex}}{\color{#f3b67d}\rule{0.55ex}{1.1ex}}{\color{#f3b47b}\rule{0.55ex}{1.1ex}}{\color{#f2b279}\rule{0.55ex}{1.1ex}}{\color{#f3b47b}\rule{7.15ex}{1.1ex}}{\color{#f3b67d}\rule{0.55ex}{1.1ex}}{\color{#f3b47b}\rule{1.65ex}{1.1ex}}{\color{#f2b279}\rule{1.10ex}{1.1ex}}$
- ${\color{#f1ad74}\rule{1.10ex}{1.1ex}}{\color{#f2af76}\rule{3.85ex}{1.1ex}}{\color{#f2b178}\rule{2.20ex}{1.1ex}}{\color{#f2af76}\rule{0.55ex}{1.1ex}}{\color{#f2b178}\rule{1.10ex}{1.1ex}}{\color{#f2b279}\rule{1.10ex}{1.1ex}}{\color{#f3b47b}\rule{0.55ex}{1.1ex}}{\color{#f2b279}\rule{0.55ex}{1.1ex}}{\color{#f3b47b}\rule{2.20ex}{1.1ex}}$
- ${\color{#f3b67d}\rule{0.55ex}{1.1ex}}{\color{#f3b47b}\rule{1.10ex}{1.1ex}}{\color{#f3b67d}\rule{1.65ex}{1.1ex}}{\color{#f3b47b}\rule{1.10ex}{1.1ex}}{\color{#f3b67d}\rule{1.10ex}{1.1ex}}{\color{#f3b47b}\rule{2.20ex}{1.1ex}}{\color{#f3b67d}\rule{1.10ex}{1.1ex}}{\color{#f3b47b}\rule{1.10ex}{1.1ex}}{\color{#f2b279}\rule{2.75ex}{1.1ex}}{\color{#f3b47b}\rule{0.55ex}{1.1ex}}$
- ${\color{#f3b47b}\rule{3.30ex}{1.1ex}}{\color{#f2b178}\rule{0.55ex}{1.1ex}}{\color{#f2b279}\rule{1.10ex}{1.1ex}}{\color{#f2b178}\rule{2.75ex}{1.1ex}}{\color{#f2af76}\rule{0.55ex}{1.1ex}}{\color{#f1ad74}\rule{0.55ex}{1.1ex}}{\color{#f1a971}\rule{0.55ex}{1.1ex}}{\color{#f0a56e}\rule{0.55ex}{1.1ex}}{\color{#efa16a}\rule{0.55ex}{1.1ex}}{\color{#ee9b65}\rule{0.55ex}{1.1ex}}{\color{#ee9862}\rule{0.55ex}{1.1ex}}{\color{#ed945f}\rule{0.55ex}{1.1ex}}{\color{#ec905c}\rule{0.55ex}{1.1ex}}{\color{#eb8a57}\rule{0.55ex}{1.1ex}}$
- ${\color{#3b146d}\rule{13.20ex}{1.1ex}}$
- ${\color{#3b146d}\rule{13.20ex}{1.1ex}}$
- ${\color{#3b146d}\rule{13.20ex}{1.1ex}}$
- ${\color{#3b146d}\rule{13.20ex}{1.1ex}}$

That's the magma ramp of a mixed blob, rendered by the equation typesetter. It is,
against all reason, *legible*.

## Exhibit B — `byteclass`, which does not

`vizbin render mixed_regions.bin -m byteclass` colours every byte by class, so the
high-entropy rows change colour constantly — many rules per row:

- ${\color{#5fcd73}\rule{1.65ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{2.75ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{2.75ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{2.75ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{1.10ex}{1.1ex}}$
- ${\color{#5fcd73}\rule{1.65ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{2.75ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{2.75ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{2.75ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{1.10ex}{1.1ex}}$
- ${\color{#5fcd73}\rule{1.65ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{2.75ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{2.75ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{2.75ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{1.10ex}{1.1ex}}$
- ${\color{#16161e}\rule{13.20ex}{1.1ex}}$
- ${\color{#16161e}\rule{13.20ex}{1.1ex}}$
- ${\color{#16161e}\rule{13.20ex}{1.1ex}}$
- ${\color{#16161e}\rule{13.20ex}{1.1ex}}$
- ${\color{#16161e}\rule{13.20ex}{1.1ex}}$
- ${\color{#6e7deb}\rule{1.65ex}{1.1ex}}{\color{#5fcd73}\rule{1.10ex}{1.1ex}}{\color{#6e7deb}\rule{1.65ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.10ex}{1.1ex}}{\color{#5fcd73}\rule{1.10ex}{1.1ex}}{\color{#6e7deb}\rule{2.20ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{1.10ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}$
- ${\color{#5fcd73}\rule{1.10ex}{1.1ex}}{\color{#6e7deb}\rule{2.20ex}{1.1ex}}{\color{#5fcd73}\rule{1.10ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{2.75ex}{1.1ex}}{\color{#6e7deb}\rule{1.10ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.65ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}$
- ${\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.10ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{1.10ex}{1.1ex}}{\color{#6e7deb}\rule{1.65ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{1.10ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{2.20ex}{1.1ex}}{\color{#6e7deb}\rule{1.10ex}{1.1ex}}$
- ${\color{#6e7deb}\rule{1.10ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.10ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.10ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.10ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{1.10ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}$
- ${\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.10ex}{1.1ex}}{\color{#5fcd73}\rule{2.20ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{1.10ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.10ex}{1.1ex}}{\color{#5fcd73}\rule{1.65ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}$
- ${\color{#5fcd73}\rule{1.10ex}{1.1ex}}{\color{#6e7deb}\rule{1.65ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.65ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{1.65ex}{1.1ex}}{\color{#6e7deb}\rule{1.10ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#46b4b9}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.65ex}{1.1ex}}$
- ${\color{#6e7deb}\rule{1.65ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.65ex}{1.1ex}}{\color{#5fcd73}\rule{2.20ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{2.20ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}$
- ${\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#e15f50}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{0.55ex}{1.1ex}}{\color{#5fcd73}\rule{0.55ex}{1.1ex}}{\color{#6e7deb}\rule{1.10ex}{1.1ex}}{\color{#5fcd73}\rule{8.80ex}{1.1ex}}$
- ${\color{#5fcd73}\rule{13.20ex}{1.1ex}}$
- ${\color{#5fcd73}\rule{13.20ex}{1.1ex}}$
- ${\color{#5fcd73}\rule{13.20ex}{1.1ex}}$
- ${\color{#5fcd73}\rule{13.20ex}{1.1ex}}$

See how the noisy rows drift wider and the grid shears? That's the ghost from the
phart page, reincarnated. It isn't a font problem this time — it's that **MathJax
inserts a hair of spacing between adjacent atoms**, and since each row has a
*different number* of coloured rules (RLE segments the noisy rows into more pieces),
each row accumulates a different amount of slop. Uniform rows align; busy rows wander.
*Is it monospace? Is it though.*

## Would we ship this?

No. vizbin's [real gallery](GALLERY.md) uses SVG and PNGs (and vizbin can of course write RLE bitmaps), which are sharper and don't
depend on a Markdown renderer's mood. This page exists because it *works*, because it
is *ridiculous*, and because a tool with imaging in its DNA deserves at least one
picture drawn by the part of the stack that swore it only did equations.

Revisit only if some genuine use case ever makes us go "oh, yeah…".
