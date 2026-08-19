# Changelog

All notable changes to vizbin are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/scottvr/vizbin/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/scottvr/vizbin/releases/tag/v0.2.0
[0.1.0]: https://github.com/scottvr/vizbin/releases/tag/v0.1.0
