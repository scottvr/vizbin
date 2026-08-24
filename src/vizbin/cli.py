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
    # A genuinely global flag: shared via `parents=` on the top-level parser AND
    # every subparser so it parses wherever it lands on the command line.
    # default=SUPPRESS keeps a subparser from resetting a value set before the
    # subcommand, and keeps `no_hints` absent from the namespace unless passed.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--no-hints", dest="no_hints", action="store_true",
                        default=argparse.SUPPRESS,
                        help="Disable printing of mode hints")

    parser = argparse.ArgumentParser(
        prog="vizbin",
        parents=[common],
        description="Render arbitrary bytes as images so hidden structure "
                    "becomes visible. Take a blob, pretend it is an image, "
                    "vary the lie until the truth starts to show.",
    )
    parser.add_argument("--version", action="version",
                        version=f"vizbin {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, **kw):
        return sub.add_parser(name, parents=[common], **kw)

    modes_help = "projection mode: " + ", ".join(_MODES)

    # render
    r = add("render", help="render one image")
    r.add_argument("input")
    r.add_argument("-o", "--output")
    r.add_argument("-w", "--width", type=int, default=None,
                   help="image width in pixels (default: square-ish)")
    r.add_argument("-m", "--mode", default="gray", help=modes_help)
    r.add_argument("-t", "--transform", "--pipe", dest="transform", default=None,
                   help="transform axis: a transform or mode name, or a comma-chain "
                        "(e.g. xor,entropy). Painted by the last stage's colour "
                        "unless --paint is given. Order matters. Overrides -m. "
                        "(--pipe is an alias.)")
    r.add_argument("--paint", default=None,
                   help="colorizer axis: gray/magma/palette/nibble. Overrides the "
                        "mode's or pipeline's default colour.")
    r.add_argument("--rgb", default=None,
                   help="channel composition: up to 3 transforms driving R,G,B "
                        "(e.g. entropy,delta,xor). Its own colouring; overrides -m/-t.")
    r.add_argument("--term", action="store_true",
                   help="render into the terminal (24-bit ANSI half-blocks) "
                        "instead of writing a file")
    r.add_argument("--format", choices=["bmp", "svg"], default=None,
                   help="output image format (default: bmp, or svg if -o ends .svg). "
                        "SVG is crisp/scalable — best for structured renders.")
    r.add_argument("--find", default=None,
                   help="locate a string and window the render around it "
                        "(centre; window size = --length, default 8192)")
    r.add_argument("--find-hex", dest="find_hex", default=None,
                   help="like --find but the pattern is hex bytes (e.g. deadbeef)")
    _add_mode_opts(r)
    _add_region(r)
    r.set_defaults(func=commands.cmd_render)

    # sweep
    s = add("sweep", help="render several widths, one file each")
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
    c = add("contact", help="build a labelled contact sheet")
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
    a = add("animate", help="animate a width sweep")
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
    g = add("suggest", help="suggest informative widths")
    g.add_argument("input")
    g.add_argument("--top", type=int, default=12)
    g.add_argument("-v", "--verbose", action="store_true")
    _add_region(g)
    g.set_defaults(func=commands.cmd_suggest)

    # inspect
    i = add("inspect", help="map offsets <-> pixel coordinates")
    i.add_argument("input", nargs="?",
                   help="optional source file; enables the mode-specific "
                        "value/character readout")
    i.add_argument("-w", "--width", type=int, required=True)
    i.add_argument("-m", "--mode", default="gray", help=modes_help)
    i.add_argument("--modes", default=None,
                   help="comma list of modes to read out together for one "
                        "coordinate (e.g. raw-rgb,text); pair with a source file")
    i.add_argument("--rgb", default=None,
                   help="channel-composition transforms (R,G,B) to read out at "
                        "the offset, matching a `render --rgb` image")
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
    i.add_argument("-n", "--min-run", dest="min_run", type=int, default=6,
                   help="min printable run to trigger the 'looks like text' hint "
                        "(like strings -n; default 6)")
    i.set_defaults(func=commands.cmd_inspect)

    # diff
    d = add("diff", help="structural/visual diff of two binaries")
    d.add_argument("a")
    d.add_argument("b")
    d.add_argument("--block", type=int, default=None,
                   help="block size for matching (default: scaled to file size)")
    d.add_argument("-w", "--width", type=int, default=None,
                   help="diff-image width (with -o/--term)")
    d.add_argument("-o", "--output", help="write a diff image (BMP)")
    d.add_argument("--term", action="store_true",
                   help="render the diff image into the terminal")
    d.add_argument("--json", action="store_true", help="emit the diff as JSON")
    _add_region(d)
    d.set_defaults(func=commands.cmd_diff)

    # profile
    pr = add("profile", help="structural fingerprint (entropy, classes, regions)")
    pr.add_argument("input", nargs="+", help="one or more files to fingerprint")
    pr.add_argument("--json", action="store_true",
                    help="emit JSONL (one JSON object per file) for corpus tooling")
    pr.add_argument("--no-stride", dest="no_stride", action="store_true",
                    help="skip record-stride detection (faster on large corpora)")
    _add_region(pr)
    pr.set_defaults(func=commands.cmd_profile)

    # infer
    n = add("infer", help="infer a draft record/field layout")
    n.add_argument("input")
    n.add_argument("--stride", type=_auto_int, default=None,
                   help="force record length in bytes (accepts 0x..); "
                        "default: auto via byte-autocorrelation")
    n.add_argument("--format", choices=["table", "json", "kaitai", "struct"],
                   default="table", help="output format (default: table)")
    n.add_argument("--json", action="store_const", const="json", dest="format",
                   help="shorthand for --format json")
    _add_region(n)
    n.set_defaults(func=commands.cmd_infer)

    # bmp
    b = add("bmp", help="reversible payload-as-pixels BMP")
    b.add_argument("input")
    b.add_argument("output", nargs="?")
    b.add_argument("-w", "--width", type=int, default=None,
                   help="width (must be divisible by 4); default square-ish")
    _add_region(b)
    b.set_defaults(func=commands.cmd_bmp)

    # unbmp
    u = add("unbmp", help="recover payload from a vizbin bmp")
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
