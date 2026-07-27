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


# -- v1.7.1: source picker, scan preview and apply dispatch --------------------
def test_prune_sources_always_reports_lazer_as_unavailable(tmp_path):
    """Not a preference: lazer shares one content-addressed copy of an asset
    between every set that contains it, so deleting files would break other sets
    and leave client.realm pointing at nothing."""
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1, {"map.osu": b"x", "video.mp4": b"z" * 1000})
    by_key = {s["key"]: s for s in svc.prune_sources()}
    assert set(by_key) == {"library", "stable", "lazer"}
    assert by_key["library"]["available"] and by_key["library"]["sets"] == 1
    assert by_key["lazer"]["available"] is False
    assert by_key["lazer"]["reason"] == "lazer_realm"
    db.close()


def test_prune_scan_lists_only_sets_with_something_to_remove(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1, {"map.osu": b"x", "video.mp4": b"z" * 4000})
    _make_set(cfg, db, 2, {"map.osu": b"x", "audio.mp3": b"a" * 4000})  # nothing
    res = svc.prune_scan("library", "video_only")
    assert res["scanned"] == 2
    assert [s["key"] for s in res["sets"]] == ["1 A - B.osz"]
    assert res["sets"][0]["freed"] == 4000
    assert res["freed_bytes"] == 4000
    assert res["total_bytes"] > 0
    db.close()


def test_prune_scan_excludes_already_pruned_sets(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    tid = _make_set(cfg, db, 1, {"map.osu": b"x", "video.mp4": b"z" * 4000})
    db.set_pruned_state(tid, True, 5000)
    assert svc.prune_scan("library", "video_only")["sets"] == []
    db.close()


def test_prune_scan_reports_nothing_when_the_mode_matches_nothing(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1, {"map.osu": b"x", "video.mp4": b"z" * 4000})
    res = svc.prune_scan("library", "images_only")   # no images in this set
    assert res["sets"] == [] and res["freed_bytes"] == 0
    db.close()


def test_prune_scan_is_read_only(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1, {"map.osu": b"x", "video.mp4": b"z" * 4000})
    p = cfg.library_path / "1 A - B.osz"
    before = p.read_bytes()
    svc.prune_scan("library", "video_only")
    assert p.read_bytes() == before
    assert db.all_tracks()[0]["is_pruned"] == 0
    db.close()


def test_prune_apply_library_prunes_only_the_named_sets(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1, {"map.osu": b"x", "video.mp4": b"z" * 4000})
    _make_set(cfg, db, 2, {"map.osu": b"x", "video.mp4": b"z" * 4000})
    untouched = (cfg.library_path / "2 A - B.osz").read_bytes()
    res = svc.prune_apply("library", "video_only", ["1 A - B.osz"])
    assert res["pruned"] == 1 and res["freed_bytes"] == 4000
    assert (cfg.library_path / "2 A - B.osz").read_bytes() == untouched
    flags = {r["filename"]: r["is_pruned"] for r in db.all_tracks()}
    assert flags == {"1 A - B.osz": 1, "2 A - B.osz": 0}
    db.close()


def test_prune_apply_honours_the_chosen_mode_over_settings(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    cfg.prune_mode = "video_only"        # Settings says video…
    _make_set(cfg, db, 1, {"map.osu": b"x", "bg.jpg": b"b" * 3000,
                           "video.mp4": b"z" * 4000})
    res = svc.prune_apply("library", "images_only", ["1 A - B.osz"])  # …dialog says images
    assert res["freed_bytes"] == 3000    # the image, not the video
    with zipfile.ZipFile(cfg.library_path / "1 A - B.osz") as zf:
        assert "video.mp4" in zf.namelist()
    db.close()


def test_prune_apply_refuses_lazer_loudly(tmp_path):
    """Unreachable from the UI (the source is offered disabled), but it must fail
    visibly rather than silently doing nothing if it ever is."""
    cfg, db, svc = _svc(tmp_path)
    assert svc.prune_apply("lazer", "video_only", ["x"]) == {
        "pruned": 0, "freed_bytes": 0, "error": "lazer_realm"}
    db.close()


def test_prune_apply_stable_without_an_install_reports_it(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    monkeypatch.setattr("rosu.client_import.stable_songs_dir", lambda: None)
    assert svc.prune_apply("stable", "video_only", ["x"])["error"] == "no_stable"
    db.close()


def test_prune_scan_stable_walks_the_songs_folders(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    songs = tmp_path / "Songs"
    (songs / "1 A - B").mkdir(parents=True)
    (songs / "1 A - B" / "map.osu").write_bytes(b"osu file format v14\n")
    (songs / "1 A - B" / "video.mp4").write_bytes(b"v" * 6000)
    (songs / "2 C - D").mkdir(parents=True)
    (songs / "2 C - D" / "map.osu").write_bytes(b"osu file format v14\n")
    monkeypatch.setattr("rosu.client_import.stable_songs_dir", lambda: songs)
    res = svc.prune_scan("stable", "video_only")
    assert res["scanned"] == 2
    assert [s["key"] for s in res["sets"]] == ["1 A - B"]
    assert res["sets"][0]["freed"] == 6000

    trashed = []
    monkeypatch.setattr("send2trash.send2trash",
                        lambda p: (trashed.append(str(p)), __import__("os").remove(p)))
    applied = svc.prune_apply("stable", "video_only", ["1 A - B"])
    assert applied == {"pruned": 1, "freed_bytes": 6000}
    assert (songs / "1 A - B" / "map.osu").exists()      # never the beatmap
    assert len(trashed) == 1
    db.close()


def test_prune_records_when_and_with_which_mode(tmp_path):
    """"Which of my maps lost their video, and how?" must be answerable from the
    data, not only from the log file."""
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1, {"map.osu": b"x", "video.mp4": b"z" * 4000})
    svc.prune_apply("library", "video_only", ["1 A - B.osz"])
    row = db.all_tracks()[0]
    assert row["is_pruned"] == 1
    assert row["prune_mode"] == "video_only"
    assert row["pruned_at"]                       # timestamped
    assert row["original_size"] > 0
    assert db.pruned_filenames() == ["1 A - B.osz"]
    db.close()


def test_restoring_a_map_clears_its_prune_record(tmp_path, monkeypatch):
    """A restored set must carry no stale prune record — otherwise it keeps
    claiming to be pruned and shows up in the next bulk restore."""
    cfg, db, svc = _svc(tmp_path)
    tid = _make_set(cfg, db, 7, {"map.osu": b"x", "video.mp4": b"z" * 4000})
    db.set_pruned_state(tid, True, 9999, when="2026-07-27T00:00:00",
                        mode="video_only")
    assert db.pruned_filenames() == ["7 A - B.osz"]
    monkeypatch.setattr("rosu.api_mirror.download_osz", lambda bid, dest: True)
    res = svc.repair_maps(["7 A - B.osz"])
    assert res["repaired"] == 1
    row = db.all_tracks()[0]
    assert row["is_pruned"] == 0
    assert row["prune_mode"] is None and row["pruned_at"] is None
    assert db.pruned_filenames() == []
    db.close()


def test_pruned_count_feeds_the_restore_flow(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    assert svc.pruned_count() == 0
    tid = _make_set(cfg, db, 1, {"map.osu": b"x"})
    db.set_pruned_state(tid, True, 100)
    assert svc.pruned_count() == 1
    db.close()
