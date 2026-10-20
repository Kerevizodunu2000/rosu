# SPDX-License-Identifier: GPL-3.0-or-later
"""v1.7.1: the search result cap and the star histogram's data source.

Two owner-reported bugs are pinned here:

* a query matching 1600 sets listed exactly 500 of them and said nothing about
  it — ``services.search`` never passed a limit, so every query inherited
  ``rosu.search.search``'s 500 default;
* the histogram claimed to show the library's distribution while binning the
  current (already-capped) result page, and binned each set's ``star_max`` even
  though clicking a bar searches ``star>=lo star<hi``, which matches *any*
  difficulty.
"""
import tempfile
from pathlib import Path

from rosu import config, search
from rosu.db import Database
from rosu.models import DiffMeta, ParsedTrack
from rosu.query import Filter
from rosu.services import Services


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def _db():
    return Database(Path(tempfile.mkdtemp()) / "m.db")


def _svc(tmp_path):
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    return db, Services(cfg, db, DummyLog())


def _track(db, bid, name="Song", artist="Artist", in_library=True):
    t = ParsedTrack(beatmapset_id=bid, filename=f"{bid} {artist} - {name}.osz",
                    artist=artist, title=name, display_name=f"{artist} - {name}")
    tid, _ = db.upsert_track(t, "when")
    if in_library:
        db.set_library_state(tid, True, "present", "when")
    return tid


def _diff(fn, mode_int=3, keys=4):
    mode = {0: "osu!", 1: "osu!taiko", 2: "osu!catch", 3: "osu!mania"}[mode_int]
    return DiffMeta(filename=fn, version="v", mode_int=mode_int, mode=mode,
                    keycount=keys)


def _seed(db, n, *, star=6.0, first_bid=1):
    for i in range(first_bid, first_bid + n):
        tid = _track(db, i, name=f"Song{i}")
        db.upsert_difficulties(tid, [_diff("a.osu")], {"a.osu": star}, "when")


# -- 2.1 the 500 cap ---------------------------------------------------------
def test_filters_only_query_is_not_capped_at_500():
    db = _db()
    _seed(db, 620)
    rows = search.search(db, "star>5")
    assert len(rows) == 620, "the old 500 default silently truncated the answer"
    db.close()


def test_search_counted_reports_the_untruncated_total():
    db = _db()
    _seed(db, 30)
    rows, total = search.search_counted(db, "star>5", limit=10)
    assert len(rows) == 10 and total == 30
    db.close()


def test_free_text_search_counted_reports_total():
    db = _db()
    _seed(db, 25, star=6.0)
    rows, total = search.search_counted(db, "Song", limit=5)
    assert len(rows) == 5 and total == 25
    db.close()


def test_count_filtered_tracks_matches_the_rows():
    db = _db()
    _seed(db, 12, star=6.0)
    _seed(db, 8, star=2.0, first_bid=1000)
    assert db.count_filtered_tracks([Filter("star", ">", 5)]) == 12
    assert db.count_filtered_tracks([]) == 20     # no filters = every track
    db.close()


def test_service_search_page_flags_truncation(tmp_path):
    db, svc = _svc(tmp_path)
    _seed(db, 40)
    page = svc.search_page("star>5", limit=15)
    assert len(page["rows"]) == 15
    assert page["total"] == 40 and page["truncated"] is True
    full = svc.search_page("star>5")
    assert len(full["rows"]) == 40 and full["truncated"] is False
    db.close()


def test_service_search_page_browse_is_not_capped_at_500(tmp_path):
    """The empty box (browse) path — it already used 5000, keep it that way."""
    db, svc = _svc(tmp_path)
    _seed(db, 620)
    page = svc.search_page("")
    assert len(page["rows"]) == 620 and page["truncated"] is False
    db.close()


# -- 2.2 / 2.3 the histogram's source and unit -------------------------------
def test_difficulty_stars_returns_one_value_per_difficulty():
    db = _db()
    tid = _track(db, 1)
    db.upsert_difficulties(tid, [_diff("a.osu"), _diff("b.osu"), _diff("c.osu")],
                           {"a.osu": 2.0, "b.osu": 5.0, "c.osu": None}, "when")
    pairs = db.difficulty_stars()
    assert sorted(s for _t, s in pairs) == [2.0, 5.0]   # unrated diff excluded
    assert {t for t, _s in pairs} == {tid}
    db.close()


