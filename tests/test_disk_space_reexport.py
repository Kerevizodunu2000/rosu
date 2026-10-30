# SPDX-License-Identifier: GPL-3.0-or-later
"""Export checks the temp drive before re-exporting a client's sets into it."""
import os
import shutil
import tempfile
from collections import namedtuple

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu import client_import, config, diskspace, jobs
from rosu.db import Database
from rosu.services import Services

MiB = 1024 * 1024
_Usage = namedtuple("_Usage", "total used free")
STABLE, LAZER = 1000, 2000


class Log:
    def __init__(self):
        self.warns = []

    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass

    def log(self, action, level="INFO", message="", **k):
        if level == "WARN":
            self.warns.append(k.get("where"))


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "temp"))
    (tmp_path / "temp").mkdir()
    songs, lazer = tmp_path / "Songs", tmp_path / "lazer"
    (songs / "1 A - B").mkdir(parents=True)
    (songs / "1 A - B" / "a.osu").write_bytes(b"x" * STABLE)
    (lazer / "files" / "ab").mkdir(parents=True)
    (lazer / "files" / "ab" / "h1").write_bytes(b"x" * LAZER)
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: lazer)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path / "app")))
    cfg.ensure_dirs()
    cfg.stable_enabled = cfg.lazer_enabled = True
    db = Database(cfg.db_path)
    s = Services(cfg, db, Log())
    s.client_calls = []
    monkeypatch.setattr(s, "_export_client_sets",
                        lambda *a, **k: s.client_calls.append(a) or ([], 0))
    yield s
    db.close()


def _free(monkeypatch, n):
    monkeypatch.setattr(shutil, "disk_usage", lambda p: _Usage(10_000 * MiB, 0, n))


def _stage_files(tmp_path):
    return [p for p in (tmp_path / "temp").rglob("*") if p.is_file()]


NEED = {"stable": STABLE, "lazer": LAZER, "merged": STABLE + LAZER}


@pytest.mark.parametrize("source", ["stable", "lazer", "merged"])
def test_export_refused_before_anything_is_written(svc, tmp_path, monkeypatch, source):
    free = NEED[source] + diskspace.MARGIN - 1
    _free(monkeypatch, free)
    res = svc.export_sets(source, tmp_path / "out" / "exp")
    ns = res["no_space"]
    assert res["count"] == 0 and res["archives"] == []
    assert ns == {"drive": tmp_path.resolve().anchor, "need": NEED[source] + diskspace.MARGIN,
                  "free": free, "reexport": True}
    assert svc.client_calls == [] and _stage_files(tmp_path) == []
    assert svc.log.warns == ["export:space"]
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("source", ["stable", "lazer", "merged"])
def test_export_job_refused_has_no_space(svc, tmp_path, monkeypatch, source):
    _free(monkeypatch, NEED[source] + diskspace.MARGIN - 1)
    job = svc.build_export_job(source, tmp_path / "out" / "exp")
    res = jobs.run_job_sync(job)
    assert res["no_space"]["reexport"] is True and res["count"] == 0
    assert res["archives"] == [] and svc.client_calls == []
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("source", ["stable", "lazer", "merged"])
def test_export_runs_when_it_fits_exactly(svc, tmp_path, monkeypatch, source):
    _free(monkeypatch, NEED[source] + diskspace.MARGIN)
    res = svc.export_sets(source, tmp_path / "out" / "exp")
    assert "no_space" not in res and svc.client_calls


@pytest.mark.parametrize("source", ["library", "drive"])
def test_library_and_drive_never_walk_the_clients(svc, tmp_path, monkeypatch, source):
    calls = []
    monkeypatch.setattr(diskspace, "tree_size", lambda *a, **k: calls.append(a) or 10**12)
    _free(monkeypatch, 0)
    res = svc.export_sets(source, tmp_path / "out" / "exp")
    assert calls == [] and "no_space" not in res


def test_unreadable_temp_drive_does_not_refuse(svc, tmp_path, monkeypatch):
    def boom(p):
        raise OSError("gone")
    monkeypatch.setattr(shutil, "disk_usage", boom)
    res = svc.export_sets("merged", tmp_path / "out" / "exp")
    assert "no_space" not in res and svc.client_calls


def test_disabled_or_missing_client_adds_nothing(svc, tmp_path, monkeypatch):
    svc.cfg.lazer_enabled = False
    _free(monkeypatch, STABLE + diskspace.MARGIN)   # room for stable only
    assert "no_space" not in svc.export_sets("merged", tmp_path / "out" / "exp")
    svc.cfg.stable_enabled = False
    _free(monkeypatch, 0)
    assert "no_space" not in svc.export_sets("stable", tmp_path / "out" / "exp")
    svc.cfg.stable_enabled = svc.cfg.lazer_enabled = True
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: None)
    assert svc._reexport_no_space("lazer", tmp_path / "temp") is None


def test_no_space_text_names_the_reexport_folder():
    from rosu.i18n import I18N
    from rosu.ui.dashboard_tab import no_space_text
    ns = {"drive": "E:\\", "need": 300 * MiB, "free": 10 * MiB}
    i18n = I18N()
    texts = {}
    for lang in ("en", "tr"):
        i18n.set_language(lang)
        texts[lang] = no_space_text(i18n.t, {**ns, "reexport": True})
        assert "E:\\" in texts[lang]
        assert texts[lang] == i18n.t("disk_no_space_reexport", drive="E:\\",
                                     need="300.0 MB", free="10.0 MB")
        assert no_space_text(i18n.t, ns) == i18n.t("disk_no_space", drive="E:\\",
                                                   need="300.0 MB", free="10.0 MB")
    assert texts["en"] != texts["tr"]
