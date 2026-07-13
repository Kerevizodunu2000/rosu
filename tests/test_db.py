# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the search/browse DB helpers rewritten for perf (item 10/11)."""
from rosu.db import Database


def _mk(tmp_path):
    db = Database(tmp_path / "t.db")
    c = db._conn
    c.execute("INSERT INTO packs(id, code, full_name) VALUES(1,'S1','osu Pack S1')")
    c.execute("INSERT INTO packs(id, code, full_name) VALUES(2,'S2','osu Pack S2')")
    c.execute("INSERT INTO tracks(id, beatmapset_id, display_name, artist, title, tags) "
              "VALUES(10, 111, 'Hatsune Miku - A', 'Hatsune Miku', 'A', 'vocaloid')")
    c.execute("INSERT INTO tracks(id, beatmapset_id, display_name, artist, title, tags) "
              "VALUES(11, 222, 'Camellia - Hardcore', 'Camellia', 'Hardcore', 'hardcore')")
    c.execute("INSERT INTO track_sources(track_id, pack_id, subfolder, seen_at) "
              "VALUES(10,1,NULL,'t')")
    c.execute("INSERT INTO track_sources(track_id, pack_id, subfolder, seen_at) "
              "VALUES(10,2,'osu!mania','t')")
    c.execute("INSERT INTO track_sources(track_id, pack_id, subfolder, seen_at) "
              "VALUES(11,1,NULL,'t')")
    c.commit()
    return db


def test_all_tracks_name_sorted(tmp_path):
    db = _mk(tmp_path)
    rows = db.all_tracks()
    assert [r["display_name"] for r in rows] == ["Camellia - Hardcore", "Hatsune Miku - A"]
    db.close()


def test_search_candidates_returns_raw_rows_without_sources(tmp_path):
    db = _mk(tmp_path)
    rows = db.search_candidates("miku")
    assert len(rows) == 1
    assert "sources" not in rows[0]          # no N+1 attach here anymore
    db.close()


def test_attach_sources_bulk(tmp_path):
    db = _mk(tmp_path)
    rows = db.all_tracks()
    db.attach_sources_bulk(rows)
    by_id = {r["beatmapset_id"]: r for r in rows}
    assert by_id[111]["sources"] == ["S1", "S2/osu!mania"]     # ordered by pack code
    assert by_id[111]["source_full"] == ["osu Pack S1", "osu Pack S2"]
    assert by_id[222]["sources"] == ["S1"]
    db.close()


def test_attach_sources_bulk_handles_empty(tmp_path):
    db = _mk(tmp_path)
    db.attach_sources_bulk([])   # must not raise
    db.close()


def test_artists_ranked_by_length_and_bpm(tmp_path):
    db = Database(tmp_path / "a.db")
    c = db._conn
    # X: two tracks, avg length 100, avg bpm 120; Y: one track length 200, bpm 200
    c.execute("INSERT INTO tracks(beatmapset_id, artist, length_seconds, bpm) VALUES(1,'X',50,120)")
    c.execute("INSERT INTO tracks(beatmapset_id, artist, length_seconds, bpm) VALUES(2,'X',150,120)")
    c.execute("INSERT INTO tracks(beatmapset_id, artist, length_seconds, bpm) VALUES(3,'Y',200,200)")
    c.commit()
    assert [a["artist"] for a in db.artists_ranked("avg_length", True)] == ["Y", "X"]
    assert [a["artist"] for a in db.artists_ranked("avg_length", False)] == ["X", "Y"]
    assert db.artists_ranked("avg_bpm", True)[0]["artist"] == "Y"
    assert db.artists_ranked("count", True)[0]["artist"] == "X"   # X has 2 songs
    db.close()


def test_artists_ranked_nulls_sort_last(tmp_path):
    db = Database(tmp_path / "n.db")
    c = db._conn
    c.execute("INSERT INTO tracks(beatmapset_id, artist, length_seconds) VALUES(1,'HasLen',120)")
    c.execute("INSERT INTO tracks(beatmapset_id, artist, length_seconds) VALUES(2,'NoLen',NULL)")
    c.commit()
    # ascending by avg_length: the artist with data comes first, NULL last
    assert [a["artist"] for a in db.artists_ranked("avg_length", False)] == ["HasLen", "NoLen"]
    db.close()
