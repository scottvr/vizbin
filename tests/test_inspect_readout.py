"""Mode-specific `inspect` readouts.

Oracles here were derived independently from the projection builders by a
verification pass, then recomputed by hand; each asserts that the readout speaks
the projection's own language for a given byte offset.
"""

from vizbin.cli import main
from vizbin.commands import _mode_readout, _shannon_bits


def _file(tmp_path, hexstr):
    p = tmp_path / "blob.bin"
    p.write_bytes(bytes.fromhex(hexstr))
    return str(p)


def ro(tmp_path, hexstr, mode, offset, base=0, **opts):
    return _mode_readout(mode, _file(tmp_path, hexstr), offset, base, opts)


# --- single-byte modes -----------------------------------------------------

def test_gray(tmp_path):
    assert ro(tmp_path, "41", "gray", 0) == "byte 0x41 (65) -> gray 65"
    assert ro(tmp_path, "de00ad", "gray", 0) == "byte 0xde (222) -> gray 222"


def test_byteclass_classes(tmp_path):
    assert ro(tmp_path, "41", "byteclass", 0) == "byte 0x41 (65) -> class 'ascii'"
    assert ro(tmp_path, "80", "byteclass", 0) == "byte 0x80 (128) -> class 'high-bit'"
    # boundary bytes the critic flagged: space is whitespace, DEL is control
    assert ro(tmp_path, "20", "byteclass", 0) == "byte 0x20 (32) -> class 'whitespace'"
    assert ro(tmp_path, "7f", "byteclass", 0) == "byte 0x7f (127) -> class 'control'"
    assert ro(tmp_path, "00", "byteclass", 0) == "byte 0x00 (0) -> class 'nul'"
    assert ro(tmp_path, "ff", "byteclass", 0) == "byte 0xff (255) -> class '0xff'"


def test_nibble(tmp_path):
    assert ro(tmp_path, "be", "nibble", 0) == "byte 0xbe (190) -> hi 0xb, lo 0xe"


def test_text_char_and_names(tmp_path):
    assert ro(tmp_path, "48656c6c6f", "text", 0) == "byte 0x48 (72) = 'H'"
    assert ro(tmp_path, "00090a7f80", "text", 2) == "byte 0x0a (10) = LF"
    assert ro(tmp_path, "20", "text", 0) == "byte 0x20 (32) = ' '"   # printable space
    assert ro(tmp_path, "1b", "text", 0) == "byte 0x1b (27) = 0x1b"  # unnamed control
    assert ro(tmp_path, "ff", "text", 0) == "byte 0xff (255) = 0xff"  # high-bit


def test_bitplane(tmp_path):
    assert ro(tmp_path, "804021", "bitplane", 0, plane=7) == "byte 0x80 (128) -> bit[7] = 1"
    assert ro(tmp_path, "804021", "bitplane", 2, plane=0) == "byte 0x21 (33) -> bit[0] = 1"


# --- predecessor modes -----------------------------------------------------

def test_delta(tmp_path):
    assert ro(tmp_path, "9030", "delta", 0) == "byte 0x90 (144), prev 0x00 (pad) -> |delta| 144"
    assert ro(tmp_path, "0011222a30", "delta", 4) == \
        "byte 0x30 (48), prev@3 0x2a (42) -> |delta| 6"


def test_xor(tmp_path):
    # i < k -> the 0x00 padding operand, so xor == the byte itself
    assert ro(tmp_path, "104155", "xor", 1, k=2) == "byte 0x41 (65) XOR 0x00 (pad) = 0x41 (65)"
    assert ro(tmp_path, "001122330fff", "xor", 5, k=1) == \
        "byte 0xff (255) XOR @4 0x0f (15) = 0xf0 (240)"


# --- window / rgb ----------------------------------------------------------

def test_entropy(tmp_path):
    # AAAB before the window fills -> 0.81 bits over a 4-byte window
    assert ro(tmp_path, "414141424344", "entropy", 3) == \
        "entropy 0.81 bits over 4-byte window [0-3]"
    # sliding window of 4 ending at offset 5 -> ABCC -> 1.50 bits
    assert ro(tmp_path, "4141414243434343", "entropy", 5, window=4) == \
        "entropy 1.50 bits over 4-byte window [2-5]"


