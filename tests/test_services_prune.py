# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the v1.7 prune/collections/repair service methods."""
import struct
import zipfile

from rosu import config
from rosu.collections import OsuCollection, write_collection_db
from rosu.db import Database
from rosu.models import ParsedTrack
from rosu.services import Services


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def _svc(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    return cfg, db, Services(cfg, db, DummyLog())


def _make_set(cfg, db, bid, entries, checksum=None):
    fn = f"{bid} A - B.osz"
    path = cfg.library_path / fn
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    t = ParsedTrack(beatmapset_id=bid, filename=fn, artist="A", title="B",
                    display_name="A - B", size_bytes=path.stat().st_size)
    tid, _ = db.upsert_track(t, "when")
    db.set_library_state(tid, True, "present", "when")
    if checksum is not None:
        db._conn.execute(
            "INSERT INTO difficulties(track_id, filename, checksum) VALUES (?,?,?)",
            (tid, f"A - B [{bid}].osu", checksum))
        db._conn.commit()
    return tid


# -- prune_library / prune_library_plan ---------------------------------------
def test_prune_library_plan_lists_unpruned_only(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1, {"map.osu": b"x", "video.mp4": b"z" * 1000})
    tid2 = _make_set(cfg, db, 2, {"map.osu": b"x", "video.mp4": b"z" * 1000})
    db.set_pruned_state(tid2, True, 5000)   # already pruned -> excluded from the plan
    plan = svc.prune_library_plan()
    assert plan["count"] == 1
    assert plan["names"] == ["1 A - B.osz"]


def test_prune_library_only_counts_real_savings(tmp_path):
    # A set with nothing to prune (no video) must not be falsely marked pruned —
    # regression for the `freed_this >= 0` bug (every file counted as "pruned").
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1, {"map.osu": b"x", "audio.mp3": b"a" * 1000})
    res = svc.prune_library()
    assert res == {"pruned": 0, "freed_bytes": 0}
    row = db.find_track_row(1, "1 A - B.osz")
    assert row["is_pruned"] == 0


def test_prune_library_marks_real_prune(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1, {"map.osu": b"x", "video.mp4": b"z" * 5000})
    res = svc.prune_library()
    assert res["pruned"] == 1
    assert res["freed_bytes"] == 5000
    row = db.find_track_row(1, "1 A - B.osz")
    assert row["is_pruned"] == 1


def test_prune_library_respects_configured_mode(tmp_path):
    # Regression: prune_library used to always call prune_osz() with the
    # default mode, ignoring cfg.prune_mode entirely.
    cfg, db, svc = _svc(tmp_path)
    cfg.prune_mode = "heavy_assets"
    big_image = b"e" * (600 * 1024)   # only removed under heavy_assets mode
    _make_set(cfg, db, 1, {"map.osu": b"osu file format v14\n",
                          "audio.mp3": b"a" * 1000, "extra.png": big_image})
    res = svc.prune_library()
    assert res["pruned"] == 1
    assert res["freed_bytes"] == len(big_image)


# -- verify_library: pruned files must not read as "corruption" ---------------
def test_verify_library_excludes_pruned_from_mismatch(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    tid = _make_set(cfg, db, 1, {"map.osu": b"x", "audio.mp3": b"a" * 1000})
    db.set_pruned_state(tid, True, 12345)
    res = svc.verify_library()
    assert res["mismatch"] == 0
    assert res["pruned"] == 1


# -- collections: sync tags Library tracks from collection.db -----------------
def test_sync_collections_tags_matching_tracks(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    checksum = "d" * 32
    _make_set(cfg, db, 1, {"map.osu": b"x"}, checksum=checksum)
    coll_path = tmp_path / "collection.db"
    write_collection_db(coll_path, 1, [OsuCollection("Favorites", [checksum])])

    res = svc.sync_collections(coll_path)
    assert res == {"found": True, "collections": 1, "tagged": 1}
    row = db.find_track_row(1, "1 A - B.osz")
    assert "Collection:Favorites" in row["tags"].split()

    # Re-running must not double-tag or error.
    res2 = svc.sync_collections(coll_path)
    assert res2["tagged"] == 0
    row2 = db.find_track_row(1, "1 A - B.osz")
    assert row2["tags"].split().count("Collection:Favorites") == 1


def test_sync_collections_missing_file(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    res = svc.sync_collections(tmp_path / "missing.db")
    assert res == {"found": False}


def test_locate_stable_collection_db_none_when_not_installed(tmp_path, monkeypatch):
    from rosu import client_import
    cfg, db, svc = _svc(tmp_path)
    monkeypatch.setattr(client_import, "stable_install_dir", lambda: None)
    assert svc.locate_stable_collection_db() is None


# -- repair_maps: re-download via the mirror and clear the pruned flag --------
def test_repair_maps_success_clears_pruned_flag(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    tid = _make_set(cfg, db, 1, {"map.osu": b"x"})
    db.set_pruned_state(tid, True, 9999)

    monkeypatch.setattr("rosu.api_mirror.download_osz", lambda bid, dest, progress=None: True)
    res = svc.repair_maps(["1 A - B.osz"])
    assert res == {"repaired": 1, "failed": []}
    row = db.find_track_row(1, "1 A - B.osz")
    assert row["is_pruned"] == 0
    assert row["original_size"] is None


def test_repair_maps_download_failure_reported(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1, {"map.osu": b"x"})
    monkeypatch.setattr("rosu.api_mirror.download_osz", lambda bid, dest, progress=None: False)
    res = svc.repair_maps(["1 A - B.osz"])
    assert res == {"repaired": 0, "failed": ["1 A - B.osz"]}


def test_repair_maps_unknown_filename_fails(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    res = svc.repair_maps(["nonexistent.osz"])
    assert res == {"repaired": 0, "failed": ["nonexistent.osz"]}
