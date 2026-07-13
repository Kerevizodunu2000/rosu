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
