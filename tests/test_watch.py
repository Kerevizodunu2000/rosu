# SPDX-License-Identifier: GPL-3.0-or-later
"""Watch folder (v1.9): only new, settled .osz files; never the user's files."""
import os
import zipfile

from rosu import config, watch
from rosu.db import Database
from rosu.services import Services


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def _osz(path, title="T"):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"A - {title} [x].osu", f"osu file format v14\n[Metadata]\nTitle:{title}\nArtist:A\n")
    return path


def test_only_new_settled_osz_files_are_ready(tmp_path):
    _osz(tmp_path / "1 old.osz")
    seen = watch.baseline(tmp_path)                    # watching starts now
    (tmp_path / "notes.txt").write_text("x")
    _osz(tmp_path / "2 new.osz")
    take, prev, pending = watch.ready(tmp_path, seen, {})
    assert take == [] and pending                      # first look: not settled yet
    take, prev, pending = watch.ready(tmp_path, seen, prev)
    assert [p.name for p in take] == ["2 new.osz"] and not pending
    with open(tmp_path / "2 new.osz", "ab") as fh:     # still being written
        fh.write(b"more")
    os.utime(tmp_path / "2 new.osz", ns=(10**18, 10**18))
    take, _prev, pending = watch.ready(tmp_path, seen, prev)
    assert take == [] and pending


def test_state_belongs_to_one_folder(tmp_path):
    state = tmp_path / "data" / "watch_state.json"
    watch.save_state(state, tmp_path / "a", {"x|1|2"})
    assert list(watch.load_state(state, tmp_path / "a")) == ["x|1|2"]
    assert watch.load_state(state, tmp_path / "b") is None
    state.write_text("{broken", encoding="utf-8")
    assert watch.load_state(state, tmp_path / "a") is None


def test_state_keeps_the_newest_keys_in_order(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "MAX_SEEN", 3)
    state = tmp_path / "watch_state.json"
    watch.save_state(state, tmp_path, dict.fromkeys(["a", "b", "c", "d", "e"]))
    assert list(watch.load_state(state, tmp_path)) == ["c", "d", "e"]


def test_ready_takes_big_catch_ups_in_batches(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "BATCH_FILES", 2)
    for i in range(5):
        _osz(tmp_path / f"{i}.osz")
    _t, prev, _p = watch.ready(tmp_path, {}, {})
    take, prev, pending = watch.ready(tmp_path, {}, prev)
    assert [p.name for p in take] == ["0.osz", "1.osz"] and pending
    busy = {watch.key(p.name, *prev[p.name]) for p in take}
    take, prev, pending = watch.ready(tmp_path, {}, prev, busy)
    assert [p.name for p in take] == ["2.osz", "3.osz"] and pending


def test_ready_skips_empty_files(tmp_path):
    (tmp_path / "zero.osz").write_bytes(b"")
    _t, prev, _p = watch.ready(tmp_path, {}, {})
    take, _prev, pending = watch.ready(tmp_path, {}, prev)
    assert take == [] and pending


def test_import_osz_files_copies_and_never_touches_the_originals(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path / "app")))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    svc = Services(cfg, db, DummyLog())
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    a = _osz(downloads / "123 A - T.osz")
    before = a.read_bytes()
    res = svc.import_osz_files([a, downloads / "missing.osz", downloads / "x.txt"])
    assert res["new"] == 1 and res["files"] == 1
    assert (cfg.library_path / "123 A - T.osz").exists()
    assert a.read_bytes() == before                    # the user's file is untouched
    from rosu import jobs
    job = svc.build_watch_import_job([a])
    assert job.kind == "watch_import" and [s.lane for s in job.steps] == [jobs.Lane.DISK]
    db.close()


def test_import_osz_files_reports_each_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path / "app")))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    svc = Services(cfg, db, DummyLog())
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    good = _osz(downloads / "1 A - T.osz")
    fake = downloads / "2 fake.osz"
    fake.write_bytes(b"not a zip at all")
    res = svc.import_osz_files([good, fake, downloads / "gone.osz"])
    assert res["imported"] == [str(good)]
    assert sorted(res["rejected"]) == sorted([str(fake), str(downloads / "gone.osz")])
    assert res["failed"] == [] and fake.exists()       # rejected files stay put

    import shutil
    from collections import namedtuple
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda p: usage(1, 1, 0))
    res = svc.import_osz_files([good])
    assert res["failed"] == [str(good)] and res["imported"] == []
    db.close()


def test_import_waits_while_the_library_folder_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path / "app"),
                                              library_dir=str(tmp_path / "unplugged" / "Library")))
    cfg.ensure_dirs()
    (tmp_path / "unplugged" / "Library").rmdir()     # the drive went away
    db = Database(cfg.db_path)
    svc = Services(cfg, db, DummyLog())
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    a = _osz(downloads / "1 A - T.osz")
    staged = []
    import tempfile
    monkeypatch.setattr(tempfile, "mkdtemp", lambda **k: staged.append(k) or str(tmp_path / "x"))
    res = svc.import_osz_files([a])
    assert res["failed"] == [str(a)] and res["imported"] == [] and staged == []
    db.close()
