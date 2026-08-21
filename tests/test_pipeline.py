"""Pipelines: chain modes' transforms, paint with the last mode's colorizer."""

import hashlib

import pytest

from vizbin import projections as P
from vizbin.cli import main

_DATA = bytes(range(256)) * 2 + b"the quick brown fox jumps\n" * 5


def _h(raster):
    return hashlib.sha256(bytes(raster.rgb)).hexdigest()


def test_single_mode_pipeline_equals_the_mode():
    for mode, opts in [("gray", {}), ("xor", {"k": 3}), ("entropy", {"window": 64}),
                       ("bitplane", {"plane": 2}), ("nibble", {})]:
        assert _h(P.render_pipeline([mode], _DATA, 32, **opts)) == \
            _h(P.render(mode, _DATA, 32, **opts)), mode


def test_transform_plus_gray_equals_the_gray_backed_mode():
    # delta = delta-transform + gray-colorizer, so `delta,gray` == `delta`
    assert _h(P.render_pipeline(["delta", "gray"], _DATA, 32)) == \
        _h(P.render("delta", _DATA, 32))


def test_order_matters():
    a = _h(P.render_pipeline(["xor", "entropy"], _DATA, 32, k=1, window=64))
    b = _h(P.render_pipeline(["entropy", "xor"], _DATA, 32, k=1, window=64))
    assert a != b


def test_pipeline_dimensions_match_1to1_render():
    r = P.render_pipeline(["xor", "delta"], _DATA, 32)
    ref = P.render("gray", _DATA, 32)  # any 1:1 mode: same pixel count -> same shape
    assert (r.width, r.height) == (ref.width, ref.height)


def test_raw_rgb_and_text_are_not_pipeable():
    with pytest.raises(ValueError):
        P.compose_pipeline(["xor", "raw-rgb"])
    with pytest.raises(ValueError):
        P.compose_pipeline(["text", "gray"])


def test_unknown_mode_in_pipeline_raises():
    with pytest.raises(KeyError):
        P.compose_pipeline(["xor", "nope"])


def test_empty_pipeline_raises():
    with pytest.raises(ValueError):
        P.compose_pipeline([])


def test_cli_render_pipe(tmp_path, capsys):
    p = tmp_path / "in.bin"
    p.write_bytes(_DATA)
    out = tmp_path / "o.bmp"
    rc = main(["render", str(p), "--pipe", "xor,entropy", "-w", "32", "-o", str(out)])
    assert rc == 0
    assert out.exists()
    assert "[pipe xor>entropy]" in capsys.readouterr().out


def test_cli_render_pipe_bad_mode_errors(tmp_path, capsys):
    p = tmp_path / "in.bin"
    p.write_bytes(_DATA)
    rc = main(["render", str(p), "--pipe", "xor,raw-rgb", "-w", "32",
               "-o", str(tmp_path / "o.bmp")])
    assert rc == 1
    assert "pipeline" in capsys.readouterr().err
