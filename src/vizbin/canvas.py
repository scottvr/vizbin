"""In-memory RGB rasters, colormaps, a tiny bitmap font, and contact sheets.

Everything here works on a flat ``bytearray`` of R,G,B triples so it drops
straight into :func:`vizbin.bmp.write_rgb_bmp`. No third-party imaging code.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Raster
# ---------------------------------------------------------------------------

class Raster:
    """A width x height image stored as an R,G,B-interleaved bytearray."""

    __slots__ = ("width", "height", "rgb")

    def __init__(self, width: int, height: int, rgb: bytearray | None = None,
                 fill: tuple[int, int, int] = (0, 0, 0)):
        self.width = width
        self.height = height
        if rgb is None:
            rgb = bytearray(width * height * 3)
            if fill != (0, 0, 0):
                r, g, b = fill
                n = width * height
                rgb[0::3] = bytes((r,)) * n
                rgb[1::3] = bytes((g,)) * n
                rgb[2::3] = bytes((b,)) * n
        self.rgb = rgb

    def fill_rect(self, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
        r, g, b = color
        row = (bytes((r, g, b))) * w
        for yy in range(y, min(y + h, self.height)):
            start = (yy * self.width + x) * 3
            self.rgb[start:start + w * 3] = row

    def blit(self, src: "Raster", x: int, y: int) -> None:
        """Copy ``src`` onto this raster at (x, y), clipping to bounds."""
        for sy in range(src.height):
            dy = y + sy
            if dy < 0 or dy >= self.height:
                continue
            sx0 = max(0, -x)
            sx1 = min(src.width, self.width - x)
            if sx1 <= sx0:
                continue
            s = (sy * src.width + sx0) * 3
            e = (sy * src.width + sx1) * 3
            d = (dy * self.width + (x + sx0)) * 3
            self.rgb[d:d + (e - s)] = src.rgb[s:e]

    def resized(self, new_w: int, new_h: int) -> "Raster":
        """Nearest-neighbour resample to ``new_w`` x ``new_h``."""
        if new_w == self.width and new_h == self.height:
            return Raster(self.width, self.height, bytearray(self.rgb))
        new_w = max(1, new_w)
        new_h = max(1, new_h)
        out = bytearray(new_w * new_h * 3)
        # Precompute source x for each destination x.
        xmap = [(dx * self.width) // new_w for dx in range(new_w)]
        src = self.rgb
        sw = self.width
        for dy in range(new_h):
            sy = (dy * self.height) // new_h
            base = sy * sw
            d = dy * new_w * 3
            for dx in range(new_w):
                s = (base + xmap[dx]) * 3
                out[d] = src[s]
                out[d + 1] = src[s + 1]
                out[d + 2] = src[s + 2]
                d += 3
        return Raster(new_w, new_h, out)

    def fit(self, max_w: int, max_h: int) -> "Raster":
        """Downscale (never upscale) to fit within a box, preserving aspect."""
        if self.width <= max_w and self.height <= max_h:
            return self
        scale = min(max_w / self.width, max_h / self.height)
        return self.resized(max(1, int(self.width * scale)),
                            max(1, int(self.height * scale)))

    def draw_text(self, x: int, y: int, text: str,
                  color: tuple[int, int, int] = (230, 230, 230), scale: int = 1) -> None:
        cx = x
        for ch in text:
            glyph = _FONT.get(ch.lower(), _FONT[" "])
            for gy, rowbits in enumerate(glyph):
                for gx in range(FONT_W):
                    if rowbits & (1 << (FONT_W - 1 - gx)):
                        self.fill_rect(cx + gx * scale, y + gy * scale, scale, scale, color)
            cx += (FONT_W + 1) * scale


# ---------------------------------------------------------------------------
# Colormaps
# ---------------------------------------------------------------------------

def build_colormap(anchors: list[tuple[float, tuple[int, int, int]]]) -> list[tuple[int, int, int]]:
    """Interpolate a 256-entry colormap from (position, rgb) anchor points."""
    cmap: list[tuple[int, int, int]] = []
    for i in range(256):
        t = i / 255.0
        # find bracketing anchors
        lo = anchors[0]
        hi = anchors[-1]
        for j in range(len(anchors) - 1):
            if anchors[j][0] <= t <= anchors[j + 1][0]:
                lo, hi = anchors[j], anchors[j + 1]
                break
        span = hi[0] - lo[0]
        f = 0.0 if span == 0 else (t - lo[0]) / span
        r = round(lo[1][0] + (hi[1][0] - lo[1][0]) * f)
        g = round(lo[1][1] + (hi[1][1] - lo[1][1]) * f)
        b = round(lo[1][2] + (hi[1][2] - lo[1][2]) * f)
        cmap.append((r, g, b))
    return cmap


# A magma-ish perceptual ramp: dark -> purple -> orange -> pale yellow.
ENTROPY_CMAP = build_colormap([
    (0.00, (0, 0, 4)),
    (0.25, (60, 20, 110)),
    (0.50, (150, 44, 108)),
    (0.75, (230, 110, 62)),
    (1.00, (252, 232, 168)),
])


def cmap_channels(cmap: list[tuple[int, int, int]]) -> tuple[bytes, bytes, bytes]:
    """Return three 256-byte lookup tables (R, G, B) for ``bytes.translate``."""
    r = bytes(c[0] for c in cmap)
    g = bytes(c[1] for c in cmap)
    b = bytes(c[2] for c in cmap)
    return r, g, b


# ---------------------------------------------------------------------------
# Contact sheet
# ---------------------------------------------------------------------------

@dataclass
class ContactStyle:
    cell: tuple[int, int] = (256, 256)
    gap: int = 8
    label_h: int = 10
    bg: tuple[int, int, int] = (18, 18, 22)
    label_color: tuple[int, int, int] = (220, 220, 220)
    cols: int | None = None


def contact_sheet(tiles: list[tuple[str, Raster]], style: ContactStyle | None = None) -> Raster:
    """Compose labelled tiles into a grid. Each tile is (label, raster)."""
    import math

    style = style or ContactStyle()
    n = len(tiles)
    if n == 0:
        return Raster(1, 1)

    cols = style.cols or max(1, math.ceil(math.sqrt(n)))
    rows = math.ceil(n / cols)

    cell_w, cell_h = style.cell
    thumbs = [(label, r.fit(cell_w, cell_h)) for label, r in tiles]

    cw = cell_w + style.gap
    ch = cell_h + style.label_h + style.gap
    sheet = Raster(style.gap + cols * cw, style.gap + rows * ch, fill=style.bg)

    for idx, (label, thumb) in enumerate(thumbs):
        cx = style.gap + (idx % cols) * cw
        cy = style.gap + (idx // cols) * ch
        sheet.draw_text(cx, cy, label, style.label_color, scale=1)
        # centre the thumbnail within the cell
        off_x = cx + (cell_w - thumb.width) // 2
        off_y = cy + style.label_h + (cell_h - thumb.height) // 2
        sheet.blit(thumb, off_x, off_y)

    return sheet


# ---------------------------------------------------------------------------
# Tiny 5x7 bitmap font (lowercase + digits + a few symbols)
# ---------------------------------------------------------------------------

FONT_W = 5
FONT_H = 7

_GLYPHS = {
    " ": ("     ", "     ", "     ", "     ", "     ", "     ", "     "),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "..##.", ".#...", "#....", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    "a": ("     ", "     ", ".###.", "....#", ".####", "#...#", ".####"),
    "b": ("#....", "#....", "####.", "#...#", "#...#", "#...#", "####."),
    "c": ("     ", "     ", ".####", "#....", "#....", "#....", ".####"),
    "d": ("....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"),
    "e": ("     ", "     ", ".###.", "#...#", "#####", "#....", ".###."),
    "f": ("..##.", ".#..#", ".#...", "###..", ".#...", ".#...", ".#..."),
    "g": ("     ", ".####", "#...#", "#...#", ".####", "....#", ".###."),
    "h": ("#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#"),
    "i": ("..#..", "     ", ".##..", "..#..", "..#..", "..#..", ".###."),
    "j": ("...#.", "     ", "..##.", "...#.", "...#.", "#..#.", ".##.."),
    "k": ("#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#."),
    "l": (".##..", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "m": ("     ", "     ", "##.#.", "#.#.#", "#.#.#", "#...#", "#...#"),
    "n": ("     ", "     ", "####.", "#...#", "#...#", "#...#", "#...#"),
    "o": ("     ", "     ", ".###.", "#...#", "#...#", "#...#", ".###."),
    "p": ("     ", "####.", "#...#", "#...#", "####.", "#....", "#...."),
    "q": ("     ", ".####", "#...#", "#...#", ".####", "....#", "....#"),
    "r": ("     ", "     ", "#.##.", "##..#", "#....", "#....", "#...."),
    "s": ("     ", "     ", ".####", "#....", ".###.", "....#", "####."),
    "t": (".#...", ".#...", "###..", ".#...", ".#...", ".#..#", "..##."),
    "u": ("     ", "     ", "#...#", "#...#", "#...#", "#..##", ".##.#"),
    "v": ("     ", "     ", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "w": ("     ", "     ", "#...#", "#...#", "#.#.#", "#.#.#", ".#.#."),
    "x": ("     ", "     ", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"),
    "y": ("     ", "#...#", "#...#", "#...#", ".####", "....#", ".###."),
    "z": ("     ", "     ", "#####", "...#.", "..#..", ".#...", "#####"),
    ".": ("     ", "     ", "     ", "     ", "     ", ".##..", ".##.."),
    ",": ("     ", "     ", "     ", "     ", ".##..", ".##..", ".#..."),
    "-": ("     ", "     ", "     ", "#####", "     ", "     ", "     "),
    "+": ("     ", "..#..", "..#..", "#####", "..#..", "..#..", "     "),
    ":": ("     ", ".##..", ".##..", "     ", ".##..", ".##..", "     "),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    "#": (".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", ".#.#."),
    "(": ("..##.", ".#...", "#....", "#....", "#....", ".#...", "..##."),
    ")": (".##..", "...#.", "....#", "....#", "....#", "...#.", ".##.."),
    "%": ("##..#", "##.#.", "..#..", ".#...", "#..##", "..#.#", ".#.##"),
}


def _compile(rows: tuple[str, ...]) -> tuple[int, ...]:
    out = []
    for row in rows:
        bits = 0
        for i, ch in enumerate(row):
            if ch == "#":
                bits |= 1 << (FONT_W - 1 - i)
        out.append(bits)
    return tuple(out)


_FONT = {ch: _compile(rows) for ch, rows in _GLYPHS.items()}
