"""render --find / --find-hex: locate a pattern and window around it."""

from types import SimpleNamespace

from vizbin.cli import main
from vizbin.commands import _apply_find


def _args(**kw):
    base = dict(input=None, offset=0, length=None, find=None, find_hex=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_apply_find_centres_window(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"\x00" * 5000 + b"NEEDLE" + b"\x00" * 5000)
    a = _args(input=str(p), find="NEEDLE", length=1000)
    assert _apply_find(a) == 0
    # window of 1000 centred on the match near offset 5000
    assert a.length == 1000
    assert a.offset <= 5003 <= a.offset + a.length      # match inside window
    assert abs(a.offset - (5000 - 500)) <= 6            # roughly centred


def test_apply_find_default_window(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"x" * 20000 + b"TARGET")
    a = _args(input=str(p), find="TARGET")
    assert _apply_find(a) == 0
    assert a.length == 8192                              # default window


def test_apply_find_hex(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"....\xde\xad\xbe\xef....")
    a = _args(input=str(p), find_hex="deadbeef", length=8)
    assert _apply_find(a) == 0
    assert a.offset <= 4 < a.offset + a.length


def test_apply_find_not_found(tmp_path, capsys):
    p = tmp_path / "f.bin"
    p.write_bytes(b"hello world")
    a = _args(input=str(p), find="NOPE")
    assert _apply_find(a) == 1
    assert "not found" in capsys.readouterr().err


def test_apply_find_bad_hex(tmp_path, capsys):
    p = tmp_path / "f.bin"
    p.write_bytes(b"data")
    a = _args(input=str(p), find_hex="zzzz")
    assert _apply_find(a) == 1
    assert "not valid hex" in capsys.readouterr().err


def test_apply_find_window_clamped_to_file(tmp_path):
    # window larger than file: clamp to a valid slice, don't go negative/past end
    p = tmp_path / "f.bin"
    p.write_bytes(b"12345MATCH67890")
    a = _args(input=str(p), find="MATCH", length=100000)
    assert _apply_find(a) == 0
    assert a.offset == 0                                 # clamped to start
    assert a.length == 100000


def test_apply_find_noop_without_pattern(tmp_path):
    a = _args(input="whatever", offset=42, length=99)
    assert _apply_find(a) == 0
    assert a.offset == 42 and a.length == 99             # untouched


# --- CLI ------------------------------------------------------------------

def test_cli_render_find(tmp_path, capsys):
    p = tmp_path / "f.bin"
    p.write_bytes(b"\x00" * 3000 + b"FINDME_MARKER" + b"\x00" * 3000)
    out = tmp_path / "o.bmp"
    rc = main(["render", str(p), "-m", "gray", "--find", "FINDME_MARKER",
               "--length", "1024", "-w", "32", "-o", str(out), "--no-hints"])
    assert rc == 0
    o = capsys.readouterr().out
    assert "found" in o and "FINDME_MARKER" in o
    assert out.exists()


def test_cli_render_find_missing_returns_error(tmp_path, capsys):
    p = tmp_path / "f.bin"
    p.write_bytes(b"just some bytes")
    rc = main(["render", str(p), "--find", "absent", "-o", str(tmp_path / "o.bmp")])
    assert rc == 1
