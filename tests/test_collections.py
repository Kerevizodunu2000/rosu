# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the osu!(stable) collection.db binary parser (v1.7)."""
import io

import pytest

from rosu.collections import (
    OsuCollection, _read_osu_string, _read_uleb128, _write_osu_string,
    _write_uleb128, read_collection_db, write_collection_db,
)


# -- ULEB128 ------------------------------------------------------------------
@pytest.mark.parametrize("value", [0, 1, 127, 128, 300, 16384, 2_000_000])
def test_uleb128_round_trip(value):
    buf = io.BytesIO()
    _write_uleb128(buf, value)
    buf.seek(0)
    assert _read_uleb128(buf) == value


def test_uleb128_read_truncated_raises_eof():
    buf = io.BytesIO(b"")
    with pytest.raises(EOFError):
        _read_uleb128(buf)


def test_uleb128_rejects_unterminated_continuation_run():
    # A malicious/corrupt file with every continuation bit set and no
    # terminator must be refused quickly, not decoded into an ever-growing
    # int (memory/CPU exhaustion from a tiny file).
    buf = io.BytesIO(b"\xff" * 1000)
    with pytest.raises(ValueError):
        _read_uleb128(buf)


def test_osu_string_rejects_absurd_length_without_reading_it(monkeypatch):
    # A forged length prefix (~4.3 billion, well past any real collection name
    # or MD5) must be refused BEFORE the huge f.read(length) call — not after
    # a multi-GB allocation attempt from a file that's really just a few bytes.
    buf = io.BytesIO(b"\x0b" + b"\xff\xff\xff\xff\x0f")   # ULEB128 ~= 2**32

    real_read = buf.read

    def guarded_read(n=-1):
        if isinstance(n, int) and n > 10_000_000:
            raise AssertionError(f"f.read({n}) must never be called for an oversized length")
        return real_read(n)

    monkeypatch.setattr(buf, "read", guarded_read)
    with pytest.raises(ValueError, match="too long"):
        _read_osu_string(buf)


# -- osu! string format (0x00 empty / 0x0b ULEB-length-prefixed) --------------
@pytest.mark.parametrize("s", ["", "hello", "Collection Ünïcödé", "a" * 500])
def test_osu_string_round_trip(s):
    buf = io.BytesIO()
    _write_osu_string(buf, s)
    buf.seek(0)
    assert _read_osu_string(buf) == s


def test_osu_string_invalid_flag_raises():
    buf = io.BytesIO(b"\x99")
    with pytest.raises(ValueError):
        _read_osu_string(buf)


def test_osu_string_read_truncated_raises_eof():
    buf = io.BytesIO(b"")
    with pytest.raises(EOFError):
        _read_osu_string(buf)


# -- collection.db round trip --------------------------------------------------
def test_read_missing_file_returns_empty(tmp_path):
    version, cols = read_collection_db(tmp_path / "missing.db")
    assert version == 0
    assert cols == []


def test_write_then_read_round_trip(tmp_path):
    p = tmp_path / "collection.db"
    cols = [
        OsuCollection("Favorites", ["a" * 32, "b" * 32]),
        OsuCollection("Speed", []),
    ]
    write_collection_db(p, 20250101, cols)
    version, read_back = read_collection_db(p)
    assert version == 20250101
    assert [c.name for c in read_back] == ["Favorites", "Speed"]
    assert read_back[0].md5s == ["a" * 32, "b" * 32]
    assert read_back[1].md5s == []


def test_read_truncated_after_version_returns_empty(tmp_path):
    p = tmp_path / "collection.db"
    p.write_bytes((20250101).to_bytes(4, "little"))   # version only, no count
    version, cols = read_collection_db(p)
    assert version == 20250101
    assert cols == []
