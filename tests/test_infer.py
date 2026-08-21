"""Structure inference: stride detection + field segmentation."""

import random
import struct

import pytest

from vizbin import infer


def _records(n=200):
    """24-byte records: magic(4) + u32-le counter(4, full range) + reserved(4)
    + high-entropy blob(12)."""
    out = bytearray()
    for i in range(n):
        r = random.Random(i)  # genuine per-record entropy, deterministic
        blob = bytes(r.randrange(256) for _ in range(12))
        out += b"REC\x00" + struct.pack("<I", 1_000_000 + i * 7919) + bytes(4) + blob
    return bytes(out)


def _random(n_bytes=8192):
    r = random.Random(1234)
    return bytes(r.randrange(256) for _ in range(n_bytes))


# --- stride selection ------------------------------------------------------

def test_autodetects_record_stride():
    stride, why = infer.select_stride(_records())
    assert stride == 24, why


def test_autodetects_arbitrary_stride():
    # 22-byte records (not a "round" size) must still be found by autocorrelation
    data = bytearray()
    for i in range(500):
        data += b"LOG1" + struct.pack("<I", i) + bytes(14)
    stride, _ = infer.select_stride(bytes(data))
    assert stride == 22


def test_random_reports_no_structure():
    stride, why = infer.select_stride(_random())
    assert stride is None
    assert "no periodic" in why or "not enough" in why


def test_override_is_honored():
    stride, why = infer.select_stride(_records(), override=24)
    assert stride == 24
    assert "user-specified" in why


# --- field segmentation ----------------------------------------------------

def _by_offset(fields):
    return {f.offset: f for f in fields}


def test_detects_magic_counter_reserved_blob():
    data = _records()
    fields, n_rec = infer.infer_fields(data, 24)
    assert n_rec == 200
    fo = _by_offset(fields)
    assert fo[0].kind == "magic" and "REC" in fo[0].evidence
    assert fo[4].kind == "counter" and fo[4].size == 4
    assert fo[4].detail["endian"] == "little"
    assert fo[4].detail["first"] == 1_000_000
    assert fo[8].kind == "reserved"           # the zero padding
    assert any(f.kind == "blob" for f in fields)
    assert sum(f.size for f in fields) == 24   # full coverage


def test_counter_endianness_detected():
    data = bytearray()
    for i in range(200):
        data += b"MM" + struct.pack(">I", 1000 + i * 40000)  # big-endian
    fields, _ = infer.infer_fields(bytes(data), 6)
    ctr = next(f for f in fields if f.kind == "counter")
    assert ctr.detail["endian"] == "big"
    assert ctr.offset == 2 and ctr.size == 4


def test_no_false_counter_in_random():
    # random data, forced stride: nothing should read as a monotonic counter
    fields, _ = infer.infer_fields(_random(6400), 32)
    assert not any(f.kind == "counter" for f in fields)


def test_signed_sawtooth_is_not_a_counter():
    # a value that rises then wraps negative is not a counter (ends below start)
    data = bytearray()
    for i in range(300):
        data += b"VV" + struct.pack("<i", (i * 7) % 200 - 100)
    fields, _ = infer.infer_fields(bytes(data), 6)
    assert not any(f.kind == "counter" for f in fields)


def test_too_few_records_no_counter():
    # counters need enough records to be reliable
    assert infer._try_counter([bytes([1, 2, 3])] * 4, 0, 4, 3, "little") is None


# --- report ----------------------------------------------------------------

def test_report_renders():
    data = _records()
    stride, why = infer.select_stride(data)
    fields, n_rec = infer.infer_fields(data, stride)
    report = infer.format_report(data, stride, why, fields, n_rec)
    assert "counter" in report and "magic" in report
    assert "fields covering" in report
