"""The ``text`` render mode: one byte -> one glyph cell, not one pixel.

Unlike the projections in :mod:`vizbin.projections` (which map each byte to a
single pixel and lean on the shared linear layout in ``render``), text mode is a
*grid* renderer: every byte becomes an 8x8 cell. Printable ASCII is drawn as its
glyph so text regions become literally readable; everything else is painted as a
solid tile in its :func:`vizbin.projections._byte_class` colour, so NUL padding,
control bytes, and high-bit data still pop out of the surrounding prose.

This is the hybrid that beats piping a blob through ``strings``: you see the
text *and* the binary structure wrapped around it in one image. Good for tar
members, PEM/cert blobs, embedded scripts, and the ``.rodata``/``.rdata`` string
tables of executables (not ``.text`` -- that is machine code and renders as a
wall of colour, which is itself a useful tell).

Kept out of the ``PROJECTIONS`` table on purpose: it does not honour the
one-byte-one-pixel contract that :func:`vizbin.projections.render` assumes. It is
reached through that same ``render`` entry point via a lazy dispatch, so ``text``
still works everywhere a mode name is accepted (``render``, ``sweep``,
``contact --modes ...``) and composes with the pixel modes on a contact sheet.
"""

from __future__ import annotations

import math

from vizbin.canvas import Raster
from vizbin.font8x8 import FONT8X8
from vizbin.projections import _CLASS_COLORS, _byte_class

# The font is Basic Latin only; anything >= 0x80 has no glyph.
_PRINTABLE_LO = 0x20
_PRINTABLE_HI = 0x7E

# Default palette: neutral dark page, light ink -- readable, not competing with
# the byte-class tiles that only appear on the non-text bytes.
_DEFAULT_FG = (226, 226, 232)
_DEFAULT_BG = (14, 14, 18)


def render_text(data: bytes, cols: int, *, scale: int = 1, colorize: bool = True,
                fg: tuple[int, int, int] = _DEFAULT_FG,
                bg: tuple[int, int, int] = _DEFAULT_BG,
                **_ignored) -> Raster:
    """Render ``data`` as a grid of glyph cells, ``cols`` bytes per row.

    ``cols`` is the width in *cells* (== bytes per row), mirroring how width in
    the 1-byte-per-pixel modes is also bytes per row -- so ``-w 64`` lines text
    mode up with ``gray`` byte-for-byte. Each cell is ``8 * scale`` pixels square.

    * printable ASCII (0x20..0x7E) -> its glyph in ``fg`` over ``bg``
      (space is a blank glyph, so it reads as a space);
    * anything else (NUL, controls, tab/newline, high-bit, 0xFF) -> a solid tile
      in that byte's class colour when ``colorize`` (default), else left blank.
    """
    n = len(data)
    if n == 0 or cols < 1:
        return Raster(1, 1)

    scale = max(1, int(scale))
    cell = 8 * scale
    rows = math.ceil(n / cols)
    width_px = cols * cell
    height_px = rows * cell

    ras = Raster(width_px, height_px, fill=bg)
    rgb = ras.rgb
    fr, fg_, fb = fg

    for i in range(n):
        b = data[i]
        x0 = (i % cols) * cell
        y0 = (i // cols) * cell

        if _PRINTABLE_LO <= b <= _PRINTABLE_HI:
            glyph = FONT8X8[b]
            if scale == 1:
                for ry in range(8):
                    rowbits = glyph[ry]
                    if not rowbits:
                        continue
                    base = ((y0 + ry) * width_px + x0) * 3
                    for cx in range(8):
                        if rowbits & (1 << cx):
                            p = base + cx * 3
                            rgb[p] = fr
                            rgb[p + 1] = fg_
                            rgb[p + 2] = fb
            else:
                for ry in range(8):
                    rowbits = glyph[ry]
                    if not rowbits:
                        continue
                    for cx in range(8):
                        if rowbits & (1 << cx):
                            ras.fill_rect(x0 + cx * scale, y0 + ry * scale,
                                          scale, scale, fg)
        elif colorize:
            ras.fill_rect(x0, y0, cell, cell, _CLASS_COLORS[_byte_class(b)])
        # else: non-printable with colour off -> leave the background showing.

    return ras
