# SPDX-License-Identifier: GPL-3.0-or-later
"""RemovalMixin: remove sets from osu!(stable) / osu!lazer (v1.8, HANDOFF 4.1)."""
import zipfile
from pathlib import Path

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


def test_save_first_keeps_a_real_file_even_with_memory_only_imports(env):
    cfg, db, svc, songs, trash = env
    cfg.library_physical_copy = False                     # the setting covers normal imports
    _stable_set(songs, 404)
    res = svc.remove_from_client("stable", ["404 A - B"], save_first=True)
    assert res["saved"] == 1 and res["removed"] == 1, res
    assert (cfg.library_path / "404 A - B.osz").is_file()


def test_save_first_never_trusts_a_matching_id_alone(env):
    cfg, db, svc, songs, trash = env
    # The Library's set 101 is something else entirely (another map that happens
    # to share the id prefix): the folder's own difficulties are not in it.
    _library_set(cfg, db, 101)
    lib_file = cfg.library_path / "101 A - B.osz"
    before = lib_file.read_bytes()
    _stable_set(songs, 101)
    res = svc.remove_from_client("stable", ["101 A - B"], save_first=True)
    assert res["removed"] == 0 and res["kept"] == ["101 A - B"], res
    assert (songs / "101 A - B").exists()
    assert lib_file.read_bytes() == before                # never overwritten


def test_save_first_keeps_a_set_whose_library_copy_is_empty_or_edited(env):
    cfg, db, svc, songs, trash = env
    d = _stable_set(songs, 606)
    (cfg.library_path / "606 A - B.osz").write_bytes(b"")  # 0-byte "copy"
    res = svc.remove_from_client("stable", ["606 A - B"], save_first=True)
    assert res["removed"] == 0 and res["kept"] == ["606 A - B"]
    # A Library copy with every difficulty byte for byte does prove it.
    (cfg.library_path / "606 A - B.osz").unlink()
    client_import.zip_folder_to_osz(d, cfg.library_path / "606 A - B.osz")
    (d / "A - B [x].osu").write_text("osu file format v14\nedited locally\n")
    res = svc.remove_from_client("stable", ["606 A - B"], save_first=True)
    assert res["removed"] == 0 and res["kept"] == ["606 A - B"]     # edited since: kept
    client_import.zip_folder_to_osz(d, cfg.library_path / "606 A - B.osz")
    res = svc.remove_from_client("stable", ["606 A - B"], save_first=True)
    assert res["removed"] == 1 and (trash / "606 A - B").exists()


def test_remove_only_needs_a_recycle_bin_and_a_known_client_state(env, monkeypatch):
    cfg, db, svc, songs, trash = env
    _stable_set(songs, 707)
    monkeypatch.setattr(client_remove, "osu_process_paths", lambda: None)
    assert svc.remove_from_client("stable", ["707 A - B"], save_first=False)["error"] \
        == "client_check_failed"
    monkeypatch.setattr(client_remove, "osu_process_paths", lambda: [])
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda path: False)
    assert svc.remove_from_client("stable", ["707 A - B"], save_first=False)["error"] \
        == "no_recycle_bin"
    assert (songs / "707 A - B").exists()
    before = set(cfg.library_path.glob("*.osz"))
    res = svc.remove_from_client("stable", ["707 A - B"], save_first=True)   # no way round it
    assert res["error"] == "no_recycle_bin" and res["removed"] == 0 and res["saved"] == 0
    assert (songs / "707 A - B").exists()
    assert set(cfg.library_path.glob("*.osz")) == before


@pytest.mark.parametrize("save_first", [False, True])
def test_remove_refuses_all_when_one_folder_has_no_recycle_bin(env, monkeypatch, save_first):
    cfg, db, svc, songs, trash = env
    ok, bad = _stable_set(songs, 808), _stable_set(songs, 809)
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda path: path != bad)
    before = set(cfg.library_path.glob("*.osz"))
    res = svc.remove_from_client("stable", [ok.name, bad.name], save_first=save_first)
    assert res["error"] == "no_recycle_bin" and res["removed"] == 0 and res["saved"] == 0
    assert ok.exists() and bad.exists()
    assert not any(trash.iterdir())
    assert set(cfg.library_path.glob("*.osz")) == before


