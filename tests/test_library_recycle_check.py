# SPDX-License-Identifier: GPL-3.0-or-later
"""Library purge, dedup and osu!(stable) removal check the Recycle Bin first (issue #42)."""
import shutil
from pathlib import Path

import pytest

from rosu import client_import, client_remove, config
from rosu.db import Database
from rosu.models import ParsedTrack
from rosu.services import Services


class DummyLog:
    def __init__(self):
        self.lines = []

    def info(self, *a, **k):
        self.lines.append(("info", a, k))

    def error(self, *a, **k):
        self.lines.append(("error", a, k))


def _errors(svc, where):
    return [a for kind, a, _ in svc.log.lines if kind == "error" and a[0] == where]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    svc = Services(cfg, db, DummyLog())
    trash = tmp_path / "trash"
    trash.mkdir()
    calls = []

    def fake_send2trash(path):
        calls.append(path)
        shutil.move(str(path), str(trash / Path(path).name))
    monkeypatch.setattr("send2trash.send2trash", fake_send2trash)
    yield cfg, db, svc, calls
    db.close()


def _library(cfg, db, bids=(1, 2, 3)):
    names = []
    for bid in bids:
        fn = f"{bid} A - B.osz"
        (cfg.library_path / fn).write_bytes(b"PK" * 10)
        tid, _ = db.upsert_track(ParsedTrack(beatmapset_id=bid, filename=fn, artist="A",
                                             title="B", display_name="A - B"), "t0")
        db.set_library_state(tid, True, "present", "t0")
        names.append(fn)
    return names


def _duplicate(cfg, bid=1):
    dup = f"{bid} A - B (1).osz"
    (cfg.library_path / dup).write_bytes(b"PK" * 10)
    return dup


def test_purge_refuses_everything_without_a_recycle_bin(env, monkeypatch):
    cfg, db, svc, calls = env
    names = _library(cfg, db)
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda p: False)
    res = svc.purge_library_files()
    assert res["error"] == "no_recycle_bin" and res["deleted"] == 0
    assert calls == []
    assert all((cfg.library_path / n).exists() for n in names)
    assert all(db.find_track_row(bid, "")["in_library"] == 1 for bid in (1, 2, 3))
    assert len(_errors(svc, "library:purge")) == 1


def test_dedup_refuses_everything_without_a_recycle_bin(env, monkeypatch):
    cfg, db, svc, calls = env
    names = _library(cfg, db)
    dup = _duplicate(cfg)
    assert svc.dedup_library_plan()["names"] == [dup]   # a real duplicate
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda p: False)
    for res in (svc.dedup_library(names=[dup, names[1]]), svc.dedup_library()):
        assert res["error"] == "no_recycle_bin"
        assert res["removed"] == 0 and res["freed_bytes"] == 0
    assert calls == []
    assert all((cfg.library_path / n).exists() for n in names + [dup])
    assert len(_errors(svc, "dedup")) == 2


def test_purge_skips_a_file_without_a_recycle_bin(env, monkeypatch):
    cfg, db, svc, calls = env
    names = _library(cfg, db)
    bad = cfg.library_path / names[1]
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda p: Path(p) != bad)
    res = svc.purge_library_files()
    assert res == {"deleted": 2, "too_large": 0}
    assert bad.exists() and not (cfg.library_path / names[0]).exists()
    assert db.find_track_row(2, "")["in_library"] == 1
    assert db.find_track_row(1, "")["library_status"] == "memory"
    assert any(names[1] in a[1] for a in _errors(svc, "library:purge"))


def test_dedup_skips_a_file_without_a_recycle_bin(env, monkeypatch):
    cfg, db, svc, calls = env
    _library(cfg, db, (1, 2))
    dups = [_duplicate(cfg, 1), _duplicate(cfg, 2)]
    bad = cfg.library_path / dups[0]
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda p: Path(p) != bad)
    res = svc.dedup_library(names=dups)
    assert res["removed"] == 1 and res["freed_bytes"] == 20 and res["too_large"] == 0
    assert bad.exists() and not (cfg.library_path / dups[1]).exists()
    assert any(dups[0] in a[1] for a in _errors(svc, "dedup"))


def test_purge_keeps_a_file_too_large_for_the_bin(env, monkeypatch):
    cfg, db, svc, calls = env
    names = _library(cfg, db)
    big = cfg.library_path / names[2]
    monkeypatch.setattr(client_remove, "recycle_bin_fits", lambda p: Path(p) != big)
    res = svc.purge_library_files()
    assert res == {"deleted": 2, "too_large": 1}
    assert big.exists() and db.find_track_row(3, "")["in_library"] == 1
    assert any(names[2] in a[1] for a in _errors(svc, "library:purge"))


def test_dedup_keeps_a_file_too_large_for_the_bin(env, monkeypatch):
    cfg, db, svc, calls = env
    _library(cfg, db, (1, 2))
    dups = [_duplicate(cfg, 1), _duplicate(cfg, 2)]
    big = cfg.library_path / dups[1]
    monkeypatch.setattr(client_remove, "recycle_bin_fits", lambda p: Path(p) != big)
    res = svc.dedup_library()
    assert res["too_large"] == 1 and res["removed"] == 1 and res["freed_bytes"] == 20
    assert big.exists() and not (cfg.library_path / dups[0]).exists()


def test_remove_stable_keeps_a_folder_too_large_for_the_bin(env, monkeypatch, tmp_path):
    cfg, db, svc, calls = env
    songs = tmp_path / "Songs"
    songs.mkdir()
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    monkeypatch.setattr(client_remove, "osu_process_paths", lambda: [])
    cfg.stable_enabled = True
    folders = []
    for bid in (101, 202):
        d = songs / f"{bid} A - B"
        d.mkdir()
        (d / "A - B [x].osu").write_text(f"osu file format v14\n[Metadata]\nBeatmapSetID:{bid}\n")
        folders.append(d)
    big = folders[0]
    monkeypatch.setattr(client_remove, "recycle_bin_fits", lambda p: Path(p) != big)
    res = svc.remove_from_client("stable", [d.name for d in folders], save_first=False)
    assert res["failed"] == [big.name] and res["removed"] == 1
    assert big.exists() and not folders[1].exists()
    assert any("too large" in a[1] for a in _errors(svc, "remove:stable"))
