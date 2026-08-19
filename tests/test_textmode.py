from vizbin import projections
from vizbin.canvas import Raster
from vizbin.font8x8 import FONT8X8
from vizbin.projections import _CLASS_COLORS, _byte_class
from vizbin.textmode import _DEFAULT_BG, render_text


def _cell(raster, col, row, cell):
    """Return the set of distinct colours inside cell (col, row)."""
    colors = set()
    for ry in range(cell):
        for cx in range(cell):
            x, y = col * cell + cx, row * cell + ry
            i = (y * raster.width + x) * 3
            colors.add((raster.rgb[i], raster.rgb[i + 1], raster.rgb[i + 2]))
    return colors


def test_font_table_is_full_basic_latin():
    assert len(FONT8X8) == 128
    assert all(len(g) == 8 for g in FONT8X8)


def test_text_is_a_resolvable_mode_with_aliases():
    assert "text" in projections.mode_names()
    assert projections.resolve("ascii") == "text"
    assert projections.resolve("txt") == "text"
    assert projections.bytes_per_pixel("text") == 1
    assert projections.pixel_count("text", 100) == 100


def test_dimensions_are_cells_times_scale():
    # 20 bytes at 8 cols -> ceil(20/8)=3 rows; scale 2 -> 16px cells
    r = projections.render("text", bytes(20), width=8, scale=2)
    assert isinstance(r, Raster)
    assert r.width == 8 * 16
    assert r.height == 3 * 16


def test_empty_input_is_safe():
    r = render_text(b"", 16)
    assert (r.width, r.height) == (1, 1)


def test_printable_draws_ink_nonprintable_paints_class_tile():
    # 'A' (has ink) then NUL (control class tile), one row of 2 cells.
    r = render_text(b"A\x00", cols=2, colorize=True)
    a_cell = _cell(r, 0, 0, 8)
    nul_cell = _cell(r, 1, 0, 8)

    # 'A' cell: background plus light ink, but no class-colour fill.
    assert _DEFAULT_BG in a_cell
    assert len(a_cell) >= 2  # bg + at least one ink colour

    # NUL cell: a single solid colour, and it is NUL's byte-class colour.
    assert nul_cell == {_CLASS_COLORS[_byte_class(0x00)]}


def test_space_is_blank_not_a_tile():
    # space is printable (blank glyph) -> whole cell stays background.
    r = render_text(b" ", cols=1, colorize=True)
    assert _cell(r, 0, 0, 8) == {_DEFAULT_BG}


def test_mono_text_leaves_nonprintables_blank():
    r = render_text(b"\x00", cols=1, colorize=False)
    assert _cell(r, 0, 0, 8) == {_DEFAULT_BG}


def test_ratios_discriminate_text_from_binary():
    assert projections.printable_ratio(b"") == 0.0
    assert projections.printable_ratio(b"hello") == 1.0
    assert projections.text_ratio(b"a\tb\nc") == 1.0        # tab/LF count
    assert projections.printable_ratio(b"a\tb\nc") == 0.6   # tab/LF do not
    # NUL padding drags the ratio down
    assert projections.text_ratio(b"hi" + bytes(8)) == 0.2
