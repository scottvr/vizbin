"""The transforms/colorizers split: every 1:1 mode is a composable pair.

This is the internal architecture the pipeline/overlay features build on; the
byte-identical guarantee itself lives in test_projection_golden.py.
"""

from vizbin import projections as P

_DATA = b"Hello\x00\xff world, the quick brown fox\n" * 4


def test_registries_are_populated():
    assert set(P.TRANSFORMS) >= {"identity", "xor", "delta", "bitplane", "class", "entropy"}
    assert set(P.COLORIZERS) >= {"gray", "magma", "palette", "nibble"}


def test_every_1to1_mode_names_valid_transform_and_colorizer():
    for name, proj in P.PROJECTIONS.items():
        if name == "raw-rgb":  # bespoke 3:1 packing, outside the model
            assert proj.transform is None and proj.colorizer is None
            continue
        assert proj.transform in P.TRANSFORMS, name
        assert proj.colorizer in P.COLORIZERS, name


def test_compose_reproduces_named_modes():
    # composing a mode's declared (transform, colorizer) by hand must match the
    # registered builder exactly, for every 1:1 mode and a couple of opts.
    opts = {"k": 3, "plane": 2, "window": 16}
    for name, proj in P.PROJECTIONS.items():
        if name == "raw-rgb":
            continue
        hand = P.compose(proj.transform, proj.colorizer)
        got_rgb, got_n = hand(_DATA, opts)
        ref_rgb, ref_n = proj.build(_DATA, opts)
        assert bytes(got_rgb) == bytes(ref_rgb), name
        assert got_n == ref_n == len(_DATA), name


def test_transforms_preserve_length():
    opts = {"k": 2, "plane": 5, "window": 8}
    for tname, tf in P.TRANSFORMS.items():
        assert len(tf(_DATA, opts)) == len(_DATA), tname
        assert tf(b"", opts) == b"", tname  # empty in, empty out
