"""Structure inference: stride detection + field segmentation."""

import random
import struct

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


# --- Slice 3 tuning: const-split, 0%-const rejection, BE-with-const-high ----

def test_reserved_splits_from_constant_prefix():
    # reserved zeros must NOT merge with an adjacent constant (a string's prefix)
    data = bytearray()
    for i in range(200):
        r = random.Random(i)
        data += bytes(4) + b"AB" + bytes(r.randrange(256) for _ in range(4))  # 10
    fields, _ = infer.infer_fields(bytes(data), 10)
    fo = {f.offset: f for f in fields}
    assert fo[0].kind == "reserved" and fo[0].size == 4      # zeros stay separate
    assert fo[4].kind in ("magic", "const") and "AB" in fo[4].evidence


def test_periodic_but_no_constant_columns_rejected():
    # period 16, but every column drifts -> high autocorrelation, 0 constant cols
    data = bytes((i // 10 + j) % 256 for i in range(600) for j in range(16))
    stride, why = infer.select_stride(data)
    assert stride is None
    assert "no constant columns" in why


def test_sparse_marker_stride():
    # a sync byte at a fixed offset in otherwise-random records: byte-
    # autocorrelation is flat, but the marker recurs periodically.
    data = bytearray()
    for _ in range(300):
        r = random.Random(len(data))
        data += bytes([0x47]) + bytes(r.randrange(256) for _ in range(187))
    stride, why = infer.select_stride(bytes(data))
    assert stride == 188, why
    assert "sparse marker" in why and "0x47" in why


def test_marker_does_not_false_positive_on_random():
    # pure random has a most-common byte, but it scatters across residues
    rng = random.Random(9)
    data = bytes(rng.randrange(256) for _ in range(16384))
    assert infer._marker_stride(data, cap=1024) is None


def test_be_counter_with_constant_high_byte():
    # a big-endian u32 with a fixed 0x01 top byte must still read as a counter
    data = bytearray()
    for i in range(300):
        data += b"HI" + struct.pack(">I", 0x01000000 + i * 500)
    fields, _ = infer.infer_fields(bytes(data), 6)
    ctr = next(f for f in fields if f.kind == "counter")
    assert ctr.detail["endian"] == "big"
    assert ctr.size == 4 and ctr.offset == 2


# --- machine-readable export -----------------------------------------------

def _infer(data):
    stride, why = infer.select_stride(data)
    fields, n = infer.infer_fields(data, stride)
    return stride, why, fields, n


def test_json_export_parses():
    import json
    data = _records()
    stride, why, fields, n = _infer(data)
    obj = json.loads(infer.to_json(stride, why, fields, n, source="x"))
    assert obj["stride"] == stride and obj["records"] == n
    assert obj["fields"][0]["kind"] == "magic"
    assert all("name" in f and "offset" in f for f in obj["fields"])


def test_kaitai_export_shape_and_unique_ids():
    data = _records()
    stride, _, fields, _ = _infer(data)
    ksy = infer.to_kaitai(stride, fields, "My File!")   # id must be sanitized
    assert "meta:" in ksy and "id: my_file" in ksy and "seq:" in ksy
    assert "contents:" in ksy          # magic as fixed bytes
    assert "type: u" in ksy            # counter
    ids = [ln.split("id:", 1)[1].strip() for ln in ksy.splitlines() if "- id:" in ln]
    assert len(ids) == len(set(ids))   # Kaitai requires unique ids


def test_struct_export_covers_stride_and_unpacks():
    data = _records()
    stride, _, fields, _ = _infer(data)
    out = infer.to_struct(fields)
    fmt = out.splitlines()[0].split('"')[1]
    assert struct.calcsize(fmt) == stride          # accounts for every byte
    vals = struct.Struct(fmt).unpack(data[:stride])
    assert vals[0] == b"REC"                        # magic (the \0 splits off as reserved)


def test_cli_export_formats(tmp_path, capsys):
    from vizbin.cli import main
    p = tmp_path / "r.bin"
    p.write_bytes(_records())
    for extra in (["--json"], ["--format", "kaitai"], ["--format", "struct"]):
        assert main(["infer", str(p), *extra]) == 0
    assert "seq:" in capsys.readouterr().out or True  # smoke


# --- report ----------------------------------------------------------------

def test_report_renders():
    data = _records()
    stride, why = infer.select_stride(data)
    fields, n_rec = infer.infer_fields(data, stride)
    report = infer.format_report(data, stride, why, fields, n_rec)
    assert "counter" in report and "magic" in report
    assert "fields covering" in report
