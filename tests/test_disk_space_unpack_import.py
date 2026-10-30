# SPDX-License-Identifier: GPL-3.0-or-later
"""A refused or disk-full Unpack sends nothing to osu!, the Unpack job ends
FAILED, and a loose .osz moved across drives is counted (issue #46)."""
import errno
import shutil
from collections import namedtuple
from pathlib import Path

import pytest

from rosu import config, crash_report, diskspace, jobs
from rosu.db import Database
from rosu.jobs import State
from rosu.services import Services

MiB = 1024 * 1024
_Usage = namedtuple("_Usage", "total used free")
NO_SPACE = {"packs": 0, "tracks": 0, "rejected": [], "loose": 0, "kept": 1,
            "no_space": {"drive": "E:\\", "need": 300 + diskspace.MARGIN, "free": 5}}
DISK_FULL = {"packs": 1, "tracks": 2, "rejected": [], "loose": 0, "kept": 1,
             "disk_full": True, "full_drive": "E:\\"}
LOOSE = "424242 Artist - Title.osz"


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
def svc(tmp_path):
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    yield Services(cfg, db, Log())
    db.close()


@pytest.fixture
def stopped(svc, monkeypatch):
    """``stopped(res)``: Unpack returns ``res``; records any dispatch."""
    svc.dispatched = []
    monkeypatch.setattr(svc, "prescan_all", lambda *a, **k: [])
    monkeypatch.setattr(svc, "has_loose_osz", lambda: True)
    monkeypatch.setattr(svc, "_client_set_ids", lambda client: set())
    monkeypatch.setattr(svc, "_dispatch_to_client",
                        lambda *a, **k: svc.dispatched.append(a) or {"sent": 0})

    def set_result(res):
        monkeypatch.setattr(svc, "extract", lambda *a, **k: dict(res))
    return set_result


@pytest.mark.parametrize("ex", [NO_SPACE, DISK_FULL])
def test_unpack_and_import_sends_nothing(svc, stopped, ex):
    stopped(ex)
    res = svc.unpack_and_import(["lazer"])
    assert res == {"extract": ex, "imports": {}, "cancelled": False}
    assert svc.dispatched == []


def test_unpack_and_import_still_sends_after_a_clean_unpack(svc, stopped):
    stopped({"packs": 1, "tracks": 2})
    res = svc.unpack_and_import(["lazer"])
    assert "lazer" in res["imports"] and len(svc.dispatched) == 1


@pytest.mark.parametrize("ex,msg", [
    (NO_SPACE, str(diskspace.NotEnoughSpace("E:\\", 300 + diskspace.MARGIN, 5))),
    (DISK_FULL, "E:\\ is full: Unpack stopped")])
def test_unpack_job_fails_and_never_sends(svc, stopped, tmp_path, ex, msg):
    stopped(ex)
    job = svc.build_unpack_job(["lazer"])
    with pytest.raises(OSError) as ei:
        jobs.run_job_sync(job)
    exc = ei.value
    assert exc.errno == errno.ENOSPC and exc.strerror == msg
    assert "E:\\" in str(exc) and str(tmp_path) not in str(exc)
    assert job.state == State.FAILED
    assert [s.state for s in job.steps[:2]] == [State.DONE, State.FAILED]
    assert all(s.state != State.DONE for s in job.steps[2:])
    assert svc.dispatched == []
    assert job.ctx["extract"] == ex
    assert not crash_report.is_reportable(exc)


def test_unpack_job_keeps_staging_flag_out_of_the_message(svc, stopped):
    ex = {**NO_SPACE, "no_space": {**NO_SPACE["no_space"], "staging": True}}
    stopped(ex)
    with pytest.raises(OSError) as ei:
        jobs.run_job_sync(svc.build_unpack_job(["lazer"]))
    assert ei.value.strerror.startswith("Not enough free space on E:\\")


# -- loose .osz across drives ---------------------------------------------------
def _loose(svc, size=1000):
    p = svc.cfg.packs_path / LOOSE
    p.write_bytes(b"x" * size)
    return p


def test_loose_osz_across_drives_is_counted(svc, monkeypatch):
    loose = _loose(svc)
    out = Path(svc.cfg.output_path).resolve()

    def fake(path, need, margin=diskspace.MARGIN):
        p = Path(path).resolve()
        on_e = p == out or out in p.parents
        free = 500 + diskspace.MARGIN if on_e else 10_000 * MiB
        return diskspace.Space(free, 10_000 * MiB, free >= need + margin,
                               "E:\\" if on_e else "C:\\")
    monkeypatch.setattr(diskspace, "space", fake)
    res = svc.extract([])
    assert res["no_space"] == {"drive": "E:\\", "need": 1000 + diskspace.MARGIN,
                               "free": 500 + diskspace.MARGIN}
    assert loose.exists() and not (svc.cfg.output_path / LOOSE).exists()
    assert [w for w, _ in svc.log.warns] == ["extract:space"]


def test_loose_osz_on_the_same_drive_is_moved(svc, monkeypatch):
    loose = _loose(svc)
    monkeypatch.setattr(shutil, "disk_usage",
                        lambda p: _Usage(10_000 * MiB, 0, 500 + diskspace.MARGIN))
    res = svc.extract([])
    assert "no_space" not in res
    assert not loose.exists() and (svc.cfg.output_path / LOOSE).exists()
    assert res["loose"] == 1


def test_process_loose_osz_still_returns_an_int(svc):
    _loose(svc)
    n = svc.process_loose_osz()
    assert type(n) is int and n == 1
