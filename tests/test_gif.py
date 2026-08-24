"""Validate the pure-Python GIF writer, including a from-scratch LZW decoder
so we prove the bytes actually round-trip rather than merely "look like" a GIF.
"""

import random

from vizbin import gif
from vizbin.canvas import Raster


def _lzw_decode(data: bytes, mcs: int) -> bytes:
    clear = 1 << mcs
    end = clear + 1
    pos = 0
    bitpos = 0

    def read(size):
        nonlocal pos, bitpos
        val = 0
        for i in range(size):
            if pos >= len(data):
                return end
            val |= ((data[pos] >> bitpos) & 1) << i
            bitpos += 1
            if bitpos == 8:
                bitpos = 0
                pos += 1
        return val

    def init():
        return {i: [i] for i in range(clear)}, end + 1

    size = mcs + 1
    table, next_c = init()
    out = []
    prev = None
    # first code should be clear
    while True:
        code = read(size)
        if code == clear:
            table, next_c = init()
            size = mcs + 1
            prev = None
            continue
        if code == end:
            break
        if code in table:
            entry = table[code]
        elif prev is not None:
            entry = prev + [prev[0]]
        else:
            break
        out.extend(entry)
        if prev is not None:
            table[next_c] = prev + [entry[0]]
            next_c += 1
            if next_c == (1 << size) and size < 12:
                size += 1
        prev = entry
    return bytes(out)


def test_lzw_roundtrip_small():
    data = bytes([1, 2, 2, 3, 3, 3, 1, 1, 2, 2, 3])
    enc = gif._lzw_encode(data, 8)
    assert _lzw_decode(enc, 8) == data


def test_lzw_roundtrip_forces_codesize_growth():
    # a run that fills the LZW table and forces the code size to grow
    random.seed(7)
    data = bytes(random.getrandbits(8) for _ in range(20000))
    enc = gif._lzw_encode(data, 8)
    assert _lzw_decode(enc, 8) == data


def test_lzw_roundtrip_repetitive():
    data = (bytes(range(256)) * 40)
    enc = gif._lzw_encode(data, 8)
    assert _lzw_decode(enc, 8) == data


def _unpacketize(data: bytes, start: int) -> tuple[bytes, int]:
    out = bytearray()
    i = start
    while data[i] != 0:
        n = data[i]
        out += data[i + 1:i + 1 + n]
        i += 1 + n
    return bytes(out), i + 1


def _skip_subblocks(data: bytes, i: int) -> int:
    while data[i] != 0:
        i += 1 + data[i]
    return i + 1


def _find_image_descriptor(data: bytes) -> int:
    """Walk GIF blocks and return the offset of the first image descriptor."""
    packed = data[10]
    gct = 3 * (1 << ((packed & 0x07) + 1)) if packed & 0x80 else 0
    i = 13 + gct
    while True:
        b = data[i]
        if b == 0x2C:          # image descriptor
            return i
        if b == 0x21:          # extension: label byte then sub-blocks
            i = _skip_subblocks(data, i + 2)
        elif b == 0x3B:        # trailer
            raise AssertionError("no image descriptor found")
        else:
            raise AssertionError(f"unexpected block byte 0x{b:02x} at {i}")


def test_written_gif_structure_and_pixels(tmp_path):
    # a 4x2 grayscale frame with known values
    vals = bytes([0, 64, 128, 255, 10, 20, 30, 40])
    rgb = bytearray()
    for v in vals:
        rgb += bytes([v, v, v])
    frame = Raster(4, 2, rgb)

    out = tmp_path / "anim.gif"
    gif.write_gif(str(out), [frame], delay_cs=5, loop=0)
    data = out.read_bytes()

    assert data[:6] == b"GIF89a"
    assert data[-1] == 0x3B  # trailer
    w = int.from_bytes(data[6:8], "little")
    h = int.from_bytes(data[8:10], "little")
    assert (w, h) == (4, 2)

    # locate the image descriptor and decode its data
    idx = _find_image_descriptor(data)
    # image descriptor is 10 bytes; then min code size byte; then data blocks
    mcs = data[idx + 10]
    assert mcs == 8
    lzw, _ = _unpacketize(data, idx + 11)
    indices = _lzw_decode(lzw, mcs)
    # grayscale palette => index == gray value
    assert indices == vals


def test_frames_padded_to_uniform_size(tmp_path):
    # width-sweep frames differ in size; every image descriptor in the GIF must
    # be the full canvas size, or viewers won't animate it.
    frames = [Raster(4, 3), Raster(6, 2), Raster(5, 4)]  # canvas => 6x4
    out = tmp_path / "sweep.gif"
    gif.write_gif(str(out), frames, delay_cs=8, loop=0)
    data = out.read_bytes()

    canvas_w = int.from_bytes(data[6:8], "little")
    canvas_h = int.from_bytes(data[8:10], "little")
    assert (canvas_w, canvas_h) == (6, 4)

    # scan every image descriptor (0x2C ... left,top,w,h) and check w,h == canvas
    seen = 0
    i = 0
    while i < len(data):
        if data[i] == 0x2C and i + 9 <= len(data):
            w = int.from_bytes(data[i + 5:i + 7], "little")
            h = int.from_bytes(data[i + 7:i + 9], "little")
            if (w, h) == (canvas_w, canvas_h):
                seen += 1
                i += 10
                continue
        i += 1
    assert seen == 3  # all three frames at full canvas size
