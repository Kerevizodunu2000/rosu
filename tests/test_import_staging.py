# SPDX-License-Identifier: GPL-3.0-or-later
"""Staging failures never hand osu! the Output/Library originals (issue #45)."""
import errno
import shutil

import pytest

from rosu import client_import, config, osu_import
from rosu.db import Database
from rosu.services import Services
from rosu.services import import_svc

DATA = {"a.osz": b"AAA", "b.osz": b"BBBB", "c.osz": b"CCCCC"}


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def _make_services(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.ensure_dirs()
    cfg.stable_enabled = True
    cfg.osu_lazer_exe = str(tmp_path / "lazer.exe")
    install = tmp_path / "stable_install"
    install.mkdir()
    (install / "osu!.exe").write_bytes(b"")
    cfg.osu_stable_exe = str(install / "osu!.exe")
    for name, data in DATA.items():
        (cfg.output_path / name).write_bytes(data)
    db = Database(cfg.db_path)
    return cfg, db, Services(cfg, db, DummyLog())


def _capture(monkeypatch):
    got = {}

    def fake(exe, files, **kw):
        got["files"] = list(files)
        return {"files": len(files), "batches": 1 if files else 0,
                "sent": len(files), "cancelled": False}

    monkeypatch.setattr(osu_import, "import_files", fake)
    return got


def _fail_copy(monkeypatch, exc, only=None):
    real = shutil.copy2

    def copy2(src, dst, *a, **k):
        if only is None or src.name == only:
            raise exc
        return real(src, dst, *a, **k)

    monkeypatch.setattr(shutil, "copy2", copy2)


def _intact(cfg):
    for name, data in DATA.items():
        assert (cfg.output_path / name).read_bytes() == data


def _files(cfg):
    return osu_import.output_osz_files(cfg.output_path)


@pytest.mark.parametrize("target", ["lazer", "stable"])
@pytest.mark.parametrize("exc,full", [(OSError(errno.EACCES, "denied"), False),
                                      (OSError(errno.ENOSPC, "full"), True)])
def test_every_copy_fails(tmp_path, monkeypatch, target, exc, full):
    cfg, db, svc = _make_services(tmp_path)
    got = _capture(monkeypatch)
    _fail_copy(monkeypatch, exc)
    res = svc._dispatch_to_client(target, _files(cfg))
    assert got["files"] == []
    _intact(cfg)
    assert res["stage_failed"] == len(DATA)
    assert res["disk_full"] is full
    db.close()


@pytest.mark.parametrize("target", ["lazer", "stable"])
def test_partial_staging(tmp_path, monkeypatch, target):
    cfg, db, svc = _make_services(tmp_path)
    got = _capture(monkeypatch)
    _fail_copy(monkeypatch, OSError(errno.EACCES, "denied"), only="b.osz")
    res = svc._dispatch_to_client(target, _files(cfg))
    assert len(got["files"]) == len(DATA) - 1
    assert all(cfg.output_path not in p.parents for p in got["files"])
    assert res["stage_failed"] == 1
    _intact(cfg)
    db.close()


def test_stage_folder_cannot_be_created(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path)
    got = _capture(monkeypatch)
    (cfg.data_path / "_import_stage").write_bytes(b"not a folder")
    res = svc._dispatch_to_client("lazer", _files(cfg))
    assert got["files"] == []
    _intact(cfg)
    assert res["stage_failed"] == len(DATA)
    db.close()


def test_stable_without_install_folder_returns_nothing(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path)
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: None)
    assert svc._stage_for_stable(_files(cfg)) == []
    db.close()


def test_is_disk_full():
    assert import_svc._is_disk_full(OSError(errno.ENOSPC, "x"))
    for code in (112, 39):
        exc = OSError(errno.EIO, "x")
        exc.winerror = code
        assert import_svc._is_disk_full(exc)
    assert not import_svc._is_disk_full(OSError(errno.EACCES, "x"))
    assert not import_svc._is_disk_full(ValueError())


def test_send_library_with_failing_copies(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path)
    got = _capture(monkeypatch)
    lib_file = cfg.library_path / "lib.osz"
    lib_file.write_bytes(b"LIB")
    monkeypatch.setattr(db, "library_tracks",
                        lambda: [{"filename": "lib.osz", "beatmapset_id": None}])
    _fail_copy(monkeypatch, OSError(errno.EACCES, "denied"))
    svc.send_library_to_client("lazer", skip_existing=False)
    assert got["files"] == []
    assert lib_file.read_bytes() == b"LIB"
    db.close()
