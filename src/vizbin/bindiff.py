"""Structural / visual diff of two binaries.

Naive byte-by-byte comparison is useless the moment one file has an insertion or
deletion: everything after the shift reads as "changed". So we diff at the
*block* level with :class:`difflib.SequenceMatcher` (pure stdlib), which finds the
longest matching block runs and reports the gaps as replace / insert / delete --
surviving shifts the way ``cmp`` can't. Blocks are hashed by identity (their raw
bytes), and the block size scales with file size so the matcher stays fast.

The result is a list of byte-offset regions on both sides, a similarity score,
and an optional diff *image* (identical bytes dimmed, changes lit) that routes
through the same render/terminal pipeline as everything else.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from vizbin.canvas import Raster
from vizbin.projections import _interleave_gray, _lay_out

# region colours in the diff image
_C_REPLACE = (222, 52, 52)    # red   -- bytes present in both, changed
_C_INSERT = (54, 200, 84)     # green -- bytes only in B (added)


@dataclass
class Region:
    tag: str        # equal | replace | insert | delete
    a_lo: int
    a_hi: int
    b_lo: int
    b_hi: int

    @property
    def a_len(self) -> int:
        return self.a_hi - self.a_lo

    @property
    def b_len(self) -> int:
        return self.b_hi - self.b_lo


@dataclass
class DiffResult:
    size_a: int
    size_b: int
    block: int
    similarity: float          # fraction of bytes identical, 0..1
    regions: list              # list[Region], in order, covering both files


def _auto_block(size: int, target_blocks: int = 4096) -> int:
    """Block size so the matcher sees ~target_blocks blocks (bounded work)."""
    return max(8, size // target_blocks)


def diff(a: bytes, b: bytes, block: int | None = None) -> DiffResult:
    size = max(len(a), len(b))
    if block is None:
        block = _auto_block(size)
    block = max(1, block)
    A = [a[i:i + block] for i in range(0, len(a), block)]
    B = [b[i:i + block] for i in range(0, len(b), block)]
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)

    regions: list[Region] = []
    equal_bytes = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        a_lo, a_hi = i1 * block, min(i2 * block, len(a))
        b_lo, b_hi = j1 * block, min(j2 * block, len(b))
        regions.append(Region(tag, a_lo, a_hi, b_lo, b_hi))
        if tag == "equal":
            equal_bytes += a_hi - a_lo
    similarity = equal_bytes / size if size else 1.0
    return DiffResult(len(a), len(b), block, similarity, regions)


def changed_regions(result: DiffResult) -> list:
    """Just the non-equal regions (the interesting ones)."""
    return [r for r in result.regions if r.tag != "equal"]


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def format_report(result: DiffResult, name_a: str, name_b: str,
                  max_rows: int = 40) -> str:
    lines = [f"{name_a} ({result.size_a} bytes) vs {name_b} ({result.size_b} bytes)"]
    if result.similarity >= 1.0 and result.size_a == result.size_b:
        lines.append("  identical")
        return "\n".join(lines)
    changed = changed_regions(result)
    lines.append(f"  {result.similarity * 100:.1f}% identical "
                 f"(block {result.block}); {len(changed)} changed region(s)")
    for r in changed[:max_rows]:
        if r.tag == "replace":
            span = (f"A:0x{r.a_lo:08x}-0x{r.a_hi:08x}  B:0x{r.b_lo:08x}-0x{r.b_hi:08x}"
                    f"  ({r.b_len} bytes)")
        elif r.tag == "insert":
            span = f"A:{'—':>19}  B:0x{r.b_lo:08x}-0x{r.b_hi:08x}  (+{r.b_len} bytes)"
        else:  # delete
            span = f"A:0x{r.a_lo:08x}-0x{r.a_hi:08x}  B:{'—':>19}  (-{r.a_len} bytes)"
        lines.append(f"    {r.tag:<8} {span}")
    if len(changed) > max_rows:
        lines.append(f"    ... and {len(changed) - max_rows} more")
    return "\n".join(lines)


def to_json(result: DiffResult, name_a: str, name_b: str) -> str:
    import json
    return json.dumps({
        "a": name_a, "b": name_b,
        "size_a": result.size_a, "size_b": result.size_b,
        "block": result.block,
        "similarity": round(result.similarity, 4),
        "changed_regions": [
            {"tag": r.tag, "a_offset": r.a_lo, "a_size": r.a_len,
             "b_offset": r.b_lo, "b_size": r.b_len}
            for r in changed_regions(result)
        ],
    }, indent=2)


def render_diff(b: bytes, result: DiffResult, width: int) -> Raster:
    """A diff image over the *new* file (B): identical bytes dimmed to grayscale,
    replaced bytes red, inserted bytes green. Deleted bytes aren't in B."""
    rgb = bytearray(len(b) * 3)
    for r in result.regions:
        if r.tag == "delete":
            continue  # not present in B
        lo, hi = r.b_lo, r.b_hi
        if lo >= hi:
            continue
        if r.tag == "equal":
            seg = b[lo:hi].translate(_DIM)          # dim the unchanged bytes
            rgb[lo * 3:hi * 3] = _interleave_gray(seg)
        else:
            color = _C_REPLACE if r.tag == "replace" else _C_INSERT
            rgb[lo * 3:hi * 3] = bytes(color) * (hi - lo)
    return _lay_out(rgb, len(b), width)


# byte -> a dim version of itself (unchanged regions recede behind the changes)
_DIM = bytes(v // 3 for v in range(256))
