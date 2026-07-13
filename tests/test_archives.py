# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for multi-format archive reading + extra-file detection (items 24, 25)."""
import io
import tarfile
import zipfile

from rosu import archives, extractor
from rosu.db import Database
from rosu.parsing import parse_pack_name


def _make_zip(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("12345 Artist - Song.osz", b"fake-osz-bytes")
        z.writestr("readme.txt", b"hello")
        z.writestr("osu!mania/67890 A - B.osz", b"x")


def test_archive_kind_and_filter():
    assert archives.archive_kind("a.zip") == "zip"
    assert archives.archive_kind("a.7z") == "7z"
    assert archives.archive_kind("a.tar.gz") == "tar"
    assert archives.archive_kind("a.tgz") == "tar"
    assert archives.archive_kind("a.txt") is None
    f = archives.dialog_filter()
    assert "*.zip" in f and "*.7z" in f and "*.tar.gz" in f


def test_zip_members_and_open(tmp_path):
    p = tmp_path / "S1 - Pack.zip"
    _make_zip(p)
    with archives.open_reader(p) as r:
        names = sorted(m.name for m in r.members())
        assert names == ["12345 Artist - Song.osz",
                         "osu!mania/67890 A - B.osz", "readme.txt"]
        with r.open("readme.txt") as fh:
            assert fh.read() == b"hello"


def test_read_osz_entries_ignores_non_osz(tmp_path):
    p = tmp_path / "S1 - Pack.zip"
    _make_zip(p)
    ids = sorted(t.beatmapset_id for t in extractor.read_osz_entries(p))
    assert ids == [12345, 67890]


def test_extract_pack_flattens_and_flags_extras(tmp_path):
    p = tmp_path / "S1 - Pack.zip"
    _make_zip(p)
    out = tmp_path / "Output"
    db = Database(tmp_path / "m.db")
    parsed = parse_pack_name(p.name)
    res = extractor.extract_pack(p, parsed, out, db, "2026-01-01T00:00:00",
                                 read_meta=False)
    assert res["tracks"] == 2
    assert res["extra_files"] == ["readme.txt"]           # item 25
    assert (out / "12345 Artist - Song.osz").exists()
    assert (out / "67890 A - B.osz").exists()             # flattened from subfolder
    db.close()


def test_tar_gz_reader(tmp_path):
    tp = tmp_path / "S2 - Pack.tar.gz"
    with tarfile.open(tp, "w:gz") as t:
        for name, data in [("111 A - B.osz", b"osz"), ("notes.txt", b"note")]:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    assert [t.beatmapset_id for t in extractor.read_osz_entries(tp)] == [111]


def test_7z_reader(tmp_path):
    import py7zr
    src = tmp_path / "src"
    src.mkdir()
    (src / "222 C - D.osz").write_bytes(b"oszdata")
    (src / "readme.txt").write_bytes(b"txt")
    sp = tmp_path / "S3 - Pack.7z"
    with py7zr.SevenZipFile(sp, "w") as z:
        z.write(src / "222 C - D.osz", "222 C - D.osz")
        z.write(src / "readme.txt", "readme.txt")
    with archives.open_reader(sp) as r:
        assert sorted(m.name for m in r.members()) == ["222 C - D.osz", "readme.txt"]
        with r.open("222 C - D.osz") as fh:
            assert fh.read() == b"oszdata"
