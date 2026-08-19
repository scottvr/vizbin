import pytest

from vizbin import bmp


def test_header_roundtrip():
    h = bmp.make_header(10, 20, 10 * 20 * 3, reserved=12345)
    info = bmp.read_header(h)
    assert info.width == 10
    assert info.height == 20
    assert info.top_down is True
    assert info.bits_per_pixel == 24
    assert info.offset == 54
    assert info.reserved == 12345


def test_row_padding():
    assert bmp.row_padding(4) == 0
    assert bmp.row_padding(2) == 2
    assert bmp.row_padding(1) == 1
    assert bmp.row_padding(3) == 3


def test_raw_roundtrip_random(tmp_path):
    payload = bytes((i * 37 + 11) & 0xFF for i in range(5000))
    out = tmp_path / "a.bmp"
    w, h, pad = bmp.write_raw_bmp(str(out), payload)
    assert w % 4 == 0
    data = out.read_bytes()
    assert data[54:54 + len(payload)] == payload  # offset property
    assert bmp.unbmp(data) == payload             # exact reversal


def test_raw_roundtrip_trailing_nul(tmp_path):
    payload = b"ABC" + b"\x00" * 17
    out = tmp_path / "b.bmp"
    bmp.write_raw_bmp(str(out), payload)
    assert bmp.unbmp(out.read_bytes()) == payload


def test_raw_width_must_be_div4(tmp_path):
    with pytest.raises(ValueError):
        bmp.write_raw_bmp(str(tmp_path / "c.bmp"), b"x" * 100, width=13)


def test_rgb_bmp_dimensions_and_padding(tmp_path):
    rgb = bytes((i * 3) & 0xFF for i in range(5 * 4 * 3))  # 5x4
    out = tmp_path / "d.bmp"
    bmp.write_rgb_bmp(str(out), rgb, 5, 4)
    data = out.read_bytes()
    info = bmp.read_header(data)
    assert (info.width, info.height) == (5, 4)
    assert len(data) == 54 + (5 * 3 + 1) * 4  # 1 pad byte per row


def test_rgb_channel_swap(tmp_path):
    rgb = bytes([255, 0, 0] + [0] * 9)  # red pixel then 3 black, width 4
    out = tmp_path / "e.bmp"
    bmp.write_rgb_bmp(str(out), rgb, 4, 1)
    data = out.read_bytes()
    assert data[54:57] == bytes([0, 0, 255])  # stored B,G,R
