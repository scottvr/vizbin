#!/usr/bin/env python3
"""vizbin UAT: generate labeled binary test files with KNOWN structure, and
(optionally) run `vizbin infer` on each so you can compare expected vs actual.

    python scripts/uat.py                 # generate files into ./uat/ + print the manifest
    python scripts/uat.py --run           # also run `vizbin infer` on each (expected vs actual)
    python scripts/uat.py --run --struct  # ...and show the `--format struct` parser stub
    python scripts/uat.py --outdir /tmp/uat

Each case prints its TRUE layout first, then vizbin's guess -- eyeball the diff.
The generators are deterministic (seeded), so files are stable across runs and
you can re-test after tuning. Pure stdlib, like vizbin itself.
"""
from __future__ import annotations

import argparse
import os
import random
import struct
import subprocess
import sys

SEED = 0x5A11_B1  # deterministic; re-runs produce identical files
CASES = []        # (filename, expected_stride|None, truth, builder)


def case(filename, stride, truth):
    def deco(fn):
        CASES.append((filename, stride, truth, fn))
        return fn
    return deco


def _blob(rng, n):
    return bytes(rng.randrange(256) for _ in range(n))


# --- happy path: magic | u32-le counter | reserved | string | blob -----------
@case("happy_le_24.bin", 24,
      "magic 'REC\\0'(4) | u32-le counter(4) | reserved(4) | ascii name(8) | blob(4)")
def gen_happy(rng):
    out = bytearray()
    for i in range(400):
        out += (b"REC\x00" + struct.pack("<I", 100_000 + i * 137) + bytes(4)
                + (b"n%04d" % i).ljust(8, b"\x00") + _blob(rng, 4))
    return bytes(out)


# --- big-endian, two counters ------------------------------------------------
@case("bigendian_10.bin", 10,
      "magic 'BE'(2) | u32-be counter(4) | u32-be counter2(4)  [both big-endian]")
def gen_be(rng):
    out = bytearray()
    for i in range(400):
        out += b"BE" + struct.pack(">I", 0x0100_0000 + i * 0x9137) + struct.pack(">I", i)
    return bytes(out)


# --- small u16 counter -------------------------------------------------------
@case("u16_seq_12.bin", 12,
      "magic 'S1'(2) | u16-le seq(2) | reserved(2) | ascii tag(6)")
def gen_u16(rng):
    out = bytearray()
    for i in range(600):
        out += b"S1" + struct.pack("<H", i % 60000) + bytes(2) + b"tag%03d" % (i % 1000)
    return bytes(out)


# --- u64 id ------------------------------------------------------------------
@case("u64_id_20.bin", 20,
      "magic 'IDDB'(4) | u64-le id(8) | blob(8)")
def gen_u64(rng):
    out = bytearray()
    for i in range(400):
        out += b"IDDB" + struct.pack("<Q", 0x1000_0000_0000 + i * 0x5_1234) + _blob(rng, 8)
    return bytes(out)


# --- realistic Unix-epoch timestamps (read as a monotonic counter) ----------
@case("timestamps_16.bin", 16,
      "u32-le unix_time(~1.7e9, +~1s)(4) | u32-le seq(4) | blob(8)  "
      "[timestamp reads as a counter -- correct, it IS monotonic]")
def gen_ts(rng):
    out = bytearray()
    t = 1_700_000_000
    for i in range(600):
        t += rng.randrange(1, 3)
        out += struct.pack("<I", t) + struct.pack("<I", i) + _blob(rng, 8)
    return bytes(out)


# --- odd/arbitrary stride 37 (autocorrelation must find it) ------------------
@case("oddstride_37.bin", 37,
      "magic 'ODD'(3) | u32-le counter(4) | reserved(6) | ascii(8) | blob(16)")
def gen_odd(rng):
    out = bytearray()
    for i in range(500):
        out += (b"ODD" + struct.pack("<I", i * 3) + bytes(6)
                + (b"row%05d" % i)[:8].ljust(8, b"\x00") + _blob(rng, 16))
    return bytes(out)


# --- MPEG-TS-like: 188-byte packets, sync byte 0x47 -------------------------
@case("mpegts_188.bin", 188,
      "sync 0x47(1) | header(3, varying) | payload(184)  [real-world TS stride]")
def gen_ts188(rng):
    out = bytearray()
    for _ in range(300):
        out += bytes([0x47]) + _blob(rng, 3) + _blob(rng, 184)
    return bytes(out)


