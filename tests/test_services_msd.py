# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the whole-library skillset (MSD) scan (services.compute_msd, v1.6)."""
import zipfile

from rosu import config
from rosu.db import Database
from rosu.models import ParsedTrack
from rosu.services import Services


def _mania_osu(key=4, n=40, dt=125):
    """A mania .osu with an `n`-note stream (columns cycling → 'stream')."""
    head = (f"osu file format v14\n\n[General]\nMode: 3\n\n"
            f"[Metadata]\nTitle:T\nArtist:A\nVersion:{key}K\n\n"
            f"[Difficulty]\nCircleSize:{key}\n\n[TimingPoints]\n0,300,4,2,0,100,1,0\n\n"
            f"[HitObjects]\n")
    lines = []
    for i in range(n):
        col = i % key
        x = int((col + 0.5) * 512 / key)
        lines.append(f"{x},192,{1000 + i * dt},1,0,0:0:0:0:")
    return (head + "\n".join(lines) + "\n").encode("utf-8")


_STD_OSU = (b"osu file format v14\n\n[General]\nMode: 0\n\n"
            b"[Metadata]\nTitle:S\nArtist:A\nVersion:Hard\n\n"
            b"[Difficulty]\nCircleSize:4\n")


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


def _make_set(cfg, db, bid, body=None):
    fn = f"{bid} A - B.osz"
    path = cfg.library_path / fn
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"A - B [{bid}].osu", body if body is not None else _mania_osu())
    t = ParsedTrack(beatmapset_id=bid, filename=fn, artist="A", title="B",
                    display_name="A - B", size_bytes=path.stat().st_size)
    tid, _ = db.upsert_track(t, "when")
    db.set_library_state(tid, True, "present", "when")
    return tid


def _row(db, bid):
    return [r for r in db.all_tracks() if r["beatmapset_id"] == bid][0]


def test_compute_msd_scans_and_stores(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    for bid in (1, 2, 3):
        _make_set(cfg, db, bid)
    res = svc.compute_msd()
    assert res["scanned"] == 3 and res["rated"] == 3 and res["remaining"] == 0
    for bid in (1, 2, 3):
        assert _row(db, bid)["msd_scanned_at"] is not None
        radar = svc.mania_radar_for_track(_row(db, bid)["id"])
        assert radar is not None and radar["overall"] > 0
        assert radar["skills"]["stream"] > 0
    db.close()


def test_compute_msd_only_unscanned(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1)
    _make_set(cfg, db, 2)
    assert svc.compute_msd()["scanned"] == 2      # both fresh
    _make_set(cfg, db, 3)                          # a new set added afterwards
    res = svc.compute_msd()
    assert res["scanned"] == 1                     # only the new one is re-scanned
    db.close()


def test_compute_msd_non_mania_stamped_not_rated(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1, body=_STD_OSU)           # osu! set: no mania skillset
    res = svc.compute_msd()
    assert res["scanned"] == 1 and res["rated"] == 0
    assert _row(db, 1)["msd_scanned_at"] is not None   # stamped → never re-scanned
    assert svc.mania_radar_for_track(_row(db, 1)["id"]) is None
    db.close()


def test_compute_msd_cancel_mid_run(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    for bid in (1, 2, 3):
        _make_set(cfg, db, bid)
    real_apply = db.apply_msd

    def cancel_after_first(track_id, results, when):
        real_apply(track_id, results, when)
        svc._msd_cancel.set()

    monkeypatch.setattr(db, "apply_msd", cancel_after_first)
    res = svc.compute_msd()
    assert res["cancelled"] is True and res["scanned"] == 1
    db.close()


def test_msd_status_counts(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _make_set(cfg, db, 1)
    _make_set(cfg, db, 2)
    assert svc.msd_status() == {"in_library": 2, "unscanned": 2, "scanned": 0}
    svc.compute_msd()
    assert svc.msd_status() == {"in_library": 2, "unscanned": 0, "scanned": 2}
    db.close()
