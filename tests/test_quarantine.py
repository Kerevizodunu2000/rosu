# SPDX-License-Identifier: GPL-3.0-or-later
"""Quarantine safety for rejected (unsafe) archives (item A hardening, v1.0).

Verifies the post-review fix: a rejected pack is MOVED aside (works across
drives via shutil.move) and a previously quarantined file of the same name is
never overwritten or deleted.
"""
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


def test_quarantine_moves_file_out_of_packs(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    src = cfg.packs_path / "S1 - Bad.zip"
    src.write_bytes(b"bomb")
    dest = svc._quarantine(src)
    assert dest is not None and dest.exists()
    assert not src.exists()                                # moved, not copied
    assert dest.parent == cfg.root_path / "Quarantine"
    db.close()


def test_quarantine_never_overwrites_a_prior_file(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    first = cfg.packs_path / "S1 - Bad.zip"
    first.write_bytes(b"first")
    d1 = svc._quarantine(first)
    # a second, distinct unsafe archive re-uses the same filename
    second = cfg.packs_path / "S1 - Bad.zip"
    second.write_bytes(b"second")
    d2 = svc._quarantine(second)
    assert d1 != d2                                        # collision-free name
    assert d1.read_bytes() == b"first"                    # original preserved
    assert d2.read_bytes() == b"second"
    db.close()


def test_dispose_move_never_clobbers_a_prior_archive(tmp_path):
    # extractor.dispose_zip 'move' used to unlink whatever sat at the destination;
    # two different packs with the same name must both survive in Processed/.
    from rosu import extractor
    packs = tmp_path / "Packs"
    packs.mkdir()
    processed = tmp_path / "Processed"
    a = packs / "S1 - Pack.zip"
    a.write_bytes(b"first-pack")
    assert extractor.dispose_zip(a, "move", processed) == "ZIP_MOVED"
    b = packs / "S1 - Pack.zip"           # different content, same name, later run
    b.write_bytes(b"second-pack")
    assert extractor.dispose_zip(b, "move", processed) == "ZIP_MOVED"
    kept = sorted(p.read_bytes() for p in processed.glob("*.zip"))
    assert kept == [b"first-pack", b"second-pack"]   # neither was clobbered