# --- page-structured DB: 256-byte pages -------------------------------------
@case("pagedb_256.bin", 256,
      "magic 'PAGE'(4) | u32-le page_no(4) | u16-le nslots(2) | reserved(6) | payload(240)")
def gen_pagedb(rng):
    out = bytearray()
    for i in range(200):
        out += (b"PAGE" + struct.pack("<I", i) + struct.pack("<H", rng.randrange(4, 40))
                + bytes(6) + _blob(rng, 240))
    return bytes(out)


# --- float payload (floats look like varying/blob, not counters) ------------
@case("floats_16.bin", 16,
      "u32-le seq(4) | float64 value(8)  [floats are 'bytes/blob', not a counter] | pad(4)")
def gen_floats(rng):
    import math
    out = bytearray()
    for i in range(500):
        v = math.sin(i / 20) * 1000
        out += struct.pack("<I", i) + struct.pack("<d", v) + bytes(4)
    return bytes(out)


# --- NEGATIVE: newline-delimited text (variable-length, NOT fixed records) --
@case("textlog.log", None,
      "variable-length text lines -- expect NO strong record structure (or a weak/spurious stride)")
def gen_text(rng):
    lines = []
    for i in range(2000):
        lines.append(f"2026-08-21T12:{i % 60:02d}:{rng.randrange(60):02d} INFO worker={i % 8} "
                     f"msg=processed item {i}")
    return ("\n".join(lines) + "\n").encode()


# --- NEGATIVE: pure random ---------------------------------------------------
@case("random.bin", None, "pure random -- expect 'no periodic record structure'")
def gen_random(rng):
    return _blob(rng, 16384)


# --- degenerate: mostly zero padding ----------------------------------------
@case("padding.bin", None,
      "sparse data in zero padding -- expect a degenerate/near-all-constant result")
def gen_padding(rng):
    out = bytearray(16384)
    for off in range(0, len(out), 512):
        out[off:off + 4] = _blob(rng, 4)  # a few live bytes per 512 block
    return bytes(out)


# --- for the picture, not infer: mixed regions (great for --rgb / --term) ----
@case("mixed_regions.bin", None,
      "text | zeros | random | periodic 'ABCD' -- for `render --rgb entropy,delta,xor` "
      "(not a record file)")
def gen_mixed(rng):
    return (b"def hello():\n    return 'world'\n" * 60
            + bytes(3000)
            + _blob(rng, 5000)
            + b"ABCD" * 800)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", default="uat", help="where to write the files (default: ./uat)")
    ap.add_argument("--run", action="store_true", help="run `vizbin infer` on each file")
    ap.add_argument("--struct", action="store_true", help="with --run, also show --format struct")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    rng = random.Random(SEED)
    total = 0
    print(f"Generating {len(CASES)} test files into {args.outdir}/\n")
    for filename, stride, truth, builder in CASES:
        data = builder(rng)
        path = os.path.join(args.outdir, filename)
        with open(path, "wb") as fh:
            fh.write(data)
        total += len(data)
        exp = f"stride {stride}" if stride else "NO record structure"
        print(f"── {filename}  ({len(data)} bytes)")
        print(f"   TRUTH:    {exp} — {truth}")
        if args.run:
            infer = subprocess.run([sys.executable, "-m", "vizbin", "infer", path],
                                   capture_output=True, text=True)
            out = (infer.stdout or infer.stderr).rstrip()
            print("   VIZBIN:  " + out.replace("\n", "\n            "))
            if args.struct and infer.returncode == 0:
                st = subprocess.run([sys.executable, "-m", "vizbin", "infer", path,
                                     "--format", "struct"], capture_output=True, text=True)
                print("   STRUCT:  " + st.stdout.rstrip().replace("\n", "\n            "))
        print()

    print(f"Done: {len(CASES)} files, {total} bytes total in {args.outdir}/")
    if not args.run:
        print("\nTry:")
        print("  python scripts/uat.py --run           # infer, expected vs actual")
        print(f"  vizbin infer {args.outdir}/oddstride_37.bin")
        print(f"  vizbin infer {args.outdir}/pagedb_256.bin --format kaitai")
        print(f"  vizbin render {args.outdir}/mixed_regions.bin --rgb entropy,delta,xor --term")
        print(f"  vizbin suggest {args.outdir}/mpegts_188.bin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
