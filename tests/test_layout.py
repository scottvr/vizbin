from vizbin import layout


def test_parse_widths_list():
    assert layout.parse_widths("64,128,256", n_pixels=100000) == [64, 128, 256]


def test_parse_widths_hex():
    assert layout.parse_widths("0x10,0x20", n_pixels=100000) == [16, 32]


def test_parse_widths_family():
    assert layout.parse_widths("powers2", n_pixels=100000) == layout.WIDTH_FAMILIES["powers2"]


def test_parse_widths_square():
    assert layout.parse_widths("square", n_pixels=10000) == [100]


def test_square_width():
    assert layout.square_width(10000) == 100
    assert layout.square_width(0) == 1


def test_offset_map_gray_roundtrip():
    om = layout.OffsetMap(width=188, bpp=1)
    r = om.offset_to_pixel(18800)
    assert (r["x"], r["y"]) == (0, 100)
    back = om.pixel_to_offset(0, 100)
    assert back["offset"] == 18800


def test_offset_map_rawrgb_channel():
    om = layout.OffsetMap(width=100, bpp=3, phase=1)
    r = om.offset_to_pixel(1 + 3 * 5 + 2)  # phase 1, pixel 5, channel 2
    assert r["pixel"] == 5
    assert r["channel"] == 2
    back = om.pixel_to_offset(5, 0)
    assert back["offset"] == 1 + 3 * 5  # start byte of pixel 5


def test_offset_before_region():
    om = layout.OffsetMap(width=10, bpp=1, base=100)
    assert "error" in om.offset_to_pixel(50)


def test_offset_map_text_cell_geometry():
    # text mode: width is columns, each byte is an 8*scale px cell.
    om = layout.OffsetMap(width=64, bpp=1, cell=24)  # scale 3
    r = om.offset_to_pixel(260)
    assert (r["x"], r["y"]) == (4, 4)            # 260 // 64 == 4, rem 4
    assert (r["px_x"], r["px_y"]) == (96, 96)    # col/row * 24
    assert r["cell"] == 24


def test_offset_map_text_any_pixel_in_cell_maps_to_byte():
    om = layout.OffsetMap(width=64, bpp=1, cell=24)
    # every pixel inside the 24x24 cell at col 4, row 4 -> the same offset 260
    for x, y in [(96, 96), (110, 110), (119, 119)]:
        back = om.pixel_to_offset(x, y)
        assert (back["col"], back["row"]) == (4, 4)
        assert back["offset"] == 260


def test_suggest_finds_record_width():
    # 188-byte records with a constant sync byte -> strong row coherence at 188
    data = bytearray()
    for i in range(300):
        rec = bytearray(188)
        rec[0] = 0x47
        for j in range(1, 188):
            rec[j] = (i + j) & 0xFF
        data += rec
    top = layout.suggest(bytes(data), top=5)
    widths = [s.width for s in top]
    assert 188 in widths
    assert top[0].score > 0.5
