# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the whole-library star-rating scan (services.compute_ratings, v1.5).

The rosu-pp engine is stubbed so these run identically with or without the wheel;
what's under test is the scan orchestration (gating, ordering, storage, cancel).
"""
import zipfile

from rosu import config, ratings
from rosu.db import Database
from rosu.models import ParsedTrack
from rosu.services import Services

_OSU = b"""osu file format v14

[General]
Mode: 3

[Metadata]
Title:T
Artist:A
Version:4K

[Difficulty]
CircleSize:4
"""


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


def _make_library_set(cfg, db, bid):
    fn = f"{bid} A - B.osz"
    path = cfg.library_path / fn
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"A - B [{bid}].osu", _OSU)
    t = ParsedTrack(beatmapset_id=bid, filename=fn, artist="A", title="B",
                    display_name="A - B", size_bytes=path.stat().st_size)
    tid, _ = db.upsert_track(t, "when")
    db.set_library_state(tid, True, "present", "when")
    return tid


def test_compute_ratings_gated_without_engine(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    monkeypatch.setattr(ratings, "available", lambda: False)
    assert svc.compute_ratings() == {"error": "no_rosu_pp"}
    db.close()


def test_compute_ratings_scans_and_stores(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    for bid in (1, 2, 3):
        _make_library_set(cfg, db, bid)
    monkeypatch.setattr(ratings, "available", lambda: True)
    monkeypatch.setattr(ratings, "stars_for_diffs",
                        lambda diffs, raw, mods=0: {d.filename: 4.2 for d in diffs})
    res = svc.compute_ratings()
    assert res["scanned"] == 3 and res["rated"] == 3 and res["remaining"] == 0
    for r in db.all_tracks():
        assert r["star_max"] == 4.2
        assert r["diffs_scanned_at"] is not None
    db.close()


def test_compute_ratings_unscanned_first(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    tid1 = _make_library_set(cfg, db, 1)
    _make_library_set(cfg, db, 2)
    # set 1 was scanned earlier but got NO star (e.g. rosu-pp was absent then) —
    # so it's in the work pool, but AFTER the never-scanned set 2.
    from rosu.models import DiffMeta
    db.upsert_difficulties(tid1, [DiffMeta(filename="x.osu", keycount=4)],
                           {"x.osu": None}, "old")
    monkeypatch.setattr(ratings, "available", lambda: True)
    monkeypatch.setattr(ratings, "stars_for_diffs",
                        lambda diffs, raw, mods=0: {d.filename: 5.0 for d in diffs})
    res = svc.compute_ratings(max_files=1)   # only the FIRST (unscanned) set
    assert res["scanned"] == 1
    assert res["remaining"] == 1             # set 1 (missing-star) still queued
    # set 2 (never scanned) was rated first; set 1 not yet touched this run
    assert db.all_tracks() and _row(db, 2)["star_max"] == 5.0
    assert _row(db, 1)["star_max"] is None
    db.close()


def _row(db, bid):
    return [r for r in db.all_tracks() if r["beatmapset_id"] == bid][0]


def test_compute_ratings_missing_file_not_counted_as_remaining(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    _make_library_set(cfg, db, 1)
    _make_library_set(cfg, db, 2)
    (cfg.library_path / "2 A - B.osz").unlink()   # file vanished out-of-band
    monkeypatch.setattr(ratings, "available", lambda: True)
    monkeypatch.setattr(ratings, "stars_for_diffs",
                        lambda diffs, raw, mods=0: {d.filename: 4.0 for d in diffs})
    res = svc.compute_ratings()   # full run
    assert res["scanned"] == 1        # only the file that still exists
    assert res["remaining"] == 0      # full run ends at 0 despite the missing file
    db.close()


def test_compute_ratings_cancel_mid_run(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    for bid in (1, 2, 3):
        _make_library_set(cfg, db, bid)
    monkeypatch.setattr(ratings, "available", lambda: True)
    monkeypatch.setattr(ratings, "stars_for_diffs",
                        lambda diffs, raw, mods=0: {d.filename: 4.0 for d in diffs})
    real_upsert = db.upsert_difficulties

    def cancel_after_first(track_id, diffs, stars, when):
        real_upsert(track_id, diffs, stars, when)
        svc._ratings_cancel.set()   # stop before the next set

    monkeypatch.setattr(db, "upsert_difficulties", cancel_after_first)
    res = svc.compute_ratings()
    assert res["cancelled"] is True
    assert res["scanned"] == 1
    db.close()
