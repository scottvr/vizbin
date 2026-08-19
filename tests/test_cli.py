import os

from vizbin import bmp
from vizbin.cli import main


def _make_input(tmp_path):
    data = bytearray()
    for i in range(200):
        rec = bytearray(64)
        rec[0] = 0x47
        for j in range(1, 64):
            rec[j] = (i + j) & 0xFF
        data += rec
    p = tmp_path / "in.bin"
    p.write_bytes(bytes(data))
    return p


def test_render(tmp_path):
    p = _make_input(tmp_path)
    out = tmp_path / "out.bmp"
    rc = main(["render", str(p), "-w", "64", "-m", "gray", "-o", str(out)])
    assert rc == 0
    info = bmp.read_header(out.read_bytes())
    assert info.width == 64


def test_render_all_modes(tmp_path):
    p = _make_input(tmp_path)
    for m in ["gray", "raw-rgb", "byteclass", "entropy", "delta", "xor",
              "bitplane", "nibble"]:
        out = tmp_path / f"{m}.bmp"
        rc = main(["render", str(p), "-w", "64", "-m", m, "-o", str(out)])
        assert rc == 0, m
        assert out.exists()


def test_sweep(tmp_path):
    p = _make_input(tmp_path)
    outdir = tmp_path / "sw"
    rc = main(["sweep", str(p), "--widths", "32,64,128", "--outdir", str(outdir)])
    assert rc == 0
    assert len(list(outdir.glob("*.bmp"))) == 3


def test_contact_modes(tmp_path):
    p = _make_input(tmp_path)
    out = tmp_path / "c.bmp"
    rc = main(["contact", str(p), "--modes", "gray,entropy", "-w", "64",
               "-o", str(out)])
    assert rc == 0
    assert out.exists()


def test_animate_gif(tmp_path):
    p = _make_input(tmp_path)
    out = tmp_path / "a.gif"
    rc = main(["animate", str(p), "--from", "60", "--to", "68", "--step", "2",
               "-o", str(out)])
    assert rc == 0
    assert out.read_bytes()[:6] == b"GIF89a"


def test_bmp_unbmp_roundtrip(tmp_path):
    p = _make_input(tmp_path)
    b = tmp_path / "x.bmp"
    rec = tmp_path / "x.out"
    assert main(["bmp", str(p), str(b)]) == 0
    assert main(["unbmp", str(b), "-o", str(rec)]) == 0
    assert rec.read_bytes() == p.read_bytes()


def test_suggest(tmp_path, capsys):
    p = _make_input(tmp_path)
    rc = main(["suggest", str(p), "--top", "5"])
    assert rc == 0
    assert "Suggested widths" in capsys.readouterr().out


def test_inspect_offset(tmp_path, capsys):
    rc = main(["inspect", "-w", "64", "-m", "gray", "--offset", "128"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "y=2" in out  # 128 // 64 == 2


def test_region_windowing(tmp_path):
    p = _make_input(tmp_path)
    out = tmp_path / "w.bmp"
    rc = main(["render", str(p), "-w", "64", "--offset", "0x40", "--length",
               "256", "-o", str(out)])
    assert rc == 0
    info = bmp.read_header(out.read_bytes())
    assert info.width == 64
    assert info.height == 4  # 256 bytes / 64