def test_difficulty_stars_library_scope_excludes_non_library_sets():
    db = _db()
    inlib = _track(db, 1, name="In")
    out = _track(db, 2, name="Out", in_library=False)
    db.upsert_difficulties(inlib, [_diff("a.osu")], {"a.osu": 4.0}, "when")
    db.upsert_difficulties(out, [_diff("b.osu")], {"b.osu": 9.0}, "when")
    assert [s for _t, s in db.difficulty_stars("library")] == [4.0]
    assert sorted(s for _t, s in db.difficulty_stars("all")) == [4.0, 9.0]
    db.close()


def test_histogram_counts_difficulties_not_sets(tmp_path):
    """One set with a 2★ and a 5★ chart must appear in BOTH buckets — binning
    star_max put it only in the 5★ one while `star>=2 star<3` still found it."""
    db, svc = _svc(tmp_path)
    tid = _track(db, 1)
    db.upsert_difficulties(tid, [_diff("a.osu"), _diff("b.osu")],
                           {"a.osu": 2.4, "b.osu": 5.1}, "when")
    data = svc.star_histogram_data(mode="integer")
    assert data["difficulties"] == 2 and data["sets"] == 1
    counted = {(lo, hi): c for lo, hi, c in data["bins"] if c}
    assert counted == {(2.0, 3.0): 1, (5.0, 6.0): 1}
    db.close()


def test_histogram_covers_the_whole_library_not_one_page(tmp_path):
    db, svc = _svc(tmp_path)
    _seed(db, 620, star=6.0)
    data = svc.star_histogram_data()
    assert data["difficulties"] == 620 and data["sets"] == 620
    db.close()


def test_histogram_empty_library_is_safe(tmp_path):
    db, svc = _svc(tmp_path)
    data = svc.star_histogram_data()
    assert data == {"bins": [], "difficulties": 0, "sets": 0, "pairs": []}
    db.close()


def test_histogram_pairs_answer_how_many_sets_a_range_lists(tmp_path):
    """The bars count difficulties; searching a range lists SETS. "2727
    difficulties" followed by "1509 matches" read as a bug, so the selection
    label now states both — computed from these pairs, since one set can span
    several bars and the per-bar set counts do not add up."""
    db, svc = _svc(tmp_path)
    a = _track(db, 1, name="Spread")
    b = _track(db, 2, name="Single")
    db.upsert_difficulties(a, [_diff("x.osu"), _diff("y.osu")],
                           {"x.osu": 2.5, "y.osu": 2.9}, "when")
    db.upsert_difficulties(b, [_diff("z.osu")], {"z.osu": 2.7}, "when")
    pairs = svc.star_histogram_data()["pairs"]
    in_range = [(t, s) for t, s in pairs if 2.0 <= s < 3.0]
    assert len(in_range) == 3                       # three difficulties…
    assert len({t for t, _s in in_range}) == 2      # …but only two sets listed
    assert {t for t, _s in in_range} == {a, b}
    db.close()


# -- 3.5 pruned sets must be findable ----------------------------------------
def test_pruned_filter_selects_only_pruned_sets():
    """Before this the pruned flag existed only as the hidden condition for a
    right-click menu entry — there was no way to LIST what Prune had stripped."""
    db = _db()
    plain = _track(db, 1, name="Whole")
    cut = _track(db, 2, name="Stripped")
    db.set_pruned_state(cut, True, 5_000_000)
    got = db.filtered_tracks([Filter("pruned", "=", 1)])
    assert [r["display_name"] for r in got] == ["Artist - Stripped"]
    assert db.count_filtered_tracks([Filter("pruned", "=", 1)]) == 1
    rest = db.filtered_tracks([Filter("pruned", "=", 0)])
    assert [r["id"] for r in rest] == [plain]   # NULL/0 both count as not pruned
    db.close()


def test_pruned_filter_round_trips_through_search():
    db = _db()
    _track(db, 1, name="Whole")
    cut = _track(db, 2, name="Stripped")
    db.set_pruned_state(cut, True, 5_000_000)
    rows = search.search(db, "pruned=yes")
    assert [r["display_name"] for r in rows] == ["Artist - Stripped"]
    db.close()


def test_recall_cap_never_cuts_the_best_match():
    # 2100 sets merely *contain* "ion" (Motion, Vision…), inserted first; the one
    # set titled "Ion" comes last. The recall used to stop at its cap in table
    # order, so the exact match never reached the ranker.
    db = _db()
    with db.bulk():
        for i in range(1, 2101):
            _track(db, i, name=f"Motion{i}", artist="Band")
    _track(db, 9999, name="Ion", artist="Someone")
    rows = search.search(db, "ion", limit=10)
    assert rows[0]["beatmapset_id"] == 9999
    db.close()
