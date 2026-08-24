"""SVG render output (`render --format svg` / `-o *.svg`)."""

import xml.dom.minidom as minidom

from vizbin.canvas import Raster, to_svg
from vizbin.cli import main


def _raster(pixels):
    """pixels: list of (r,g,b) rows-major; returns a Raster of width=len(row)."""
    h = len(pixels)
    w = len(pixels[0])
    rgb = bytearray()
    for row in pixels:
        for (r, g, b) in row:
            rgb += bytes((r, g, b))
    return Raster(w, h, rgb)


def test_svg_is_valid_xml_with_viewbox():
    svg = to_svg(_raster([[(10, 20, 30), (40, 50, 60)]]))
    doc = minidom.parseString(svg)                 # raises on malformed XML
    root = doc.documentElement
    assert root.tagName == "svg"
    assert root.getAttribute("viewBox") == "0 0 2 1"
    assert root.getAttribute("shape-rendering") == "crispEdges"


def test_rle_collapses_solid_runs():
    red = (255, 0, 0)
    blue = (0, 0, 255)
    # a solid row -> one rect; an alternating row -> one rect per pixel
    solid = to_svg(_raster([[red, red, red, red]]))
    alt = to_svg(_raster([[red, blue, red, blue]]))
    assert solid.count("<rect") == 1
    assert alt.count("<rect") == 4


def test_rect_fill_matches_pixel():
    svg = to_svg(_raster([[(0x12, 0x34, 0x56)]]))
    assert 'fill="#123456"' in svg
    assert 'width="1" height="1"' in svg


def test_cli_format_svg(tmp_path, capsys):
    p = tmp_path / "in.bin"
    p.write_bytes(bytes(range(256)) * 4)
    out = tmp_path / "o.bmp"                        # extension overridden to .svg
    rc = main(["render", str(p), "-m", "byteclass", "-w", "32",
               "--format", "svg", "-o", str(out), "--no-hints"])
    assert rc == 0
    svg = tmp_path / "o.svg"
    assert svg.exists() and not out.exists()
    minidom.parse(str(svg))                         # valid XML
    assert "<rect" in svg.read_text()
    assert "o.svg" in capsys.readouterr().out


def test_cli_svg_by_extension(tmp_path):
    p = tmp_path / "in.bin"
    p.write_bytes(bytes(range(256)) * 4)
    out = tmp_path / "o.svg"                         # sniffed from extension
    assert main(["render", str(p), "-m", "gray", "-w", "32", "-o", str(out),
                 "--no-hints"]) == 0
    assert out.exists() and out.read_text().startswith("<svg")


def test_cli_default_is_still_bmp(tmp_path):
    p = tmp_path / "in.bin"
    p.write_bytes(bytes(range(256)) * 4)
    out = tmp_path / "o.bmp"
    assert main(["render", str(p), "-m", "gray", "-w", "32", "-o", str(out),
                 "--no-hints"]) == 0
    assert out.exists() and out.read_bytes()[:2] == b"BM"   # BMP magic


def test_contact_svg_by_extension(tmp_path):
    p = tmp_path / "in.bin"
    p.write_bytes(bytes(range(256)) * 8)
    out = tmp_path / "c.svg"
    assert main(["contact", str(p), "--modes", "gray,byteclass", "-w", "32",
                 "-o", str(out)]) == 0
    assert out.exists() and out.read_text().startswith("<svg")
    minidom.parse(str(out))


def test_diff_svg_by_extension(tmp_path):
    a = tmp_path / "a.bin"
    a.write_bytes(bytes(range(256)) * 4)
    b = tmp_path / "b.bin"
    b.write_bytes(bytes(range(256)) * 4 + b"tail")
    out = tmp_path / "d.svg"
    assert main(["diff", str(a), str(b), "-o", str(out), "-w", "32"]) == 0
    assert out.exists() and out.read_text().startswith("<svg")
    minidom.parse(str(out))
