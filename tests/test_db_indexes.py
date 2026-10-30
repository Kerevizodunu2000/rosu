# SPDX-License-Identifier: GPL-3.0-or-later
"""The tracks.filename index: present on fresh and upgraded databases, and used."""
import sqlite3

from rosu.db import Database


def _filename_index(con):
    rows = con.execute("PRAGMA index_list(tracks)").fetchall()
    return {r[1]: r[2] for r in rows}.get("idx_tracks_filename")   # name -> unique


def test_fresh_db_has_plain_filename_index(tmp_path):
    db = Database(tmp_path / "x.db")
    with db._lock:
        assert _filename_index(db._conn) == 0
        cols = [r[2] for r in db._conn.execute(
            "PRAGMA index_info(idx_tracks_filename)").fetchall()]
    assert cols == ["filename"]
    db.close()


def test_upgraded_db_gets_index_and_keeps_duplicate_filenames(tmp_path):
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
        INSERT INTO tracks(beatmapset_id, filename) VALUES(1, 'same.osz');
        INSERT INTO tracks(beatmapset_id, filename) VALUES(2, 'same.osz');
        INSERT INTO tracks(beatmapset_id, filename) VALUES(3, 'other.osz');
    """)
    con.commit()
    assert _filename_index(con) is None
    con.close()

    db = Database(dbfile)          # adds the index on open
    with db._lock:
        assert _filename_index(db._conn) == 0
        rows = db._conn.execute(
            "SELECT beatmapset_id, filename FROM tracks ORDER BY beatmapset_id").fetchall()
    assert [tuple(r) for r in rows] == [(1, "same.osz"), (2, "same.osz"), (3, "other.osz")]
    db.close()


def test_find_track_row_filename_query_uses_index(tmp_path):
    db = Database(tmp_path / "x.db")
    with db._lock:
        details = [r[3] for r in db._conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM tracks WHERE filename=?", ("a.osz",))]
    db.close()
    assert any("USING INDEX idx_tracks_filename" in d for d in details), details
    assert not any(d.startswith("SCAN tracks") for d in details), details
