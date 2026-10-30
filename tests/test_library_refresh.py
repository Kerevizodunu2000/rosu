# SPDX-License-Identifier: GPL-3.0-or-later
"""Refresh Library: one bad set is skipped; a database failure still stops it."""
import sqlite3
import zipfile

import pytest

from rosu import config, library
from rosu.beatmap import parse_osu_sections
from rosu.db import Database
from rosu.logsvc import LogService
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


def _env(tmp_path, log=None):
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    return cfg, db, Services(cfg, db, log or LogService(tmp_path / "logs"))


def _osz(cfg, bid):
    fn = f"{bid} A - B.osz"
    with zipfile.ZipFile(cfg.library_path / fn, "w") as zf:
        zf.writestr(f"A - B [{bid}].osu", _OSU)
    return fn


def _fail_for(monkeypatch, bad_fn):
    real = library.read_osz_full

    def fake(path):
        if path.name == bad_fn:
            raise ValueError("boom " + str(path))
        return real(path)
    monkeypatch.setattr(library, "read_osz_full", fake)


def test_bad_set_is_skipped_and_progress_reported(tmp_path, monkeypatch):
    cfg, db, _ = _env(tmp_path)
    _osz(cfg, 1)
    bad = _osz(cfg, 2)
    _osz(cfg, 3)
    _fail_for(monkeypatch, bad)
    seen = []
    res = library.refresh_library(cfg.library_path, db, "now", seen.append)
    assert res["added"] == 2
    assert res["skipped"] == [{"file": bad, "error": "ValueError"}]
    assert len(seen) == 3


def test_skipped_set_on_disk_is_not_disappeared(tmp_path, monkeypatch):
    cfg, db, _ = _env(tmp_path)
    bad = _osz(cfg, 2)
    t = ParsedTrack(beatmapset_id=2, filename=bad, artist="A", title="B",
                    display_name="A - B", size_bytes=1)
    tid, _id = db.upsert_track(t, "when")
    db.set_library_state(tid, True, "present", "when")
    _fail_for(monkeypatch, bad)
    res = library.refresh_library(cfg.library_path, db, "now")
    assert res["skipped"] and res["disappeared"] == 0
    row = db.find_track_row(2, bad)
    assert row["library_status"] == "present"


def test_database_error_stops_refresh(tmp_path, monkeypatch):
    cfg, db, _ = _env(tmp_path)
    _osz(cfg, 1)

    def boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(db, "upsert_track", boom)
    with pytest.raises(sqlite3.DatabaseError):
        library.refresh_library(cfg.library_path, db, "now")


def test_service_logs_skip_without_path(tmp_path, monkeypatch):
    cfg, db, svc = _env(tmp_path)
    _osz(cfg, 1)
    bad = _osz(cfg, 2)
    _fail_for(monkeypatch, bad)
    res = svc.refresh()
    assert len(res["skipped"]) == 1
    text = svc.log._log_file().read_text(encoding="utf-8")
    skip = [ln for ln in text.splitlines() if "where=refresh:skip" in ln]
    assert len(skip) == 1 and "ERROR" in skip[0]
    assert bad in skip[0] and "ValueError" in skip[0]
    assert str(cfg.library_path) not in text
    assert any("REFRESH" in ln and "skipped=1" in ln for ln in text.splitlines())


def test_infinite_beat_length_gives_no_bpm():
    inf = "[TimingPoints]\n0,1e400,4,2,0,100,1,0\n"
    assert parse_osu_sections(inf)["bpm"] is None
    both = inf + "0,500,4,2,0,100,1,0\n"
    assert parse_osu_sections(both)["bpm"] == 120.0
