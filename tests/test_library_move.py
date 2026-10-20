# SPDX-License-Identifier: GPL-3.0-or-later
"""Move the Library to another folder (v1.9): copy, verify, switch, recycle."""
import os

import pytest

from rosu import client_remove, config
from rosu.db import Database
from rosu.services import Services
from rosu.services import move_svc


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    saved = []
    monkeypatch.setattr(config, "save_config", lambda cfg: saved.append(cfg.library_dir))
    cfg = config._fill_defaults(config.Config(root=str(tmp_path / "app")))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    svc = Services(cfg, db, DummyLog())
    for i in range(3):
        (cfg.library_path / f"{i} A - B.osz").write_bytes(bytes([i]) * (1000 + i))
    trash = []
    monkeypatch.setattr("send2trash.send2trash", lambda p: trash.append(p))
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda p: True)
    yield cfg, svc, saved, trash
    db.close()


def test_plan_previews_without_touching_files(env, tmp_path):
    cfg, svc, saved, _ = env
    plan = svc.library_move_plan(tmp_path / "D" / "Library")
    assert plan["files"] == 3 and plan["bytes"] == 1000 + 1001 + 1002
    assert plan["conflicts"] == [] and plan["enough_space"] and "error" not in plan
    assert saved == [] and len(list(cfg.library_path.glob("*.osz"))) == 3
    assert svc.library_move_plan(cfg.library_path)["error"] == "same"
    assert svc.library_move_plan(cfg.library_path / "sub")["error"] == "inside"
    assert svc.library_move_plan(cfg.library_path.parent)["error"] == "inside"


def test_move_copies_verifies_and_switches(env, tmp_path):
    cfg, svc, saved, trash = env
    old = cfg.library_path
    dest = tmp_path / "D" / "Library"
    res = svc.move_library(dest)
    assert res["moved"] == 3 and "error" not in res
    assert cfg.library_path == dest and saved == [str(dest)]
    assert sorted(p.name for p in dest.glob("*.osz")) == sorted(p.name for p in old.glob("*.osz"))
    assert (dest / "2 A - B.osz").read_bytes() == bytes([2]) * 1002
    assert trash == [] and not list(dest.glob("*.part"))       # old copies kept


def test_move_can_recycle_the_old_copies(env, tmp_path):
    cfg, svc, saved, trash = env
    old = cfg.library_path
    res = svc.move_library(tmp_path / "D", remove_old=True)
    assert res["old_removed"] == 3 and sorted(trash) == sorted(str(p) for p in old.glob("*.osz"))


def test_old_copies_stay_without_a_recycle_bin(env, tmp_path, monkeypatch):
    cfg, svc, saved, trash = env
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda p: False)
    res = svc.move_library(tmp_path / "D", remove_old=True)
    assert res["old_kept"] and trash == [] and res["moved"] == 3


def test_conflicts_and_identical_files_at_the_destination(env, tmp_path):
    cfg, svc, saved, _ = env
    dest = tmp_path / "D"
    dest.mkdir()
    (dest / "0 A - B.osz").write_bytes(bytes([0]) * 1000)       # the same file
    (dest / "1 A - B.osz").write_bytes(b"other")                 # a different file
    plan = svc.library_move_plan(dest)
    assert plan["same"] == 1 and plan["conflicts"] == ["1 A - B.osz"]
    res = svc.move_library(dest)
    assert res["error"] == "conflicts" and saved == []
    assert (dest / "1 A - B.osz").read_bytes() == b"other"       # never overwritten
    (dest / "1 A - B.osz").unlink()
    res = svc.move_library(dest)
    assert res["moved"] == 2 and res["same"] == 1 and cfg.library_path == dest


def test_cancel_or_a_bad_copy_leaves_everything_as_it_was(env, tmp_path, monkeypatch):
    cfg, svc, saved, _ = env
    old = cfg.library_path
    calls = []

    def cancel_after_first():
        calls.append(1)
        return len(calls) > 1
    dest = tmp_path / "D"
    res = svc.move_library(dest, cancel=cancel_after_first)
    assert res["cancelled"] and cfg.library_path == old and saved == []
    assert not list(dest.iterdir())                               # its own copies removed
    real = move_svc._sha256
    monkeypatch.setattr(move_svc, "_sha256",
                        lambda p: "bad" if str(p).endswith(".part") else real(p))
    res = svc.move_library(dest)
    assert res["error"] == "copy_failed" and cfg.library_path == old
    assert not list(dest.iterdir())


