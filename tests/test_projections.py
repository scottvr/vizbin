from vizbin import projections


def _avg_luma(raster):
    rgb = raster.rgb
    if not rgb:
        return 0.0
    return sum(rgb) / len(rgb)


def test_render_dimensions_and_padding():
    data = bytes(range(256)) * 4  # 1024 bytes
    r = projections.render("gray", data, width=100)
    assert r.width == 100
    assert r.height == 11              # ceil(1024/100)
    assert len(r.rgb) == 100 * 11 * 3  # padded to full rows


def test_gray_is_identity_per_channel():
    data = bytes([0, 128, 255])
    r = projections.render("gray", data, width=3)
    assert r.rgb[0:3] == bytes([0, 0, 0])
    assert r.rgb[3:6] == bytes([128, 128, 128])
    assert r.rgb[6:9] == bytes([255, 255, 255])


def test_raw_rgb_phase():
    data = bytes([1, 2, 3, 4, 5, 6, 7])
    r0 = projections.render("raw-rgb", data, width=1, phase=0)
    assert r0.rgb[0:3] == bytes([1, 2, 3])
    r1 = projections.render("raw-rgb", data, width=1, phase=1)
    assert r1.rgb[0:3] == bytes([2, 3, 4])


def test_byteclass_colours():
    from vizbin.projections import _CLASS_COLORS
    data = bytes([0x00, 0xFF, ord("A"), 0x01])
    r = projections.render("byteclass", data, width=4)
    assert tuple(r.rgb[0:3]) == _CLASS_COLORS[0]   # NUL
    assert tuple(r.rgb[3:6]) == _CLASS_COLORS[1]   # 0xFF
    assert tuple(r.rgb[6:9]) == _CLASS_COLORS[3]   # printable
    assert tuple(r.rgb[9:12]) == _CLASS_COLORS[4]  # control


def test_entropy_random_brighter_than_constant():
    import random
    random.seed(0)
    rnd = bytes(random.getrandbits(8) for _ in range(4096))
    const = b"\x41" * 4096
    r_rnd = projections.render("entropy", rnd, width=64)
    r_const = projections.render("entropy", const, width=64)
    assert _avg_luma(r_rnd) > _avg_luma(r_const)


def test_delta_of_ramp_is_low():
    ramp = bytes(range(256))  # deltas all == 1
    r = projections.render("delta", ramp, width=16)
    # every non-padding pixel should be value 1 (except the first which is 0)
    assert r.rgb[3] == 1


def test_xor_self_cancels_with_lag():
    data = bytes([5, 5, 5, 5, 5])
    r = projections.render("xor", data, width=5, k=1)
    # 5 ^ 5 == 0 for lagged positions
    assert r.rgb[3] == 0


def test_bitplane_top_bit():
    data = bytes([0x80, 0x7F])
    r = projections.render("bitplane", data, width=2, plane=7)
    assert r.rgb[0] == 255  # 0x80 has top bit set
    assert r.rgb[3] == 0    # 0x7F does not


def test_resolve_aliases():
    assert projections.resolve("rawrgb") == "raw-rgb"
    assert projections.resolve("grey") == "gray"


def test_pixel_count():
    assert projections.pixel_count("gray", 100) == 100
    assert projections.pixel_count("raw-rgb", 100, phase=0) == 33
    assert projections.pixel_count("raw-rgb", 100, phase=1) == 33
