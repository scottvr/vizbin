"""vizbin command-line interface.

    vizbin
    |-- render     one image at a chosen width/mode
    |-- sweep      many widths, one file each
    |-- contact    a labelled grid of widths / modes / phases
    |-- animate    a width sweep as an animated GIF (or mp4 via ffmpeg)
    |-- suggest    candidate widths, ranked by row coherence
    |-- inspect    map between byte offsets and pixel coordinates
    |-- bmp        reversible "payload as pixels" BMP
    `-- unbmp      recover the payload from a bmp
"""

from __future__ import annotations

import argparse

from vizbin import __version__, commands, projections


def _auto_int(s: str) -> int:
    """Parse an int allowing 0x.., 0o.., 0b.. and decimal."""
    return int(s, 0)


def _add_region(p: argparse.ArgumentParser) -> None:
    p.add_argument("--offset", type=_auto_int, default=0,
                   help="start reading at this byte offset (accepts 0x..)")
    p.add_argument("--length", type=_auto_int, default=None,
                   help="read at most this many bytes")


def _add_mode_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--phase", type=int, default=0,
                   help="raw-rgb byte-grouping phase (0/1/2)")
    p.add_argument("--window", type=int, default=256,
                   help="entropy sliding-window size in bytes")
    p.add_argument("--k", type=int, default=1,
                   help="xor lag k for the xor mode")
    p.add_argument("--plane", type=int, default=7,
                   help="bit index 0..7 for the bitplane mode")
    p.add_argument("--scale", type=int, default=1,
                   help="text mode: glyph magnification (cell = 8*scale px)")
    p.add_argument("--mono-text", dest="mono_text", action="store_true",
                   help="text mode: draw non-printable bytes blank instead of "
                        "byte-class colour tiles")


_MODES = projections.mode_names()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vizbin",
        description="Render arbitrary bytes as images so hidden structure "
                    "becomes visible. Take a blob, pretend it is an image, "
                    "vary the lie until the truth starts to show.",
    )
    parser.add_argument("--version", action="version",
                        version=f"vizbin {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    modes_help = "projection mode: " + ", ".join(_MODES)

    # render
    r = sub.add_parser("render", help="render one image")
    r.add_argument("input")
    r.add_argument("-o", "--output")
    r.add_argument("-w", "--width", type=int, default=None,
                   help="image width in pixels (default: square-ish)")
    r.add_argument("-m", "--mode", default="gray", help=modes_help)
    _add_mode_opts(r)
    _add_region(r)
    r.set_defaults(func=commands.cmd_render)

    # sweep
    s = sub.add_parser("sweep", help="render several widths, one file each")
    s.add_argument("input")
    s.add_argument("-o", "--output", help="only valid with a single width")
    s.add_argument("--outdir", help="directory for output files")
    s.add_argument("--widths", default="common",
                   help="family (powers2/storage/textish/screenish/records), "
                        "'common', 'square', or a comma list")
    s.add_argument("-m", "--mode", default="gray", help=modes_help)
    _add_mode_opts(s)
    _add_region(s)
    s.set_defaults(func=commands.cmd_sweep)

    # contact
    c = sub.add_parser("contact", help="build a labelled contact sheet")
    c.add_argument("input")
    c.add_argument("-o", "--output")
    c.add_argument("--widths", default="common",
                   help="widths to vary (default axis of variation)")
    c.add_argument("--modes", default=None,
                   help="comma list of modes to vary at a fixed width")
    c.add_argument("--phases", default=None,
                   help="comma list of raw-rgb phases to vary at a fixed width")
    c.add_argument("-w", "--width", type=int, default=None,
                   help="fixed width for --modes/--phases")
    c.add_argument("-m", "--mode", default="gray", help=modes_help)
    c.add_argument("--cell", type=int, default=256, help="tile size in pixels")
    c.add_argument("--cols", type=int, default=None, help="columns in the grid")
    _add_mode_opts(c)
    _add_region(c)
    c.set_defaults(func=commands.cmd_contact)

    # animate
    a = sub.add_parser("animate", help="animate a width sweep")
    a.add_argument("input")
    a.add_argument("-o", "--output")
    a.add_argument("--from", dest="frm", type=int, default=64)
    a.add_argument("--to", type=int, default=1024)
    a.add_argument("--step", type=int, default=4)
    a.add_argument("--widths", default=None,
                   help="explicit widths instead of --from/--to/--step")
    a.add_argument("-m", "--mode", default="gray", help=modes_help)
    a.add_argument("--fps", type=int, default=12)
    a.add_argument("--format", choices=["gif", "mp4"], default="gif")
    a.add_argument("--max-size", dest="max_size", type=int, default=512,
                   help="cap each frame's largest dimension (0 = no cap)")
    _add_mode_opts(a)
    _add_region(a)
    a.set_defaults(func=commands.cmd_animate)

    # suggest
    g = sub.add_parser("suggest", help="suggest informative widths")
    g.add_argument("input")
    g.add_argument("--top", type=int, default=12)
    g.add_argument("-v", "--verbose", action="store_true")
    _add_region(g)
    g.set_defaults(func=commands.cmd_suggest)

    # inspect
    i = sub.add_parser("inspect", help="map offsets <-> pixel coordinates")
    i.add_argument("input", nargs="?",
                   help="optional source file; enables the mode-specific "
                        "value/character readout")
    i.add_argument("-w", "--width", type=int, required=True)
    i.add_argument("-m", "--mode", default="gray", help=modes_help)
    i.add_argument("--offset", type=_auto_int, default=None,
                   help="byte offset to locate (accepts 0x..)")
    i.add_argument("--x", type=int, default=None)
    i.add_argument("--y", type=int, default=None)
    i.add_argument("--phase", type=int, default=0)
    i.add_argument("--k", type=int, default=1,
                   help="xor lag k (for the readout in xor mode)")
    i.add_argument("--window", type=int, default=256,
                   help="entropy window (for the readout in entropy mode)")
    i.add_argument("--plane", type=int, default=7,
                   help="bit index 0..7 (for the readout in bitplane mode)")
    i.add_argument("--scale", type=int, default=1,
                   help="text mode: glyph scale used at render time (cell = 8*scale px)")
    i.add_argument("--base", type=_auto_int, default=0,
                   help="base offset the render started at (render --offset)")
    i.set_defaults(func=commands.cmd_inspect)

    # bmp
    b = sub.add_parser("bmp", help="reversible payload-as-pixels BMP")
    b.add_argument("input")
    b.add_argument("output", nargs="?")
    b.add_argument("-w", "--width", type=int, default=None,
                   help="width (must be divisible by 4); default square-ish")
    _add_region(b)
    b.set_defaults(func=commands.cmd_bmp)

    # unbmp
    u = sub.add_parser("unbmp", help="recover payload from a vizbin bmp")
    u.add_argument("input")
    u.add_argument("-o", "--output",
                   help="write payload here (default: stdout)")
    u.set_defaults(func=commands.cmd_unbmp)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # normalise output attr presence
    if not hasattr(args, "output"):
        args.output = None
    if not hasattr(args, "outdir"):
        args.outdir = None
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
