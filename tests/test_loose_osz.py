# SPDX-License-Identifier: GPL-3.0-or-later
"""Loose .osz dropped straight into Packs go straight to Output, tagged 'Direct'
(fixes the "no archive found" dead-end when a user adds .osz directly)."""
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


def test_has_loose_osz(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    assert svc.has_loose_osz() is False
    (cfg.packs_path / "111 A - B.osz").write_bytes(b"osz")
    assert svc.has_loose_osz() is True
    db.close()


def test_process_loose_osz_moves_and_tags_direct(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    (cfg.packs_path / "424242 Artist - Title.osz").write_bytes(b"osz")
    moved = svc.process_loose_osz()
    assert moved == 1
    assert not (cfg.packs_path / "424242 Artist - Title.osz").exists()   # left Packs
    assert (cfg.output_path / "424242 Artist - Title.osz").exists()      # now in Output
    assert db.get_pack_by_code("Direct") is not None                     # 'Direct' source
    rows = [dict(db.find_track_row(424242, ""))]
    db.attach_sources_bulk(rows)
    assert "Direct" in rows[0]["sources"]
    db.close()
