#!/usr/bin/env python3
"""Regenerate the deterministic sample blobs under examples/sample-data/.

These exist so the demo and docs have something with obvious visual structure
to point at (fixed-size records, an entropy staircase, mixed text/binary).
"""

import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sample-data")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(1234)

    # plain text
    with open(os.path.join(OUT, "hello.txt"), "wb") as fh:
        fh.write(b"vizbin: take a blob, pretend it is an image.\n" * 40)

    # high-entropy noise
    with open(os.path.join(OUT, "random.bin"), "wb") as fh:
        fh.write(bytes(rng.getrandbits(8) for _ in range(16384)))

    # 188-byte "TS-like" fixed records with a sync byte + counter
    rec = bytearray()
    for i in range(400):
        r = bytearray(188)
        r[0] = 0x47
        r[1] = i & 0xFF
        r[2] = (i >> 8) & 0xFF
        for j in range(3, 188):
            r[j] = (i * 7 + j) & 0xFF
        rec += r
    with open(os.path.join(OUT, "records.bin"), "wb") as fh:
        fh.write(bytes(rec))

    # mixed: nul padding, text, random, 0xff run
    mixed = bytearray()
    mixed += b"\x00" * 2048
    mixed += b"CONFIG key=value section=[main]\n" * 30
    mixed += bytes(rng.getrandbits(8) for _ in range(4096))
    mixed += b"\xff" * 1024
    with open(os.path.join(OUT, "mixed.bin"), "wb") as fh:
        fh.write(bytes(mixed))

    for name in ("hello.txt", "random.bin", "records.bin", "mixed.bin"):
        p = os.path.join(OUT, name)
        print(f"{name:14} {os.path.getsize(p)} bytes")


if __name__ == "__main__":
    main()
