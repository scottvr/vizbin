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
from typing import Callable, Union

from vizbin.canvas import ENTROPY_CMAP, Raster, cmap_channels

_CMAP_R, _CMAP_G, _CMAP_B = cmap_channels(ENTROPY_CMAP)


@dataclass
class Projection:
    name: str
    bpp: int  # source bytes consumed per pixel (for offset mapping)
    build: Callable[[bytes, dict], tuple[bytearray, int]]
    doc: str
    # For 1:1 modes, the (transform, colorizer) names this projection composes
    # (see TRANSFORMS / COLORIZERS). None for bespoke modes like raw-rgb.
    transform: str | None = None
    colorizer: str | None = None


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


# Text/whitespace that the ``text`` mode renders meaningfully: printable ASCII
# draws a glyph; tab/LF/CR are structural whitespace tiles.
_TEXT_WS = {0x09, 0x0A, 0x0D}
_PRINTABLE_TABLE = bytes(1 if 0x20 <= i <= 0x7E else 0 for i in range(256))
_TEXTISH_TABLE = bytes(
    1 if (0x20 <= i <= 0x7E or i in _TEXT_WS) else 0 for i in range(256))


def printable_ratio(data: bytes) -> float:
    """Fraction of bytes that are printable ASCII (0x20..0x7E)."""
    if not data:
        return 0.0
    return sum(data.translate(_PRINTABLE_TABLE)) / len(data)


def text_ratio(data: bytes) -> float:
    """Fraction that is printable ASCII or text whitespace (tab/LF/CR).

    A cheap "how textish is this?" score used to advise the ``text`` mode.
    """
    if not data:
        return 0.0
    return sum(data.translate(_TEXTISH_TABLE)) / len(data)


_CLASS_TABLE = bytes(_byte_class(i) for i in range(256))


# Channels come from either bytes.translate (-> bytes) or bytearray.translate
# (-> bytearray), so accept both. Extended-slice assignment handles either.
# Union[...] (not `bytes | bytearray`) so the runtime alias is valid on 3.9.
_Bytes = Union[bytes, bytearray]


def _interleave_gray(channel: _Bytes) -> bytearray:
    n = len(channel)
    rgb = bytearray(n * 3)
    rgb[0::3] = channel
    rgb[1::3] = channel
    rgb[2::3] = channel
    return rgb


def _interleave(r: _Bytes, g: _Bytes, b: _Bytes) -> bytearray:
    rgb = bytearray(len(r) * 3)
    rgb[0::3] = r
    rgb[1::3] = g
    rgb[2::3] = b
    return rgb


# ---------------------------------------------------------------------------
# Transforms (bytes -> bytes) and colorizers (bytes -> pixels)
# ---------------------------------------------------------------------------
#
# A projection is a *transform* -- measure the bytes into a new equal-length
# byte stream -- followed by a *colorizer* that paints that stream into an
# R,G,B buffer. Most modes are a 1:1 (transform, colorizer) pair, which is what
# lets them compose. ``raw-rgb`` packs three source bytes into one pixel and
# ``text`` is a grid renderer, so both stay outside this 1:1 model.

Transform = Callable[[bytes, dict], _Bytes]
Colorizer = Callable[[_Bytes, dict], bytearray]


# -- transforms -------------------------------------------------------------

def _t_identity(data: bytes, opts: dict) -> _Bytes:
    return data


def _t_xor(data: bytes, opts: dict) -> _Bytes:
    n = len(data)
    if n == 0:
        return b""
    k = max(1, int(opts.get("k", 1)))
    if k >= n:
        return data  # nothing to xor against; pass the bytes through
    prev = bytes(k) + data[:-k]
    return bytes(a ^ b for a, b in zip(data, prev))


def _t_delta(data: bytes, opts: dict) -> _Bytes:
    if not data:
        return b""
    prev = b"\x00" + data[:-1]
    return bytes(x - y if x >= y else y - x for x, y in zip(data, prev))


