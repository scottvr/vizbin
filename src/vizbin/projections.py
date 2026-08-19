"""Projections: turn bytes into pixels under different "hypotheses of meaning".

Each projection produces a flat R,G,B pixel buffer plus a pixel count; the
shared :func:`render` helper lays that buffer out at a chosen width (padding the
final row with black) and returns a :class:`~vizbin.canvas.Raster`.

Performance note: these lean on ``bytes.translate`` (a 256-entry C-level lookup)
and extended-slice assignment (``buf[0::3] = channel``) so the common projections
stay fast without numpy. ``entropy`` uses an O(n) incremental sliding window.
``delta``/``xor`` fall back to a Python-level zip and are the slowest paths.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from vizbin.canvas import ENTROPY_CMAP, Raster, cmap_channels

_CMAP_R, _CMAP_G, _CMAP_B = cmap_channels(ENTROPY_CMAP)


@dataclass
class Projection:
    name: str
    bpp: int  # source bytes consumed per pixel (for offset mapping)
    build: Callable[[bytes, dict], tuple[bytearray, int]]
    doc: str


# ---------------------------------------------------------------------------
# byteclass palette
# ---------------------------------------------------------------------------

_WHITESPACE = {0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20}

_CLASS_COLORS = [
    (22, 22, 30),     # 0: NUL
    (245, 245, 245),  # 1: 0xFF
    (70, 180, 185),   # 2: whitespace
    (95, 205, 115),   # 3: printable ASCII
    (225, 95, 80),    # 4: control
    (110, 125, 235),  # 5: high-bit
]


def _byte_class(b: int) -> int:
    if b == 0x00:
        return 0
    if b == 0xFF:
        return 1
    if b in _WHITESPACE:
        return 2
    if 0x21 <= b <= 0x7E:
        return 3
    if b < 0x20 or b == 0x7F:
        return 4
    return 5


_CLASS_TABLE = bytes(_byte_class(i) for i in range(256))
_PAL_R = bytes(_CLASS_COLORS[_byte_class(i)][0] for i in range(256))
_PAL_G = bytes(_CLASS_COLORS[_byte_class(i)][1] for i in range(256))
_PAL_B = bytes(_CLASS_COLORS[_byte_class(i)][2] for i in range(256))


def _interleave_gray(channel: bytes) -> bytearray:
    n = len(channel)
    rgb = bytearray(n * 3)
    rgb[0::3] = channel
    rgb[1::3] = channel
    rgb[2::3] = channel
    return rgb


def _interleave(r: bytes, g: bytes, b: bytes) -> bytearray:
    rgb = bytearray(len(r) * 3)
    rgb[0::3] = r
    rgb[1::3] = g
    rgb[2::3] = b
    return rgb


# ---------------------------------------------------------------------------
# Projection builders
# ---------------------------------------------------------------------------

def _build_gray(data: bytes, opts: dict) -> tuple[bytearray, int]:
    return _interleave_gray(data), len(data)


def _build_raw_rgb(data: bytes, opts: dict) -> tuple[bytearray, int]:
    phase = int(opts.get("phase", 0)) % 3
    d = data[phase:]
    p = len(d) // 3
    return bytearray(d[:p * 3]), p


def _build_byteclass(data: bytes, opts: dict) -> tuple[bytearray, int]:
    r = data.translate(_PAL_R)
    g = data.translate(_PAL_G)
    b = data.translate(_PAL_B)
    return _interleave(r, g, b), len(data)


def _build_entropy(data: bytes, opts: dict) -> tuple[bytearray, int]:
    n = len(data)
    if n == 0:
        return bytearray(), 0
    window = max(2, min(int(opts.get("window", 256)), n))
    log2 = math.log2
    # +2 headroom: a count can momentarily reach window+1 between add and evict.
    clog = [0.0] * (window + 2)
    for c in range(1, window + 2):
        clog[c] = c * log2(c)

    counts = [0] * 256
    sum_clogc = 0.0
    total = 0
    idx = bytearray(n)
    inv8 = 1.0 / 8.0
    for i in range(n):
        b = data[i]
        c = counts[b]
        sum_clogc += clog[c + 1] - clog[c]
        counts[b] = c + 1
        total += 1
        if total > window:
            ob = data[i - window]
            c = counts[ob]
            sum_clogc += clog[c - 1] - clog[c]
            counts[ob] = c - 1
            total -= 1
        ent = log2(total) - sum_clogc / total  # bits in [0, log2(total)]
        v = ent * inv8
        idx[i] = 255 if v >= 1.0 else int(v * 255)

    r = idx.translate(_CMAP_R)
    g = idx.translate(_CMAP_G)
    b = idx.translate(_CMAP_B)
    return _interleave(r, g, b), n


def _build_delta(data: bytes, opts: dict) -> tuple[bytearray, int]:
    n = len(data)
    if n == 0:
        return bytearray(), 0
    prev = b"\x00" + data[:-1]
    d = bytes(x - y if x >= y else y - x for x, y in zip(data, prev))
    return _interleave_gray(d), n


def _build_xor(data: bytes, opts: dict) -> tuple[bytearray, int]:
    n = len(data)
    if n == 0:
        return bytearray(), 0
    k = max(1, int(opts.get("k", 1)))
    if k >= n:
        return _interleave_gray(data), n
    prev = bytes(k) + data[:-k]
    x = bytes(a ^ b for a, b in zip(data, prev))
    return _interleave_gray(x), n


def _build_bitplane(data: bytes, opts: dict) -> tuple[bytearray, int]:
    plane = max(0, min(7, int(opts.get("plane", 7))))
    mask = 1 << plane
    table = bytes(255 if (i & mask) else 0 for i in range(256))
    bits = data.translate(table)
    return _interleave_gray(bits), len(data)


def _build_nibble(data: bytes, opts: dict) -> tuple[bytearray, int]:
    hi = bytes((i >> 4) * 17 for i in range(256))
    lo = bytes((i & 0x0F) * 17 for i in range(256))
    r = data.translate(hi)
    g = data.translate(lo)
    b = bytes(len(data))
    return _interleave(r, g, b), len(data)


PROJECTIONS: dict[str, Projection] = {
    "gray":      Projection("gray", 1, _build_gray, "one byte -> one grayscale pixel"),
    "raw-rgb":   Projection("raw-rgb", 3, _build_raw_rgb, "three bytes -> one RGB pixel (phase-sensitive)"),
    "byteclass": Projection("byteclass", 1, _build_byteclass, "colour by semantic class (nul/ff/ws/ascii/ctrl/high)"),
    "entropy":   Projection("entropy", 1, _build_entropy, "sliding-window Shannon entropy, magma colormap"),
    "delta":     Projection("delta", 1, _build_delta, "|byte[i]-byte[i-1]| as grayscale"),
    "xor":       Projection("xor", 1, _build_xor, "byte[i] XOR byte[i-k] as grayscale"),
    "bitplane":  Projection("bitplane", 1, _build_bitplane, "a single bitplane as black/white"),
    "nibble":    Projection("nibble", 1, _build_nibble, "high nibble -> red, low nibble -> green"),
}

# Convenient aliases.
_ALIASES = {"rawrgb": "raw-rgb", "rgb": "raw-rgb", "grey": "gray"}


def resolve(name: str) -> str:
    name = name.lower()
    name = _ALIASES.get(name, name)
    if name not in PROJECTIONS:
        raise KeyError(f"unknown mode {name!r}; known: {', '.join(PROJECTIONS)}")
    return name


def bytes_per_pixel(name: str) -> int:
    return PROJECTIONS[resolve(name)].bpp


def pixel_count(name: str, data_len: int, *, phase: int = 0) -> int:
    if bytes_per_pixel(name) == 3:
        return max(0, (data_len - (phase % 3))) // 3
    return data_len


def render(name: str, data: bytes, width: int, **opts) -> Raster:
    """Project ``data`` and lay it out at ``width`` pixels wide."""
    proj = PROJECTIONS[resolve(name)]
    rgb, p = proj.build(data, opts)
    if p == 0 or width < 1:
        return Raster(1, 1)
    height = math.ceil(p / width)
    total = width * height
    if total > p:
        rgb.extend(b"\x00" * ((total - p) * 3))
    return Raster(width, height, rgb)
