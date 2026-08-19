"""Layout: width families, the square-ish default, offset<->pixel mapping,
and the ``suggest`` scoring heuristic.

Width is a *hypothesis* about stride/record length. These helpers turn that
idea into concrete candidate widths and a cheap score for how "coherent" a
given width makes the data look.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Width families (from the design notes)
# ---------------------------------------------------------------------------

WIDTH_FAMILIES: dict[str, list[int]] = {
    "powers2":   [16, 32, 64, 128, 256, 512, 1024, 2048, 4096],
    "storage":   [512, 1024, 2048, 4096, 8192, 16384],
    "textish":   [40, 64, 72, 80, 96, 120, 132, 160],
    "screenish": [160, 320, 640, 800, 1024, 1280, 1920],
    "records":   [12, 16, 20, 24, 32, 40, 48, 64, 96, 128, 188, 256, 512],
}

# A curated mix used when the user asks for "common".
COMMON_WIDTHS = sorted(set(
    [64, 80, 128, 188, 256, 320, 512, 640, 1024]
))


def family(name: str) -> list[int]:
    if name not in WIDTH_FAMILIES:
        raise KeyError(f"unknown width family {name!r}; "
                       f"known: {', '.join(sorted(WIDTH_FAMILIES))}, common, square")
    return list(WIDTH_FAMILIES[name])


def square_width(pixel_count: int) -> int:
    """Near-square width for a given number of pixels."""
    return max(1, round(math.sqrt(max(pixel_count, 1))))


def parse_widths(spec: str, *, n_pixels: int) -> list[int]:
    """Parse a ``--widths`` spec.

    Accepts a family name (``powers2``/``storage``/``textish``/``screenish``/
    ``records``/``common``), ``square``, or a comma-separated list of integers.
    Results are de-duplicated, sorted, and clamped to widths that produce at
    least one full row for the data.
    """
    spec = spec.strip()
    if spec == "square":
        widths = [square_width(n_pixels)]
    elif spec == "common":
        widths = list(COMMON_WIDTHS)
    elif spec in WIDTH_FAMILIES:
        widths = family(spec)
    else:
        widths = []
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            widths.append(int(part, 0))
    # keep only sane widths
    widths = sorted({w for w in widths if w >= 1})
    return widths


# ---------------------------------------------------------------------------
# Offset <-> pixel mapping
# ---------------------------------------------------------------------------

@dataclass
class OffsetMap:
    """Bidirectional mapping between byte offsets and pixel coordinates.

    ``bpp`` is *source bytes per pixel* (1 for gray/byteclass/entropy/...,
    3 for raw-rgb). ``phase`` and ``base`` account for a leading byte skip
    (raw-rgb grouping phase and/or an inspection ``--offset`` start).
    """
    width: int
    bpp: int = 1
    phase: int = 0
    base: int = 0

    def offset_to_pixel(self, offset: int) -> dict:
        rel = offset - self.base - self.phase
        if rel < 0:
            return {"error": "offset is before the rendered region"}
        pixel = rel // self.bpp
        channel = rel % self.bpp
        return {
            "offset": offset,
            "pixel": pixel,
            "x": pixel % self.width,
            "y": pixel // self.width,
            "channel": channel if self.bpp > 1 else None,
        }

    def pixel_to_offset(self, x: int, y: int) -> dict:
        pixel = y * self.width + x
        start = self.base + self.phase + pixel * self.bpp
        return {
            "x": x,
            "y": y,
            "pixel": pixel,
            "offset": start,
            "offset_end": start + self.bpp - 1,
            "byte_range": (start, start + self.bpp),
        }


# ---------------------------------------------------------------------------
# suggest: candidate generation + row-correlation scoring
# ---------------------------------------------------------------------------

@dataclass
class Suggestion:
    width: int
    family: str
    score: float
    why: str


def candidate_widths(n_bytes: int) -> dict[int, str]:
    """Curated candidate widths tagged by the family they came from.

    Includes every family member that yields at least a couple of rows, plus a
    square-ish width. Later families win the tag on collisions only if a width
    is otherwise untagged.
    """
    cands: dict[int, str] = {}

    def add(w: int, tag: str):
        if w < 1:
            return
        if n_bytes // max(1, w) < 2:  # need at least ~2 rows to be meaningful
            return
        cands.setdefault(w, tag)

    sq = square_width(n_bytes)
    add(sq, "square")
    # a couple of powers of two bracketing the square width
    for fam_name, widths in WIDTH_FAMILIES.items():
        for w in widths:
            add(w, fam_name)
    return cands


def _row_coherence(data: bytes, width: int, *, max_pairs: int = 96) -> float:
    """Mean adjacent-row similarity in [0, 1] for a candidate width (1 bpp).

    High values mean successive rows look alike -- a sign the width aligns with
    a repeating stride/record/row structure. Sampled for speed.
    """
    rows = len(data) // width
    if rows < 2:
        return 0.0
    pairs = min(max_pairs, rows - 1)
    step = max(1, (rows - 1) // pairs)
    total = 0.0
    count = 0
    for i in range(0, rows - 1, step):
        a = data[i * width:(i + 1) * width]
        b = data[(i + 1) * width:(i + 2) * width]
        # mean absolute difference across the row
        diff = 0
        for x, y in zip(a, b):
            diff += x - y if x > y else y - x
        total += 1.0 - (diff / (width * 255.0))
        count += 1
        if count >= pairs:
            break
    return total / count if count else 0.0


def suggest(data: bytes, *, top: int = 12) -> list[Suggestion]:
    """Rank candidate widths by row coherence (design's v2 ``suggest``)."""
    n = len(data)
    cands = candidate_widths(n)
    scored: list[Suggestion] = []
    for w, tag in cands.items():
        score = _row_coherence(data, w)
        why = _explain(tag, score)
        scored.append(Suggestion(width=w, family=tag, score=score, why=why))
    scored.sort(key=lambda s: (-s.score, s.width))
    return scored[:top]


def _explain(tag: str, score: float) -> str:
    base = {
        "square": "near-square default",
        "powers2": "machine-ish power of two",
        "storage": "common page/block size",
        "textish": "human/text layout width",
        "screenish": "common display width",
        "records": "likely fixed-record size",
    }.get(tag, tag)
    if score >= 0.75:
        return f"{base}; strong adjacent-row coherence"
    if score >= 0.55:
        return f"{base}; row correlation spike"
    return base
