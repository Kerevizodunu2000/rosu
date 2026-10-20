# SPDX-License-Identifier: GPL-3.0-or-later
"""RemovalMixin: remove sets from osu!(stable) / osu!lazer (v1.8, HANDOFF 4.1)."""
import zipfile

import pytest

from rosu import client_import, client_remove, config
from rosu.db import Database
from rosu.models import ParsedTrack
from rosu.services import Services


class DummyLog:
    def __init__(self):
        self.lines = []

    def info(self, *a, **k):
        self.lines.append(("info", a, k))

    def error(self, *a, **k):
        self.lines.append(("error", a, k))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    cfg.stable_enabled = True
    db = Database(cfg.db_path)
    svc = Services(cfg, db, DummyLog())
    songs = tmp_path / "Songs"
    songs.mkdir()
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    monkeypatch.setattr(client_remove, "osu_process_paths", lambda: [])
    trash = tmp_path / "trash"
    trash.mkdir()

    def fake_send2trash(path):
        import shutil
        from pathlib import Path
        shutil.move(str(path), str(trash / Path(path).name))
    monkeypatch.setattr("send2trash.send2trash", fake_send2trash)
    yield cfg, db, svc, songs, trash
    db.close()


def _stable_set(songs, bid, name="A - B"):
    d = songs / f"{bid} {name}"
    d.mkdir()
    (d / f"{name} [x].osu").write_text(f"osu file format v14\n[Metadata]\nBeatmapSetID:{bid}\n")
    (d / "audio.mp3").write_bytes(b"a" * 100)
    return d


def _library_set(cfg, db, bid):
    fn = f"{bid} A - B.osz"
    with zipfile.ZipFile(cfg.library_path / fn, "w") as z:
        z.writestr("x.osu", "osu file format v14\n")
    t = ParsedTrack(beatmapset_id=bid, filename=fn, artist="A", title="B", display_name="A - B")
    tid, _ = db.upsert_track(t, "when")
    db.set_library_state(tid, True, "present", "when")
    db.set_in_osu(bid, True, client="stable")
    return tid


def test_sources_reflect_settings_and_helper(env, monkeypatch):
    cfg, db, svc, songs, _ = env
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: songs)   # "installed"
    monkeypatch.setattr(type(svc), "lazer_helper_capabilities", lambda self: {"export"})
    by = {s["key"]: s for s in svc.removal_sources()}
    assert by["stable"]["available"] is True
    assert by["lazer"] == {"key": "lazer", "available": False, "reason": "lazer_helper"}
    monkeypatch.setattr(type(svc), "lazer_helper_capabilities", lambda self: {"export", "list", "delete"})
    assert {s["key"]: s for s in svc.removal_sources()}["lazer"]["available"] is True
    cfg.stable_enabled = False
    assert {s["key"]: s for s in svc.removal_sources()}["stable"]["reason"] == "disabled"


def test_scan_marks_what_the_library_already_holds(env):
    cfg, db, svc, songs, _ = env
    _stable_set(songs, 101)
    _stable_set(songs, 202)
    _library_set(cfg, db, 101)
    res = svc.removal_scan("stable")
    flags = {s["beatmapset_id"]: s["backed_up"] for s in res["sets"]}
    assert flags == {101: True, 202: False}


def test_remove_only_recycles_folders_and_clears_the_stable_flag(env):
    cfg, db, svc, songs, trash = env
    _stable_set(songs, 101)
    _library_set(cfg, db, 101)
    res = svc.remove_from_client("stable", ["101 A - B"], save_first=False)
    assert res["removed"] == 1 and res["failed"] == [] and res["kept"] == []
    assert not (songs / "101 A - B").exists()
    assert (trash / "101 A - B").exists()                 # recoverable
    row = db.find_track_row(101, None)
    assert row["in_osu_stable"] == 0


def test_save_first_copies_into_the_library_then_removes(env):
    cfg, db, svc, songs, trash = env
    _stable_set(songs, 303)
    res = svc.remove_from_client("stable", ["303 A - B"], save_first=True)
    assert res["saved"] == 1 and res["removed"] == 1, res
    assert any(p.name.startswith("303") for p in cfg.library_path.glob("*.osz"))
    assert (trash / "303 A - B").exists()


def test_save_first_keeps_sets_it_cannot_prove_are_in_the_library(env):
    cfg, db, svc, songs, trash = env
    cfg.library_physical_copy = False                     # memory-only: no .osz kept
    _stable_set(songs, 404)
    res = svc.remove_from_client("stable", ["404 A - B"], save_first=True)
    assert res["removed"] == 0 and res["kept"] == ["404 A - B"]
    assert (songs / "404 A - B").exists()


def test_refuses_names_outside_songs_and_a_running_client(env, monkeypatch):
    cfg, db, svc, songs, trash = env
    victim = songs.parent / "precious"
    victim.mkdir()
    res = svc.remove_from_client("stable", ["../precious"], save_first=False)
    assert res["removed"] == 0 and res["failed"] == ["../precious"]
    assert victim.exists()
    _stable_set(songs, 505)
    monkeypatch.setattr(client_remove, "osu_process_paths", lambda: [r"C:\osu!\osu!.exe"])
    res = svc.remove_from_client("stable", ["505 A - B"], save_first=False)
    assert res["error"] == "client_running" and (songs / "505 A - B").exists()


def test_lazer_removal_goes_through_the_helper_only(env, monkeypatch, tmp_path):
    cfg, db, svc, songs, _ = env
    data = tmp_path / "lazer"
    data.mkdir()
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: data)
    calls = []

    def fake_run(self, args, cancel=None, timeout=0):
        calls.append([str(a) for a in args])
        if args[0] == "--capabilities":
            return 0, "CAPS export list delete\n", ""
        if args[0] == "delete":
            return 0, "BACKUP C:\\osu\\client.realm.rosu-1.bak\nDELETED 7\n", "done deleted=1"
        return 1, "", "unexpected"
    monkeypatch.setattr(type(svc), "_lazer_helper", lambda self: tmp_path / "helper.exe")
    (tmp_path / "helper.exe").write_bytes(b"")
    monkeypatch.setattr(type(svc), "_lazer_helper_run", fake_run)
    _library_set(cfg, db, 7)
    db.set_in_osu(7, True, client="lazer")
    res = svc.remove_from_client("lazer", ["7", "not-an-id"], save_first=False)
    assert res["removed"] == 1 and res["failed"] == ["not-an-id"]
    assert res["backup"].endswith(".bak")
    assert db.find_track_row(7, None)["in_osu_lazer"] == 0
    assert [c[0] for c in calls] == ["--capabilities", "delete"]
    assert not any(p.name != "lazer" for p in data.iterdir())   # never touched lazer's files


def test_lazer_without_the_new_helper_is_refused(env, monkeypatch, tmp_path):
    cfg, db, svc, songs, _ = env
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: tmp_path)
    monkeypatch.setattr(type(svc), "lazer_helper_capabilities", lambda self: {"export"})
    assert svc.remove_from_client("lazer", ["7"], save_first=False)["error"] == "lazer_helper"


def test_remove_job_reports_its_options(env):
    cfg, db, svc, songs, _ = env
    job = svc.build_remove_job("stable", ["a", "b"], save_first=False)
    assert job.kind == "remove"
    assert job.ctx["options"] == {"remove_source": "stable", "sets": 2, "save_first": False}
