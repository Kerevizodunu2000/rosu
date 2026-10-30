# SPDX-License-Identifier: GPL-3.0-or-later
"""Import to osu! checks the free space for the staged copies and the client's
own folder before staging anything, and passes a refusal on (issue #46)."""
import shutil
from collections import namedtuple
from pathlib import Path

import pytest

from rosu import client_import, config, diskspace, jobs, osu_import
from rosu.db import Database
from rosu.services import Services, import_svc

MiB = 1024 * 1024
_Usage = namedtuple("_Usage", "total used free")
DATA = {"1 A - B.osz": b"A" * 100, "2 C - D.osz": b"B" * 200}
TOTAL = 300


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
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    cfg.stable_enabled = True
    cfg.osu_lazer_exe = str(tmp_path / "lazer.exe")
    install = tmp_path / "stable_install"
    install.mkdir()
    (install / "osu!.exe").write_bytes(b"")
    cfg.osu_stable_exe = str(install / "osu!.exe")
    for name, data in DATA.items():
        (cfg.output_path / name).write_bytes(data)
    (tmp_path / "lazerdata").mkdir()
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: None)
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: tmp_path / "lazerdata")
    db = Database(cfg.db_path)
    s = Services(cfg, db, Log())
    s.sent, s.flagged = [], []

    def fake_import(exe, files, **kw):
        s.sent.append(list(files))
        return {"files": len(files), "batches": 1, "sent": len(files), "cancelled": False}
    monkeypatch.setattr(osu_import, "import_files", fake_import)
    monkeypatch.setattr(db, "set_in_osu", lambda bid, client: s.flagged.append(bid))
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


def _files(svc):
    return osu_import.output_osz_files(svc.cfg.output_path)


def _refused(svc, res, tmp_path, drive, need):
    assert res == {"no_space": {"drive": drive, "need": need, "free": res["no_space"]["free"]},
                   "sent": 0, "files": 0, "batches": 0, "stage_failed": 0,
                   "disk_full": False}
    assert svc.sent == [] and svc.flagged == []
    assert [w for w, _ in svc.log.warns] == ["import:space"]
    assert all(str(tmp_path) not in d and str(tmp_path.resolve()) not in d
               for _, d in svc.log.warns)


def test_is_disk_full_is_the_shared_helper():
    assert import_svc._is_disk_full is diskspace.is_disk_full


def test_stable_refused_when_stage_and_songs_share_the_drive(svc, tmp_path, monkeypatch):
    _free(monkeypatch, TOTAL + diskspace.MARGIN)   # one copy fits, two don't
    res = svc._dispatch_to_client("stable", _files(svc))
    _refused(svc, res, tmp_path, tmp_path.resolve().anchor, 2 * TOTAL + diskspace.MARGIN)
    stage = tmp_path / "stable_install" / "_rosu_import"
    assert not stage.exists() or not list(stage.glob("*.osz"))


def test_stable_uses_custom_songs_folder(svc, tmp_path, monkeypatch):
    songs = tmp_path / "songs_elsewhere"
    songs.mkdir()
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    _two_drives(monkeypatch, songs, TOTAL - 1 + diskspace.MARGIN)
    res = svc._dispatch_to_client("stable", _files(svc))
    _refused(svc, res, tmp_path, "E:\\", TOTAL + diskspace.MARGIN)


def test_stable_goes_ahead_with_room(svc, monkeypatch):
    _free(monkeypatch, 2 * TOTAL + diskspace.MARGIN)
    res = svc._dispatch_to_client("stable", _files(svc))
    assert "no_space" not in res and res["sent"] == 2
    assert len(svc.sent[0]) == 2 and sorted(svc.flagged) == [1, 2]


def test_stable_without_install_folder_skips_the_check(svc, tmp_path, monkeypatch):
    svc.cfg.osu_stable_exe = str(tmp_path / "missing" / "osu!.exe")
    _free(monkeypatch, 0)
    res = svc._dispatch_to_client("stable", _files(svc))
    assert "no_space" not in res and res["files"] == 0 and res["stage_failed"] == 2


def test_lazer_refused_when_stage_and_data_share_the_drive(svc, tmp_path, monkeypatch):
    _free(monkeypatch, TOTAL + diskspace.MARGIN)
    res = svc._dispatch_to_client("lazer", _files(svc))
    _refused(svc, res, tmp_path, tmp_path.resolve().anchor, 2 * TOTAL + diskspace.MARGIN)
    stage = svc.cfg.data_path / "_import_stage"
    assert not stage.exists() or not list(stage.glob("*.osz"))


def test_lazer_refused_when_only_the_data_drive_is_short(svc, tmp_path, monkeypatch):
    _two_drives(monkeypatch, tmp_path / "lazerdata", TOTAL - 1 + diskspace.MARGIN)
    res = svc._dispatch_to_client("lazer", _files(svc))
    _refused(svc, res, tmp_path, "E:\\", TOTAL + diskspace.MARGIN)


def test_lazer_goes_ahead_with_room(svc, tmp_path, monkeypatch):
    _two_drives(monkeypatch, tmp_path / "lazerdata", TOTAL + diskspace.MARGIN)
    res = svc._dispatch_to_client("lazer", _files(svc))
    assert "no_space" not in res and res["sent"] == 2 and len(svc.sent[0]) == 2


def test_lazer_without_data_folder_checks_only_the_stage(svc, monkeypatch):
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: None)
    _free(monkeypatch, TOTAL + diskspace.MARGIN)
    res = svc._dispatch_to_client("lazer", _files(svc))
    assert "no_space" not in res and res["sent"] == 2


# -- pass-through ----------------------------------------------------------------
NO_SPACE = {"drive": "E:\\", "need": 5, "free": 1}
REFUSED = {"no_space": NO_SPACE, "sent": 0, "files": 0, "batches": 0,
           "stage_failed": 0, "disk_full": False}
FULL = {"sent": 1, "files": 1, "batches": 1, "cancelled": False,
        "stage_failed": 1, "disk_full": True}


@pytest.fixture
def dispatch(svc, tmp_path, monkeypatch):
    osz = tmp_path / "x.osz"
    osz.write_bytes(b"x")
    monkeypatch.setattr(svc, "_client_set_ids", lambda client: set())
    monkeypatch.setattr(svc, "_export_client_sets",
                        lambda *a, **k: ([osz], 0))
    (tmp_path / "lazer.exe").write_bytes(b"")
    lib = svc.cfg.library_path / "1 A - B.osz"
    lib.write_bytes(b"x")
    monkeypatch.setattr(svc.db, "library_tracks",
                        lambda: [{"filename": lib.name, "beatmapset_id": 1}])

    def set_result(res):
        monkeypatch.setattr(svc, "_dispatch_to_client", lambda *a, **k: dict(res))
    return set_result


@pytest.mark.parametrize("res,want", [(REFUSED, {"no_space": NO_SPACE, "disk_full": False}),
                                      (FULL, {"disk_full": True})])
def test_results_pass_space_on(svc, dispatch, res, want):
    dispatch(res)
    for out in (svc.transfer_between_clients("stable", "lazer"),
                jobs.run_job_sync(svc.build_transfer_job("stable", "lazer")),
                svc.send_library_to_client("lazer", skip_existing=False)):
        assert {k: out[k] for k in ("no_space", "disk_full") if k in out} == want
