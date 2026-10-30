# SPDX-License-Identifier: GPL-3.0-or-later
"""Export checks the free space first and stops cleanly on a full disk,
keeping the volumes already finished (issue #46)."""
import errno
import shutil
import tempfile
from collections import namedtuple
from pathlib import Path

import pytest

from rosu import config, diskspace, exporter, jobs
from rosu.db import Database
from rosu.jobs import State
from rosu.services import Services

MiB = 1024 * 1024
_Usage = namedtuple("_Usage", "total used free")
SIZES = {"1 A - B.osz": 100, "2 C - D.osz": 100, "3 E - F.osz": 100}


class Log:
    def __init__(self):
        self.warns = []

    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass

    def log(self, action, level="INFO", message="", **k):
        if level == "WARN":
            self.warns.append((k.get("where"), k.get("detail", "")))


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "temp"))
    (tmp_path / "temp").mkdir()
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    for name, size in SIZES.items():
        (cfg.library_path / name).write_bytes(b"x" * size)
    db = Database(cfg.db_path)
    s = Services(cfg, db, Log())
    s.uploads = []
    monkeypatch.setattr(s, "_upload_export_to_drive",
                        lambda *a, **k: s.uploads.append(a) or {"uploaded": 1, "files": []})
    yield s
    db.close()


def _free(monkeypatch, n):
    monkeypatch.setattr(shutil, "disk_usage", lambda p: _Usage(10_000 * MiB, 0, n))


def _two_drives(monkeypatch, short, free_short, free_other=10_000 * MiB):
    short = Path(short).resolve()

    def fake(path, need, margin=diskspace.MARGIN):
        p = Path(path).resolve()
        on_e = p == short or short in p.parents
        free = free_short if on_e else free_other
        return diskspace.Space(free, 10_000 * MiB, free >= need + margin,
                               "E:\\" if on_e else "C:\\")
    monkeypatch.setattr(diskspace, "space", fake)


def _fail_volume(monkeypatch, n, err=errno.ENOSPC):
    """The ``n``-th archive volume fails its first write with ``err``."""
    real = exporter._open_archive
    opened = []

    def fake(tmp, fmt):
        opened.append(tmp)
        z = real(tmp, fmt)
        if len(opened) == n:
            def boom(*a, **k):
                raise OSError(err, "write failed")
            z.write = boom
        return z
    monkeypatch.setattr(exporter, "_open_archive", fake)


def _leftovers(folder):
    return sorted(p.name for p in Path(folder).rglob("*") if p.suffix in (".zip", ".part"))


def _no_path(svc, tmp_path):
    for where, detail in svc.log.warns:
        assert str(tmp_path) not in detail and str(tmp_path.resolve()) not in detail


# -- refused before writing ----------------------------------------------------
def test_export_refused_writes_nothing(svc, tmp_path, monkeypatch):
    _free(monkeypatch, 299 + diskspace.MARGIN)
    dest = tmp_path / "out" / "exp"
    res = svc.export_sets("library", dest, upload_to_drive=True)
    assert res == {"source": "library", "count": 0, "archives": [], "cancelled": False,
                   "no_space": {"drive": tmp_path.resolve().anchor,
                                "need": 300 + diskspace.MARGIN,
                                "free": 299 + diskspace.MARGIN}}
    assert not dest.parent.exists()
    assert svc.uploads == []
    assert [w for w, _ in svc.log.warns] == ["export:space"]
    _no_path(svc, tmp_path)


def test_export_job_refused_ends_done(svc, tmp_path, monkeypatch):
    _free(monkeypatch, 299 + diskspace.MARGIN)
    dest = tmp_path / "out" / "exp"
    job = svc.build_export_job("library", dest, upload=True)
    res = jobs.run_job_sync(job)
    assert job.state == State.DONE
    assert res["no_space"]["need"] == 300 + diskspace.MARGIN
    assert res["count"] == 0 and res["archives"] == []
    assert not dest.parent.exists() and svc.uploads == []


def test_export_fits_exactly(svc, tmp_path, monkeypatch):
    _free(monkeypatch, 300 + diskspace.MARGIN)
    res = svc.export_sets("library", tmp_path / "out" / "exp")
    assert "no_space" not in res and len(res["archives"]) == 1


