# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the Drive manifest logic (pure — no network/keyring)."""
from rosu.drive import manifest


def test_make_key_prefixes_and_nullable_id():
    assert manifest.make_key(123, "a.osz") == "id:123"
    assert manifest.make_key(None, "a.osz") == "name:a.osz"
    # a numeric filename can never collide with a numeric beatmapset id
    assert manifest.make_key(None, "123") != manifest.make_key(123, "x")


def test_shard_round_trip_atomic(tmp_path):
    p = tmp_path / manifest.shard_name("dev1")
    entries = {"id:1": {"chunk": "chunk-0000.zip", "name": "a.osz",
                        "size": 10, "hash": "h", "beatmapset_id": 1,
                        "metadata": {"artist": "X"}}}
    manifest.save_shard(p, "dev1", entries)
    assert p.exists()
    assert not (tmp_path / (p.name + ".part")).exists()   # temp cleaned up
    assert manifest.load_shard(p) == entries


def test_load_shard_missing_or_corrupt(tmp_path):
    assert manifest.load_shard(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert manifest.load_shard(bad) == {}


def test_merge_shards_union():
    a = {"id:1": {"chunk": "chunk-0000.zip"}}
    b = {"id:2": {"chunk": "chunk-0001.zip"}}
    merged = manifest.merge_shards([a, b])
    assert set(merged) == {"id:1", "id:2"}


def test_diff_to_upload_by_key():
    local = [
        {"beatmapset_id": 1, "filename": "one.osz"},
        {"beatmapset_id": None, "filename": "noid.osz"},
        {"beatmapset_id": 2, "filename": "two.osz"},
    ]
    manifest_map = {"id:1": {"chunk": "chunk-0000.zip"}}   # only #1 already up
    todo = manifest.diff_to_upload(local, manifest_map)
    keys = {manifest.track_key(t) for t in todo}
    assert keys == {"name:noid.osz", "id:2"}


def test_entry_from_track_snapshots_metadata():
    track = {"beatmapset_id": 7, "filename": "s.osz", "artist": "A",
             "title": "T", "display_name": "A - T", "bpm": 180.0,
             "diff_count": 3, "creator": "M"}
    e = manifest.entry_from_track(track, "chunk-0001.zip", 999, "deadbeef")
    assert e["chunk"] == "chunk-0001.zip" and e["size"] == 999
    assert e["hash"] == "deadbeef" and e["beatmapset_id"] == 7
    assert e["metadata"]["artist"] == "A" and e["metadata"]["bpm"] == 180.0
    assert e["metadata"]["diff_count"] == 3


def test_diff_reuploads_on_size_change():
    local = [{"beatmapset_id": 1, "filename": "a.osz", "size": 200}]
    changed = {"id:1": {"chunk": "chunk-x-0000.zip", "size": 100}}
    assert manifest.diff_to_upload(local, changed) == local   # size differs -> re-upload
    same = {"id:1": {"chunk": "chunk-x-0000.zip", "size": 200}}
    assert manifest.diff_to_upload(local, same) == []         # unchanged -> skip