def test_entropy_offset_zero_is_one_byte_window(tmp_path):
    # critic edge case: at offset 0 the effective window is 1 byte -> 0 bits
    assert ro(tmp_path, "4243", "entropy", 0) == "entropy 0.00 bits over 1-byte window [0-0]"


def test_raw_rgb(tmp_path):
    # these bytes are all printable, so the inline ASCII gloss fires
    assert ro(tmp_path, "102030405060708090", "raw-rgb", 4, phase=0) == \
        'pixel 1 -> R@3=0x40 G@4=0x50 B@5=0x60 -> "@P`"'
    assert ro(tmp_path, "0011223344556677", "raw-rgb", 4, phase=1) == \
        'pixel 1 -> R@4=0x44 G@5=0x55 B@6=0x66 -> "DUf"'


def test_raw_rgb_no_gloss_when_not_all_printable(tmp_path):
    # 0x01 is a control byte -> no ASCII gloss
    assert ro(tmp_path, "0141420001", "raw-rgb", 0, phase=0) == \
        "pixel 0 -> R@0=0x01 G@1=0x41 B@2=0x42"


# --- edge cases the critic surfaced ----------------------------------------

def test_base_makes_lookups_region_relative(tmp_path):
    # render started at base=1; absolute offset 1 is the region's first byte,
    # so delta there uses the 0x00 pad (not file[0]).
    path = _file(tmp_path, "ff41")
    assert _mode_readout("gray", path, 1, 1, {}) == "byte 0x41 (65) -> gray 65"
    assert _mode_readout("delta", path, 1, 1, {}) == \
        "byte 0x41 (65), prev 0x00 (pad) -> |delta| 65"


def test_offset_beyond_data(tmp_path):
    assert ro(tmp_path, "4142", "gray", 9) == "(offset beyond data)"


def test_shannon_bits_matches_hand_values():
    assert _shannon_bits([]) == 0.0
    assert _shannon_bits([1, 1, 1, 1]) == 0.0            # single symbol -> 0
    assert abs(_shannon_bits([1, 2, 3, 4]) - 2.0) < 1e-9  # 4 distinct -> log2(4)


# --- CLI wiring ------------------------------------------------------------

def test_cli_offset_readout(tmp_path, capsys):
    path = _file(tmp_path, "48656c6c6f")
    rc = main(["inspect", path, "-w", "64", "-m", "text", "--offset", "0"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "= 'H'" in out


def test_cli_without_input_is_geometry_only(tmp_path, capsys):
    rc = main(["inspect", "-w", "64", "-m", "gray", "--offset", "128"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "y=2" in out
    assert "byte 0x" not in out  # no readout without a source file


# --- Slice 1: raw-rgb ASCII gloss + multi-mode stacking --------------------

def test_ascii_gloss_helper():
    from vizbin.commands import _ascii_gloss
    assert _ascii_gloss([0x73, 0x74, 0x61]) == ' -> "sta"'
    assert _ascii_gloss([0x73, 0x00, 0x61]) == ""   # a non-printable -> no gloss
    assert _ascii_gloss([]) == ""


def test_cli_multi_mode_stacks_readouts(tmp_path, capsys):
    path = _file(tmp_path, "737461")  # s t a -> raw-rgb pixel 0 spells "sta"
    rc = main(["inspect", path, "-w", "64", "--modes", "raw-rgb,text,gray",
               "--offset", "0"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[raw-rgb" in out and "[text" in out and "[gray" in out
    assert '-> "sta"' in out          # rgb gloss reveals the string
    assert "= 's'" in out             # text reads the char at offset 0
    assert "-> gray 115" in out       # gray value of 's'


def test_cli_single_mode_via_modes_flag_uses_detailed_path(tmp_path, capsys):
    path = _file(tmp_path, "48")
    rc = main(["inspect", path, "-w", "64", "--modes", "text", "--offset", "0"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "= 'H'" in out
    assert "cell" in out or "pixel" in out  # detailed single-mode geometry kept
