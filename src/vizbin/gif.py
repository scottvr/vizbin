"""A tiny, dependency-free animated GIF writer.

Enough of GIF89a to turn a list of :class:`~vizbin.canvas.Raster` frames into a
looping animation. Frames may differ in size (width sweeps produce exactly
that); each is drawn at the top-left of a canvas sized to the largest frame and
cleared between frames via the "restore to background" disposal method.

Colour handling:

* If every sampled pixel is grayscale (R==G==B), a 256-level gray palette is
  used and the byte value maps straight to a palette index -- lossless for the
  gray/entropy-as-gray/delta/bitplane projections.
* Otherwise a 3-3-2 bit palette (256 colours) is used. Lossy but adequate for
  spotting structure, which is the whole point.

LZW is the standard GIF variable-width scheme (no "early change").
"""

from __future__ import annotations

from vizbin.canvas import Raster

GIF_HEADER = b"GIF89a"


# ---------------------------------------------------------------------------
# Palettes / quantization
# ---------------------------------------------------------------------------

def _gray_palette() -> bytes:
    pal = bytearray(256 * 3)
    for i in range(256):
        pal[i * 3] = i
        pal[i * 3 + 1] = i
        pal[i * 3 + 2] = i
    return bytes(pal)


def _rgb332_palette() -> bytes:
    pal = bytearray(256 * 3)
    for i in range(256):
        r3 = (i >> 5) & 0x07
        g3 = (i >> 2) & 0x07
        b2 = i & 0x03
        pal[i * 3] = r3 * 255 // 7
        pal[i * 3 + 1] = g3 * 255 // 7
        pal[i * 3 + 2] = b2 * 255 // 3
    return bytes(pal)


_R332 = bytes(i & 0xE0 for i in range(256))
_G332 = bytes((i & 0xE0) >> 3 for i in range(256))
_B332 = bytes((i & 0xC0) >> 6 for i in range(256))