def test_move_job_runs_on_the_disk_lane(env, tmp_path):
    from rosu import jobs
    cfg, svc, saved, _ = env
    job = svc.build_library_move_job(tmp_path / "D", remove_old=False)
    assert [s.lane for s in job.steps] == [jobs.Lane.DISK] and job.kind == "library_move"
    assert jobs.run_job_sync(job)["moved"] == 3


def test_reserved_folders_and_no_side_effects_in_the_plan(env, tmp_path):
    cfg, svc, saved, _ = env
    assert svc.library_move_plan(cfg.output_path)["error"] == "reserved"   # Unpack clears it
    assert svc.library_move_plan(cfg.data_path / "lib")["error"] == "reserved"
    dest = tmp_path / "Not" / "Yet"
    assert "error" not in svc.library_move_plan(dest)
    assert not dest.exists()                                  # the preview creates nothing


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
def test_a_link_to_the_same_file_is_a_conflict_not_a_copy(env, tmp_path):
    cfg, svc, saved, trash = env
    dest = tmp_path / "D"
    dest.mkdir()
    try:
        (dest / "0 A - B.osz").symlink_to(cfg.library_path / "0 A - B.osz")
    except OSError:
        pytest.skip("symlinks not permitted")
    plan = svc.library_move_plan(dest)
    assert plan["conflicts"] == ["0 A - B.osz"] and plan["same"] == 0
    res = svc.move_library(dest, remove_old=True)
    assert res["error"] == "conflicts" and trash == []        # the only copy is never recycled


def test_changed_originals_stay_and_late_files_follow(env, tmp_path, monkeypatch):
    cfg, svc, saved, trash = env
    old = cfg.library_path
    real_save = move_svc.LibraryMoveMixin._move_files

    def move_then_write(self, files, new, verified, made, res, progress, cancel):
        real_save(self, files, new, verified, made, res, progress, cancel)
        if not (old / "9 Late.osz").exists():
            (old / "9 Late.osz").write_bytes(b"late")             # an import lands mid-move
            (old / "1 A - B.osz").write_bytes(b"rewritten")       # an original changes
    monkeypatch.setattr(move_svc.LibraryMoveMixin, "_move_files", move_then_write)
    res = svc.move_library(tmp_path / "D", remove_old=True)
    assert res["moved"] == 4 and "error" not in res, res          # the late file came along
    assert (tmp_path / "D" / "9 Late.osz").read_bytes() == b"late"
    assert str(old / "1 A - B.osz") not in trash and res["old_failed"] == 1


def test_a_failed_config_save_keeps_the_old_library(env, tmp_path, monkeypatch):
    cfg, svc, saved, trash = env
    old = cfg.library_dir

    def boom(c):
        raise OSError("disk full")
    monkeypatch.setattr(config, "save_config", boom)
    res = svc.move_library(tmp_path / "D", remove_old=True)
    assert res["error"] == "config_save" and cfg.library_dir == old and trash == []


def test_an_existing_part_file_is_not_clobbered(env, tmp_path):
    cfg, svc, saved, _ = env
    dest = tmp_path / "D"
    dest.mkdir()
    (dest / "0 A - B.osz.part").write_bytes(b"user's own")
    assert svc.move_library(dest)["moved"] == 3
    assert (dest / "0 A - B.osz.part").read_bytes() == b"user's own"


def test_a_file_written_at_the_switch_is_copied_after_it(env, tmp_path, monkeypatch):
    cfg, svc, saved, trash = env
    old = cfg.library_path

    def save_and_race(c):
        (old / "8 Race.osz").write_bytes(b"race")                 # written just as we switch
    monkeypatch.setattr(config, "save_config", save_and_race)
    res = svc.move_library(tmp_path / "D")
    assert res["late"] == 1 and res["left_behind"] == []
    assert (tmp_path / "D" / "8 Race.osz").read_bytes() == b"race"
