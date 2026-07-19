# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the per-difficulty table, star rollup, filter SQL and API
enrichment (v1.5 schema, rosu.db)."""
import tempfile
from pathlib import Path

from rosu import search
from rosu.db import Database
from rosu.models import DiffMeta, MsdResult, ParsedTrack
from rosu.query import Filter


def _db():
    return Database(Path(tempfile.mkdtemp()) / "m.db")


def _track(db, bid, name="Song", artist="Artist"):
    t = ParsedTrack(beatmapset_id=bid, filename=f"{bid} {artist} - {name}.osz",
                    artist=artist, title=name, display_name=f"{artist} - {name}")
    tid, _ = db.upsert_track(t, "when")
    return tid


def _diff(fn, keys=None, mode_int=3, checksum=None, version="v"):
    mode = {0: "osu!", 1: "osu!taiko", 2: "osu!catch", 3: "osu!mania"}[mode_int]
    return DiffMeta(filename=fn, version=version, mode_int=mode_int, mode=mode,
                    keycount=keys, cs=float(keys) if keys else None,
                    checksum=checksum)


def test_upsert_difficulties_writes_rows_and_rollup():
    db = _db()
    tid = _track(db, 1)
    diffs = [_diff("a.osu", keys=4), _diff("b.osu", keys=7)]
    db.upsert_difficulties(tid, diffs, {"a.osu": 2.5, "b.osu": 6.2}, "when")
    rows = db.difficulties_for_track(tid)
    assert [(r["keycount"], r["star_rating"], r["star_source"]) for r in rows] == [
        (4, 2.5, "rosu-pp"), (7, 6.2, "rosu-pp")]
    t = db.all_tracks()[0]
    assert t["star_min"] == 2.5 and t["star_max"] == 6.2
    assert t["diffs_scanned_at"] == "when"
    db.close()


def test_apply_msd_writes_skillset_and_stamps_track():
    db = _db()
    tid = _track(db, 1)
    db.upsert_difficulties(tid, [_diff("a.osu", keys=7)], {"a.osu": 5.0}, "when")
    res = MsdResult(overall=5.4, stream=4.1, jumpstream=3.0, handstream=2.0,
                    stamina=4.8, jackspeed=1.2, chordjack=0.5, technical=2.7)
    db.apply_msd(tid, {"a.osu": res}, "later")
    row = db.difficulties_for_track(tid)[0]
    assert row["msd_overall"] == 5.4 and row["msd_stream"] == 4.1
    assert row["msd_source"] == "rosu-heuristic-v1"
    assert db.all_tracks()[0]["msd_scanned_at"] == "later"
    db.close()


def test_apply_msd_stamps_even_with_no_results():
    db = _db()
    tid = _track(db, 1)
    db.apply_msd(tid, {}, "stamp")          # non-mania set: nothing to write
    assert db.all_tracks()[0]["msd_scanned_at"] == "stamp"
    db.close()


def test_mania_msd_for_pack_aggregation():
    db = _db()
    from rosu.models import ParsedPack
    pack_id = db.get_or_create_local_pack("TP1")
    for bid, ov in ((1, 5.0), (2, 7.0)):
        tid = _track(db, bid)
        db.upsert_difficulties(tid, [_diff("a.osu", keys=4)], {"a.osu": 4.0}, "w")
        db.add_track_source(tid, pack_id, None, "w")
        db.apply_msd(tid, {"a.osu": MsdResult(overall=ov, stream=ov)}, "w")
    rows = db.mania_msd_for_pack(pack_id)
    assert len(rows) == 2
    assert {round(r["msd_overall"], 1) for r in rows} == {5.0, 7.0}
    db.close()


def test_upsert_difficulties_reconciles_removed_diffs():
    db = _db()
    tid = _track(db, 1)
    db.upsert_difficulties(tid, [_diff("a.osu", keys=4), _diff("b.osu", keys=7)],
                           {"a.osu": 2.0, "b.osu": 6.0}, "w1")
    # a later re-parse where 'b.osu' is gone (map updated) drops that row
    db.upsert_difficulties(tid, [_diff("a.osu", keys=4)], {"a.osu": 2.0}, "w2")
    rows = db.difficulties_for_track(tid)
    assert [r["filename"] for r in rows] == ["a.osu"]
    assert db.all_tracks()[0]["star_max"] == 2.0
    db.close()


def test_upsert_difficulties_without_star_keeps_prior_star():
    db = _db()
    tid = _track(db, 1)
    db.upsert_difficulties(tid, [_diff("a.osu", keys=4)], {"a.osu": 3.3}, "w1")
    # re-parse with no fresh local star (e.g. rosu-pp uninstalled) must NOT wipe it
    db.upsert_difficulties(tid, [_diff("a.osu", keys=4)], {"a.osu": None}, "w2")
    assert db.difficulties_for_track(tid)[0]["star_rating"] == 3.3
    db.close()


def test_filter_exists_same_difficulty_semantics():
    db = _db()
    tid = _track(db, 1)     # a set with an easy 4K and a hard 7K
    db.upsert_difficulties(
        tid, [_diff("e.osu", keys=4), _diff("h.osu", keys=7)],
        {"e.osu": 2.5, "h.osu": 6.5}, "w")
    # star>5 AND key=7 must be satisfied by the SAME diff (the 7K is 6.5)
    assert len(db.filtered_tracks([Filter("star", ">", 5), Filter("key", "=", 7)])) == 1
    # star>5 AND key=4 must NOT match (the 4K is only 2.5)
    assert len(db.filtered_tracks([Filter("star", ">", 5), Filter("key", "=", 4)])) == 0
    db.close()


def test_mixed_track_and_diff_filters_param_order():
    """A track-level filter (bpm) AND a diff-level filter (star/key) must bind
    their parameters in the right SQL order — a mismatch silently returns wrong
    rows."""
    db = _db()
    for bid, name, bpm, star, keys in [
            (1, "Fast", 200.0, 6.5, 7), (2, "Slow", 120.0, 6.5, 7),
            (3, "FastEasy", 200.0, 2.0, 4)]:
        tid = _track(db, bid, name=name)
        db._conn.execute("UPDATE tracks SET bpm=? WHERE id=?", (bpm, tid))
        db._conn.commit()
        db.upsert_difficulties(tid, [_diff("d.osu", keys=keys)],
                               {"d.osu": star}, "w")
    rows = db.filtered_tracks([Filter("bpm", ">", 150.0),
                               Filter("star", ">", 5.0), Filter("key", "=", 7)])
    assert [r["display_name"] for r in rows] == ["Artist - Fast"]
    db.close()


def test_search_candidates_with_filters_and_free_text():
    db = _db()
    t1 = _track(db, 1, name="Ghost", artist="Camellia")
    _track(db, 2, name="Sunset", artist="Camellia")
    db.upsert_difficulties(t1, [_diff("h.osu", keys=7)], {"h.osu": 6.5}, "w")
    rows = db.search_candidates("Camellia", filters=[Filter("star", ">", 5)])
    assert [r["display_name"] for r in rows] == ["Camellia - Ghost"]
    db.close()


def test_text_contains_filters_and_attach_difficulties():
    db = _db()
    t1 = _track(db, 1, name="Ghost", artist="Camellia")
    _track(db, 2, name="Sunset", artist="Halozy")
    db.upsert_difficulties(t1, [_diff("a.osu", keys=4), _diff("b.osu", keys=7)],
                           {"a.osu": 2.5, "b.osu": 6.5}, "w")
    # artist= contains filter
    rows = db.filtered_tracks([Filter("artist", "contains", "camel")])
    assert [r["display_name"] for r in rows] == ["Camellia - Ghost"]
    # attach_difficulties_bulk exposes per-diff rows for the Star/Keys columns
    db.attach_difficulties_bulk(rows)
    stars = sorted(d["star_rating"] for d in rows[0]["difficulties"])
    assert stars == [2.5, 6.5]
    keys = sorted(d["keycount"] for d in rows[0]["difficulties"])
    assert keys == [4, 7]
    db.close()


def test_search_filters_only_does_not_crash_rank():
    """A filters-only query ('star>5') has zero free-text tokens; it must return
    filter-matched rows name-sorted, not crash rank() (which drops every row on
    an empty token list)."""
    db = _db()
    t1 = _track(db, 1, name="Ghost")
    _track(db, 2, name="Sunset")
    db.upsert_difficulties(t1, [_diff("h.osu", keys=7)], {"h.osu": 6.5}, "w")
    rows = search.search(db, "star>5")
    assert [r["display_name"] for r in rows] == ["Artist - Ghost"]
    # empty query still returns nothing (unchanged behaviour)
    assert search.search(db, "") == []
    db.close()


def test_apply_api_enrichment_sets_not_coalesce():
    db = _db()
    tid = _track(db, 42)
    db.apply_api_enrichment(42, {"status": "pending", "play_count": 100}, "t1")
    assert db.all_tracks()[0]["ranked_status"] == "pending"
    # a later run must OVERWRITE (live fields), not keep the first value
    db.apply_api_enrichment(42, {"status": "ranked", "play_count": 999}, "t2")
    row = db.all_tracks()[0]
    assert row["ranked_status"] == "ranked" and row["play_count"] == 999
    assert row["availability"] == "available"   # a successful fetch implies live
    db.close()


def test_apply_api_enrichment_fills_missing_star_by_checksum():
    db = _db()
    tid = _track(db, 7)
    db.upsert_difficulties(tid, [_diff("a.osu", keys=4, checksum="abc")],
                           {"a.osu": None}, "w")   # no local star
    db.apply_api_enrichment(7, {"beatmaps": [
        {"checksum": "abc", "difficulty_rating": 3.8, "version": "v", "mode_int": 3}]},
        "t")
    row = db.difficulties_for_track(tid)[0]
    assert row["star_rating"] == 3.8 and row["star_source"] == "api"
    db.close()


def test_apply_api_enrichment_never_overwrites_local_star():
    db = _db()
    tid = _track(db, 7)
    db.upsert_difficulties(tid, [_diff("a.osu", keys=4, checksum="abc")],
                           {"a.osu": 5.0}, "w")   # local rosu-pp star
    db.apply_api_enrichment(7, {"beatmaps": [
        {"checksum": "abc", "difficulty_rating": 9.9}]}, "t")
    row = db.difficulties_for_track(tid)[0]
    assert row["star_rating"] == 5.0 and row["star_source"] == "rosu-pp"
    db.close()
