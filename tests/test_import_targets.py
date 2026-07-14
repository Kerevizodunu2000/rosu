# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the stable/lazer import-target split (item C, v1.0)."""
from rosu import client_import, config, library, osu_import
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
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: None)  # skip staging
    svc.import_osu(target="stable")
    assert captured["exe"] == "C:/stable/osu!.exe"
    db.close()


def test_batches_single_file_mode():
    from pathlib import Path
    files = [Path(f"{i} A - B.osz") for i in range(5)]
    # osu!(stable): one file per launch; osu!lazer: batched together
    assert len(osu_import.batches(files, 1)) == 5
    assert len(osu_import.batches(files)) == 1


def _capture_kwargs(monkeypatch):
    captured = {}

    def fake_import_files(exe, files, **kw):
        captured.update(kw)
        return {"files": 0, "batches": 0, "sent": 0, "cancelled": False}

    monkeypatch.setattr(osu_import, "import_files", fake_import_files)
    return captured


def test_import_osu_stable_sends_one_file_per_launch(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path)
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: None)  # skip staging
    kw = _capture_kwargs(monkeypatch)
    svc.import_osu(target="stable")
    assert kw.get("max_batch_files") == 1     # the "Error moving file" fix
    db.close()


def test_import_osu_lazer_uses_default_batching(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path)
    kw = _capture_kwargs(monkeypatch)
    svc.import_osu(target="lazer")
    assert "max_batch_files" not in kw        # many files per launch (default)
    db.close()


def test_stage_for_stable_falls_back_without_songs(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path)
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: None)
    files = [tmp_path / "a.osz", tmp_path / "b.osz"]
    assert svc._stage_for_stable(files) == files
    db.close()


def test_stage_for_stable_uses_exe_install_dir(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path)
    install = tmp_path / "custom_osu"          # a custom install path (not %LOCALAPPDATA%)
    install.mkdir()
    exe = install / "osu!.exe"
    exe.write_bytes(b"")
    src = cfg.output_path / "777 A - B.osz"
    src.write_bytes(b"osz")
    staged = svc._stage_for_stable([src], str(exe))
    assert staged[0].parent == install / "_rosu_import"
    assert staged[0].exists() and src.exists()   # copied to the install drive
    db.close()


def test_stage_for_stable_copies_to_songs_drive(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path)
    songs = tmp_path / "osu!" / "Songs"
    songs.mkdir(parents=True)
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    src = cfg.output_path / "555 A - B.osz"
    src.write_bytes(b"osz")
    staged = svc._stage_for_stable([src])
    assert len(staged) == 1
    assert staged[0].parent == songs.parent / "_rosu_import"
    assert staged[0].exists()
    assert src.exists()          # Output preserved (copied, not moved)
    db.close()


def test_import_from_osu_client_marks_in_osu(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    (cfg.output_path / "321 X - Y.osz").write_bytes(b"osz")
    library.copy_to_library(cfg.output_path, cfg.library_path, db, "when",
                            physical_copy=True, source_label="local_osu_lazer")
    row = db.find_track_row(321, "")
    assert row["in_osu"] == 1 and row["in_osu_lazer"] == 1 and row["in_osu_stable"] == 0
    db.close()


def test_import_from_stable_marks_stable(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    (cfg.output_path / "654 P - Q.osz").write_bytes(b"osz")
    library.copy_to_library(cfg.output_path, cfg.library_path, db, "when",
                            physical_copy=True, source_label="local_osu_stable")
    row = db.find_track_row(654, "")
    assert row["in_osu_stable"] == 1 and row["in_osu_lazer"] == 0
    db.close()
