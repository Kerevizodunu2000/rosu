# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the stable/lazer import-target split (item C, v1.0)."""
from rosu import client_import, config, osu_import
from rosu.db import Database
from rosu.services import Services


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


# -- config migration + stable detection ---------------------------------------
def test_legacy_osu_exe_migrates_to_lazer():
    cfg = config.Config(osu_exe="C:/old/osu!.exe")
    config._fill_defaults(cfg)
    assert cfg.osu_lazer_exe == "C:/old/osu!.exe"
    assert cfg.osu_exe == "C:/old/osu!.exe"          # legacy field mirrored


def test_lazer_exe_not_overwritten_by_legacy():
    cfg = config.Config(osu_exe="C:/legacy.exe", osu_lazer_exe="C:/lazer.exe")
    config._fill_defaults(cfg)
    assert cfg.osu_lazer_exe == "C:/lazer.exe"


def test_detect_stable_exe_found(tmp_path, monkeypatch):
    base = tmp_path / "osu!"
    base.mkdir()
    (base / "osu!.exe").write_bytes(b"")
    monkeypatch.setattr(client_import, "stable_install_dir", lambda: base)
    assert config.detect_stable_exe() == str(base / "osu!.exe")


def test_detect_stable_exe_missing(monkeypatch):
    monkeypatch.setattr(client_import, "stable_install_dir", lambda: None)
    assert config.detect_stable_exe() == ""


# -- import_osu(target) launches the right client ------------------------------
def _make_services(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.ensure_dirs()
    cfg.osu_lazer_exe = "C:/lazer/osu!.exe"
    cfg.osu_stable_exe = "C:/stable/osu!.exe"
    db = Database(cfg.db_path)
    return cfg, db, Services(cfg, db, DummyLog())


def _capture_exe(monkeypatch):
    captured = {}

    def fake_import_files(exe, files, **kw):
        captured["exe"] = exe
        return {"files": 0, "batches": 0, "sent": 0, "cancelled": False}

    monkeypatch.setattr(osu_import, "import_files", fake_import_files)
    return captured


def test_import_osu_defaults_to_lazer(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path)
    captured = _capture_exe(monkeypatch)
    svc.import_osu()
    assert captured["exe"] == "C:/lazer/osu!.exe"
    db.close()


def test_import_osu_target_stable(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path)
    captured = _capture_exe(monkeypatch)
    svc.import_osu(target="stable")
    assert captured["exe"] == "C:/stable/osu!.exe"
    db.close()
