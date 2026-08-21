# Changelog

All notable changes to vizbin are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`infer`** — structure inference: draft a record/field layout from repeating
  binary structure. Detects the record stride by byte-autocorrelation (any size,
  or `--stride N`), profiles each byte column across records, and reports fields
  with evidence + confidence: constant **magic**/reserved, monotonic **counters**
  (with endianness), printable **strings**, and high-entropy **blobs**. Reports
  honestly when there's no strong record structure. Closes the loop from "I can
  *see* records" to "here's a machine-readable guess at their layout."
- **`infer` export formats** — `--json` (structured, for pipelines), `--format
  kaitai` (a Kaitai Struct `.ksy` stub with per-field endianness and fixed-magic
  `contents`), and `--format struct` (a Python `struct` format + field names that
  accounts for every byte, so `struct.calcsize(format) == stride`). Turns the
  draft layout into an actual parser you can compile.

## [0.4.0] - 2026-08-21

### Added
- **Exposed the two projection axes.** A mode is a *transform* (`-t`/`--transform`,
  also `--pipe`) plus a *colorizer* (`--paint`); the named modes are now just
  presets for common pairings and no longer limit what's expressible. `-t` accepts
  transform names (`identity, xor, delta, bitplane, class, entropy`) as well as
  mode names, and `--paint` (`gray, magma, palette, nibble`) overrides the colour
  of any mode or pipeline. Any transform pairs with any colorizer — no combination
  is disallowed (the only limit is structural: `raw-rgb`/`text` aren't transforms).
  A chain's default colour is still its last stage's (so `xor,entropy` stays
  magma — no change from 0.3.0).
- **`render --rgb t1,t2,t3` channel composition**: up to three transforms drive
  R, G, B in parallel (`entropy,delta,xor`) — the *breadth* partner to `-t`'s
  *depth*. `inspect --rgb ...` reports the three channel values at an offset,
  matching the rendered pixel exactly. New API: `projections.compose_channels` /
  `render_channels`.

### Docs
- New guided-tour tutorial (`docs/QUICKSTART-TUTORIAL.md`), replacing the old
  exploration field guide; README's intro link now points to it.

## [0.3.0] - 2026-08-21

### Added
- `render --pipe m1,m2,...` **pipelines**: chain modes' transforms in order and
  paint with the last mode's colorizer (e.g. `xor,entropy` = "entropy of the xor
  stream"). Order-significant; a single-mode pipe equals the mode, and
  `delta,gray` == `delta`. Only 1:1 modes compose (`raw-rgb`/`text` are rejected).
  New API: `projections.compose_pipeline` / `render_pipeline`.
- `inspect` now reports **mode-specific readouts** when given the source file: the
  character in `text`, RGB source bytes in `raw-rgb`, XOR operands + result in
  `xor`, the selected bit in `bitplane`, the local entropy window in `entropy`,
  and the delta in `delta` (plus byte value/class/nibbles for the simple modes).
  Predecessors, windows, and phase are computed region-relative to `--base` so the
  readout matches exactly what the projection rendered; it reads only a bounded
  window around the offset. New `inspect` options `--k`, `--window`, `--plane`.
  Without a source file, `inspect` stays pure offset↔pixel geometry.
- `inspect --modes a,b,c` stacks a readout per mode for one coordinate (each
  projection is an independent view of the same offset).
- `raw-rgb` readouts add an inline ASCII gloss (`-> "sta"`) when the pixel's three
  source bytes are all printable.
- Cross-mode **ASCII advisory** (default on, `--no-hints` to silence): when you
  view a non-`text` mode but the bytes look like text, `inspect` whispers what the
  surrounding bytes spell and `render` nudges toward `-m text`. Advisory only —
  vizbin never switches mode for you. `--no-hints` is a **global flag**: it parses
  anywhere on the command line, appears once in the top-level `--help`, and also
  silences the `suggest` hint. The `inspect` hint also fires on a printable **run**
  of at least `-n`/`--min-run` glyphs (default 6, like `strings -n`), so it catches
  a magic string / filename embedded in binary or padding, not just wholly-text
  regions.

### Internal
- Refactored the projection engine into composable **transforms** (bytes→bytes)
  and **colorizers** (bytes→pixels): each 1:1 mode is now a `(transform,
  colorizer)` pair (e.g. `xor` = xor-transform + gray-colorizer, `byteclass` =
  class-index + palette). Output is byte-identical (golden-hash guarded). This is
  the groundwork the `--pipe` pipelines build on.

## [0.2.0] - 2026-08-19

### Added
- `text` render mode (aliases `ascii`, `txt`): a glyph-per-byte grid renderer.
  Printable ASCII is drawn as its glyph so text regions are readable, while
  non-text bytes (NUL, controls, tab/LF/CR, high-bit, `0xFF`) are painted as
  solid `byteclass`-coloured tiles — a visual `strings` that keeps the
  surrounding binary structure visible. Options: `--scale`, `--mono-text`.
  Composes with the pixel modes in `contact --modes ...`.
- Vendored public-domain 8×8 font (`font8x8_basic`, CC0) as `vizbin.font8x8`,
  keeping the project pure-stdlib.
- `suggest` now prints an advisory hint to try `-m text` when the input is
  substantially printable (never switches mode for you).
- `inspect` is text-mode aware: `OffsetMap` gained a `cell` field so
  offset↔pixel mapping accounts for `8*scale`-pixel glyph cells. New
  `inspect --scale`.

### Changed
- Version is now single-sourced from `vizbin.__version__` and read by the build
  backend; the CLI `--version` and packaging metadata stay in lock-step.

### Project
- Added CI (lint + type-check + test matrix on Python 3.9–3.14), a hardened
  Trusted-Publishing release workflow with version-consistency gates, an
  action-SHA-pinning policy check, Dependabot, and lightweight pre-commit hooks.

## [0.1.0]

### Added
- Initial release: `render`, `sweep`, `contact`, `animate`, `suggest`,
  `inspect`, and reversible `bmp`/`unbmp` payload modes. Projections: `gray`,
  `raw-rgb`, `byteclass`, `entropy`, `delta`, `xor`, `bitplane`, `nibble`.
  Pure-stdlib BMP writer and animated-GIF encoder.

[Unreleased]: https://github.com/scottvr/vizbin/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/scottvr/vizbin/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/scottvr/vizbin/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/scottvr/vizbin/releases/tag/v0.2.0
[0.1.0]: https://github.com/scottvr/vizbin/releases/tag/v0.1.0
