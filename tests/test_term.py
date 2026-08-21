"""Terminal rendering: 24-bit ANSI half-block output (`render --term`)."""

from vizbin.canvas import Raster, to_ansi_halfblocks
from vizbin.cli import main


def test_halfblocks_structure():
    r = Raster(2, 2)
    r.rgb[:] = bytes([255, 0, 0,  0, 255, 0,    # top row: red, green
                      0, 0, 255,  255, 255, 0])  # bottom row: blue, yellow
    s = to_ansi_halfblocks(r)
    assert "▀" in s                       # upper half block
    assert "\x1b[38;2;255;0;0m" in s           # top-left as foreground
    assert "\x1b[48;2;0;0;255m" in s           # bottom-left as background
    assert "\x1b[0m" in s                       # reset per line
    assert s.count("\n") == 1                   # 2px tall -> one text row


def test_halfblocks_odd_height_uses_default_bg():
    r = Raster(1, 3)                            # 3 rows -> 2 text rows, last dangles
    s = to_ansi_halfblocks(r)
    assert s.count("\n") == 2
    assert "\x1b[49m" in s                      # dangling last row: default background


def test_cli_term_prints_ansi_and_writes_no_file(tmp_path, capsys):
    p = tmp_path / "t.bin"
    p.write_bytes(bytes(range(256)) * 2)
    rc = main(["render", str(p), "-m", "byteclass", "-w", "16", "--term", "--no-hints"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "\x1b[38;2;" in out and "▀" in out
    assert "-> terminal" in out
    assert not list(tmp_path.glob("*.bmp"))     # nothing written to disk


def test_cli_term_works_with_rgb_and_pipe(tmp_path, capsys):
    p = tmp_path / "t.bin"
    p.write_bytes(bytes(range(256)) * 4)
    for extra in (["--rgb", "entropy,delta,xor"], ["-t", "xor,entropy"]):
        assert main(["render", str(p), *extra, "-w", "16", "--term", "--no-hints"]) == 0
        assert "▀" in capsys.readouterr().out
