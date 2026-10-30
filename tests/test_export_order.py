# SPDX-License-Identifier: GPL-3.0-or-later
"""Export source order: the string sort key must match ``Path`` order (one folder)."""
import zipfile

from rosu import config
from rosu.db import Database
from rosu.services import Services

NAMES = ["10 A - B.osz", "2 C - D.osz", "b.osz", "A.osz"]
EXPECTED = ["10 A - B.osz", "2 C - D.osz", "A.osz", "b.osz"]


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def _svc(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.stable_enabled = True
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    return cfg, db, Services(cfg, db, DummyLog())


def _add_lib(db, bid, filename, *, in_drive=0):
    db._conn.execute(
        "INSERT INTO tracks(beatmapset_id, filename, display_name, in_library, "
        "library_status, in_drive) VALUES(?,?,?,1,'present',?)",
        (bid, filename, f"Artist - {bid}", in_drive))
    db._conn.commit()


def _write(cfg, names):
    for n in names:
        (cfg.library_path / n).write_bytes(b"x" * 10)


def test_library_source_order(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _write(cfg, NAMES)
    got = svc._gather_export_sources("library", tmp_path / "stage")
    assert [p.name for p in got] == EXPECTED
    assert got == sorted(cfg.library_path.glob("*.osz"))
    db.close()


def test_drive_source_order(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _write(cfg, NAMES + ["z.osz"])
    for i, n in enumerate(NAMES):
        _add_lib(db, i + 1, n, in_drive=1)
    _add_lib(db, 99, "z.osz", in_drive=0)
    got = svc._gather_export_sources("drive", tmp_path / "stage")
    assert [p.name for p in got] == EXPECTED
    assert got == sorted(cfg.library_path / n for n in NAMES)
    db.close()


def test_export_zip_member_order(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    _write(cfg, NAMES)
    res = svc.export_sets("library", tmp_path / "out" / "X", fmt="zip")
    assert len(res["archives"]) == 1
    with zipfile.ZipFile(res["archives"][0]) as z:
        assert z.namelist() == EXPECTED
    db.close()
