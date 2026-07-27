# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the pure-Python auto-import helpers (item 15, stable side)."""
import zipfile

from rosu import client_import as ci


def test_id_from_folder_prefix(tmp_path):
    f = tmp_path / "12345 Artist - Title"
    f.mkdir()
    assert ci.beatmapset_id_for_folder(f) == 12345


def test_id_from_osu_fallback(tmp_path):
    f = tmp_path / "my custom map"
    f.mkdir()
    (f / "map.osu").write_text("[Metadata]\nTitle:X\nBeatmapSetID:678\n", encoding="utf-8")
    assert ci.beatmapset_id_for_folder(f) == 678


def test_id_none_when_unresolvable(tmp_path):
    f = tmp_path / "no id here"
    f.mkdir()
    (f / "map.osu").write_text("[Metadata]\nTitle:X\nBeatmapSetID:-1\n", encoding="utf-8")
    assert ci.beatmapset_id_for_folder(f) is None


def test_zip_folder_preserves_subfolders(tmp_path):
    f = tmp_path / "999 A - B"
    (f / "sb").mkdir(parents=True)
    (f / "map.osu").write_text("osu file", encoding="utf-8")
    (f / "audio.mp3").write_bytes(b"\x00\x01")
    (f / "sb" / "bg.png").write_bytes(b"img")
    dest = tmp_path / "out" / "999 A - B.osz"
    ci.zip_folder_to_osz(f, dest)
    with zipfile.ZipFile(dest) as z:
        assert sorted(z.namelist()) == ["audio.mp3", "map.osu", "sb/bg.png"]
        assert z.read("sb/bg.png") == b"img"


def test_iter_osz_in_folder(tmp_path):
    (tmp_path / "a.osz").write_bytes(b"x")
    (tmp_path / "b.olz").write_bytes(b"y")
    (tmp_path / "notes.txt").write_bytes(b"z")
    names = sorted(p.name for p in ci.iter_osz_in_folder(tmp_path))
    assert names == ["a.osz", "b.olz"]


# -- v1.7.1: proving the lazer save landed before anything is deleted ---------
def test_not_in_library_names_what_did_not_make_it(tmp_path):
    """The lazer prune steps tell the user to delete their beatmaps out of lazer
    next, so "N new sets added" is not good enough: an already-known set counts
    as a duplicate and a failed copy counts as nothing."""
    import zipfile
    from rosu import config
    from rosu.db import Database
    from rosu.models import ParsedTrack
    from rosu.services import Services

    class _Log:
        def info(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    svc = Services(cfg, db, _Log())

    saved = cfg.library_path / "10 A - B.osz"
    with zipfile.ZipFile(saved, "w") as z:
        z.writestr("map.osu", b"o")
    tid, _ = db.upsert_track(
        ParsedTrack(beatmapset_id=10, filename=saved.name, artist="A", title="B",
                    display_name="A - B", size_bytes=1), "when")
    db.set_library_state(tid, True, "present", "when")

    exported = [tmp_path / "10 A - B.osz",     # in the Library
                tmp_path / "11 C - D.osz",     # never arrived
                tmp_path / "no-id.osz"]        # unparseable name
    assert svc._not_in_library(exported) == ["11 C - D.osz", "no-id.osz"]

    # A row that exists but whose file is gone must also count as missing.
    saved.unlink()
    assert "10 A - B.osz" in svc._not_in_library(exported)
    db.close()
