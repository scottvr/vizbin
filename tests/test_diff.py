"""Structural / visual binary diff."""

import json
import random

from vizbin import bindiff
from vizbin.cli import main


def _rand(n, seed=0):
    r = random.Random(seed)
    return bytes(r.randrange(256) for _ in range(n))


def test_identical():
    a = _rand(4096)
    r = bindiff.diff(a, a)
    assert r.similarity == 1.0
    assert bindiff.changed_regions(r) == []


def test_in_place_change():
    a = bytearray(_rand(4096, 1))
    b = bytearray(a)
    b[1000:1064] = _rand(64, 99)          # patch 64 bytes in place, same length
    r = bindiff.diff(bytes(a), bytes(b), block=8)
    changed = bindiff.changed_regions(r)
    assert all(c.tag == "replace" for c in changed)
    # the change is localized around offset 1000, not smeared across the file
    assert any(c.b_lo <= 1000 < c.b_hi for c in changed)
    assert sum(c.b_len for c in changed) <= 128     # ~one block of slack


def test_insertion_does_not_poison_the_tail():
    # THE key property: a mid-file insertion must not mark the whole tail changed
    a = _rand(8192, 2)
    b = a[:4096] + b"INSERTED" + a[4096:]           # 8-byte insertion mid-file
    r = bindiff.diff(a, b, block=8)
    assert r.similarity > 0.98                        # still ~identical
    changed = bindiff.changed_regions(r)
    assert any(c.tag == "insert" for c in changed)
    assert not any(c.tag == "replace" for c in changed)  # only an insert, no smear


def test_deletion_detected():
    a = _rand(4096, 3)
    b = a[:1000] + a[1016:]                            # delete 16 bytes
    r = bindiff.diff(a, b, block=8)
    assert any(c.tag == "delete" for c in bindiff.changed_regions(r))


def test_completely_different():
    r = bindiff.diff(_rand(4096, 4), _rand(4096, 5), block=16)
    assert r.similarity < 0.2


def test_render_marks_changes(tmp_path):
    a = bytearray(_rand(2048, 6))
    b = bytearray(a)
    b[500:600] = _rand(100, 7)
    r = bindiff.diff(bytes(a), bytes(b), block=8)
    raster = bindiff.render_diff(bytes(b), r, width=64)
    px = raster.rgb
    # a changed byte in [500,600) is painted red (222,52,52)
    i = 550 * 3
    assert (px[i], px[i + 1], px[i + 2]) == bindiff._C_REPLACE
    # an unchanged byte is a dim gray (r==g==b, and dark)
    j = 100 * 3
    assert px[j] == px[j + 1] == px[j + 2] and px[j] < 90


# --- CLI -------------------------------------------------------------------

def test_cli_report(tmp_path, capsys):
    a = tmp_path / "a.bin"
    a.write_bytes(_rand(4096, 8))
    b = tmp_path / "b.bin"
    bb = bytearray(a.read_bytes())
    bb[100:110] = _rand(10, 9)
    b.write_bytes(bytes(bb))
    assert main(["diff", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "identical" in out and "changed region" in out and "replace" in out


def test_cli_json(tmp_path, capsys):
    a = tmp_path / "a.bin"
    a.write_bytes(_rand(2048, 10))
    b = tmp_path / "b.bin"
    b.write_bytes(_rand(2048, 10))            # same seed -> identical
    assert main(["diff", str(a), str(b), "--json"]) == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["similarity"] == 1.0 and obj["changed_regions"] == []


def test_cli_writes_image(tmp_path, capsys):
    a = tmp_path / "a.bin"
    a.write_bytes(_rand(2048, 11))
    b = tmp_path / "b.bin"
    bb = bytearray(a.read_bytes())
    bb[0:64] = _rand(64, 12)
    b.write_bytes(bytes(bb))
    out = tmp_path / "d.bmp"
    assert main(["diff", str(a), str(b), "-o", str(out), "-w", "64"]) == 0
    assert out.exists() and "diff image" in capsys.readouterr().out