def test_remove_stable_rechecks_the_recycle_bin_before_each_delete(env, monkeypatch):
    cfg, db, svc, songs, trash = env
    d = _stable_set(songs, 101)
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda path: False)
    res = {"source": "stable", "removed": 0, "kept": [], "failed": [], "saved": 0,
           "cancelled": False}
    svc._remove_stable(songs, {d.name: 101}, False, res, None, lambda: False)
    assert res["failed"] == [d.name] and res["removed"] == 0
    assert d.exists() and not any(trash.iterdir())
    assert any(kind == "error" and a[0] == "remove:stable" for kind, a, _ in svc.log.lines)


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


def _fake_lazer(svc, monkeypatch, tmp_path, exports):
    """A stand-in helper: ``export`` writes ``exports`` ({file name: .osu text},
    all for set 7), ``delete`` soft-deletes whatever ids it is given."""
    data = tmp_path / "lazer"
    data.mkdir()
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: data)
    calls = []

    def fake_run(self, args, cancel=None, timeout=0):
        a = [str(x) for x in args]
        calls.append(a)
        if a[0] == "--capabilities":
            return 0, "CAPS export list delete\n", ""
        if a[0] == "export":
            out = Path(a[2])
            out.mkdir(parents=True, exist_ok=True)
            lines = []
            for name, osu in exports.items():
                with zipfile.ZipFile(out / name, "w") as z:
                    z.writestr("A - B [x].osu", osu)
                    z.writestr("audio.mp3", b"a" * 10)
                lines.append(f"EXPORT 7\t{name}")
            return 0, "\n".join(lines) + "\n", ""
        if a[0] == "delete":
            ids = Path(a[2]).read_text().split()
            return 0, "BACKUP C:\\osu\\client.realm.rosu-1.bak\n" + \
                "".join(f"DELETED {i}\n" for i in ids), "done"
        return 1, "", "unexpected"
    monkeypatch.setattr(type(svc), "_lazer_helper", lambda self: tmp_path / "helper.exe")
    (tmp_path / "helper.exe").write_bytes(b"")
    monkeypatch.setattr(type(svc), "_lazer_helper_run", fake_run)
    return data, calls


def test_lazer_removal_saves_first_and_goes_through_the_helper_only(env, monkeypatch, tmp_path):
    cfg, db, svc, songs, _ = env
    # Two lazer sets share id 7 (an edited copy): both must reach the Library.
    data, calls = _fake_lazer(svc, monkeypatch, tmp_path, {
        "7 A - B.osz": "osu file format v14\nBeatmapSetID:7\n",
        "7 A - B (2).osz": "osu file format v14\nBeatmapSetID:7\nedited\n"})
    db.set_in_osu(7, True, client="lazer")
    res = svc.remove_from_client("lazer", ["7", "not-an-id"], save_first=False)  # forced to save
    assert res["removed"] == 1 and res["failed"] == ["not-an-id"] and res["kept"] == [], res
    assert {p.name for p in cfg.library_path.glob("7 *.osz")} == {"7 A - B.osz", "7 A - B (2).osz"}
    assert res["backup"].endswith(".bak")
    assert db.find_track_row(7, None)["in_osu_lazer"] == 0
    assert [c[0] for c in calls] == ["--capabilities", "export", "delete"]
    assert not any(p.name != "lazer" for p in data.iterdir())   # never touched lazer's files


def test_lazer_keeps_a_set_when_the_library_holds_another_version(env, monkeypatch, tmp_path):
    cfg, db, svc, songs, _ = env
    data, calls = _fake_lazer(svc, monkeypatch, tmp_path, {
        "7 A - B.osz": "osu file format v14\nBeatmapSetID:7\nlazer's version\n"})
    _library_set(cfg, db, 7)                       # same name, different difficulty bytes
    before = (cfg.library_path / "7 A - B.osz").read_bytes()
    res = svc.remove_from_client("lazer", ["7"], save_first=True)
    assert res["removed"] == 0 and res["kept"] == ["7"], res
    assert (cfg.library_path / "7 A - B.osz").read_bytes() == before   # not overwritten
    assert "delete" not in [c[0] for c in calls]


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
    assert svc.build_remove_job("lazer", ["7"], save_first=False).ctx["options"]["save_first"]
