"""Golden guard: projection outputs must stay byte-identical across the
transforms/colorizers refactor. Hashes captured on the pre-refactor code.
"""

import hashlib

from vizbin import projections as P

_DATA = bytes(range(256)) * 2 + b"the quick brown fox jumps\n" * 5

# (mode, opts, sha256(rgb)[:16], width, height)
GOLDEN = [
    ("gray", {}, "2cbf7d349c6084a7", 32, 21),
    ("byteclass", {}, "92cec00a430187ec", 32, 21),
    ("nibble", {}, "9b814350dbd01185", 32, 21),
    ("delta", {}, "b802ecddd9a8f501", 32, 21),
    ("xor", {"k": 3}, "4b8f1e6fce3d33ab", 32, 21),
    ("bitplane", {"plane": 3}, "c892c62789582588", 32, 21),
    ("entropy", {"window": 64}, "98c453b5e27b5a1e", 32, 21),
    ("raw-rgb", {"phase": 1}, "d185749231d8f7f0", 32, 7),
]


def test_projection_outputs_are_byte_identical():
    for mode, opts, digest, w, h in GOLDEN:
        r = P.render(mode, _DATA, 32, **opts)
        assert (r.width, r.height) == (w, h), mode
        assert hashlib.sha256(bytes(r.rgb)).hexdigest()[:16] == digest, mode
