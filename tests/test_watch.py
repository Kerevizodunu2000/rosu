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
    assert watch.load_state(state, tmp_path / "a") == {"x|1|2"}
    assert watch.load_state(state, tmp_path / "b") is None
    state.write_text("{broken", encoding="utf-8")
    assert watch.load_state(state, tmp_path / "a") is None


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
