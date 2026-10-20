# SPDX-License-Identifier: GPL-3.0-or-later
"""Mode / Keys / Where / Library columns agree with what the DB stores
(HANDOFF 4.3 column audit)."""
import zipfile

from rosu import columns, config, health, library
from rosu.db import Database
from rosu.i18n import I18N


def _make(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.ensure_dirs()
    return cfg, Database(cfg.db_path)


def _osu(mode: int, version: str, cs: float = 4.0) -> bytes:
    return (
        "osu file format v14\n\n"
        "[General]\nAudioFilename: audio.mp3\n"
        f"Mode: {mode}\n\n"
        "[Metadata]\nTitle:Song\nArtist:Band\nCreator:Mapper\n"
        f"Version:{version}\nBeatmapSetID:777\n\n"
        f"[Difficulty]\nHPDrainRate:5\nCircleSize:{cs}\n"
        "OverallDifficulty:8\nApproachRate:9\n\n"
        "[TimingPoints]\n0,500,4,2,0,100,1,0\n\n"
        "[HitObjects]\n64,192,1000,1,0,0:0:0:0:\n"
        "192,192,61000,1,0,0:0:0:0:\n"
    ).encode("utf-8")


def _mixed_osz(path):
    """A set whose alphabetically-first .osu is osu! but which also has a 7K
    mania chart — the shape that made Mode read "osu!" while mode=mania matched."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Band - Song (Mapper) [A Normal].osu", _osu(0, "A Normal"))
        z.writestr("Band - Song (Mapper) [B 7K].osu", _osu(3, "B 7K", cs=7))


# -- pure column derivations ---------------------------------------------------
def test_mode_text_lists_every_diff_mode_in_osu_order():
    diffs = [{"mode": "osu!mania", "mode_int": 3}, {"mode": "osu!", "mode_int": 0},
             {"mode": "osu!mania", "mode_int": 3}]
    assert columns.mode_text(diffs, "osu!") == "osu!, osu!mania"


def test_mode_text_falls_back_to_stored_mode_only_without_parsed_diffs():
    assert columns.mode_text([], "osu!taiko") == "osu!taiko"
    assert columns.mode_text([{"mode": None}], None) == ""
    # A parsed set never shows the stale representative value.
    assert columns.mode_text([{"mode": "osu!mania", "mode_int": 3}],
                             "osu!") == "osu!mania"


def test_has_library_copy_ignores_memory_only_rows():
    assert columns.has_library_copy({"in_library": 1, "library_status": "present"})
    # memory-only import: in_library=1 but no .osz was ever written
    assert not columns.has_library_copy({"in_library": 1, "library_status": "memory"})
    # purged: in_library=0 + memory — the same situation, other encoding
    assert not columns.has_library_copy({"in_library": 0, "library_status": "memory"})
    assert not columns.has_library_copy({"in_library": 0,
                                         "library_status": "disappeared"})


def test_where_marks_never_claims_a_library_file_for_memory_only():
    marks, _ = columns.where_marks({"in_library": 1, "library_status": "memory",
                                    "in_osu": 1, "in_osu_lazer": 1})
    assert marks == ["🎮"]


def test_where_marks_per_client_and_legacy():
    assert columns.where_marks({"in_osu": 1, "in_osu_stable": 1})[0] == ["🕹️"]
    assert columns.where_marks({"in_osu": 1})[0] == ["🎮"]   # pre-v1.0 flag
    both = {"in_osu": 1, "in_osu_stable": 1, "in_osu_lazer": 1,
            "in_library": 1, "library_status": "present", "in_drive": 1}
    assert columns.where_marks(both)[0] == ["🎮", "🕹️", "💾", "☁️"]


def test_where_weight_follows_the_icons():
    # Same icons ⇒ same weight; a stable-only row no longer sorts with lazer
    # rows, and a memory-only row no longer outranks one with nothing at all.
    lazer = columns.where_marks({"in_osu_lazer": 1, "in_osu": 1})[1]
    stable = columns.where_marks({"in_osu_stable": 1, "in_osu": 1})[1]
    mem = columns.where_marks({"in_library": 1, "library_status": "memory"})[1]
    assert lazer != stable
    assert mem == 0


def test_library_status_is_translated():
    for lang in ("en", "tr"):
        t = I18N(lang).t
        for status in ("present", "memory", "disappeared"):
            text = columns.library_status_text({"library_status": status}, t)
            assert text == t(f"lib_status_{status}") and text != f"lib_status_{status}"
        gone = columns.library_status_text(
            {"library_status": "disappeared", "status_changed_at": "2026-01-02"}, t)
        assert "2026-01-02" in gone
    t = I18N("tr").t
    assert columns.library_status_text({"library_status": "present"}, t) != "present"
    assert columns.library_status_text({}, t) == "-"


# -- health scrub --------------------------------------------------------------
def test_scrub_memory_only_import_is_not_a_dead_link():
    rows = [{"filename": "1 A - B.osz", "in_library": 1, "library_status": "memory"},
            {"filename": "2 A - B.osz", "in_library": 1, "library_status": "present"}]
    res = health.scrub(rows, {})
    assert [r["filename"] for r in res["dead_links"]] == ["2 A - B.osz"]
    assert res["memory"] == 1


# -- DB writers ----------------------------------------------------------------
def _seed(db, tmp_path, bid=777, name="777 Band - Song.osz"):
    src = tmp_path / "src" / name
    _mixed_osz(src)
    return src


def _row(db, bid):
    return dict(db.find_track_row(bid, ""))


def test_clearing_one_client_keeps_legacy_flag_while_the_other_has_it(tmp_path):
    cfg, db = _make(tmp_path)
    _seed(db, tmp_path)
    library.copy_to_library(tmp_path / "src", cfg.library_path, db, "t1")
    db.set_in_osu(777, client="stable")
    db.set_in_osu(777, client="lazer")
    db.set_in_osu(777, False, client="stable")
    r = _row(db, 777)
    assert (r["in_osu"], r["in_osu_stable"], r["in_osu_lazer"]) == (1, 0, 1)
    db.set_in_osu(777, False, client="lazer")
    r = _row(db, 777)
    assert (r["in_osu"], r["in_osu_stable"], r["in_osu_lazer"]) == (0, 0, 0)
    db.set_in_osu(777, client="lazer")
    db.set_in_osu(777, False)            # no client: gone from every client
    r = _row(db, 777)
    assert (r["in_osu"], r["in_osu_stable"], r["in_osu_lazer"]) == (0, 0, 0)
    db.close()


def test_client_import_records_mode_and_keys(tmp_path):
    """A set pulled straight out of osu! used to land as a bare name: blank
    Mode / Keys / Star until a Refresh Library."""
    cfg, db = _make(tmp_path)
    _seed(db, tmp_path)
    library.copy_to_library(tmp_path / "src", cfg.library_path, db, "t1",
                            source_label="local_osu_lazer")
    r = _row(db, 777)
    assert r["diffs_scanned_at"] and r["creator"] == "Mapper"
    diffs = db.difficulties_for_track(r["id"])
    assert {d["mode"] for d in diffs} == {"osu!", "osu!mania"}
    assert [d["keycount"] for d in diffs if d["mode_int"] == 3] == [7]
    assert all(d["keycount"] is None for d in diffs if d["mode_int"] != 3)
    db.close()


def test_memory_only_client_import_still_records_mode(tmp_path):
    # Refresh only reads the Library folder, so with physical copies off this
    # import was the only chance to read the set.
    cfg, db = _make(tmp_path)
    _seed(db, tmp_path)
    library.copy_to_library(tmp_path / "src", cfg.library_path, db, "t1",
                            physical_copy=False, source_label="local_osu_stable")
    r = _row(db, 777)
    assert not (cfg.library_path / "777 Band - Song.osz").exists()
    assert r["library_status"] == "memory"
    assert len(db.difficulties_for_track(r["id"])) == 2
    db.close()


def test_already_scanned_set_is_not_reparsed(tmp_path, monkeypatch):
    cfg, db = _make(tmp_path)
    _seed(db, tmp_path)
    library.copy_to_library(tmp_path / "src", cfg.library_path, db, "t1")
    calls = []
    real = library.read_osz_full
    monkeypatch.setattr(library, "read_osz_full",
                        lambda p: calls.append(p) or real(p))
    library.copy_to_library(tmp_path / "src", cfg.library_path, db, "t2")
    assert calls == []
    db.close()


def test_unreadable_archive_stays_unscanned_for_refresh(tmp_path):
    cfg, db = _make(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "5 A - B.osz").write_bytes(b"not a zip")
    library.copy_to_library(src, cfg.library_path, db, "t1")
    assert not _row(db, 5)["diffs_scanned_at"]
    db.close()


def test_artist_rows_carry_difficulties_for_the_mode_column(tmp_path):
    cfg, db = _make(tmp_path)
    _seed(db, tmp_path)
    library.copy_to_library(tmp_path / "src", cfg.library_path, db, "t1")
    rows = db.tracks_by_artist("Band")
    assert len(rows) == 1
    assert columns.mode_text(rows[0]["difficulties"],
                             rows[0]["mode"]) == "osu!, osu!mania"
    # The stored representative value is still the first .osu's — which is
    # exactly why the column must not read it directly.
    assert rows[0]["mode"] == "osu!"
    db.close()
