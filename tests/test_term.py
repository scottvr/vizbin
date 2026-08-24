"""Terminal rendering: ANSI half-block output (`render --term`)."""

from vizbin.canvas import Raster, rgb_to_256, to_ansi_halfblocks
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


def test_rgb_to_256_landmarks():
    assert rgb_to_256(0, 0, 0) == 16            # cube corner: black
    assert rgb_to_256(255, 255, 255) == 231     # cube corner: white
    assert rgb_to_256(255, 0, 0) == 196         # cube corner: red
    # near-neutral grays resolve to the gray ramp (232..255), not a tinted cube
    assert 232 <= rgb_to_256(5, 5, 5) <= 255
    assert 232 <= rgb_to_256(128, 128, 128) <= 255


def test_halfblocks_256_form_has_no_truecolor_or_leaking_bytes():
    # A byte value of 5 in a 24-bit sequence misparses to SGR 5 (blink) on
    # terminals without truecolor. The 256 form must not emit 38;2/48;2 at all,
    # and its only bare "5" is the palette selector (38;5;/48;5;).
    r = Raster(1, 2)
    r.rgb[:] = bytes([5, 5, 5,  0, 255, 0])
    s = to_ansi_halfblocks(r, truecolor=False)
    assert "38;2;" not in s and "48;2;" not in s
    assert "\x1b[38;5;" in s and "\x1b[48;5;" in s


def test_cli_term_forces_color_depth(tmp_path, capsys):
    p = tmp_path / "t.bin"
    p.write_bytes(bytes(range(256)) * 2)

    # --color truecolor: 24-bit regardless of $COLORTERM in the env
    rc = main(["render", str(p), "-m", "byteclass", "-w", "16", "--term",
               "--color", "truecolor", "--no-hints"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "\x1b[38;2;" in out and "▀" in out
    assert "-> terminal" in out
    assert not list(tmp_path.glob("*.bmp"))     # nothing written to disk

    # --color 256: palette form, never 24-bit
    rc = main(["render", str(p), "-m", "byteclass", "-w", "16", "--term",
               "--color", "256", "--no-hints"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "\x1b[38;5;" in out and "38;2;" not in out


def test_cli_term_auto_follows_colorterm(tmp_path, capsys, monkeypatch):
    p = tmp_path / "t.bin"
    p.write_bytes(bytes(range(256)) * 2)

    monkeypatch.setenv("COLORTERM", "truecolor")
    assert main(["render", str(p), "-w", "16", "--term", "--no-hints"]) == 0
    assert "\x1b[38;2;" in capsys.readouterr().out

    monkeypatch.delenv("COLORTERM", raising=False)   # e.g. macOS Terminal.app
    assert main(["render", str(p), "-w", "16", "--term", "--no-hints"]) == 0
    out = capsys.readouterr().out
    assert "\x1b[38;5;" in out and "38;2;" not in out


def test_cli_term_works_with_rgb_and_pipe(tmp_path, capsys):
    p = tmp_path / "t.bin"
    p.write_bytes(bytes(range(256)) * 4)
    for extra in (["--rgb", "entropy,delta,xor"], ["-t", "xor,entropy"]):
        assert main(["render", str(p), *extra, "-w", "16", "--term", "--no-hints"]) == 0
        assert "▀" in capsys.readouterr().out
