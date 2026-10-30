# SPDX-License-Identifier: GPL-3.0-or-later
"""The folder watcher, Library move and Drive restore use diskspace.space."""
import hashlib
import io
import shutil
import zipfile
from collections import namedtuple

import pytest

from rosu import config
from rosu.db import Database
from rosu.services import Services, drive_restore_svc, move_svc

MiB = 1024 * 1024
_Usage = namedtuple("_Usage", "total used free")


class Log:
    def __init__(self):
        self.errors = []

    def info(self, *a, **k):
        pass

    def error(self, where, msg="", *a, **k):
        self.errors.append(where)


def _free(monkeypatch, n):
    monkeypatch.setattr(shutil, "disk_usage", lambda p: _Usage(10_000 * MiB, 0, n))


def _unreadable(monkeypatch):
    def boom(p):
        raise OSError("gone")
    monkeypatch.setattr(shutil, "disk_usage", boom)


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path / "app")))
    cfg.device_id = "devHERE"
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    s = Services(cfg, db, Log())
    yield s
    db.close()


# -- watcher ---------------------------------------------------------------------
def _osz(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("A - T [x].osu", "osu file format v14\n[Metadata]\nTitle:T\nArtist:A\n")
    return path


def test_watcher_refuses_on_a_short_drive(svc, tmp_path, monkeypatch):
    f = _osz(tmp_path / "1 A - T.osz")
    _free(monkeypatch, 1 * MiB)
    staged = []
    monkeypatch.setattr(shutil, "copy2", lambda *a: staged.append(a))
    res = svc.import_osz_files([f])
    assert res["failed"] == [str(f)] and res["imported"] == []
    assert svc.log.errors == ["watch:space"] and staged == []


def test_watcher_refuses_when_only_the_library_is_short(svc, tmp_path, monkeypatch):
    f = _osz(tmp_path / "1 A - T.osz")
    lib = svc.cfg.library_path.resolve()
    monkeypatch.setattr(shutil, "disk_usage", lambda p: _Usage(
        10_000 * MiB, 0, 1 * MiB if lib in (p, *p.parents) else 5_000 * MiB))
    res = svc.import_osz_files([f])
    assert res["failed"] == [str(f)] and svc.log.errors == ["watch:space"]
    assert not list(svc.cfg.library_path.glob("*.osz"))


def test_watcher_refuses_when_only_the_stage_is_short(svc, tmp_path, monkeypatch):
    f = _osz(tmp_path / "1 A - T.osz")
    lib = svc.cfg.library_path.resolve()
    monkeypatch.setattr(shutil, "disk_usage", lambda p: _Usage(
        10_000 * MiB, 0, 5_000 * MiB if lib in (p, *p.parents) else 1 * MiB))
    res = svc.import_osz_files([f])
    assert res["failed"] == [str(f)] and svc.log.errors == ["watch:space"]


@pytest.mark.parametrize("mode", ["ample", "unreadable"])
def test_watcher_imports_with_room_or_an_unreadable_drive(svc, tmp_path, monkeypatch, mode):
    f = _osz(tmp_path / "1 A - T.osz")
    _free(monkeypatch, 5_000 * MiB) if mode == "ample" else _unreadable(monkeypatch)
    res = svc.import_osz_files([f])
    assert res["imported"] == [str(f)] and res["failed"] == []
    assert "watch:space" not in svc.log.errors


# -- move ------------------------------------------------------------------------
def _lib_bytes(svc):
    return sum(p.stat().st_size for p in svc.cfg.library_path.glob("*.osz"))


@pytest.fixture
def lib_svc(svc):
    for i in range(3):
        (svc.cfg.library_path / f"{i} A - B.osz").write_bytes(bytes([i]) * (1000 + i))
    return svc


def test_move_plan_boundary(lib_svc, tmp_path, monkeypatch):
    total = _lib_bytes(lib_svc)
    dest = tmp_path / "D" / "Library"
    _free(monkeypatch, total + move_svc._FREE_MARGIN - 1)
    plan = lib_svc.library_move_plan(dest)
    assert plan["enough_space"] is False and plan["free"] == total + move_svc._FREE_MARGIN - 1
    _free(monkeypatch, total + move_svc._FREE_MARGIN)
    assert lib_svc.library_move_plan(dest)["enough_space"] is True


def test_move_plan_unreadable_drive_is_enough(lib_svc, tmp_path, monkeypatch):
    _unreadable(monkeypatch)
    plan = lib_svc.library_move_plan(tmp_path / "D" / "Library")
    assert plan["enough_space"] is True and plan["free"] is None


def test_move_library_refuses_and_moves_nothing(lib_svc, tmp_path, monkeypatch):
    _free(monkeypatch, _lib_bytes(lib_svc) + move_svc._FREE_MARGIN - 1)
    dest = tmp_path / "D" / "Library"
    old = lib_svc.cfg.library_path
    res = lib_svc.move_library(dest)
    assert res["error"] == "no_space" and res["moved"] == 0
    assert lib_svc.cfg.library_path == old and not dest.exists()


# -- drive restore -----------------------------------------------------------------
def test_free_bytes_reads_through_the_helper(tmp_path, monkeypatch):
    _free(monkeypatch, 123)
    assert drive_restore_svc._free_bytes(tmp_path) == 123
    _unreadable(monkeypatch)
    assert drive_restore_svc._free_bytes(tmp_path) is None


class FakeAuth:
    def is_connected(self):
        return True


class FakeDrive:
    def __init__(self, files):
        self.files = dict(files)
        self.downloads = []

    def ensure_folder(self, name="Rosu", parent=None):
        return "FOLDER"

    def list_folder(self, parent):
        return [{"id": "id-" + n, "name": n, "size": len(b)} for n, b in self.files.items()]

    def download_file(self, file_id, dest, progress=None, max_bytes=None):
        self.downloads.append(file_id[3:])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.files[file_id[3:]])
        return dest


def test_restore_refuses_on_a_faked_small_disk(svc, monkeypatch):
    osz = io.BytesIO()
    with zipfile.ZipFile(osz, "w") as z:
        z.writestr("A - T [x].osu", "osu file format v14\n[Metadata]\nTitle:T\nArtist:A\n")
    data = osz.getvalue()
    chunk_buf = io.BytesIO()
    with zipfile.ZipFile(chunk_buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("70 A.osz", data)
    chunk = "chunk-devX-0000.zip"
    drive = FakeDrive({chunk: chunk_buf.getvalue()})
    svc._drive_auth = lambda: FakeAuth()
    svc._make_drive_client = lambda: drive
    entry = {"chunk": chunk, "name": "70 A.osz", "size": len(data),
             "hash": hashlib.sha256(data).hexdigest(), "beatmapset_id": 70,
             "metadata": {"artist": "A", "title": "T"}}
    _free(monkeypatch, 1024)
    res = svc.drive_restore([entry])
    assert res["failed"] == [{"name": "70 A.osz", "reason": "disk_full"}]
    assert "drive:restore_space" in svc.log.errors and drive.downloads == []
