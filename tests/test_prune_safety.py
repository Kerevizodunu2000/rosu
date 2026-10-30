# SPDX-License-Identifier: GPL-3.0-or-later
"""prune_osz / prune_folder never lose the only copy (issue #16)."""
import os
import zipfile

import pytest

from rosu import client_remove, exporter
from rosu.prune import prune_folder, prune_osz, scan_folder

OSU = "osu file format v14\n[General]\nAudioFilename: audio.mp3\n[Events]\n0,0,\"sub/bg.jpg\",0,0\n"


def _osz(path, video=b"v" * 4096):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("map.osu", OSU)
        z.writestr("audio.mp3", b"a" * 100)
        z.writestr("video.mp4", video)
    return path


@pytest.fixture
def recorder(monkeypatch):
    calls = []
    monkeypatch.setattr("send2trash.send2trash", lambda path: calls.append(path))
    return calls


def test_failed_trash_keeps_the_original(tmp_path, monkeypatch):
    p = _osz(tmp_path / "set.osz")
    orig = p.read_bytes()

    def boom(path):
        raise OSError("no recycle bin")
    monkeypatch.setattr("send2trash.send2trash", boom)
    assert prune_osz(p, mode="video_only") == 0
    assert p.read_bytes() == orig
    assert list(tmp_path.iterdir()) == [p]           # no .orig, no temp file


def test_no_recycle_bin_prunes_nothing(tmp_path, monkeypatch, recorder):
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda path: False)
    p = _osz(tmp_path / "set.osz")
    orig = p.read_bytes()
    assert prune_osz(p, mode="video_only") == 0
    assert p.read_bytes() == orig
    assert recorder == []

    songs = tmp_path / "Songs"
    folder = songs / "1 A - B"
    folder.mkdir(parents=True)
    (folder / "map.osu").write_text(OSU)
    (folder / "video.mp4").write_bytes(b"v" * 4096)
    before = sorted(folder.rglob("*"))
    assert prune_folder(folder, mode="video_only", root=songs) == 0
    assert sorted(folder.rglob("*")) == before
    assert recorder == []


def test_original_is_trashed_before_it_changes(tmp_path, monkeypatch):
    p = _osz(tmp_path / "set.osz")
    orig = p.read_bytes()
    seen = []

    def fake(path):
        seen.append(p.read_bytes() == orig)
    monkeypatch.setattr("send2trash.send2trash", fake)
    assert prune_osz(p, mode="video_only") > 0
    assert seen == [True]
    assert p.read_bytes() != orig
    with zipfile.ZipFile(p) as z:
        assert "video.mp4" not in z.namelist()


def test_heavy_assets_keeps_files_referenced_from_subfolders(tmp_path, monkeypatch):
    monkeypatch.setattr("send2trash.send2trash", os.remove)
    songs = tmp_path / "Songs"
    folder = songs / "1 A - B"
    (folder / "sub").mkdir(parents=True)
    (folder / "map.osu").write_text(OSU)
    (folder / "audio.mp3").write_bytes(b"a" * 100)
    (folder / "sub" / "bg.jpg").write_bytes(b"b" * 600 * 1024)
    (folder / "video.mp4").write_bytes(b"v" * 4096)
    _total, removable = scan_folder(folder, mode="heavy_assets")
    assert removable == 4096
    assert prune_folder(folder, mode="heavy_assets", root=songs) == 4096
    assert (folder / "sub" / "bg.jpg").exists()
    assert not (folder / "video.mp4").exists()


def test_throwaway_copies_skip_the_recycle_bin(tmp_path, recorder):
    p = _osz(tmp_path / "a.osz")
    assert prune_osz(p, mode="video_only", keep_original=False) > 0
    assert recorder == []
    assert not list(tmp_path.glob("*.orig"))

    q = _osz(tmp_path / "b.osz")
    assert prune_osz(q, mode="video_only") > 0
    assert len(recorder) == 1

    recorder.clear()
    src = _osz(tmp_path / "c.osz")
    out = exporter.write_export([src], tmp_path / "out" / "export", prune_mode="video_only")
    assert out and recorder == []
