"""Command implementations. The CLI in :mod:`vizbin.cli` is a thin wrapper."""

from __future__ import annotations

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

def cmd_render(args) -> int:
    mode = projections.resolve(args.mode)
    data = load_region(args.input, args.offset, args.length)
    opts = _mode_opts(args)
    width = args.width or _default_width(mode, data, opts["phase"])

    raster = projections.render(mode, data, width, **opts)
    phase = opts["phase"] if mode == "raw-rgb" else None
    default = out_name(args.input, width=width, mode=mode, phase=phase)
    out = _resolve_output(args, default)
    bmp.write_rgb_bmp(out, bytes(raster.rgb), raster.width, raster.height)
    print(f"{args.input}: {len(data)} bytes -> {raster.width}x{raster.height} "
          f"[{mode}] -> {out}")
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


def cmd_suggest(args) -> int:
    data = load_region(args.input, args.offset, args.length)
    suggestions = layout.suggest(data, top=args.top)
    if args.verbose:
        print(f"Width  Family     Score   Why")
        print(f"-----  ---------  ------  " + "-" * 40)
        for s in suggestions:
            print(f"{s.width:<5}  {s.family:<9}  {s.score:0.2f}    {s.why}")
    else:
        print(f"Suggested widths for {args.input}:")
        for s in suggestions:
            print(f"  {s.width:<7} {s.family}")
    advice = _text_advice(data)
    if advice:
        print(f"\nhint: {advice}")
    return 0


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

def cmd_inspect(args) -> int:
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
        return 0

    print("give either --offset, or both --x and --y", file=sys.stderr)
    return 1


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