def _is_grayscale(frames: list[Raster]) -> bool:
    for fr in frames:
        rgb = fr.rgb
        # sample up to ~4k pixels
        step = max(3, (len(rgb) // (4096 * 3)) * 3)
        for i in range(0, len(rgb) - 2, step):
            if rgb[i] != rgb[i + 1] or rgb[i + 1] != rgb[i + 2]:
                return False
    return True


def _indices_gray(fr: Raster) -> bytes:
    return bytes(fr.rgb[0::3])


def _indices_332(fr: Raster) -> bytes:
    r = bytes(fr.rgb[0::3]).translate(_R332)
    g = bytes(fr.rgb[1::3]).translate(_G332)
    b = bytes(fr.rgb[2::3]).translate(_B332)
    n = len(r)
    if n == 0:
        return b""
    combined = (int.from_bytes(r, "big")
                | int.from_bytes(g, "big")
                | int.from_bytes(b, "big"))
    return combined.to_bytes(n, "big")


# ---------------------------------------------------------------------------
# LZW
# ---------------------------------------------------------------------------

def _lzw_encode(indices: bytes, min_code_size: int) -> bytes:
    clear_code = 1 << min_code_size
    end_code = clear_code + 1
    code_size = min_code_size + 1

    out = bytearray()
    bitbuf = 0
    nbits = 0

    def emit(code: int) -> None:
        nonlocal bitbuf, nbits
        bitbuf |= code << nbits
        nbits += code_size
        while nbits >= 8:
            out.append(bitbuf & 0xFF)
            bitbuf >>= 8
            nbits -= 8

    def fresh_table() -> tuple[dict, int]:
        table = {(i,): i for i in range(clear_code)}
        return table, end_code + 1

    table, next_code = fresh_table()
    emit(clear_code)

    if indices:
        w: tuple[int, ...] = (indices[0],)
        for i in range(1, len(indices)):
            k = indices[i]
            wk = w + (k,)
            if wk in table:
                w = wk
            else:
                emit(table[w])
                if next_code < 4096:
                    # Add the new string, then grow the code width one step
                    # *after* the table has outgrown the current width. This
                    # ">" (not "==") timing is what GIF decoders expect: the
                    # decoder builds its table one entry behind the encoder.
                    table[wk] = next_code
                    next_code += 1
                    if next_code > (1 << code_size) and code_size < 12:
                        code_size += 1
                else:
                    # Table full (12-bit codes exhausted): reset.
                    emit(clear_code)
                    table, next_code = fresh_table()
                    code_size = min_code_size + 1
                w = (k,)
        emit(table[w])

    emit(end_code)
    if nbits > 0:
        out.append(bitbuf & 0xFF)
    return bytes(out)


def _packetize(data: bytes) -> bytes:
    """Wrap LZW output in GIF sub-blocks (<=255 bytes each), NUL terminated."""
    out = bytearray()
    for i in range(0, len(data), 255):
        chunk = data[i:i + 255]
        out.append(len(chunk))
        out.extend(chunk)
    out.append(0)
    return bytes(out)


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def write_gif(path: str, frames: list[Raster], *, delay_cs: int = 8,
              loop: int = 0) -> None:
    """Write ``frames`` as an animated GIF.

    ``delay_cs`` is the per-frame delay in centiseconds. ``loop`` is the number
    of extra loops (0 = loop forever).
    """
    if not frames:
        raise ValueError("no frames to write")

    canvas_w = max(fr.width for fr in frames)
    canvas_h = max(fr.height for fr in frames)

    # Pad every frame to the canvas size. A width sweep produces frames of
    # differing sizes, and many viewers (kitty, some image apps) refuse to
    # *animate* a GIF whose frames vary in size -- they show the first and stop.
    # Uniform full-canvas frames are the maximally-compatible form.
    if any(fr.width != canvas_w or fr.height != canvas_h for fr in frames):
        padded: list[Raster] = []
        for fr in frames:
            if fr.width == canvas_w and fr.height == canvas_h:
                padded.append(fr)
            else:
                c = Raster(canvas_w, canvas_h)  # black background
                c.blit(fr, 0, 0)
                padded.append(c)
        frames = padded

    gray = _is_grayscale(frames)
    palette = _gray_palette() if gray else _rgb332_palette()
    to_indices = _indices_gray if gray else _indices_332

    out = bytearray()
    out += GIF_HEADER

    # Logical Screen Descriptor
    out += canvas_w.to_bytes(2, "little")
    out += canvas_h.to_bytes(2, "little")
    # packed: GCT flag=1, colour resolution=7, sort=0, GCT size=7 (=>256)
    out.append(0b1_111_0_111)
    out.append(0)   # background colour index
    out.append(0)   # pixel aspect ratio
    out += palette

    # Netscape looping extension
    out += b"\x21\xFF\x0B" + b"NETSCAPE2.0" + b"\x03\x01"
    out += loop.to_bytes(2, "little") + b"\x00"

    min_code_size = 8
    for fr in frames:
        # Graphic Control Extension (disposal=2 restore to bg)
        out += b"\x21\xF9\x04"
        out.append(0b000_010_0_0)     # disposal method 2
        out += delay_cs.to_bytes(2, "little")
        out.append(0)                 # transparent colour index
        out.append(0)                 # block terminator

        # Image Descriptor
        out.append(0x2C)
        out += (0).to_bytes(2, "little")   # left
        out += (0).to_bytes(2, "little")   # top
        out += fr.width.to_bytes(2, "little")
        out += fr.height.to_bytes(2, "little")
        out.append(0)                      # no local colour table

        out.append(min_code_size)
        indices = to_indices(fr)
        out += _packetize(_lzw_encode(indices, min_code_size))

    out.append(0x3B)  # trailer

    with open(path, "wb") as fh:
        fh.write(out)
