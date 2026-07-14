# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for Services.output_listing — the Dashboard Output view (item D, v1.0)."""
from rosu import config
from rosu.db import Database
from rosu.services import Services


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def _svc(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    return cfg, db, Services(cfg, db, DummyLog())


def test_output_listing_empty(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    assert svc.output_listing() == []
    db.close()


def test_output_listing_reports_name_and_size(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    (cfg.output_path / "123 A - B.osz").write_bytes(b"x" * 10)
    (cfg.output_path / "456 C - D.osz").write_bytes(b"y" * 20)
    (cfg.output_path / "notes.txt").write_bytes(b"ignore")  # non-.osz is ignored
    listing = svc.output_listing()
    sizes = {r["name"]: r["size_bytes"] for r in listing}
    assert sizes == {"123 A - B.osz": 10, "456 C - D.osz": 20}
    db.close()
