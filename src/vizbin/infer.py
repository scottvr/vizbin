"""Structure inference: turn a repeating-record binary into a draft layout.

The loop is: pick a record stride (via row-coherence, reusing :mod:`vizbin.layout`),
reshape the bytes into an ``n_records x stride`` grid, then work out the fields in
two passes -- first claim multi-byte **counters** (monotonic integers, found by
trying int widths directly, since a counter's low byte *cycles* and would never
look like a slowly-varying column), then group the remaining columns into
constant magic, printable strings, and opaque high-entropy blobs.

The result is a *draft* the analyst verifies, not ground truth, so every field
carries its evidence and a confidence. Pure stdlib.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from dataclasses import field as dc_field

_WS = {0x09, 0x0A, 0x0D}


def _printable(b: int) -> bool:
    return 0x20 <= b <= 0x7E


def _shannon(col: bytes) -> float:
    n = len(col)
    if n == 0:
        return 0.0
    counts: dict[int, int] = {}
    for b in col:
        counts[b] = counts.get(b, 0) + 1
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


# ---------------------------------------------------------------------------
# per-column profile
# ---------------------------------------------------------------------------

@dataclass
class ColumnProfile:
    index: int
    distinct: int
    constant: int | None          # the value, if every record agrees
    printable_frac: float
    entropy: float                # bits, 0..8
    label: str                    # const | ascii | high | vary


def _profile_column(index: int, col: bytes) -> ColumnProfile:
    distinct = len(set(col))
    constant = col[0] if distinct == 1 else None
    printable = sum(1 for b in col if _printable(b) or b in _WS) / len(col)
    ent = _shannon(col)
    if constant is not None:
        label = "const"
    elif printable >= 0.75:
        label = "ascii"
    elif ent >= 6.5:
        label = "high"
    else:
        label = "vary"
    return ColumnProfile(index, distinct, constant, printable, ent, label)


# ---------------------------------------------------------------------------
# inferred fields
# ---------------------------------------------------------------------------

@dataclass
class Field:
    offset: int
    size: int
    kind: str            # magic | reserved | const | string | counter | blob | bytes
    name: str
    confidence: float
    evidence: str
    detail: dict = dc_field(default_factory=dict)


def _col_ints(cols: list[bytes], lo: int, width: int, n_rec: int, endian: str) -> list[int]:
    out = []
    for r in range(n_rec):
        b = bytes(cols[lo + c][r] for c in range(width))
        out.append(int.from_bytes(b, endian))  # type: ignore[arg-type]
    return out


def _counter_fit(vals: list[int]):
    """Return (nondec_fraction, median_abs_delta) for a candidate int sequence."""
    pairs = list(zip(vals, vals[1:]))
    nondec = sum(1 for a, b in pairs if b >= a) / len(pairs)
    deltas = sorted(abs(b - a) for a, b in pairs)
    med = deltas[len(deltas) // 2]
    return nondec, med


_MIN_RECORDS = 16  # below this, column stats and counters are unreliable


def _try_counter(cols: list[bytes], lo: int, width: int, n_rec: int, endian: str):
    """If [lo, lo+width) reads as a clean monotonic counter in the given
    ``endian``, return (endian, score, first, last); else None."""
    if n_rec < 8:  # too few records: random ints look 'monotonic' by chance
        return None
    vals = _col_ints(cols, lo, width, n_rec, endian)
    if vals[-1] <= vals[0]:
        return None  # a counter ends higher than it starts (rejects signed
        #              sawtooths that look mostly-increasing as unsigned)
    nondec, med = _counter_fit(vals)
    avg = (vals[-1] - vals[0]) / (n_rec - 1)  # a counter increments consistently
    if nondec >= 0.95 and med <= 4 * abs(avg) + 4:
        return endian, nondec, vals[0], vals[-1]
    return None


def infer_fields(data: bytes, stride: int) -> tuple[list[Field], int]:
    """Infer the field layout of ``stride``-byte records in ``data``.

    Three ordered passes: (A) claim runs of >=2 printable columns as strings, so
    an incrementing ASCII field (e.g. "0199") is a string, not a fake counter;
    (B) claim monotonic-integer counters on the remaining varying columns (an
    *isolated* printable byte -- like a counter's high byte -- is still fair
    game); (C) group everything else into magic/reserved/blob/bytes.
    """
    n_rec = len(data) // stride
    if n_rec < 2:
        return [], n_rec
    cols = [data[j:n_rec * stride:stride] for j in range(stride)]
    profs = [_profile_column(j, cols[j]) for j in range(stride)]
    claimed = [False] * stride
    is_const = [p.constant is not None for p in profs]
    is_zero = [p.constant == 0 for p in profs]
    starts: dict[int, Field] = {}  # pre-claimed strings and counters, by offset

    # --- pass A: printable string runs (>=2 adjacent ASCII columns) ---
    j = 0
    while j < stride:
        if profs[j].label == "ascii":
            k = j
            while k < stride and profs[k].label == "ascii":
                k += 1
            if k - j >= 2:
                frac = sum(profs[c].printable_frac for c in range(j, k)) / (k - j)
                starts[j] = Field(j, k - j, "string", "text", round(frac, 2),
                                  "printable ASCII across records")
                for c in range(j, k):
                    claimed[c] = True
            j = k
        else:
            j += 1

    # --- pass B: counters, anchored to runs of non-const, unclaimed columns ---
    # Grow a varying run to the smallest power-of-2 that covers it, padding with
    # adjacent zeros only (a small counter's own high zeros -- never a separate
    # reserved field or a magic). LE pads on the right, BE on the left.
    j = 0
    while j < stride:
        if is_const[j] or claimed[j]:
            j += 1
            continue
        k = j
        while k < stride and not is_const[k] and not claimed[k]:
            k += 1
        run_w = k - j
        chosen = None
        if run_w <= 8:
            w = 2 if run_w <= 2 else 4 if run_w <= 4 else 8
            for lo, endian in ((j, "little"), (k - w, "big")):
                if lo < 0 or lo + w > stride or any(claimed[c] for c in range(lo, lo + w)):
                    continue
                if not all(is_zero[c] for c in range(lo, lo + w) if not (j <= c < k)):
                    continue
                res = _try_counter(cols, lo, w, n_rec, endian)
                if res:
                    chosen = (lo, w, res)
                    break
        if chosen:
            lo, w, (endian, score, first, last) = chosen
            for c in range(lo, lo + w):
                claimed[c] = True
            starts[lo] = Field(lo, w, "counter", "count", round(score, 2),
                               f"monotonic {8 * w}-bit int ({endian}-endian), "
                               f"e.g. {first}..{last}",
                               {"endian": endian, "first": first, "last": last})
            j = max(k, lo + w)
        else:
            j = k

    # --- pass C: assemble in order, filling gaps with const/blob/bytes ---
    fields: list[Field] = []
    j = 0
    while j < stride:
        if j in starts:
            fields.append(starts[j])
            j += starts[j].size
            continue
        p = profs[j]
        if p.label == "const":
            k = j
            while k < stride and not claimed[k] and profs[k].label == "const":
                k += 1
            vals = bytes(profs[c].constant or 0 for c in range(j, k))
            allzero = all(b == 0 for b in vals)
            n_print = sum(_printable(b) for b in vals)
            magicish = (not allzero and n_print >= 2
                        and all(_printable(b) or b == 0 for b in vals))
            if allzero:
                kind, ev = "reserved", "constant zero (padding/reserved)"
            elif magicish:
                kind = "magic"
                ev = f'constant "{vals.decode("ascii", "replace").rstrip(chr(0))}"'
            else:
                kind, ev = "const", f"constant 0x{vals.hex()}"
            fields.append(Field(j, k - j, kind, kind, 1.0, ev, {"value": vals.hex()}))
            j = k
        elif p.label == "ascii":  # isolated printable column (runs were pre-claimed)
            fields.append(Field(j, 1, "string", "text", round(p.printable_frac, 2),
                                "printable byte"))
            j += 1
        else:
            k = j
            while (k < stride and not claimed[k] and k not in starts
                   and profs[k].label in ("high", "vary")):
                k += 1
            ent = sum(profs[c].entropy for c in range(j, k)) / (k - j)
            if ent >= 6.5:
                fields.append(Field(j, k - j, "blob", "data", round(ent / 8, 2),
                                    f"high entropy ~{ent:.1f} bits/byte (hash/compressed?)"))
            else:
                fields.append(Field(j, k - j, "bytes", "field", 0.4,
                                    f"low-entropy varying (~{ent:.1f} bits/byte)"))
            j = k

    return fields, n_rec


# ---------------------------------------------------------------------------
# stride selection + report
# ---------------------------------------------------------------------------

def _aligned_const_frac(data: bytes, stride: int, sample: int = 512) -> float:
    """Fraction of byte columns that are near-constant (modal value in >=90% of
    records) at a candidate stride. Sample-size invariant -- a true constant is
    1.0 at any record count, while random data effectively never hits 0.9 -- so
    it isolates the stride at which fixed fields (magic/reserved/flags) line up,
    without the small-sample inflation that biases mean-peakiness toward huge
    strides."""
    n_rec = min(len(data) // stride, sample)
    if n_rec < _MIN_RECORDS:
        return 0.0
    c = 0
    for j in range(stride):
        col = data[j:n_rec * stride:stride]
        if Counter(col).most_common(1)[0][1] / n_rec >= 0.9:
            c += 1
    return c / stride


def _autocorr(sample: bytes, lag: int) -> float:
    """Fraction of byte positions equal to the byte ``lag`` ahead. Peaks at the
    record stride (and its multiples), because fixed fields repeat every record."""
    n = len(sample) - lag
    if n <= 0:
        return 0.0
    return sum(x == y for x, y in zip(sample, sample[lag:])) / n


def select_stride(data: bytes, override: int | None = None):
    """Pick a record stride. Returns (stride|None, why).

    Finds the period by byte-autocorrelation (dense over every lag, so arbitrary
    record sizes work), takes the *smallest* strong local peak (the fundamental,
    not a multiple), and requires enough records to be reliable.
    """
    if override:
        n_rec = len(data) // override if override else 0
        note = "" if n_rec >= 8 else f" -- only {n_rec} records, low confidence"
        return override, f"user-specified (--stride){note}"

    cap = min(len(data) // _MIN_RECORDS, 1024)
    if cap < 2:
        return None, (f"not enough data for auto-detection "
                      f"(need >= {2 * _MIN_RECORDS} bytes; try --stride)")
    sample = data[:16384]
    ac = [(_autocorr(sample, d), d) for d in range(4, cap + 1)]  # >=4-byte records
    if not ac:
        return None, "not enough data for auto-detection (try --stride)"
    peak = max(v for v, _ in ac)
    if peak < 0.12:
        return None, f"no periodic record structure (byte-autocorrelation {peak:.2f})"
    acmap = {d: v for v, d in ac}
    strong = [d for v, d in ac
              if v >= 0.85 * peak
              and v >= acmap.get(d - 1, 0) and v >= acmap.get(d + 1, 0)]  # local peak
    stride = min(strong) if strong else min(d for v, d in ac if v >= 0.85 * peak)
    frac = _aligned_const_frac(data, stride)
    note = " -- nearly all-constant, may be padding not records" if frac >= 0.95 else ""
    return stride, (f"period @ {stride} (autocorr {acmap[stride]:.2f}, "
                    f"{frac * 100:.0f}% constant columns){note}")


def format_report(data: bytes, stride: int, why: str,
                  fields: list[Field], n_rec: int) -> str:
    lines = [f"stride {stride} bytes ({why}); {n_rec} complete records", ""]
    lines.append(f"  {'offset':>7}  {'size':>4}  {'kind':<9} {'conf':>4}  evidence")
    lines.append(f"  {'-' * 7}  {'-' * 4}  {'-' * 9} {'-' * 4}  {'-' * 44}")
    for f in fields:
        lines.append(f"  0x{f.offset:04x}  {f.size:>4}  {f.kind:<9} "
                     f"{f.confidence:>4.2f}  {f.evidence}")
    covered = sum(f.size for f in fields)
    lines.append("")
    lines.append(f"  {len(fields)} fields covering {covered}/{stride} bytes")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# machine-readable export
# ---------------------------------------------------------------------------

def _sanitize_id(name: str) -> str:
    """A valid lowercase identifier (Kaitai/struct field or meta id)."""
    s = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
    if not s or not s[0].isalpha():
        s = "r_" + s
    return s


def _field_names(fields: list[Field]) -> list[str]:
    """Unique lowercase names, one per field, for exports."""
    base_for = {"magic": "magic", "counter": "count", "string": "text",
                "reserved": "reserved", "blob": "data", "const": "const",
                "bytes": "field"}
    seen: dict[str, int] = {}
    out = []
    for f in fields:
        base = base_for.get(f.kind, "field")
        seen[base] = seen.get(base, 0) + 1
        out.append(base if seen[base] == 1 else f"{base}{seen[base]}")
    return out


def to_json(stride: int, why: str, fields: list[Field], n_rec: int,
            source: str | None = None) -> str:
    import json
    names = _field_names(fields)
    return json.dumps({
        "source": source,
        "stride": stride,
        "records": n_rec,
        "detected_by": why,
        "fields": [
            {"name": name, "offset": f.offset, "size": f.size, "kind": f.kind,
             "confidence": f.confidence, "evidence": f.evidence,
             **({"detail": f.detail} if f.detail else {})}
            for f, name in zip(fields, names)
        ],
    }, indent=2)


def to_kaitai(stride: int, fields: list[Field], meta_id: str = "record") -> str:
    """A Kaitai Struct (.ksy) stub for one record."""
    names = _field_names(fields)
    lines = ["meta:", f"  id: {_sanitize_id(meta_id)}", "seq:"]
    for f, name in zip(fields, names):
        lines.append(f"  - id: {name}")
        value = f.detail.get("value")
        if f.kind in ("magic", "const") and value:
            arr = ", ".join(f"0x{b:02x}" for b in bytes.fromhex(value))
            lines.append(f"    contents: [{arr}]")
        elif f.kind == "counter":
            suffix = "le" if f.detail.get("endian") == "little" else "be"
            lines.append(f"    type: u{f.size}{suffix}")
        elif f.kind == "string":
            lines.append("    type: str")
            lines.append(f"    size: {f.size}")
            lines.append("    encoding: ASCII")
        else:  # reserved / blob / bytes -> raw bytes
            lines.append(f"    size: {f.size}")
    return "\n".join(lines) + "\n"


def to_struct(fields: list[Field]) -> str:
    """A Python ``struct`` format string + field names for one record."""
    endians = [f.detail["endian"] for f in fields
               if f.kind == "counter" and "endian" in f.detail]
    order = ">" if endians and endians[0] == "big" else "<"
    mixed = len(set(endians)) > 1
    intcode = {2: "H", 4: "I", 8: "Q"}
    names = _field_names(fields)
    codes, fieldnames = [], []
    for f, name in zip(fields, names):
        if f.kind == "counter" and f.size in intcode:
            codes.append(intcode[f.size])
            fieldnames.append(name)
        elif f.kind == "reserved":
            codes.append(f"{f.size}x")  # padding: skipped, no name
        else:  # magic / string / blob / bytes / const / odd-size counter
            codes.append(f"{f.size}s")
            fieldnames.append(name)
    fmt = order + "".join(codes)
    lines = [f'format = "{fmt}"',
             f"fields = {fieldnames!r}",
             f'# struct.Struct("{fmt}").unpack(record) -> ({", ".join(fieldnames)})']
    if mixed:
        lines.append(f"# NOTE: mixed endianness detected; struct uses one order "
                     f"({order}). Use kaitai for per-field endianness.")
    return "\n".join(lines)