def _t_bitplane(data: bytes, opts: dict) -> _Bytes:
    plane = max(0, min(7, int(opts.get("plane", 7))))
    mask = 1 << plane
    table = bytes(255 if (i & mask) else 0 for i in range(256))
    return data.translate(table)


def _t_class(data: bytes, opts: dict) -> _Bytes:
    return data.translate(_CLASS_TABLE)  # -> class index 0..5


def _t_entropy(data: bytes, opts: dict) -> _Bytes:
    """Sliding-window Shannon entropy scaled to a 0..255 magma index."""
    n = len(data)
    if n == 0:
        return b""
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
        sym = data[i]
        c = counts[sym]
        sum_clogc += clog[c + 1] - clog[c]
        counts[sym] = c + 1
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
    return idx


TRANSFORMS: dict[str, Transform] = {
    "identity": _t_identity,
    "xor": _t_xor,
    "delta": _t_delta,
    "bitplane": _t_bitplane,
    "class": _t_class,
    "entropy": _t_entropy,
}


# -- colorizers -------------------------------------------------------------

# class index (0..5) -> class colour; slots past the class count pad the
# 256-entry translate table and are never hit.
_PALIDX_R = bytes(_CLASS_COLORS[i][0] if i < len(_CLASS_COLORS) else 0 for i in range(256))
_PALIDX_G = bytes(_CLASS_COLORS[i][1] if i < len(_CLASS_COLORS) else 0 for i in range(256))
_PALIDX_B = bytes(_CLASS_COLORS[i][2] if i < len(_CLASS_COLORS) else 0 for i in range(256))

_NIB_HI = bytes((i >> 4) * 17 for i in range(256))
_NIB_LO = bytes((i & 0x0F) * 17 for i in range(256))


def _c_gray(stream: _Bytes, opts: dict) -> bytearray:
    return _interleave_gray(stream)


def _c_magma(stream: _Bytes, opts: dict) -> bytearray:
    s = bytes(stream)
    return _interleave(s.translate(_CMAP_R), s.translate(_CMAP_G), s.translate(_CMAP_B))


def _c_palette(stream: _Bytes, opts: dict) -> bytearray:
    s = bytes(stream)
    return _interleave(s.translate(_PALIDX_R), s.translate(_PALIDX_G), s.translate(_PALIDX_B))


def _c_nibble(stream: _Bytes, opts: dict) -> bytearray:
    s = bytes(stream)
    return _interleave(s.translate(_NIB_HI), s.translate(_NIB_LO), bytes(len(s)))


COLORIZERS: dict[str, Colorizer] = {
    "gray": _c_gray,
    "magma": _c_magma,
    "palette": _c_palette,
    "nibble": _c_nibble,
}


def compose(transform: str, colorizer: str) -> Callable[[bytes, dict], tuple[bytearray, int]]:
    """Build a 1:1 projection builder from a transform + colorizer name."""
    tf = TRANSFORMS[transform]
    cf = COLORIZERS[colorizer]

    def build(data: bytes, opts: dict) -> tuple[bytearray, int]:
        return cf(tf(data, opts), opts), len(data)

    return build


# -- raw-rgb: a bespoke 3:1 packing, outside the transform/colorizer model ---

def _build_raw_rgb(data: bytes, opts: dict) -> tuple[bytearray, int]:
    phase = int(opts.get("phase", 0)) % 3
    d = data[phase:]
    p = len(d) // 3
    return bytearray(d[:p * 3]), p


# ---------------------------------------------------------------------------
# Projection registry
# ---------------------------------------------------------------------------

# 1:1 modes expressed as (transform, colorizer, doc).
_COMPOSED: dict[str, tuple[str, str, str]] = {
    "gray":      ("identity", "gray",    "one byte -> one grayscale pixel"),
    "byteclass": ("class",    "palette", "colour by semantic class (nul/ff/ws/ascii/ctrl/high)"),
    "entropy":   ("entropy",  "magma",   "sliding-window Shannon entropy, magma colormap"),
    "delta":     ("delta",    "gray",    "|byte[i]-byte[i-1]| as grayscale"),
    "xor":       ("xor",      "gray",    "byte[i] XOR byte[i-k] as grayscale"),
    "bitplane":  ("bitplane", "gray",    "a single bitplane as black/white"),
    "nibble":    ("identity", "nibble",  "high nibble -> red, low nibble -> green"),
}

