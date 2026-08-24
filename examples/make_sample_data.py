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

    # 188-byte "TS-like" records: a 0x47 sync byte, a fixed magic, a u32 counter,
    # then a 179-byte payload that RANDOM-WALKS from record to record -- each
    # column drifts +-40 per step. Two properties fall out of that walk, and they
    # are what make this file demo the whole find->verify loop:
    #   * adjacent records look alike (small per-step drift) -> high row coherence,
    #     so `suggest` ranks 188 first and `infer` locks onto the 188 stride;
    #   * each column still wanders across its full range over 400 records -> high
    #     entropy, so `infer` reads the payload as one clean blob (not fragments).
    # Visually the walk paints a vertical wood-grain at the true 188 stride that
    # shears into diagonals at any other width -- so a width sweep snaps cleanly.
    # (A flat random payload had neither the coherence nor the vertical grain.)
    walk = random.Random(0xC0FFEE)
    payload = [walk.randrange(256) for _ in range(179)]
    rec = bytearray()
    for i in range(400):
        for j in range(179):
            payload[j] = (payload[j] + walk.randrange(-40, 41)) & 0xFF
        r = bytes([0x47]) + b"REC1" + i.to_bytes(4, "little") + bytes(payload)  # 1+4+4+179
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
