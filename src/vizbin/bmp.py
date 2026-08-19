"""Pure-Python 24-bit BMP writing/reading.

Two write paths:

* :func:`write_raw_bmp` -- the "constant-offset payload" mode from the original
  shell trick. The input bytes are copied verbatim into the pixel-data section,
  so payload byte ``n`` lands at file offset ``54 + n``. This is what makes a
  ``vizbin bmp`` output reversible and offset-preservable. It requires a width
  whose row stride (``width * 3``) is a multiple of 4 so that no per-row padding
  is needed and the payload stays contiguous.

* :func:`write_rgb_bmp` -- the general projection path. It takes an already
  computed RGB raster and writes a valid top-down BMP, inserting BMP's mandatory
  per-row padding. Bytes are *not* preserved here; the raster is the projection's
  interpretation of the bytes.

We deliberately depend on nothing but the standard library. BMP is trivial to
emit by hand, and doing so keeps the elegant offset property under our control.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass

HEADER_SIZE = 54  # BITMAPFILEHEADER (14) + BITMAPINFOHEADER (40)
_FILE_HEADER = "<2sIHHI"   # bfType, bfSize, bfReserved1, bfReserved2, bfOffBits
_DIB_HEADER = "<IiiHHIIiiII"


def row_padding(width: int) -> int:
    """Padding bytes appended to each scanline to reach a 4-byte boundary."""
    return (-(width * 3)) % 4


def make_header(width: int, height: int, pixel_bytes: int, reserved: int = 0) -> bytes:
    """Build a 54-byte 24-bit top-down BMP header.

    ``height`` is stored negative (top-down) so that row 0 is the top of the
    image, matching how we lay bytes out. ``reserved`` is stashed into the
    4 reserved header bytes; :func:`write_raw_bmp` uses it to record the
    original payload length for exact reversal.
    """
    file_size = HEADER_SIZE + pixel_bytes
    file_header = struct.pack(
        _FILE_HEADER,
        b"BM",
        file_size,
        reserved & 0xFFFF,
        (reserved >> 16) & 0xFFFF,
        HEADER_SIZE,
    )
    dib_header = struct.pack(
        _DIB_HEADER,
        40,             # biSize
        width,          # biWidth
        -height,        # biHeight (negative -> top-down)
        1,              # biPlanes
        24,             # biBitCount
        0,              # biCompression (BI_RGB)
        pixel_bytes,    # biSizeImage
        2835,           # biXPelsPerMeter (~72 DPI)
        2835,           # biYPelsPerMeter
        0,              # biClrUsed
        0,              # biClrImportant
    )
    return file_header + dib_header


# ---------------------------------------------------------------------------
# Reversible "payload as pixels" mode
# ---------------------------------------------------------------------------

def square_bmp_dimensions(n: int) -> tuple[int, int, int]:
    """Pick a near-square width (divisible by 4) for ``n`` payload bytes.

    Returns ``(width, height, padding)``. A width divisible by 4 keeps the row
    stride (``width * 3``) a multiple of 4, so the payload stays contiguous and
    the offset property holds.
    """
    ideal = math.sqrt(max(n, 1) / 3)
    base = max(4, int(ideal) // 4 * 4)
    best: tuple[int, int, int, int] | None = None
    for w in (base, base + 4):
        row_bytes = w * 3
        h = max(1, math.ceil(n / row_bytes))
        padding = row_bytes * h - n
        cand = (abs(w - h), padding, w, h)
        if best is None or cand < best:
            best = cand
    assert best is not None  # loop always runs, but pin it for type-checkers
    _, padding, w, h = best
    return w, h, padding


def write_raw_bmp(path: str, payload: bytes, width: int | None = None) -> tuple[int, int, int]:
    """Write ``payload`` verbatim as BMP pixel data (the reversible mode).

    Returns ``(width, height, padding)``. If ``width`` is ``None`` a near-square
    width is chosen. ``width`` must be divisible by 4. The original payload
    length is recorded in the header's reserved field so :func:`unbmp` can
    recover the exact bytes.
    """
    n = len(payload)
    if width is None:
        width, height, padding = square_bmp_dimensions(n)
    else:
        if width % 4 != 0:
            raise ValueError(
                f"raw BMP width must be divisible by 4 (got {width}); "
                "otherwise per-row padding would break the offset property"
            )
        row_bytes = width * 3
        height = max(1, math.ceil(n / row_bytes))
        padding = row_bytes * height - n

    pixel_bytes = width * height * 3
    header = make_header(width, height, pixel_bytes, reserved=n)
    with open(path, "wb") as out:
        out.write(header)
        out.write(payload)
        if padding:
            out.write(b"\x00" * padding)
    return width, height, padding


# ---------------------------------------------------------------------------
# General RGB raster mode
# ---------------------------------------------------------------------------

def rgb_to_bmp_bytes(rgb: bytes, width: int, height: int) -> bytes:
    """Serialize an RGB-interleaved buffer to a complete BMP byte string.

    ``rgb`` must contain exactly ``width * height * 3`` bytes in R,G,B order.
    Handles the RGB->BGR channel swap and per-row padding.
    """
    expected = width * height * 3
    if len(rgb) != expected:
        raise ValueError(f"rgb buffer is {len(rgb)} bytes, expected {expected}")

    pad = row_padding(width)
    row_stride = width * 3

    if pad == 0:
        # Fast path: one channel-swap over the whole buffer.
        bgr = bytearray(len(rgb))
        bgr[0::3] = rgb[2::3]
        bgr[1::3] = rgb[1::3]
        bgr[2::3] = rgb[0::3]
        pixel_data = bytes(bgr)
    else:
        pad_bytes = b"\x00" * pad
        parts = []
        for y in range(height):
            start = y * row_stride
            row = rgb[start:start + row_stride]
            bgr = bytearray(row_stride)
            bgr[0::3] = row[2::3]
            bgr[1::3] = row[1::3]
            bgr[2::3] = row[0::3]
            parts.append(bytes(bgr))
            parts.append(pad_bytes)
        pixel_data = b"".join(parts)

    header = make_header(width, height, len(pixel_data))
    return header + pixel_data


def write_rgb_bmp(path: str, rgb: bytes, width: int, height: int) -> None:
    """Write an RGB-interleaved raster to ``path`` as a 24-bit BMP."""
    with open(path, "wb") as out:
        out.write(rgb_to_bmp_bytes(rgb, width, height))


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

@dataclass
class BmpInfo:
    width: int
    height: int          # absolute value
    top_down: bool
    bits_per_pixel: int
    offset: int          # bfOffBits
    reserved: int        # our stashed original-length (0 if unused)
    file_size: int


def read_header(data: bytes) -> BmpInfo:
    """Parse a BMP header from the first bytes of ``data``."""
    if len(data) < HEADER_SIZE or data[:2] != b"BM":
        raise ValueError("not a BMP file (missing 'BM' signature)")
    (_sig, file_size, res1, res2, off_bits) = struct.unpack_from(_FILE_HEADER, data, 0)
    (_dib_size, width, height, _planes, bpp, _compression,
     _img_size, _xppm, _yppm, _clr_used, _clr_imp) = struct.unpack_from(_DIB_HEADER, data, 14)
    reserved = (res1 & 0xFFFF) | ((res2 & 0xFFFF) << 16)
    return BmpInfo(
        width=width,
        height=abs(height),
        top_down=height < 0,
        bits_per_pixel=bpp,
        offset=off_bits,
        reserved=reserved,
        file_size=file_size,
    )


def unbmp(data: bytes) -> bytes:
    """Recover the original payload from a BMP produced by :func:`write_raw_bmp`.

    Uses the reserved-field length when present. Otherwise falls back to the full
    pixel region with trailing NUL padding stripped (which is lossy only if the
    original payload genuinely ended in NUL bytes).
    """
    info = read_header(data)
    if info.bits_per_pixel != 24:
        raise ValueError(f"unbmp expects 24-bit BMP, got {info.bits_per_pixel}-bit")
    start = info.offset
    if info.reserved and start + info.reserved <= len(data):
        return data[start:start + info.reserved]
    return data[start:].rstrip(b"\x00")
