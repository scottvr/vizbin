"""Command implementations. The CLI in :mod:`vizbin.cli` is a thin wrapper."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys

from vizbin import bmp, gif, layout, projections
from vizbin.canvas import ContactStyle, Raster, contact_sheet


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def load_region(path: str, offset: int = 0, length: int | None = None) -> bytes:
    """Read bytes from ``path``, optionally windowed by ``offset``/``length``."""
    with open(path, "rb") as fh:
        if offset:
            fh.seek(offset)
        return fh.read() if length is None else fh.read(length)


def _mode_opts(args) -> dict:
    return {
        "phase": getattr(args, "phase", 0) or 0,
        "window": getattr(args, "window", 256) or 256,
        "k": getattr(args, "k", 1) or 1,
        "plane": getattr(args, "plane", 7) if getattr(args, "plane", None) is not None else 7,
        "scale": getattr(args, "scale", 1) or 1,
        "colorize": not getattr(args, "mono_text", False),
    }


def out_name(src: str, *, width=None, mode=None, phase=None, kind=None,
             ext="bmp", suffix=None) -> str:
    stem = os.path.splitext(os.path.basename(src))[0]
    parts = [stem]
    if kind:
        parts.append(kind)
    if width is not None:
        parts.append(f"w{width}")
    if mode:
        parts.append(mode.replace("-", ""))
    if phase:
        parts.append(f"phase{phase}")
    if suffix:
        parts.append(suffix)
    return ".".join(parts) + "." + ext


def _resolve_output(args, default: str) -> str:
    out = getattr(args, "output", None)
    if out:
        return out
    outdir = getattr(args, "outdir", None)
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        return os.path.join(outdir, default)
    return default


def _default_width(mode: str, data: bytes, phase: int) -> int:
    p = projections.pixel_count(mode, len(data), phase=phase)
    return layout.square_width(p)


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def _render_pipeline(args, data: bytes, opts: dict, spec: str,
                     paint: str | None = None) -> int:
    names = [m.strip() for m in spec.split(",") if m.strip()]
    width = args.width or layout.square_width(len(data))
    try:
        raster = projections.render_pipeline(names, data, width, paint=paint, **opts)
    except (ValueError, KeyError) as e:
        print(e.args[0] if e.args else str(e), file=sys.stderr)
        return 1
    suffix = "-".join(n.replace("-", "") for n in names)
    if paint:
        suffix += f".{paint}"
    default = out_name(args.input, width=width, mode="pipe", suffix=suffix)
    out = _resolve_output(args, default)
    bmp.write_rgb_bmp(out, bytes(raster.rgb), raster.width, raster.height)
    label = ">".join(names) + (f" +{paint}" if paint else "")
    print(f"{args.input}: {len(data)} bytes -> {raster.width}x{raster.height} "
          f"[pipe {label}] -> {out}")
    if not getattr(args, "no_hints", False):
        advice = _text_advice(data)
        if advice:
            print(f"  hint: {advice}")
    return 0


def _render_channels(args, data: bytes, opts: dict, spec: str) -> int:
    names = [n.strip() for n in spec.split(",") if n.strip()]
    width = args.width or layout.square_width(len(data))
    try:
        raster = projections.render_channels(names, data, width, **opts)
    except (ValueError, KeyError) as e:
        print(e.args[0] if e.args else str(e), file=sys.stderr)
        return 1
    default = out_name(args.input, width=width, mode="rgb",
                       suffix="-".join(n.replace("-", "") for n in names))
    out = _resolve_output(args, default)
    bmp.write_rgb_bmp(out, bytes(raster.rgb), raster.width, raster.height)
    print(f"{args.input}: {len(data)} bytes -> {raster.width}x{raster.height} "
          f"[rgb {'/'.join(names)}] -> {out}")
    if not getattr(args, "no_hints", False):
        advice = _text_advice(data)
        if advice:
            print(f"  hint: {advice}")
    return 0


def cmd_render(args) -> int:
    data = load_region(args.input, args.offset, args.length)
    opts = _mode_opts(args)
    paint = getattr(args, "paint", None)

    if getattr(args, "rgb", None):
        return _render_channels(args, data, opts, args.rgb)

    if getattr(args, "transform", None):
        return _render_pipeline(args, data, opts, args.transform, paint)

    mode = projections.resolve(args.mode)
    if paint:  # -m <mode> --paint <colorizer>: mode's transform, repainted
        return _render_pipeline(args, data, opts, mode, paint)
    width = args.width or _default_width(mode, data, opts["phase"])

    raster = projections.render(mode, data, width, **opts)
    phase = opts["phase"] if mode == "raw-rgb" else None
    default = out_name(args.input, width=width, mode=mode, phase=phase)
    out = _resolve_output(args, default)
    bmp.write_rgb_bmp(out, bytes(raster.rgb), raster.width, raster.height)
    print(f"{args.input}: {len(data)} bytes -> {raster.width}x{raster.height} "
          f"[{mode}] -> {out}")
    if mode != "text" and not getattr(args, "no_hints", False):
        advice = _text_advice(data)
        if advice:
            print(f"  hint: {advice}")
    return 0


# ---------------------------------------------------------------------------
# sweep
# ---------------------------------------------------------------------------

def cmd_sweep(args) -> int:
    mode = projections.resolve(args.mode)
    data = load_region(args.input, args.offset, args.length)
    opts = _mode_opts(args)
    p = projections.pixel_count(mode, len(data), phase=opts["phase"])
    widths = layout.parse_widths(args.widths, n_pixels=p)
    if not widths:
        print("no valid widths to render", file=sys.stderr)
        return 1

    phase = opts["phase"] if mode == "raw-rgb" else None
    for w in widths:
        raster = projections.render(mode, data, w, **opts)
        default = out_name(args.input, width=w, mode=mode, phase=phase)
        out = _resolve_output(args, default) if args.output else (
            os.path.join(args.outdir, default) if args.outdir else default)
        if args.outdir:
            os.makedirs(args.outdir, exist_ok=True)
        bmp.write_rgb_bmp(out, bytes(raster.rgb), raster.width, raster.height)
        print(f"  w{w:<6} {raster.width}x{raster.height} -> {out}")
    print(f"{args.input}: {len(widths)} widths [{mode}]")
    return 0


# ---------------------------------------------------------------------------
# contact
# ---------------------------------------------------------------------------

def cmd_contact(args) -> int:
    data = load_region(args.input, args.offset, args.length)
    opts = _mode_opts(args)
    tiles: list[tuple[str, Raster]] = []

    if args.modes:
        modes = [projections.resolve(m) for m in args.modes.split(",") if m.strip()]
        width = args.width or _default_width("gray", data, 0)
        for m in modes:
            r = projections.render(m, data, width, **opts)
            tiles.append((f"{m} w{width}", r))
        vary, base_mode = "modes", "multi"
    elif args.phases:
        phases = [int(p) for p in args.phases.split(",") if p.strip() != ""]
        width = args.width or _default_width("raw-rgb", data, 0)
        for ph in phases:
            o = dict(opts, phase=ph)
            r = projections.render("raw-rgb", data, width, **o)
            tiles.append((f"rawrgb phase{ph}", r))
        vary, base_mode = "phases", "rawrgb"
    else:
        mode = projections.resolve(args.mode)
        p = projections.pixel_count(mode, len(data), phase=opts["phase"])
        widths = layout.parse_widths(args.widths, n_pixels=p)
        for w in widths:
            r = projections.render(mode, data, w, **opts)
            tiles.append((f"w{w} {mode}", r))
        vary, base_mode = "widths", mode

    if not tiles:
        print("nothing to put on the contact sheet", file=sys.stderr)
        return 1

    style = ContactStyle(cell=(args.cell, args.cell), cols=args.cols)
    sheet = contact_sheet(tiles, style)
    default = out_name(args.input, kind="contact", mode=base_mode, suffix=vary)
    out = _resolve_output(args, default)
    bmp.write_rgb_bmp(out, bytes(sheet.rgb), sheet.width, sheet.height)
    print(f"{args.input}: contact sheet {len(tiles)} tiles "
          f"({sheet.width}x{sheet.height}) -> {out}")
    return 0


# ---------------------------------------------------------------------------
# animate
# ---------------------------------------------------------------------------

def _animation_widths(args, n_pixels: int) -> list[int]:
    if args.widths:
        return layout.parse_widths(args.widths, n_pixels=n_pixels)
    start, stop, step = args.frm, args.to, max(1, args.step)
    return list(range(start, stop + 1, step))


def cmd_animate(args) -> int:
    mode = projections.resolve(args.mode)
    data = load_region(args.input, args.offset, args.length)
    opts = _mode_opts(args)
    p = projections.pixel_count(mode, len(data), phase=opts["phase"])
    widths = _animation_widths(args, p)
    if not widths:
        print("no widths for animation", file=sys.stderr)
        return 1

    frames: list[Raster] = []
    for w in widths:
        r = projections.render(mode, data, w, **opts)
        if args.max_size:
            r = r.fit(args.max_size, args.max_size)
        frames.append(r)

    delay_cs = max(1, round(100 / max(1, args.fps)))

    if args.format == "mp4":
        return _animate_mp4(args, frames, delay_cs)

    default = out_name(args.input, kind="anim", mode=mode, ext="gif",
                       suffix=f"{widths[0]}-{widths[-1]}")
    out = _resolve_output(args, default)
    gif.write_gif(out, frames, delay_cs=delay_cs, loop=0)
    print(f"{args.input}: {len(frames)} frames [{mode}] -> {out}")
    return 0


def _animate_mp4(args, frames: list[Raster], delay_cs: int) -> int:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("mp4 output requires ffmpeg on PATH (or use --format gif)",
              file=sys.stderr)
        return 1
    cw = max(f.width for f in frames)
    ch = max(f.height for f in frames)
    tmp = os.path.abspath(f".vizbin_frames_{os.getpid()}")
    os.makedirs(tmp, exist_ok=True)
    try:
        for i, fr in enumerate(frames):
            canvas = Raster(cw, ch, fill=(0, 0, 0))
            canvas.blit(fr, 0, 0)
            bmp.write_rgb_bmp(os.path.join(tmp, f"f{i:05d}.bmp"),
                              bytes(canvas.rgb), cw, ch)
        default = out_name(args.input, kind="anim", mode=args.mode, ext="mp4")
        out = _resolve_output(args, default)
        fps = max(1, args.fps)
        subprocess.run(
            [ffmpeg, "-y", "-framerate", str(fps),
             "-i", os.path.join(tmp, "f%05d.bmp"),
             "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
             out],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print(f"{args.input}: {len(frames)} frames [{args.mode}] -> {out}")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# suggest
# ---------------------------------------------------------------------------

def _text_advice(data: bytes) -> str | None:
    """Advise the ``text`` mode when the data looks substantially printable.

    Advisory only -- vizbin never switches mode on its own; the user picks the
    hypothesis. Returns a one-line hint, or ``None`` when text mode is unlikely
    to help.
    """
    tr = projections.text_ratio(data)
    pct = round(tr * 100)
    if tr >= 0.90:
        return (f"~{pct}% of bytes are printable/whitespace -- this looks like "
                f"text; try  -m text")
    if tr >= 0.65:
        return (f"~{pct}% of bytes are printable/whitespace -- mixed text/binary; "
                f"-m text may surface the strings in place")
    return None


def _longest_run(buf: bytes) -> int:
    """Length of the longest run of printable glyphs (0x20..0x7E) in ``buf``."""
    longest = cur = 0
    for x in buf:
        if 0x20 <= x <= 0x7E:
            cur += 1
            if cur > longest:
                longest = cur
        else:
            cur = 0
    return longest


def _ascii_hint(path: str, offset: int, radius: int = 16,
                min_run: int = 6) -> str | None:
    """A 'psst, these look like text' hint for the bytes around ``offset``.

    Advisory only. Fires on either signal: the window is mostly printable
    (fraction >= 0.75, "this region is text"), OR it contains a printable run of
    at least ``min_run`` glyphs ("a string is hiding in here" -- like ``strings
    -n``, catching magic numbers/filenames embedded in binary/padding). The
    window is rendered as the string it spells, non-printables as ``.``. Returns
    ``None`` otherwise.
    """
    start = max(0, offset - radius)
    buf = load_region(path, start, 2 * radius + 1)
    if not buf:
        return None
    printable = sum(1 for x in buf if 0x20 <= x <= 0x7E or x in (0x09, 0x0A, 0x0D))
    if printable / len(buf) < 0.75 and _longest_run(buf) < min_run:
        return None
    rendered = "".join(chr(x) if 0x20 <= x <= 0x7E else "." for x in buf)
    return f'psst: bytes [{start}-{start + len(buf) - 1}] look like text: "{rendered}"'


def cmd_suggest(args) -> int:
    data = load_region(args.input, args.offset, args.length)
    suggestions = layout.suggest(data, top=args.top)
    if args.verbose:
        print("Width  Family     Score   Why")
        print("-----  ---------  ------  " + "-" * 40)
        for s in suggestions:
            print(f"{s.width:<5}  {s.family:<9}  {s.score:0.2f}    {s.why}")
    else:
        print(f"Suggested widths for {args.input}:")
        for s in suggestions:
            print(f"  {s.width:<7} {s.family}")
    if not getattr(args, "no_hints", False):
        advice = _text_advice(data)
        if advice:
            print(f"\nhint: {advice}")
    return 0


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

# Class-index -> name (matches projections._byte_class ordering) and the small
# set of control mnemonics text mode is willing to name; everything else prints
# as its 0xHH literal.
_CLASS_NAMES = {0: "nul", 1: "0xff", 2: "whitespace", 3: "ascii",
                4: "control", 5: "high-bit"}
_CTRL_NAMES = {0x00: "NUL", 0x09: "TAB", 0x0A: "LF", 0x0D: "CR", 0x7F: "DEL"}


def _shannon_bits(window: list[int]) -> float:
    """Shannon entropy in bits of a byte window (matches the entropy transform)."""
    n = len(window)
    if n == 0:
        return 0.0
    counts: dict[int, int] = {}
    for b in window:
        counts[b] = counts.get(b, 0) + 1
    return math.log2(n) - sum(c * math.log2(c) for c in counts.values()) / n


def _ascii_gloss(vals: list[int]) -> str:
    """A ' -> "sta"' suffix when every byte is printable ASCII, else ''.

    Turns a run of hex bytes into the string they'd spell -- the 'psst, those
    RGB values are hex for "sta"' reveal, shown inline where we already have the
    bytes in hand.
    """
    if vals and all(0x20 <= v <= 0x7E for v in vals):
        return f' -> "{"".join(chr(v) for v in vals)}"'
    return ""


def _mode_readout(mode: str, path: str, offset: int, base: int, opts: dict) -> str | None:
    """Describe byte ``offset`` in ``mode``'s own terms, matching the renderer.

    Offsets are absolute file positions; ``base`` is where the render started, so
    the projection index is ``j = offset - base`` and predecessors/windows are
    computed region-relative (the 0x00 lead-in padding at ``j < k`` etc. matches
    what the builder actually drew). Reads only a bounded window around ``offset``,
    so it stays a cheap point query. Returns ``None`` when the mode has no readout.
    """
    j = offset - base
    if j < 0:
        return None
    k = max(1, int(opts.get("k", 1)))
    window = max(2, int(opts.get("window", 256)))
    plane = max(0, min(7, int(opts.get("plane", 7))))
    phase = int(opts.get("phase", 0)) % 3

    if mode == "entropy":
        back = window
    elif mode == "xor":
        back = k
    elif mode == "delta":
        back = 1
    elif mode == "raw-rgb":
        back = 2
    else:
        back = 0
    fwd = 2 if mode == "raw-rgb" else 0

    start = max(0, offset - back)
    buf = load_region(path, start, (offset - start) + fwd + 1)

    def at(a: int) -> int | None:
        i = a - start
        return buf[i] if 0 <= i < len(buf) else None

    b = at(offset)
    if b is None:
        return "(offset beyond data)"

    def hd(v: int) -> str:
        return f"0x{v:02x} ({v})"

    if mode == "gray":
        return f"byte {hd(b)} -> gray {b}"
    if mode == "byteclass":
        return f"byte {hd(b)} -> class '{_CLASS_NAMES[projections._byte_class(b)]}'"
    if mode == "nibble":
        return f"byte {hd(b)} -> hi 0x{b >> 4:x}, lo 0x{b & 0x0F:x}"
    if mode == "text":
        if 0x20 <= b <= 0x7E:
            ch = f"'{chr(b)}'"
        elif b in _CTRL_NAMES:
            ch = _CTRL_NAMES[b]
        else:
            ch = f"0x{b:02x}"
        return f"byte {hd(b)} = {ch}"
    if mode == "bitplane":
        return f"byte {hd(b)} -> bit[{plane}] = {(b >> plane) & 1}"
    if mode == "delta":
        if j == 0:
            return f"byte {hd(b)}, prev 0x00 (pad) -> |delta| {b}"
        pb = at(offset - 1)
        assert pb is not None  # j > 0 => predecessor is inside the read window
        return f"byte {hd(b)}, prev@{offset - 1} {hd(pb)} -> |delta| {abs(b - pb)}"
    if mode == "xor":
        if j < k:
            return f"byte {hd(b)} XOR 0x00 (pad) = {hd(b)}"
        ob = at(offset - k)
        assert ob is not None  # j >= k => operand is inside the read window
        return f"byte {hd(b)} XOR @{offset - k} {hd(ob)} = {hd(b ^ ob)}"
    if mode == "entropy":
        total = min(j + 1, window)
        lo = offset - total + 1
        wb = list(buf[lo - start:offset - start + 1])  # the `total` window bytes
        return (f"entropy {_shannon_bits(wb):.2f} bits over "
                f"{total}-byte window [{lo}-{offset}]")
    if mode == "raw-rgb":
        rel = j - phase
        if rel < 0:
            return f"in the phase-{phase} lead-in (before the first pixel)"
        p = rel // 3
        ro = base + phase + 3 * p
        r, g, bl = at(ro), at(ro + 1), at(ro + 2)
        if r is None or g is None or bl is None:
            return f"in the trailing bytes (incomplete pixel {p})"
        return (f"pixel {p} -> R@{ro}=0x{r:02x} G@{ro + 1}=0x{g:02x} "
                f"B@{ro + 2}=0x{bl:02x}" + _ascii_gloss([r, g, bl]))
    return None


def _transform_value_at(tname: str, path: str, offset: int, base: int,
                        opts: dict) -> int | None:
    """The output byte of a single transform at ``offset`` (region-relative to
    ``base``), computed over a bounded window so it matches the rendered value."""
    tkey = projections._resolve_transform_name(tname)  # ValueError/KeyError on bad
    k = max(1, int(opts.get("k", 1)))
    window = max(2, int(opts.get("window", 256)))
    back = {"xor": k, "entropy": window, "delta": 1}.get(tkey, 0)
    start = max(base, offset - back)
    buf = load_region(path, start, (offset - start) + 1)
    li = offset - start
    if li < 0 or li >= len(buf):
        return None
    return projections.TRANSFORMS[tkey](bytes(buf), opts)[li]


def _rgb_readout(names: list[str], path: str, offset: int, base: int,
                 opts: dict) -> str | None:
    """`R(entropy)=0x.. G(delta)=0x.. B(xor)=0x..` for a `--rgb` composition."""
    labels = ("R", "G", "B")
    parts = []
    for i, n in enumerate(names[:3]):
        try:
            v = _transform_value_at(n, path, offset, base, opts)
        except (ValueError, KeyError):
            return None
        if v is None:
            return None
        parts.append(f"{labels[i]}({n})=0x{v:02x} ({v})")
    return "  ".join(parts)


def _inspect_rgb(args) -> int:
    """Inspect a `--rgb` channel composition: geometry (1:1) + per-channel values."""
    names = [n.strip() for n in args.rgb.split(",") if n.strip()]
    omap = layout.OffsetMap(width=args.width, bpp=1, base=args.base)
    tag = "/".join(names)
    if args.offset is not None:
        off = args.offset
        r = omap.offset_to_pixel(off)
        if "error" in r:
            print(r["error"], file=sys.stderr)
            return 1
        print(f"offset 0x{off:x} ({off}) [rgb {tag}, w={args.width}]")
        print(f"  -> pixel {r['pixel']} at x={r['x']}, y={r['y']}")
    elif args.x is not None and args.y is not None:
        off = omap.pixel_to_offset(args.x, args.y)["offset"]
        print(f"pixel x={args.x}, y={args.y} [rgb {tag}, w={args.width}]")
        print(f"  -> byte offset {off} (0x{off:x})")
    else:
        print("give either --offset, or both --x and --y", file=sys.stderr)
        return 1
    if args.input:
        readout = _rgb_readout(names, args.input, off, args.base, _mode_opts(args))
        if readout:
            print(f"  -> {readout}")
    return 0


def _maybe_ascii_hint(args, modes: list[str], offset: int) -> None:
    """Print the 'psst, looks like text' hint unless suppressed or redundant."""
    if (getattr(args, "input", None) and not getattr(args, "no_hints", False)
            and "text" not in modes):
        hint = _ascii_hint(args.input, offset,
                           min_run=max(1, getattr(args, "min_run", 6) or 6))
        if hint:
            print(f"  {hint}")


def _inspect_multi(modes: list[str], args) -> int:
    """Stack per-mode readouts for one coordinate under a shared header.

    Each mode is an independent *view* of the same offset, so a mode list is
    additive: ``inspect --modes raw-rgb,text`` shows both the RGB bytes and the
    character. With ``--x/--y`` each mode resolves its own byte (geometry differs
    per mode); with ``--offset`` they share the absolute offset.
    """
    if args.offset is not None:
        print(f"offset 0x{args.offset:x} ({args.offset}) [w={args.width}]")
    elif args.x is not None and args.y is not None:
        print(f"pixel x={args.x}, y={args.y} [w={args.width}]")
    else:
        print("give either --offset, or both --x and --y", file=sys.stderr)
        return 1

    opts = _mode_opts(args)
    pad = max(len(m) for m in modes)
    hint_off = args.offset
    for mode in modes:
        bpp = projections.bytes_per_pixel(mode)
        phase = (args.phase or 0) if mode == "raw-rgb" else 0
        cell = (8 * max(1, getattr(args, "scale", 1) or 1)
                if mode in projections.GLYPH_MODES else 1)
        omap = layout.OffsetMap(width=args.width, bpp=bpp, phase=phase,
                                base=args.base, cell=cell)
        if args.offset is not None:
            off = args.offset
            r = omap.offset_to_pixel(off)
            if "error" in r:
                print(f"  [{mode:<{pad}}] {r['error']}")
                continue
        else:
            off = omap.pixel_to_offset(args.x, args.y)["offset"]
        if hint_off is None:
            hint_off = off
        if args.input:
            line = _mode_readout(mode, args.input, off, args.base, opts) or "(no readout)"
        else:
            line = f"offset {off} (0x{off:x})"
        print(f"  [{mode:<{pad}}] {line}")
    if hint_off is not None:
        _maybe_ascii_hint(args, modes, hint_off)
    return 0


def cmd_inspect(args) -> int:
    if getattr(args, "rgb", None):
        return _inspect_rgb(args)

    raw_modes = getattr(args, "modes", None)
    if raw_modes:
        modes = [projections.resolve(m) for m in raw_modes.split(",") if m.strip()]
        if len(modes) > 1:
            return _inspect_multi(modes, args)
        if modes:
            args.mode = modes[0]  # single mode via --modes: use the detailed path

    mode = projections.resolve(args.mode)
    bpp = projections.bytes_per_pixel(mode)
    phase = (args.phase or 0) if mode == "raw-rgb" else 0
    # text mode is a grid of 8*scale-pixel cells; other modes are 1 px per cell.
    cell = (8 * max(1, getattr(args, "scale", 1) or 1)
            if mode in projections.GLYPH_MODES else 1)
    omap = layout.OffsetMap(width=args.width, bpp=bpp, phase=phase,
                            base=args.base, cell=cell)

    if args.offset is not None:
        r = omap.offset_to_pixel(args.offset)
        if "error" in r:
            print(r["error"], file=sys.stderr)
            return 1
        print(f"offset 0x{args.offset:x} ({args.offset}) [{mode}, w={args.width}]")
        if "px_x" in r:
            c = r["cell"]
            print(f"  -> cell col={r['x']}, row={r['y']} "
                  f"(pixels x=[{r['px_x']},{r['px_x'] + c}) "
                  f"y=[{r['px_y']},{r['px_y'] + c}))")
        else:
            chan = "" if r["channel"] is None else f", channel {r['channel']}"
            print(f"  -> pixel {r['pixel']} at x={r['x']}, y={r['y']}{chan}")
        if args.input:
            readout = _mode_readout(mode, args.input, args.offset, args.base, _mode_opts(args))
            if readout:
                print(f"  -> {readout}")
        _maybe_ascii_hint(args, [mode], args.offset)
        return 0

    if args.x is not None and args.y is not None:
        r = omap.pixel_to_offset(args.x, args.y)
        lo, hi = r["byte_range"]
        print(f"pixel x={args.x}, y={args.y} [{mode}, w={args.width}]")
        if cell > 1:
            print(f"  -> cell col={r['col']}, row={r['row']} = 1 byte at "
                  f"offset {r['offset']} (0x{r['offset']:x})")
        else:
            print(f"  -> byte offset {r['offset']} (0x{r['offset']:x})"
                  f", range [{lo}, {hi}) = {hi - lo} byte(s)")
        if args.input:
            readout = _mode_readout(mode, args.input, r["offset"], args.base, _mode_opts(args))
            if readout:
                print(f"  -> {readout}")
        _maybe_ascii_hint(args, [mode], r["offset"])
        return 0

    print("give either --offset, or both --x and --y", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# infer (draft record/field layout)
# ---------------------------------------------------------------------------

def cmd_infer(args) -> int:
    from vizbin import infer
    data = load_region(args.input, args.offset, args.length)
    stride, why = infer.select_stride(data, args.stride)
    if stride is None:
        print(f"{args.input}: {why}", file=sys.stderr)
        return 1
    fields, n_rec = infer.infer_fields(data, stride)
    if not fields:
        print(f"{args.input}: stride {stride} ({why}), but too few records "
              f"to profile", file=sys.stderr)
        return 1
    print(f"{args.input}:")
    print(infer.format_report(data, stride, why, fields, n_rec))
    return 0


# ---------------------------------------------------------------------------
# bmp / unbmp (reversible payload mode)
# ---------------------------------------------------------------------------

def cmd_bmp(args) -> int:
    payload = load_region(args.input, args.offset, args.length)
    default = out_name(args.input, ext="bmp")
    out = _resolve_output(args, default)
    width, height, padding = bmp.write_raw_bmp(out, payload, args.width)
    print(f"{args.input}: {len(payload)} bytes -> {width}x{height}, "
          f"{padding} padding bytes -> {out}")
    print(f"  payload byte n lands at file offset {bmp.HEADER_SIZE}+n; "
          f"recover with: vizbin unbmp {out}")
    return 0


def cmd_unbmp(args) -> int:
    with open(args.input, "rb") as fh:
        data = fh.read()
    payload = bmp.unbmp(data)
    if args.output:
        with open(args.output, "wb") as fh:
            fh.write(payload)
        print(f"{args.input}: recovered {len(payload)} bytes -> {args.output}",
              file=sys.stderr)
    else:
        sys.stdout.buffer.write(payload)
    return 0
