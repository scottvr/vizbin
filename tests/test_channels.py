"""Channel composition (--rgb): drive R/G/B each by its own transform."""

import pytest

from vizbin import projections as P
from vizbin.cli import main
from vizbin.commands import _transform_value_at

_DATA = bytes(range(256)) * 2 + b"the quick brown fox jumps\n" * 5


def test_channels_are_the_transform_outputs():
    opts = {"k": 2, "window": 32}
    r = P.render_channels(["entropy", "delta", "xor"], _DATA, 32, **opts)
    er = bytes(P.TRANSFORMS["entropy"](_DATA, opts))
    dl = bytes(P.TRANSFORMS["delta"](_DATA, opts))
    xr = bytes(P.TRANSFORMS["xor"](_DATA, opts))
    # first pixel's R/G/B == first byte of each transform's output
    assert (r.rgb[0], r.rgb[1], r.rgb[2]) == (er[0], dl[0], xr[0])
    # a middle pixel too
    i = 100 * 3
    assert (r.rgb[i], r.rgb[i + 1], r.rgb[i + 2]) == (er[100], dl[100], xr[100])


def test_missing_channels_are_zero():
    r = P.render_channels(["xor"], _DATA, 32, k=1)
    xr = bytes(P.TRANSFORMS["xor"](_DATA, {"k": 1}))
    assert (r.rgb[0], r.rgb[1], r.rgb[2]) == (xr[0], 0, 0)


def test_dimensions_are_1to1():
    r = P.render_channels(["entropy", "delta"], _DATA, 32)
    ref = P.render("gray", _DATA, 32)
    assert (r.width, r.height) == (ref.width, ref.height)


def test_channel_names_accept_transforms_and_modes():
    # `byteclass` (mode) contributes its `class` transform
    a = P.render_channels(["class", "identity", "xor"], _DATA, 32)
    b = P.render_channels(["byteclass", "gray", "xor"], _DATA, 32)
    assert bytes(a.rgb) == bytes(b.rgb)


def test_too_many_channels_raises():
    with pytest.raises(ValueError):
        P.compose_channels(["a", "b", "c", "d"])


def test_empty_and_bad_channels_raise():
    with pytest.raises(ValueError):
        P.compose_channels([])
    with pytest.raises(KeyError):
        P.compose_channels(["nope"])
    with pytest.raises(ValueError):
        P.compose_channels(["raw-rgb"])  # not a transform


# --- inspect --rgb readout matches the rendered pixel (the symmetry) -------

def test_inspect_rgb_readout_matches_render():
    opts = {"k": 2, "window": 32}
    r = P.render_channels(["entropy", "delta", "xor"], _DATA, 64, **opts)
    # write _DATA to a file for the offset-based readout
    import tempfile
    import os
    fd, path = tempfile.mkstemp()
    try:
        os.write(fd, _DATA)
        os.close(fd)
        for off in (0, 1, 100, 260):
            i = off * 3
            vals = tuple(_transform_value_at(t, path, off, 0, opts)
                         for t in ["entropy", "delta", "xor"])
            assert vals == (r.rgb[i], r.rgb[i + 1], r.rgb[i + 2]), off
    finally:
        os.unlink(path)


def test_cli_render_and_inspect_rgb(tmp_path, capsys):
    p = tmp_path / "in.bin"
    p.write_bytes(_DATA)
    out = tmp_path / "o.bmp"
    assert main(["render", str(p), "--rgb", "entropy,delta,xor", "-w", "32",
                 "-o", str(out)]) == 0
    assert "[rgb entropy/delta/xor]" in capsys.readouterr().out
    assert out.exists()

    assert main(["inspect", str(p), "-w", "32", "--rgb", "entropy,delta,xor",
                 "--offset", "100"]) == 0
    o = capsys.readouterr().out
    assert "R(entropy)=" in o and "G(delta)=" in o and "B(xor)=" in o
