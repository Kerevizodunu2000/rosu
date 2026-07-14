# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the Drive chunk-bundling logic (real files in tmp_path)."""
import zipfile

import pytest

from rosu.drive import bundle


def test_chunk_name_and_parse():
    assert bundle.chunk_name(0, "devA") == "chunk-devA-0000.zip"
    assert bundle.chunk_name(42, "devA") == "chunk-devA-0042.zip"
    assert bundle.parse_chunk_index("chunk-devA-0042.zip") == 42
    assert bundle.parse_chunk_index("path/to/chunk-devA-0007.zip") == 7
    assert bundle.parse_chunk_index("chunk-0007.zip") == 7   # legacy name still parses
    assert bundle.parse_chunk_index("not-a-chunk.zip") is None


def test_next_chunk_index():
    assert bundle.next_chunk_index({}) == 0
    m = {"id:1": {"chunk": "chunk-devA-0000.zip"},
         "id:2": {"chunk": "chunk-devA-0003.zip"}}
    assert bundle.next_chunk_index(m) == 4


def test_plan_chunks_groups_under_cap():
    items = [{"size": 40}, {"size": 40}, {"size": 40}]
    chunks = bundle.plan_chunks(items, chunk_bytes=100, start_index=0, device_id="d")
    # 40+40 <= 100; the third would overflow -> new chunk
    assert [c["name"] for c in chunks] == ["chunk-d-0000.zip", "chunk-d-0001.zip"]
    assert len(chunks[0]["items"]) == 2 and len(chunks[1]["items"]) == 1


def test_plan_chunks_oversized_item_gets_own_chunk():
    items = [{"size": 500}, {"size": 10}]
    chunks = bundle.plan_chunks(items, chunk_bytes=100, start_index=5, device_id="d")
    assert chunks[0]["index"] == 5 and len(chunks[0]["items"]) == 1
    assert chunks[1]["index"] == 6 and chunks[1]["items"][0]["size"] == 10


def test_plan_chunks_rejects_bad_cap():
    with pytest.raises(ValueError):
        bundle.plan_chunks([{"size": 1}], chunk_bytes=0, start_index=0, device_id="d")


def test_sha256_file(tmp_path):
    import hashlib
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello world")
    assert bundle.sha256_file(p) == hashlib.sha256(b"hello world").hexdigest()


def test_write_chunk_atomic_and_stored(tmp_path):
    a = tmp_path / "a.osz"
    a.write_bytes(b"AAAA")
    b = tmp_path / "b.osz"
    b.write_bytes(b"BBBBBB")
    out = tmp_path / "chunk-0000.zip"
    bundle.write_chunk([a, b], out)
    assert out.exists()
    assert not (tmp_path / "chunk-0000.zip.part").exists()   # atomic, no leftover
    with zipfile.ZipFile(out) as z:
        assert sorted(z.namelist()) == ["a.osz", "b.osz"]    # flattened basenames
        assert all(i.compress_type == zipfile.ZIP_STORED for i in z.infolist())
        assert z.read("b.osz") == b"BBBBBB"