PROJECTIONS: dict[str, Projection] = {
    name: Projection(name, 1, compose(t, c), doc, transform=t, colorizer=c)
    for name, (t, c, doc) in _COMPOSED.items()
}
PROJECTIONS["raw-rgb"] = Projection(
    "raw-rgb", 3, _build_raw_rgb,
    "three bytes -> one RGB pixel (phase-sensitive)")

# Glyph-grid modes: not one-byte-one-pixel, so they live outside PROJECTIONS
# and are dispatched separately by ``render`` (see :mod:`vizbin.textmode`).
GLYPH_MODES = {"text"}

# Convenient aliases.
_ALIASES = {"rawrgb": "raw-rgb", "rgb": "raw-rgb", "grey": "gray",
            "ascii": "text", "txt": "text"}


def mode_names() -> list[str]:
    """Every mode name a user may pass, pixel modes then glyph modes."""
    return sorted(PROJECTIONS) + sorted(GLYPH_MODES)


def resolve(name: str) -> str:
    name = name.lower()
    name = _ALIASES.get(name, name)
    if name not in PROJECTIONS and name not in GLYPH_MODES:
        raise KeyError(f"unknown mode {name!r}; known: {', '.join(mode_names())}")
    return name


def bytes_per_pixel(name: str) -> int:
    n = resolve(name)
    if n in GLYPH_MODES:
        return 1  # one source byte per glyph cell
    return PROJECTIONS[n].bpp


def pixel_count(name: str, data_len: int, *, phase: int = 0) -> int:
    n = resolve(name)
    if n in GLYPH_MODES:
        return data_len  # one cell per byte
    if PROJECTIONS[n].bpp == 3:
        return max(0, (data_len - (phase % 3))) // 3
    return data_len


def _lay_out(rgb: bytearray, p: int, width: int) -> Raster:
    """Lay a flat R,G,B buffer of ``p`` pixels out at ``width``, padding to a
    full final row with black."""
    if p == 0 or width < 1:
        return Raster(1, 1)
    height = math.ceil(p / width)
    total = width * height
    if total > p:
        rgb.extend(b"\x00" * ((total - p) * 3))
    return Raster(width, height, rgb)


def render(name: str, data: bytes, width: int, **opts) -> Raster:
    """Project ``data`` and lay it out at ``width`` pixels wide.

    For glyph modes (``text``), ``width`` is the number of cells per row and the
    work is delegated to :func:`vizbin.textmode.render_text`.
    """
    rn = resolve(name)
    if rn in GLYPH_MODES:
        from vizbin import textmode  # lazy: textmode imports back from here
        return textmode.render_text(data, width, **opts)
    rgb, p = PROJECTIONS[rn].build(data, opts)
    return _lay_out(rgb, p, width)


# ---------------------------------------------------------------------------
# Pipelines: chain modes' transforms, paint with the last mode's colorizer
# ---------------------------------------------------------------------------

def _resolve_transform_name(name: str) -> str:
    """Resolve a transform name or a 1:1 mode name to a TRANSFORMS key.

    Transform names (``xor``, ``class``, ``identity``, ...) map directly; a 1:1
    mode name (``gray``, ``byteclass``, ...) contributes its transform. Since
    the overlapping names (``xor``/``delta``/...) name the same transform either
    way, both vocabularies compose freely. ``raw-rgb``/``text`` are not
    transforms.
    """
    n = _ALIASES.get(name.lower(), name.lower())
    if n in TRANSFORMS:
        return n
    if n in PROJECTIONS:
        t = PROJECTIONS[n].transform
        if t is None:
            raise ValueError(f"mode {n!r} can't be used as a transform "
                             f"(not an equal-length byte stream; e.g. raw-rgb)")
        return t
    if n in GLYPH_MODES:
        raise ValueError(f"mode {n!r} can't be used as a transform")
    raise KeyError(f"unknown transform {name!r}; known: "
                   f"{', '.join(sorted(TRANSFORMS))} (or a 1:1 mode name)")


