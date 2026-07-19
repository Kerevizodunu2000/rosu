# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.8.1 fixes: id-based new/duplicate counting (item 7), synthetic-source
provenance (item 9), and the data-generation staleness counter (item 10)."""
from rosu import config, library
from rosu.db import Database


def _make(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.ensure_dirs()
    return cfg, Database(cfg.db_path)


def _osz(folder, name, data=b"osz"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)


def test_reimport_of_owned_set_counts_as_duplicate(tmp_path):
    cfg, db = _make(tmp_path)
    _osz(cfg.output_path, "123 A - T.osz", b"first")
    r1 = library.copy_to_library(cfg.output_path, cfg.library_path, db, "t1")
    assert (r1["new"], r1["duplicates"]) == (1, 0)

    # osu!lazer re-exports the SAME set with different bytes/size; it must count as
    # a duplicate by beatmapset id, not be miscounted as new (item 7).
    _osz(cfg.output_path, "123 A - T.osz", b"re-exported-different-size")
    r2 = library.copy_to_library(cfg.output_path, cfg.library_path, db, "t2")
    assert (r2["new"], r2["duplicates"]) == (0, 1)
    db.close()


def test_preexisting_identical_file_counts_as_duplicate(tmp_path):
    # A byte-identical file already sitting in Library (its DB row not yet flagged
    # in_library, e.g. a manual/restored copy) must count as a duplicate, not new
    # (review finding on the v0.8.1 id-based counting change).
    cfg, db = _make(tmp_path)
    _osz(cfg.library_path, "42 A - T.osz", b"same-bytes")
    _osz(cfg.output_path, "42 A - T.osz", b"same-bytes")
    res = library.copy_to_library(cfg.output_path, cfg.library_path, db, "t1")
    assert (res["new"], res["duplicates"]) == (0, 1)
    db.close()


def test_source_label_records_provenance_and_hides_pack(tmp_path):
    cfg, db = _make(tmp_path)
    _osz(cfg.output_path, "555 A - T.osz")
    library.copy_to_library(cfg.output_path, cfg.library_path, db, "t1",
                            source_label="local_osu_lazer")
    rows = db.all_tracks()
    db.attach_sources_bulk(rows)
    assert any("local_osu_lazer" in r.get("sources", []) for r in rows)
    # the synthetic pack must not surface in the Packs tab filters or as a gap (item 9)
    assert "local_osu_lazer" not in db.category_list()
    assert db.series_list() == []
    db.close()


def test_no_source_label_leaves_sources_empty(tmp_path):
    cfg, db = _make(tmp_path)
    _osz(cfg.output_path, "777 A - T.osz")
    library.copy_to_library(cfg.output_path, cfg.library_path, db, "t1")
    rows = db.all_tracks()
    db.attach_sources_bulk(rows)
    assert all(not r.get("sources") for r in rows)   # no phantom source pack
    db.close()


def test_data_generation_bumps_on_write_only(tmp_path):
    cfg, db = _make(tmp_path)
    g0 = db.data_generation()
    _osz(cfg.output_path, "9 A - T.osz")
    library.copy_to_library(cfg.output_path, cfg.library_path, db, "t1")
    g1 = db.data_generation()
    assert g1 > g0                        # writing a track bumped it (item 10)
    db.artists_ranked()                   # a pure read
    assert db.data_generation() == g1     # reads never bump
    db.close()


# -- v1.7 prune interaction: a pruned Library target must never be re-inflated --
def test_pruned_target_not_overwritten_on_size_mismatch(tmp_path):
    cfg, db = _make(tmp_path)
    _osz(cfg.output_path, "88 A - T.osz", b"original-full-file")
    library.copy_to_library(cfg.output_path, cfg.library_path, db, "t1")
    row = db.find_track_row(88, "88 A - T.osz")
    db.set_pruned_state(row["id"], True, len(b"original-full-file"))

    # Simulate the on-disk effect of a prune: the Library copy shrinks.
    lib_file = cfg.library_path / "88 A - T.osz"
    lib_file.write_bytes(b"pruned")

    # A later re-import of the (still full-size) set must NOT overwrite the
    # pruned Library copy with the unpruned bytes — that would silently undo
    # the space savings on every subsequent import/refresh.
    _osz(cfg.output_path, "88 A - T.osz", b"original-full-file")
    library.copy_to_library(cfg.output_path, cfg.library_path, db, "t2")
    assert lib_file.read_bytes() == b"pruned"
    db.close()


def test_pruned_target_matching_original_size_counts_as_duplicate(tmp_path):
    cfg, db = _make(tmp_path)
    original = b"original-full-file"
    _osz(cfg.output_path, "89 A - T.osz", original)
    library.copy_to_library(cfg.output_path, cfg.library_path, db, "t1")
    row = db.find_track_row(89, "89 A - T.osz")
    db.set_pruned_state(row["id"], True, len(original))
    (cfg.library_path / "89 A - T.osz").write_bytes(b"pruned")

    _osz(cfg.output_path, "89 A - T.osz", original)
    res = library.copy_to_library(cfg.output_path, cfg.library_path, db, "t2")
    assert (res["new"], res["duplicates"]) == (0, 1)
    db.close()


def test_auto_prune_shrinks_new_video_bearing_set(tmp_path):
    import zipfile
    cfg, db = _make(tmp_path)
    cfg.output_path.mkdir(parents=True, exist_ok=True)
    p = cfg.output_path / "90 A - T.osz"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("map.osu", b"osu file format v14\n")
        zf.writestr("video.mp4", b"z" * 5000)

    res = library.copy_to_library(cfg.output_path, cfg.library_path, db, "t1",
                                  auto_prune=True, prune_mode="video_only")
    assert res["new"] == 1
    row = db.find_track_row(90, "90 A - T.osz")
    assert row["is_pruned"] == 1
    with zipfile.ZipFile(cfg.library_path / "90 A - T.osz") as zf:
        assert "video.mp4" not in zf.namelist()
    db.close()
