"""Structural fingerprint of a blob.

`profile` distills a file into a compact, machine-readable description -- overall
entropy, byte-class mix, a coarse entropy-band **region** map, and (if present) a
detected record stride. Emitted as JSON/JSONL, it turns vizbin into a *sensor*:
fingerprint a whole corpus and cluster / triage / anomaly-detect it in the
terminal -- something interactive visualizers structurally cannot do.

The `regions` map (adjacent windows merged by entropy class) is also the seed for
finding *heterogeneous* blobs -- a file with several differently-structured parts.

Pure stdlib; leans on :mod:`vizbin.projections` for the byte classes so the
fingerprint lines up with the ``byteclass`` render, and on :mod:`vizbin.infer`
for the optional record stride.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass
from dataclasses import field as dc_field

from vizbin import projections

_CLASS_NAMES = ("nul", "ff", "whitespace", "ascii", "control", "high")


def _entropy_from_counter(c: "Counter[int]", total: int) -> float:
    if total == 0:
        return 0.0
    # + 0.0 normalizes a single-symbol window's -0.0 to 0.0
    return -sum((n / total) * math.log2(n / total) for n in c.values()) + 0.0


def _printable_frac(data: bytes) -> float:
    if not data:
        return 0.0
    return sum(data.translate(projections._TEXTISH_TABLE)) / len(data)


def _region_kind(entropy: float, printable: float) -> str:
    """Classify a window by its entropy + printability."""
    if printable >= 0.70:
        return "text"
    if entropy < 1.0:
        return "sparse"          # zeros / padding / very repetitive
    if entropy >= 7.5:
        return "compressed"      # compressed or encrypted (near-max entropy)
    if entropy >= 6.0:
        return "code"            # native code / packed
    return "binary"              # structured binary / mixed


@dataclass
class Region:
    offset: int
    size: int
    kind: str
    entropy: float
    printable: float


@dataclass
class Profile:
    source: str
    size: int
    entropy: float
    distinct_bytes: int
    printable_ratio: float
    byte_classes: dict            # name -> fraction (sums to ~1)
    head_hex: str                 # first 16 bytes, for magic-based grouping
    record_stride: int | None
    regions: list                 # list[Region]
    entropy_profile: list         # fixed-length coarse entropy vector (for clustering)
    notes: list = dc_field(default_factory=list)


def _windows(data: bytes, win: int):
    for off in range(0, len(data), win):
        chunk = data[off:off + win]
        c = Counter(chunk)
        ent = _entropy_from_counter(c, len(chunk))
        printable = _printable_frac(chunk)
        yield off, len(chunk), ent, printable


def _resample(values: list, n: int) -> list:
    """Down/-up-sample a list to exactly ``n`` values by bucket-averaging."""
    if not values:
        return [0.0] * n
    out = []
    for i in range(n):
        lo = i * len(values) // n
        hi = max(lo + 1, (i + 1) * len(values) // n)
        bucket = values[lo:hi]
        out.append(round(sum(bucket) / len(bucket), 3))
    return out


def build_profile(data: bytes, source: str, *, detect_stride: bool = True) -> Profile:
    n = len(data)
    hist = Counter(data)
    entropy = _entropy_from_counter(hist, n)

    class_counts = {name: 0 for name in _CLASS_NAMES}
    for value, count in hist.items():
        class_counts[_CLASS_NAMES[projections._byte_class(value)]] += count
    byte_classes = {name: round(c / n, 4) if n else 0.0
                    for name, c in class_counts.items()}

    # window the file: >=1024 bytes so per-window entropy is meaningful (a 256-
    # byte window of random data only reaches ~7.1 bits, below the 'compressed'
    # threshold), capped so a huge file stays cheap.
    win = min(max(1024, n // 256), 65536) if n else 1024
    wins = list(_windows(data, win)) if n else []

    regions: list[Region] = []
    for off, size, ent, printable in wins:
        kind = _region_kind(ent, printable)
        if regions and regions[-1].kind == kind:
            r = regions[-1]
            # size-weighted running entropy/printable as the region grows
            tot = r.size + size
            r.entropy = round((r.entropy * r.size + ent * size) / tot, 3)
            r.printable = round((r.printable * r.size + printable * size) / tot, 3)
            r.size = tot
        else:
            regions.append(Region(off, size, kind, round(ent, 3), round(printable, 3)))

    entropy_profile = _resample([w[2] for w in wins], 32)

    stride = None
    notes: list = []
    if detect_stride and n:
        try:
            from vizbin import infer
            stride, why = infer.select_stride(data)
            if stride:
                notes.append(f"record stride {stride}: {why}")
        except Exception:  # stride detection is a bonus; never fail the profile
            stride = None
    if len(regions) > 1:
        kinds = sorted({r.kind for r in regions})
        notes.append(f"heterogeneous: {len(regions)} regions ({', '.join(kinds)})")

    return Profile(
        source=source, size=n, entropy=round(entropy, 3),
        distinct_bytes=len(hist), printable_ratio=round(_printable_frac(data), 4),
        byte_classes=byte_classes, head_hex=data[:16].hex(),
        record_stride=stride, regions=regions,
        entropy_profile=entropy_profile, notes=notes,
    )


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def to_dict(p: Profile) -> dict:
    d = asdict(p)
    d["regions"] = [asdict(r) for r in p.regions]
    return d


def to_json(p: Profile) -> str:
    import json
    return json.dumps(to_dict(p))  # one line -> JSONL-friendly for corpora


def format_report(p: Profile) -> str:
    lines = [f"{p.source}:  {p.size} bytes"]
    lines.append(f"  entropy {p.entropy:.2f} bits/byte   printable {p.printable_ratio * 100:.0f}%"
                 f"   distinct {p.distinct_bytes}/256   head {p.head_hex[:16]}")
    cls = "  ".join(f"{name} {frac * 100:.0f}%"
                    for name, frac in p.byte_classes.items() if frac >= 0.01)
    lines.append(f"  byte-classes: {cls}")
    if p.record_stride:
        lines.append(f"  record stride: {p.record_stride}  (try: vizbin infer {p.source})")
    if len(p.regions) > 1:
        lines.append(f"  regions ({len(p.regions)}):")
        for r in p.regions:
            lines.append(f"    0x{r.offset:08x}  {r.size:>8}  {r.kind:<10} "
                         f"entropy {r.entropy:.2f}")
    else:
        r = p.regions[0] if p.regions else None
        if r:
            lines.append(f"  uniform: {r.kind} (entropy {r.entropy:.2f})")
    return "\n".join(lines)