def test_export_prune_refused_on_short_temp_drive(svc, tmp_path, monkeypatch):
    svc.cfg.export_prune = True
    _two_drives(monkeypatch, tmp_path / "temp", 99 + diskspace.MARGIN)
    dest = tmp_path / "out" / "exp"
    res = svc.export_sets("library", dest)
    assert res["no_space"] == {"drive": "E:\\", "need": 100 + diskspace.MARGIN,
                               "free": 99 + diskspace.MARGIN}
    assert not dest.parent.exists()


def test_export_without_prune_ignores_temp_drive(svc, tmp_path, monkeypatch):
    _two_drives(monkeypatch, tmp_path / "temp", 0)
    res = svc.export_sets("library", tmp_path / "out" / "exp")
    assert "no_space" not in res and len(res["archives"]) == 1


# -- disk full while writing ---------------------------------------------------
def test_export_disk_full_keeps_first_volume(svc, tmp_path, monkeypatch):
    _fail_volume(monkeypatch, 2)
    dest = tmp_path / "out" / "exp"
    res = svc.export_sets("library", dest, split_bytes=100, upload_to_drive=True)
    first = dest.parent / "exp.part01.zip"
    assert res["archives"] == [str(first)] and first.exists()
    assert res["disk_full"] is True and res["full_drive"] == tmp_path.resolve().anchor
    assert _leftovers(dest.parent) == ["exp.part01.zip"]
    assert svc.uploads == []
    assert [w for w, _ in svc.log.warns] == ["export:disk_full"]
    _no_path(svc, tmp_path)


def test_export_job_disk_full_keeps_first_volume(svc, tmp_path, monkeypatch):
    _fail_volume(monkeypatch, 2)
    dest = tmp_path / "out" / "exp"
    job = svc.build_export_job("library", dest, split_bytes=100, upload=True)
    res = jobs.run_job_sync(job)
    first = dest.parent / "exp.part01.zip"
    assert job.state == State.DONE
    assert res["archives"] == [str(first)] and first.exists()
    assert res["disk_full"] is True and res["full_drive"] == tmp_path.resolve().anchor
    assert _leftovers(dest.parent) == ["exp.part01.zip"]
    assert svc.uploads == [] and "drive" not in res


def test_export_disk_full_names_the_fuller_temp_drive_with_prune(svc, tmp_path, monkeypatch):
    svc.cfg.export_prune = True
    monkeypatch.setattr("rosu.prune.prune_osz", lambda *a, **k: None)
    _two_drives(monkeypatch, tmp_path / "temp", 100 + diskspace.MARGIN)
    _fail_volume(monkeypatch, 2)
    res = svc.export_sets("library", tmp_path / "out" / "exp", split_bytes=100)
    assert res["full_drive"] == "E:\\" and len(res["archives"]) == 1


def test_write_export_attaches_finished_volumes(tmp_path, monkeypatch):
    files = []
    for name, size in SIZES.items():
        (tmp_path / name).write_bytes(b"x" * size)
        files.append(tmp_path / name)
    _fail_volume(monkeypatch, 3)
    with pytest.raises(OSError) as ei:
        exporter.write_export(files, tmp_path / "out" / "exp", split_bytes=100)
    assert [p.name for p in ei.value.written] == ["exp.part01.zip", "exp.part02.zip"]
    assert _leftovers(tmp_path / "out") == ["exp.part01.zip", "exp.part02.zip"]


def test_other_write_error_still_propagates(svc, tmp_path, monkeypatch):
    _fail_volume(monkeypatch, 2, errno.EACCES)
    with pytest.raises(OSError) as ei:
        svc.export_sets("library", tmp_path / "out" / "exp", split_bytes=100,
                        upload_to_drive=True)
    assert ei.value.errno == errno.EACCES and not hasattr(ei.value, "written")
    assert svc.uploads == []
    _fail_volume(monkeypatch, 2, errno.EACCES)
    job = svc.build_export_job("library", tmp_path / "out2" / "exp", split_bytes=100)
    with pytest.raises(OSError):
        jobs.run_job_sync(job)
    assert job.state == State.FAILED
