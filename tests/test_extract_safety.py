# SPDX-License-Identifier: GPL-3.0-or-later
"""An archive is disposed only after a complete extract; corrupt archives are
skipped, nothing is deleted for good, and "Remove already-added" removes only
archives whose every beatmap is in the database (issue #15)."""
import os
import zipfile

import pytest

from rosu import client_remove, config, extractor, parsing
from rosu.db import Database
from rosu.services import Services


class Log:
    def __init__(self):
        self.warns = []

    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass

    def log(self, action, level="INFO", message="", **k):
        if level == "WARN":
            self.warns.append(k.get("detail", ""))


@pytest.fixture
def trashed(monkeypatch):
    calls = []
    monkeypatch.setattr("send2trash.send2trash", lambda p: calls.append(str(p)))
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda p: True)
    return calls


@pytest.fixture
def svc(tmp_path, trashed):
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    s = Services(cfg, db, Log())
    yield s
    db.close()


def _pack(svc, name="S1 - Pack.zip", entries=(("1 A - B.osz", 10), ("2 C - D.osz", 1000))):
    path = svc.cfg.packs_path / name
    with zipfile.ZipFile(path, "w") as z:
        for n, size in entries:
            z.writestr(n, b"x" * size)
    return path, parsing.parse_pack_name(name)


def test_cancel_midway_keeps_archive(svc, trashed):
    path, parsed = _pack(svc)
    seen = []
    res = svc.extract([(path, parsed)], progress=seen.append, cancel=lambda: len(seen) >= 1)
    assert path.exists() and str(path) not in trashed
    assert res["kept"] == 1 and res["tracks"] == 1
    assert any("cancelled" in w for w in svc.log.warns)


def test_one_bad_entry_keeps_archive(svc, trashed, monkeypatch):
    path, parsed = _pack(svc)
    monkeypatch.setattr(extractor, "_MAX_OSZ_BYTES", 100)   # "2 C - D.osz" is 1000
    res = svc.extract([(path, parsed)])
    assert path.exists() and str(path) not in trashed
    assert (svc.cfg.output_path / "1 A - B.osz").exists()
    assert not (svc.cfg.output_path / "2 C - D.osz").exists()
    assert res["tracks"] == 1 and res["kept"] == 1


def test_all_bad_entries_keep_archive(svc, trashed, monkeypatch):
    path, parsed = _pack(svc)
    monkeypatch.setattr(extractor, "_MAX_OSZ_BYTES", 1)
    res = svc.extract([(path, parsed)])
    assert path.exists() and str(path) not in trashed
    assert res["tracks"] == 0 and res["kept"] == 1


def test_clean_extract_disposes(svc, trashed, monkeypatch):
    path, parsed = _pack(svc)
    results = []
    real = extractor.extract_pack
    monkeypatch.setattr(extractor, "extract_pack",
                        lambda *a, **k: results.append(real(*a, **k)) or results[-1])
    res = svc.extract([(path, parsed)])
    assert trashed.count(str(path)) == 1
    assert results[0]["failed"] == 0 and results[0]["cancelled"] is False
    assert res["tracks"] == 2 and res["kept"] == 0


def test_unparsed_member_counts_as_failed(svc, tmp_path, monkeypatch):
    path, parsed = _pack(svc)
    real = extractor.parse_osz_entry
    monkeypatch.setattr(extractor, "parse_osz_entry",
                        lambda n, s=0: None if n.startswith("2 ") else real(n, s))
    res = extractor.extract_pack(path, parsed, tmp_path / "out", svc.db, "2026-01-01",
                                 read_meta=False, log=svc.log)
    assert res["tracks"] == 1 and res["failed"] == 1 and res["cancelled"] is False
    assert any("2 C - D.osz" in w for w in svc.log.warns)


def test_delete_setting_migrated_to_recycle(tmp_path):
    cfg = config._fill_defaults(config.Config(root=str(tmp_path), zip_disposal="delete"))
    assert cfg.zip_disposal == "recycle"
    assert "delete" not in config.ZIP_DISPOSAL


def test_remove_added_keeps_partly_known(svc, trashed):
    path, parsed = _pack(svc)
    svc.db.upsert_pack(parsed, 2, "2026-01-01")
    svc.db.upsert_track(parsing.parse_osz_entry("1 A - B.osz", 10), "2026-01-01", None)
    assert svc.pack_known(parsed.code)
    assert svc.remove_added_archives([path]) == {"removed": 0, "kept": 1}
    assert path.exists() and trashed == []
    assert svc.log.warns


def test_remove_added_disposes_fully_known(svc, trashed):
    path, parsed = _pack(svc)
    data = path.read_bytes()
    svc.extract([(path, parsed)])
    path.write_bytes(data)   # the stub "recycled" nothing; put it back in Packs anyway
    trashed.clear()
    assert svc.remove_added_archives([path]) == {"removed": 1, "kept": 0}
    assert trashed == [str(path)]


def test_remove_added_unreadable_kept(svc, trashed):
    path = svc.cfg.packs_path / "S9 - Bad.zip"
    path.write_bytes(os.urandom(256))
    assert svc.remove_added_archives([path]) == {"removed": 0, "kept": 1}
    assert path.exists() and trashed == []


def test_no_recycle_bin_disposes_nothing(svc, trashed, monkeypatch, tmp_path):
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda p: False)
    path, _ = _pack(svc)
    assert extractor.dispose_zip(path, "recycle", tmp_path / "Processed") == "ZIP_KEPT"
    assert path.exists()
    osz = [svc.cfg.output_path / f"{i} A - B.osz" for i in (1, 2)]
    for p in osz:
        p.write_bytes(b"osz")
    assert svc.clear_output() == 0
    assert all(p.exists() for p in osz)
    assert trashed == []
    assert svc.log.warns
    # dispose_archives does not count a kept archive as disposed
    assert svc.dispose_archives([path]) == 0 and path.exists()


def test_loose_osz_recycles_old_output_file(svc, trashed):
    old = svc.cfg.output_path / "5 E - F.osz"
    old.write_bytes(b"old")
    (svc.cfg.packs_path / "5 E - F.osz").write_bytes(b"new")
    assert svc.process_loose_osz() == 1
    assert trashed == [str(old)]
    assert old.read_bytes() == b"new" and not (svc.cfg.packs_path / "5 E - F.osz").exists()


def test_loose_osz_without_recycle_bin_stays(svc, trashed, monkeypatch):
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda p: False)
    old = svc.cfg.output_path / "5 E - F.osz"
    old.write_bytes(b"old")
    loose = svc.cfg.packs_path / "5 E - F.osz"
    loose.write_bytes(b"new")
    assert svc.process_loose_osz() == 0
    assert loose.read_bytes() == b"new" and old.read_bytes() == b"old"
    assert trashed == [] and svc.log.warns


def test_corrupt_archive_does_not_block_unpack(svc):
    bad = svc.cfg.packs_path / "S1 - Bad.zip"
    bad.write_bytes(os.urandom(512))
    good, good_parsed = _pack(svc, "S2 - Good.zip", (("7 G - H.osz", 10),))
    plans = svc.prescan_all()
    assert [p.zip_path for p in plans] == [str(good)]
    res = svc.extract([(bad, parsing.parse_pack_name(bad.name)), (good, good_parsed)])
    assert (svc.cfg.output_path / "7 G - H.osz").exists()
    assert bad.exists() and not (svc.cfg.root_path / "Quarantine" / bad.name).exists()
    assert res["kept"] >= 1 and res["rejected"] == []
