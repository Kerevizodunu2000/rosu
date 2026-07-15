# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for rosu.health (pure) + the Services health/verify integration."""
from rosu import config, health
from rosu.db import Database
from rosu.drive.bundle import sha256_file
from rosu.services import Services


# -- pure logic --------------------------------------------------------------
def test_disk_usage():
    assert health.disk_usage({}) == {"files": 0, "total_bytes": 0}
    assert health.disk_usage({"a.osz": 100, "b.osz": 250}) == {
        "files": 2, "total_bytes": 350}


def test_biggest_sets_orders_annotates_and_caps():
    rows = [{"filename": "a.osz", "display_name": "Artist - A"}]
    disk = {"a.osz": 300, "b.osz": 300, "c.osz": 900}
    out = health.biggest_sets(rows, disk, n=2)
    assert [s["filename"] for s in out] == ["c.osz", "a.osz"]   # size desc, tie→name
    assert out[1]["display_name"] == "Artist - A"               # annotated from DB
    assert out[0]["display_name"] is None                       # unknown → None


def test_scrub_classifies_present_orphan_dead_and_memory():
    rows = [
        {"filename": "a.osz", "in_library": 1, "library_status": "present",
         "display_name": "A"},                                  # present on disk
        {"filename": "b.osz", "in_library": 1, "library_status": "present"},  # dead
        {"filename": "c.osz", "in_library": 0, "library_status": "memory"},   # memory
    ]
    disk = {"a.osz": 100, "orphan.osz": 50}
    res = health.scrub(rows, disk)
    assert res["present"] == 1
    assert res["orphans"] == ["orphan.osz"]
    assert [r["filename"] for r in res["dead_links"]] == ["b.osz"]
    assert res["memory"] == 1


def test_verify_classify():
    assert health.verify_classify("abc", "abc") == "ok"
    assert health.verify_classify("abc", "xyz") == "mismatch"
    assert health.verify_classify("abc", None) == "unhashed"
    assert health.verify_classify("abc", "") == "unhashed"


# -- Services integration ----------------------------------------------------
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


def _add(db, bid, filename, *, drive_hash=None, size=0):
    db._conn.execute(
        "INSERT INTO tracks(beatmapset_id, filename, display_name, in_library, "
        "library_status, drive_hash, size_bytes) VALUES(?,?,?,1,'present',?,?)",
        (bid, filename, f"Artist - {bid}", drive_hash, size))
    db._conn.commit()


def test_verify_library_classifies_each_case(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    good = cfg.library_path / "good.osz"
    good.write_bytes(b"good-bytes")
    bad = cfg.library_path / "bad.osz"
    bad.write_bytes(b"bad-bytes")
    new = cfg.library_path / "new.osz"
    new.write_bytes(b"new-bytes")

    _add(db, 1, "good.osz", drive_hash=sha256_file(good))   # matches → ok
    _add(db, 2, "bad.osz", drive_hash="0" * 64)             # wrong hash → mismatch
    _add(db, 3, "new.osz", drive_hash=None)                 # never backed up → unhashed
    _add(db, 4, "gone.osz", drive_hash="abc")               # no file → missing

    res = svc.verify_library()
    assert res["checked"] == 3
    assert res["ok"] == 1
    assert res["mismatch"] == 1 and res["mismatches"] == ["bad.osz"]
    assert res["unhashed"] == 1
    assert res["missing"] == 1
    assert res["cancelled"] is False
    db.close()


def test_verify_library_respects_max_files(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    for i in range(5):
        f = cfg.library_path / f"{i}.osz"
        f.write_bytes(b"x" * (i + 1))
        _add(db, i, f.name, drive_hash=sha256_file(f))
    res = svc.verify_library(max_files=2)
    assert res["checked"] == 2
    db.close()


def test_library_health_reports_usage_scrub_and_biggest(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "small.osz").write_bytes(b"x" * 100)
    (cfg.library_path / "big.osz").write_bytes(b"y" * 900)
    (cfg.library_path / "orphan.osz").write_bytes(b"z" * 10)   # on disk, no DB row
    (cfg.library_path / "mem.osz").write_bytes(b"m" * 5)       # re-added memory set
    _add(db, 1, "small.osz")
    _add(db, 2, "big.osz")
    _add(db, 3, "gone.osz")                                    # DB row, no file → dead
    db._conn.execute(                                          # purged, file re-added
        "INSERT INTO tracks(beatmapset_id, filename, display_name, in_library, "
        "library_status) VALUES(5,'mem.osz','Artist - mem',0,'memory')")
    db._conn.commit()

    rep = svc.library_health()
    assert rep["usage"]["files"] == 4
    assert rep["usage"]["total_bytes"] == 1015
    assert rep["scrub"]["present"] == 3                        # small, big, mem
    assert rep["scrub"]["orphans"] == ["orphan.osz"]           # mem.osz NOT an orphan
    assert rep["scrub"]["memory"] == 1
    assert [r["filename"] for r in rep["scrub"]["dead_links"]] == ["gone.osz"]
    assert rep["biggest"][0]["filename"] == "big.osz"         # largest first
    db.close()
