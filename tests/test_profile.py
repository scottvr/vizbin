"""Structural fingerprint (`profile`)."""

import json
import random

from vizbin import profile
from vizbin.cli import main


def _rand(n, seed=0):
    r = random.Random(seed)
    return bytes(r.randrange(256) for _ in range(n))


def test_entropy_and_classes():
    p = profile.build_profile(b"AAAA" * 1000, "x", detect_stride=False)
    assert p.entropy == 0.0                       # single symbol
    assert p.distinct_bytes == 1
    assert p.byte_classes["ascii"] == 1.0
    assert p.entropy >= 0.0                        # never -0.0


def test_random_is_high_entropy_compressed():
    p = profile.build_profile(_rand(16384), "x", detect_stride=False)
    assert p.entropy > 7.5
    assert p.regions[0].kind == "compressed"


def test_text_region():
    p = profile.build_profile(b"the quick brown fox jumps\n" * 500, "x", detect_stride=False)
    assert p.printable_ratio > 0.9
    assert all(r.kind == "text" for r in p.regions)


def test_heterogeneous_regions_segmented():
    data = (b"hello world text here\n" * 100        # text
            + bytes(4096)                            # sparse
            + _rand(6000, seed=3))                   # compressed
    p = profile.build_profile(data, "x", detect_stride=False)
    kinds = [r.kind for r in p.regions]
    assert "text" in kinds and "sparse" in kinds and "compressed" in kinds
    assert len(p.regions) >= 3
    assert any("heterogeneous" in note for note in p.notes)
    # regions tile the whole file with no gaps/overlaps
    assert p.regions[0].offset == 0
    assert sum(r.size for r in p.regions) == len(data)


def test_entropy_profile_is_fixed_length():
    for n in (500, 5000, 200000):
        p = profile.build_profile(_rand(n, seed=n), "x", detect_stride=False)
        assert len(p.entropy_profile) == 32       # stable feature-vector length


def test_head_hex_is_magic():
    p = profile.build_profile(b"\x89PNG\r\n\x1a\n" + _rand(4096), "x", detect_stride=False)
    assert p.head_hex.startswith("89504e470d0a1a0a")


def test_stride_detection_included():
    import struct
    data = b"".join(b"REC\x00" + struct.pack("<I", i) + bytes(4) for i in range(300))
    p = profile.build_profile(data, "x", detect_stride=True)
    assert p.record_stride == 12


def test_empty_file():
    p = profile.build_profile(b"", "x", detect_stride=True)
    assert p.size == 0 and p.record_stride is None


# --- CLI -------------------------------------------------------------------

def test_cli_json_is_valid_jsonl(tmp_path, capsys):
    a = tmp_path / "a.bin"
    a.write_bytes(_rand(4096, 1))
    b = tmp_path / "b.bin"
    b.write_bytes(b"text file\n" * 200)
    rc = main(["profile", str(a), str(b), "--json", "--no-stride"])
    assert rc == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert len(lines) == 2                          # one JSON object per file
    objs = [json.loads(ln) for ln in lines]
    assert objs[0]["size"] == 4096
    assert set(objs[0]) >= {"entropy", "byte_classes", "regions", "entropy_profile"}


def test_cli_human_report(tmp_path, capsys):
    p = tmp_path / "f.bin"
    p.write_bytes(b"hi\n" * 100 + bytes(2048) + _rand(3000, 2))
    assert main(["profile", str(p), "--no-stride"]) == 0
    out = capsys.readouterr().out
    assert "entropy" in out and "regions" in out


def test_cli_missing_file_returns_error(tmp_path, capsys):
    ok = tmp_path / "ok.bin"
    ok.write_bytes(_rand(1024))
    rc = main(["profile", str(ok), str(tmp_path / "nope.bin"), "--json", "--no-stride"])
    assert rc == 1                                  # one failed, but the other still ran
    assert capsys.readouterr().out.strip()          # ok.bin still produced output
