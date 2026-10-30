# SPDX-License-Identifier: GPL-3.0-or-later
"""PRUNE_ERROR lines use the real LogService signature and leak no path."""
import zipfile

from rosu import client_import, config, prune
from rosu.db import Database
from rosu.logsvc import LogService
from rosu.services import Services


def _env(tmp_path):
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    return cfg, Services(cfg, db, LogService(tmp_path / "logs"))


def _lines(svc):
    return svc.log._log_file().read_text(encoding="utf-8").splitlines()


def test_prune_library_error_is_logged(tmp_path, monkeypatch):
    cfg, svc = _env(tmp_path)
    name = "1 A - B.osz"
    with zipfile.ZipFile(cfg.library_path / name, "w") as zf:
        zf.writestr("a.osu", b"x")

    def boom(p, mode="video_only"):
        raise OSError(f"cannot write {p}")
    monkeypatch.setattr(prune, "prune_osz", boom)
    res = svc.prune_library(names=[name])
    assert res["pruned"] == 0
    text = "\n".join(_lines(svc))
    line = [ln for ln in text.splitlines() if "PRUNE_ERROR" in ln]
    assert len(line) == 1 and name in line[0] and "OSError" in line[0]
    assert str(cfg.library_path) not in text


def test_prune_stable_error_is_logged(tmp_path, monkeypatch):
    cfg, svc = _env(tmp_path)
    songs = tmp_path / "Songs"
    songs.mkdir()
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)

    def boom(*a, **k):
        raise OSError(f"cannot write {songs}")
    monkeypatch.setattr(prune, "prune_folder", boom)
    res = svc.prune_stable(["77 Folder"])
    assert res["pruned"] == 0
    text = "\n".join(_lines(svc))
    line = [ln for ln in text.splitlines() if "PRUNE_ERROR" in ln]
    assert len(line) == 1 and "77 Folder" in line[0] and "OSError" in line[0]
    assert str(songs) not in text
