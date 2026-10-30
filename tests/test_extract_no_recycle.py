# SPDX-License-Identifier: GPL-3.0-or-later
"""extract() keeps and reports a clean pack whose drive has no Recycle Bin
(dispose_zip returns ZIP_KEPT) instead of logging it as disposed (issue #15)."""
import zipfile

from rosu import client_remove, config, parsing
from rosu.db import Database
from rosu.services import Services


class Log:
    def __init__(self):
        self.actions, self.warns = [], []

    def info(self, action, **k):
        self.actions.append(action)

    def error(self, *a, **k):
        pass

    def log(self, action, level="INFO", message="", **k):
        if level == "WARN":
            self.warns.append(k.get("detail", ""))


def test_extract_keeps_pack_without_recycle_bin(tmp_path, monkeypatch):
    trashed = []
    monkeypatch.setattr("send2trash.send2trash", lambda p: trashed.append(str(p)))
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda p: False)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    svc = Services(cfg, db, Log())
    path = cfg.packs_path / "S1 - Pack.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("1 A - B.osz", b"x" * 10)
        z.writestr("2 C - D.osz", b"x" * 10)

    res = svc.extract([(path, parsing.parse_pack_name(path.name))])

    assert path.exists() and trashed == []
    assert res["kept"] == 1 and res["tracks"] == 2
    assert any("no Recycle Bin" in w for w in svc.log.warns)
    assert "ZIP_KEPT" not in svc.log.actions and "ZIP_TRASHED" not in svc.log.actions
    db.close()
