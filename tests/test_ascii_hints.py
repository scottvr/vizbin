"""Slice 2: the cross-mode 'looks like text' advisory (default on, --no-hints)."""

from vizbin.cli import main
from vizbin.commands import _ascii_hint


def _printable(tmp_path):
    p = tmp_path / "src.txt"
    p.write_text("def main():\n    return 1\n" * 8)
    return str(p)


def _binary(tmp_path):
    # genuinely non-printable: alternating NUL / 0xFF (0% printable)
    p = tmp_path / "bin.dat"
    p.write_bytes(bytes([0x00, 0xFF] * 128))
    return str(p)


def test_ascii_hint_helper(tmp_path):
    assert _ascii_hint(_printable(tmp_path), 20) is not None
    assert _ascii_hint(_binary(tmp_path), 100) is None


# --- render advisory -------------------------------------------------------

def test_render_advisory_fires_and_suppresses(tmp_path, capsys):
    p, o = _printable(tmp_path), str(tmp_path / "o.bmp")
    main(["render", p, "-m", "raw-rgb", "-o", o])
    assert "hint:" in capsys.readouterr().out
    main(["render", p, "-m", "raw-rgb", "--no-hints", "-o", o])
    assert "hint:" not in capsys.readouterr().out


def test_render_no_advisory_on_binary(tmp_path, capsys):
    main(["render", _binary(tmp_path), "-m", "gray", "-o", str(tmp_path / "o.bmp")])
    assert "hint:" not in capsys.readouterr().out


def test_render_text_mode_does_not_advise_itself(tmp_path, capsys):
    main(["render", _printable(tmp_path), "-m", "text", "-o", str(tmp_path / "o.bmp")])
    assert "-m text" not in capsys.readouterr().out


# --- inspect psst ----------------------------------------------------------

def test_inspect_psst_fires_and_suppresses(tmp_path, capsys):
    p = _printable(tmp_path)
    main(["inspect", p, "-w", "64", "-m", "gray", "--offset", "20"])
    assert "psst:" in capsys.readouterr().out
    main(["inspect", p, "-w", "64", "-m", "gray", "--offset", "20", "--no-hints"])
    assert "psst:" not in capsys.readouterr().out


def test_inspect_no_psst_on_binary(tmp_path, capsys):
    main(["inspect", _binary(tmp_path), "-w", "64", "-m", "gray", "--offset", "100"])
    assert "psst:" not in capsys.readouterr().out


def test_inspect_no_psst_when_text_mode_present(tmp_path, capsys):
    # text already shows the character, so the advisory would be redundant
    main(["inspect", _printable(tmp_path), "-w", "64", "--modes", "gray,text", "--offset", "20"])
    assert "psst:" not in capsys.readouterr().out
