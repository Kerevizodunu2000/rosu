# SPDX-License-Identifier: GPL-3.0-or-later
"""v1.0 DB fixes: relax legacy NOT NULL on packs, and the in_osu flag."""
import sqlite3

from rosu.db import Database
from rosu.models import ParsedTrack


def test_relax_packs_series_notnull_lets_local_pack_insert(tmp_path):
    # An OLD database where packs.series was declared NOT NULL — importing from an
    # installed osu! client (which stores a synthetic local pack with NULL
    # series/number/category) used to crash with an IntegrityError.
    dbfile = tmp_path / "old.db"
    con = sqlite3.connect(dbfile)
    con.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE packs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL, series TEXT NOT NULL, number INTEGER,
            category TEXT, full_name TEXT, title TEXT, mode TEXT, season TEXT,
            year INTEGER, track_count INTEGER DEFAULT 0, extracted_at TEXT,
            source_zip TEXT, status TEXT DEFAULT 'processed');
        CREATE TABLE tracks (id INTEGER PRIMARY KEY AUTOINCREMENT,
            beatmapset_id INTEGER UNIQUE, filename TEXT, artist TEXT,
            display_name TEXT, in_library INTEGER DEFAULT 0,
            in_drive INTEGER DEFAULT 0);
        CREATE TABLE track_sources (track_id INTEGER, pack_id INTEGER,
            subfolder TEXT, seen_at TEXT, UNIQUE(track_id, pack_id));
        INSERT INTO packs(code, series, number) VALUES('S1821', 'S', 1821);
    """)
    con.commit()
    con.close()

    db = Database(dbfile)          # runs the relax-notnull migration on open
    pid = db.get_or_create_local_pack("local_osu_lazer")   # NULL series — must work
    assert pid is not None
    row = db.get_pack_by_code("S1821")                     # existing data preserved
    assert row["series"] == "S" and row["number"] == 1821
    db.close()


def test_relax_is_idempotent_on_a_fresh_db(tmp_path):
    dbfile = tmp_path / "fresh.db"
    db = Database(dbfile)
    db.get_or_create_local_pack("local_osu_stable")
    db.close()
    db2 = Database(dbfile)          # re-open: migration is a no-op, data intact
    assert db2.get_pack_by_code("local_osu_stable") is not None
    db2.close()


def _track(db, bsid, name="A - B"):
    t = ParsedTrack(beatmapset_id=bsid, filename=f"{bsid} {name}.osz", artist="A",
                    title="B", display_name=name, size_bytes=1)
    tid, _new = db.upsert_track(t, "when")
    return tid


def test_set_pack_extra_records_count(tmp_path):
    db = Database(tmp_path / "m.db")
    db.get_or_create_local_pack("local_osu_lazer")
    db.set_pack_extra("local_osu_lazer", 7)
    assert db.get_pack_by_code("local_osu_lazer")["extra_count"] == 7
    db.close()


def test_mark_library_memory_flags_all_rows(tmp_path):
    db = Database(tmp_path / "m.db")
    for bsid in (1, 2):
        db.set_library_state(_track(db, bsid), True, "present", "t0")
    changed = db.mark_library_memory("t1")
    assert changed == 2
    assert db.library_tracks() == []           # nothing physically present anymore
    rows = db.library_records()                # ...but the memory survives
    assert {r["library_status"] for r in rows} == {"memory"}
    db.close()


def test_mode_set_counts_only_counts_library_sets(tmp_path):
    from rosu.models import DiffMeta
    db = Database(tmp_path / "m.db")
    in_lib = _track(db, 10)
    db.set_library_state(in_lib, True, "present", "t0")
    db.upsert_difficulties(in_lib, [
        DiffMeta(filename="a.osu", mode_int=3, mode="osu!mania", keycount=4),
        DiffMeta(filename="b.osu", mode_int=3, mode="osu!mania", keycount=7),
        DiffMeta(filename="c.osu", mode_int=0, mode="osu!"),
    ], {}, "t0")
    outside = _track(db, 20)                  # not in library — must not count
    db.upsert_difficulties(outside, [
        DiffMeta(filename="d.osu", mode_int=1, mode="osu!taiko"),
    ], {}, "t0")
    counts = db.mode_set_counts()
    assert counts == {"osu!mania": 1, "osu!": 1}   # one SET per mode, no taiko
    db.close()


def test_deleting_a_track_cascades_to_difficulties(tmp_path):
    from rosu.models import DiffMeta
    db = Database(tmp_path / "m.db")
    tid = _track(db, 30)
    db.upsert_difficulties(tid, [
        DiffMeta(filename="a.osu", mode_int=0, mode="osu!"),
    ], {}, "t0")
    assert db.difficulties_for_track(tid) != []
    with db._lock:                             # raw delete: exercise ON DELETE CASCADE
        db._conn.execute("DELETE FROM tracks WHERE id=?", (tid,))
        db._conn.commit()
    assert db.difficulties_for_track(tid) == []
    db.close()


def test_set_in_osu_flag(tmp_path):
    db = Database(tmp_path / "m.db")
    t = ParsedTrack(beatmapset_id=999, filename="999 A - B.osz", artist="A",
                    title="B", display_name="A - B", size_bytes=1)
    db.upsert_track(t, "when")
    db.set_in_osu(999, client="lazer")
    row = db.find_track_row(999, "")
    assert row["in_osu"] == 1 and row["in_osu_lazer"] == 1 and row["in_osu_stable"] == 0
    db.set_in_osu(999, client="stable")
    row = db.find_track_row(999, "")
    assert row["in_osu_stable"] == 1 and row["in_osu_lazer"] == 1   # both now
    db.set_in_osu(None)            # guarded no-op, must not raise
    db.close()