def _default_colorizer_for(name: str) -> str:
    """The colorizer a stage paints with absent ``--paint``: a mode's own colour,
    else gray for a bare transform."""
    n = _ALIASES.get(name.lower(), name.lower())
    if n in PROJECTIONS and PROJECTIONS[n].colorizer is not None:
        return PROJECTIONS[n].colorizer  # type: ignore[return-value]
    return "gray"


def compose_pipeline(names: list[str], paint: str | None = None
                     ) -> Callable[[bytes, dict], tuple[bytearray, int]]:
    """Build a projection builder that chains transforms and paints the result.

    Each name is a transform or a 1:1 mode (whose transform is used); they run in
    order (output feeds the next). The result is painted by ``paint`` if given,
    else by the last stage's natural colorizer (a mode's own colour, or gray for
    a bare transform). So ``xor,entropy`` is "the entropy of the xor stream"
    (magma by default), and order matters (``entropy,xor`` differs). Any
    transform pairs with any colorizer -- no combination is disallowed.
    """
    if not names:
        raise ValueError("empty pipeline")
    steps = [TRANSFORMS[_resolve_transform_name(n)] for n in names]
    ckey = paint if paint is not None else _default_colorizer_for(names[-1])
    if ckey not in COLORIZERS:
        raise KeyError(f"unknown colorizer {ckey!r}; known: "
                       f"{', '.join(sorted(COLORIZERS))}")
    painter = COLORIZERS[ckey]

    def build(data: bytes, opts: dict) -> tuple[bytearray, int]:
        stream: _Bytes = data
        for step in steps:
            stream = step(bytes(stream), opts)
        return painter(stream, opts), len(data)

    return build


def render_pipeline(names: list[str], data: bytes, width: int,
                    paint: str | None = None, **opts) -> Raster:
    """Render a transform pipeline (see :func:`compose_pipeline`)."""
    rgb, p = compose_pipeline(names, paint=paint)(data, opts)
    return _lay_out(rgb, p, width)


# ---------------------------------------------------------------------------
# Channel composition: drive R/G/B each by its own transform (the parallel axis)
# ---------------------------------------------------------------------------

def compose_channels(names: list[str]) -> Callable[[bytes, dict], tuple[bytearray, int]]:
    """Build a projection that maps up to three transforms onto R, G, B.

    Unlike a pipeline (which chains transforms in *depth*), this runs each
    transform on the *same* source bytes in parallel and packs the results into
    the colour channels -- so ``entropy,delta,xor`` answers "where is it high-
    entropy AND fast-changing AND periodic" in one image. It generalises
    ``nibble`` (R=hi-nibble, G=lo-nibble, B=0). 1-3 transforms; missing channels
    are zero.
    """
    if not names:
        raise ValueError("empty --rgb")
    if len(names) > 3:
        raise ValueError("--rgb takes at most 3 transforms (R, G, B)")
    steps = [TRANSFORMS[_resolve_transform_name(n)] for n in names]

    def build(data: bytes, opts: dict) -> tuple[bytearray, int]:
        chans = [bytes(step(data, opts)) for step in steps]
        while len(chans) < 3:
            chans.append(bytes(len(data)))  # unspecified channel -> 0
        return _interleave(chans[0], chans[1], chans[2]), len(data)

    return build


def render_channels(names: list[str], data: bytes, width: int, **opts) -> Raster:
    """Render a channel composition (see :func:`compose_channels`)."""
    rgb, p = compose_channels(names)(data, opts)
    return _lay_out(rgb, p, width)
