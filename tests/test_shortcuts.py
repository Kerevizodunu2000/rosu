# SPDX-License-Identifier: GPL-3.0-or-later
"""Service-layer tests for the Shortcuts (Kısayollar) tab (v1.2)."""
from pathlib import Path

from rosu import client_import, config
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


def _add_lib(db, bid, filename, *, in_drive=0):
    db._conn.execute(
        "INSERT INTO tracks(beatmapset_id, filename, display_name, in_library, "
        "library_status, in_drive) VALUES(?,?,?,1,'present',?)",
        (bid, filename, f"Artist - {bid}", in_drive))
    db._conn.commit()


# -- installed_summary -------------------------------------------------------
def test_installed_summary_counts(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    _add_lib(db, 1, "a.osz", in_drive=1)
    _add_lib(db, 2, "b.osz", in_drive=0)
    _add_lib(db, 3, "c.osz", in_drive=1)

    songs = tmp_path / "Songs"
    songs.mkdir()
    for i in range(3):
        (songs / f"{i} Artist - Title").mkdir()
    (songs / "loose.txt").write_bytes(b"x")   # a stray file is NOT a set folder
    lazer = tmp_path / "lazerdata"
    lazer.mkdir()
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: lazer)

    summ = svc.installed_summary()
    assert summ["stable"] == {"installed": True, "count": 3}    # only the folders
    assert summ["lazer"]["installed"] is True
    assert summ["lazer"]["count"] is None                        # Realm-opaque
    assert summ["library"]["count"] == 3
    assert summ["drive"]["count"] == 2
    db.close()


def test_installed_summary_none_installed(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: None)
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: None)
    summ = svc.installed_summary()
    assert summ["stable"] == {"installed": False, "count": 0}
    assert summ["lazer"] == {"installed": False, "count": None}
    assert summ["library"]["count"] == 0
    assert summ["drive"]["count"] == 0
    db.close()


# -- ⑤ unpack_and_import -----------------------------------------------------
class _Plan:
    def __init__(self, kind, zip_path):
        self.kind = kind
        self.zip_path = zip_path
        self.parsed = object()


def test_unpack_and_import_only_new_then_imports(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    monkeypatch.setattr(svc, "prescan_all", lambda progress=None: [
        _Plan("new", "a.zip"), _Plan("all_present", "b.zip"), _Plan("new", "c.zip")])
    got = {}

    def fake_extract(approved, progress=None):
        got["approved"] = approved
        return {"packs": len(approved), "tracks": 5}

    monkeypatch.setattr(svc, "extract", fake_extract)
    monkeypatch.setattr(svc, "has_loose_osz", lambda: False)
    dispatched = []
    monkeypatch.setattr(svc, "_dispatch_to_client",
                        lambda target, files, progress=None: (dispatched.append(target),
                                                             {"sent": 0})[1])
    res = svc.unpack_and_import(["lazer", "stable"])
    assert [Path(p).name for p, _ in got["approved"]] == ["a.zip", "c.zip"]  # only new
    assert dispatched == ["lazer", "stable"]
    assert res["extract"]["packs"] == 2
    db.close()


def test_unpack_and_import_nothing_new_still_imports(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    monkeypatch.setattr(svc, "prescan_all", lambda progress=None: [])
    monkeypatch.setattr(svc, "has_loose_osz", lambda: False)
    calls = []
    monkeypatch.setattr(svc, "extract",
                        lambda approved, progress=None: calls.append("extract"))
    dispatched = []
    monkeypatch.setattr(svc, "_dispatch_to_client",
                        lambda target, files, progress=None: (dispatched.append(target),
                                                             {"sent": 0})[1])
    res = svc.unpack_and_import(["lazer"])
    assert calls == []                       # nothing to unpack → extract skipped
    assert res["extract"] == {"packs": 0, "tracks": 0}
    assert "lazer" in res["imports"]
    db.close()


def test_unpack_and_import_skips_target_duplicates(tmp_path, monkeypatch):
    """Review/feedback: don't re-send Output sets the target client already has."""
    cfg, db, svc = _svc(tmp_path)
    monkeypatch.setattr(svc, "prescan_all", lambda progress=None: [])
    monkeypatch.setattr(svc, "has_loose_osz", lambda: False)
    (cfg.output_path / "10 A - B.osz").write_bytes(b"x")
    (cfg.output_path / "20 C - D.osz").write_bytes(b"y")
    db._conn.execute(
        "INSERT INTO tracks(beatmapset_id, in_osu, in_osu_lazer) VALUES(20,1,1)")
    db._conn.commit()
    sent = {}
    monkeypatch.setattr(
        svc, "_dispatch_to_client",
        lambda target, files, progress=None: sent.update(
            {target: sorted(Path(f).name for f in files)}) or {"sent": len(files)})
    res = svc.unpack_and_import(["lazer"], skip_duplicates=True)
    assert sent["lazer"] == ["10 A - B.osz"]          # set 20 skipped (already in lazer)
    assert res["imports"]["lazer"]["skipped"] == 1
    db.close()


# -- ③ save_installed_to_library ---------------------------------------------
def test_save_installed_to_library_dispatches_selected(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    calls = []
    monkeypatch.setattr(svc, "import_from_stable",
                        lambda progress=None: (calls.append("stable"), {"new": 1})[1])
    monkeypatch.setattr(svc, "import_from_lazer",
                        lambda progress=None: (calls.append("lazer"), {"new": 2})[1])
    out = svc.save_installed_to_library(["lazer"])
    assert calls == ["lazer"] and out["lazer"] == {"new": 2}
    db.close()


# -- ①② transfer_between_clients ---------------------------------------------
def test_transfer_same_client_errors(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    assert svc.transfer_between_clients("lazer", "lazer") == {"error": "same_client"}
    db.close()


def test_transfer_no_target_exe(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    monkeypatch.setattr(config, "detect_stable_exe", lambda: "")
    res = svc.transfer_between_clients("lazer", "stable")
    assert res["error"] == "no_target_exe"
    db.close()


def test_client_set_ids_stable(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    songs = tmp_path / "Songs"
    songs.mkdir()
    (songs / "123 A - B").mkdir()
    (songs / "456 C - D").mkdir()
    (songs / "no-id-folder").mkdir()   # no numeric prefix, no .osu → no id → skipped
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    assert svc._client_set_ids("stable") == {123, 456}
    assert svc._client_set_ids("lazer") == set()   # no in_osu_lazer flags yet
    db.close()


def test_export_client_sets_stable_skips_target_ids(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    songs = tmp_path / "Songs"
    songs.mkdir()
    for bid in (100, 200, 300):
        d = songs / f"{bid} A - B"
        d.mkdir()
        (d / "x.osu").write_text("osu file")
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    files, skipped = svc._export_client_sets("stable", tmp_path / "stage", {200}, None)
    assert skipped == 1                                     # 200 already in target
    assert sorted(p.name for p in files) == ["100 A - B.osz", "300 A - B.osz"]
    assert all(p.exists() for p in files)                  # zipped to stage
    db.close()


def test_transfer_stable_to_lazer_end_to_end(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    exe = tmp_path / "osu!.exe"
    exe.write_bytes(b"")
    cfg.osu_lazer_exe = str(exe)
    songs = tmp_path / "Songs"
    songs.mkdir()
    for bid in (11, 22):
        d = songs / f"{bid} A - B"
        d.mkdir()
        (d / "x.osu").write_text("o")
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    dispatched = {}

    def fake_dispatch(target, files, progress=None):
        dispatched["target"] = target
        dispatched["files"] = [Path(f).name for f in files]
        return {"files": len(files), "batches": 1, "sent": len(files),
                "cancelled": False}

    monkeypatch.setattr(svc, "_dispatch_to_client", fake_dispatch)
    res = svc.transfer_between_clients("stable", "lazer")   # lazer target → no skip
    assert dispatched["target"] == "lazer"
    assert sorted(dispatched["files"]) == ["11 A - B.osz", "22 A - B.osz"]
    assert res["found"] == 2 and res["transferred"] == 2 and res["skipped"] == 0
    db.close()


# -- extra: library dedup ----------------------------------------------------
def test_plan_library_dedup_keeps_canonical():
    from rosu import library
    entries = [
        {"name": "123 A - B.osz", "size": 100, "beatmapset_id": 123,
         "canonical": "123 A - B.osz"},
        {"name": "123 A - B (1).osz", "size": 100, "beatmapset_id": 123,
         "canonical": "123 A - B.osz"},                     # dup copy → removed
        {"name": "456 C - D.osz", "size": 50, "beatmapset_id": 456,
         "canonical": "456 C - D.osz"},                     # lone → kept
        {"name": "no-id.osz", "size": 10, "beatmapset_id": None, "canonical": None},
    ]
    assert library.plan_library_dedup(entries) == ["123 A - B (1).osz"]


def test_plan_library_dedup_skips_group_without_canonical():
    from rosu import library
    entries = [
        {"name": "9 X.osz", "size": 1, "beatmapset_id": 9, "canonical": None},
        {"name": "9 X (1).osz", "size": 1, "beatmapset_id": 9, "canonical": None},
    ]
    assert library.plan_library_dedup(entries) == []   # no canonical → untouched


def test_dedup_library_recycles_dupes(tmp_path, monkeypatch):
    trashed = []

    def fake_trash(p):
        trashed.append(p)
        Path(p).unlink()

    monkeypatch.setattr("send2trash.send2trash", fake_trash)
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "123 A - B.osz").write_bytes(b"x" * 100)
    (cfg.library_path / "123 A - B (1).osz").write_bytes(b"y" * 40)   # dup copy
    db._conn.execute(
        "INSERT INTO tracks(beatmapset_id, filename, in_library, library_status) "
        "VALUES(123,'123 A - B.osz',1,'present')")
    db._conn.commit()

    res = svc.dedup_library()
    assert res["removed"] == 1 and res["groups"] == 1
    assert res["freed_bytes"] == 40
    assert not (cfg.library_path / "123 A - B (1).osz").exists()   # copy recycled
    assert (cfg.library_path / "123 A - B.osz").exists()           # canonical kept
    db.close()


# -- ④ export_sets -----------------------------------------------------------
def test_export_sets_library_writes_one_zip(tmp_path):
    import zipfile
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "1 A - B.osz").write_bytes(b"a" * 10)
    (cfg.library_path / "2 C - D.osz").write_bytes(b"b" * 10)
    res = svc.export_sets("library", tmp_path / "out" / "MyExport", fmt="zip")
    assert res["count"] == 2 and len(res["archives"]) == 1
    with zipfile.ZipFile(res["archives"][0]) as z:
        assert set(z.namelist()) == {"1 A - B.osz", "2 C - D.osz"}
    db.close()


def test_export_sets_drive_subset_only(tmp_path):
    import zipfile
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "1 A - B.osz").write_bytes(b"a" * 10)
    (cfg.library_path / "2 C - D.osz").write_bytes(b"b" * 10)
    db._conn.execute(
        "INSERT INTO tracks(beatmapset_id, filename, in_library, library_status, "
        "in_drive) VALUES(1,'1 A - B.osz',1,'present',1)")
    db._conn.execute(
        "INSERT INTO tracks(beatmapset_id, filename, in_library, library_status, "
        "in_drive) VALUES(2,'2 C - D.osz',1,'present',0)")
    db._conn.commit()
    res = svc.export_sets("drive", tmp_path / "out" / "DriveExport", fmt="zip")
    assert res["count"] == 1                        # only the in_drive one
    with zipfile.ZipFile(res["archives"][0]) as z:
        assert z.namelist() == ["1 A - B.osz"]
    db.close()


def test_export_sets_empty_source(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    res = svc.export_sets("library", tmp_path / "out" / "E", fmt="zip")
    assert res["count"] == 0 and res["archives"] == []
    db.close()


def test_export_sets_random_limit_samples(tmp_path):
    import zipfile
    cfg, db, svc = _svc(tmp_path)
    for i in range(5):
        (cfg.library_path / f"{i} A - B.osz").write_bytes(b"x" * 10)
    res = svc.export_sets("library", tmp_path / "out" / "R", fmt="zip", limit=2)
    assert res["count"] == 2                             # sampled down from 5
    with zipfile.ZipFile(res["archives"][0]) as z:
        assert len(z.namelist()) == 2
    # limit >= available exports everything
    res_all = svc.export_sets("library", tmp_path / "out" / "A", fmt="zip", limit=99)
    assert res_all["count"] == 5
    db.close()


def test_export_sets_merged_dedups_by_id(tmp_path, monkeypatch):
    import zipfile
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "1 A - B.osz").write_bytes(b"a" * 10)   # id 1 in Library
    songs = tmp_path / "Songs"
    songs.mkdir()
    for bid in (1, 5):                       # id 1 dup (skip), id 5 new
        d = songs / f"{bid} A - B"
        d.mkdir()
        (d / "x.osu").write_text("o")
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: None)   # no lazer
    res = svc.export_sets("merged", tmp_path / "out" / "Merged", fmt="zip")
    with zipfile.ZipFile(res["archives"][0]) as z:
        names = set(z.namelist())
    assert "1 A - B.osz" in names and "5 A - B.osz" in names
    assert res["count"] == 2                 # id 1 counted once (Library kept)
    db.close()


# -- DriveClient share-link helpers (drive.file scope) -----------------------
def test_drive_client_share_and_link():
    from rosu.drive.client import DriveClient
    calls = []

    def fake_transport(method, url, headers=None, body=None, timeout=120):
        calls.append((method, url))
        if "permissions" in url:
            return 200, {}, b'{"id":"perm1"}'
        if "webViewLink" in url:
            return (200, {},
                    b'{"webViewLink":"https://drive.google.com/file/d/abc/view"}')
        return 200, {}, b'{}'

    class FakeAuth:
        def get_access_token(self):
            return "tok"

    client = DriveClient(FakeAuth(), transport=fake_transport)
    client.share_anyone("abc")
    link = client.get_link("abc")
    assert link == "https://drive.google.com/file/d/abc/view"
    assert any("permissions" in u for _m, u in calls)   # permission was POSTed


def test_upload_export_records_shared_when_link_fails(tmp_path, monkeypatch):
    """Security fix: if share_anyone succeeds but get_link fails, the file is
    already public — record shared=True + link_error so the UI can warn."""
    from rosu.drive.auth import DriveError
    cfg, db, svc = _svc(tmp_path)
    cfg.drive_folder_id = "fid"        # avoid config.save_config writing a real file

    class FakeAuth:
        def is_connected(self):
            return True

    class FakeClient:
        def ensure_folder(self, name, parent=None):
            return "fid"

        def upload_file(self, path, name, parent, progress=None, cancel=None):
            return "F1"

        def share_anyone(self, fid, role="reader"):
            return None                     # grant succeeds

        def get_link(self, fid):
            raise DriveError("boom")        # link fetch fails afterwards

    monkeypatch.setattr(svc, "_drive_auth", lambda: FakeAuth())
    monkeypatch.setattr(svc, "_make_drive_client", lambda: FakeClient())
    res = svc._upload_export_to_drive([tmp_path / "e.zip"], share=True)
    f = res["files"][0]
    assert f["shared"] is True and f["link"] is None and f["link_error"] is True
    db.close()


# -- review fixes: merged id-less, cancel, found-count, lazer DB dedup --------
def test_export_sets_merged_keeps_idless_sets(tmp_path, monkeypatch):
    """Review #1 (HIGH): distinct id-less sets must not collapse onto a fake id 0."""
    import zipfile
    cfg, db, svc = _svc(tmp_path)
    songs = tmp_path / "Songs"
    songs.mkdir()
    for name in ("My Local Edit One", "My Local Edit Two"):
        d = songs / name
        d.mkdir()
        (d / "a.osu").write_text("no BeatmapSetID here")   # unresolvable id
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: None)
    res = svc.export_sets("merged", tmp_path / "out" / "M", fmt="zip")
    assert res["count"] == 2                                # BOTH kept, not 1
    with zipfile.ZipFile(res["archives"][0]) as z:
        assert set(z.namelist()) == {"My Local Edit One.osz", "My Local Edit Two.osz"}
    db.close()


def test_transfer_lazer_target_skips_via_db_flag(tmp_path, monkeypatch):
    """Review #3/#4: found = sent + skipped, and a lazer target skips sets Rosu
    already recorded as present in lazer (in_osu_lazer)."""
    cfg, db, svc = _svc(tmp_path)
    exe = tmp_path / "osu!.exe"
    exe.write_bytes(b"")
    cfg.osu_lazer_exe = str(exe)
    songs = tmp_path / "Songs"
    songs.mkdir()
    for bid in (10, 20, 30):
        d = songs / f"{bid} A - B"
        d.mkdir()
        (d / "x.osu").write_text("o")
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    db._conn.execute(
        "INSERT INTO tracks(beatmapset_id, in_osu, in_osu_lazer) VALUES(20,1,1)")
    db._conn.commit()
    dispatched = {}

    def fake_dispatch(target, files, progress=None):
        dispatched["files"] = sorted(Path(f).name for f in files)
        return {"sent": len(files), "cancelled": False}

    monkeypatch.setattr(svc, "_dispatch_to_client", fake_dispatch)
    res = svc.transfer_between_clients("stable", "lazer")
    assert res["skipped"] == 1                              # set 20 skipped via flag
    assert res["found"] == 3                                # 10, 20, 30 examined
    assert res["transferred"] == 2                          # 10, 30 sent
    assert dispatched["files"] == ["10 A - B.osz", "30 A - B.osz"]
    db.close()


def test_export_client_sets_stops_on_cancel(tmp_path, monkeypatch):
    """Review #2 (HIGH): the export/zip phase must honor the cancel token."""
    cfg, db, svc = _svc(tmp_path)
    songs = tmp_path / "Songs"
    songs.mkdir()
    for bid in (1, 2, 3):
        d = songs / f"{bid} A - B"
        d.mkdir()
        (d / "x.osu").write_text("o")
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    svc._cancel.set()                                       # user cancelled
    files, skipped = svc._export_client_sets("stable", tmp_path / "st", None, None)
    assert files == []                                     # nothing zipped after cancel
    db.close()


def test_export_sets_cancelled_before_write(tmp_path, monkeypatch):
    """Review #2: a cancel during gather stops before any archive is written."""
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "1 A - B.osz").write_bytes(b"a" * 10)
    orig = svc._gather_export_sources

    def fake_gather(source, stage, progress=None):
        files = orig(source, stage, progress)
        svc._cancel.set()                                  # user hits Cancel
        return files

    monkeypatch.setattr(svc, "_gather_export_sources", fake_gather)
    res = svc.export_sets("library", tmp_path / "out" / "C", fmt="zip")
    assert res["cancelled"] is True and res["archives"] == []
    db.close()


# -- test-feedback fixes: dedup preview/confirm + cancellable lazer helper ----
def test_dedup_library_plan_previews_without_deleting(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "123 A - B.osz").write_bytes(b"x" * 100)
    (cfg.library_path / "123 A - B (1).osz").write_bytes(b"y" * 40)   # dup copy
    db._conn.execute(
        "INSERT INTO tracks(beatmapset_id, filename, in_library, library_status) "
        "VALUES(123,'123 A - B.osz',1,'present')")
    db._conn.commit()
    plan = svc.dedup_library_plan()
    assert plan["count"] == 1 and plan["names"] == ["123 A - B (1).osz"]
    assert plan["freed_bytes"] == 40 and plan["groups"] == 1
    assert (cfg.library_path / "123 A - B (1).osz").exists()   # preview deletes nothing
    db.close()


def test_dedup_library_ignores_stale_shared_cancel(tmp_path, monkeypatch):
    """v1.3 guard: dedup_library(cancel=None) must NOT honor a leftover shared
    _cancel from an earlier op — in v1.2 it never owned that token and always ran
    to completion. (A prior cancelled extract/import leaves _cancel set.)"""
    monkeypatch.setattr("send2trash.send2trash", lambda p: Path(p).unlink())
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "b.osz").write_bytes(b"y" * 20)
    svc._cancel.set()                          # leftover cancel from a prior op
    res = svc.dedup_library(names=["b.osz"])   # must still recycle, not no-op
    assert res["removed"] == 1
    assert not (cfg.library_path / "b.osz").exists()
    db.close()


def test_dedup_library_with_explicit_names(tmp_path, monkeypatch):
    trashed = []

    def fake_trash(p):
        trashed.append(p)
        Path(p).unlink()

    monkeypatch.setattr("send2trash.send2trash", fake_trash)
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "a.osz").write_bytes(b"x" * 10)
    (cfg.library_path / "b.osz").write_bytes(b"y" * 20)
    res = svc.dedup_library(names=["b.osz"])                   # remove exactly this
    assert res["removed"] == 1 and res["freed_bytes"] == 20
    assert not (cfg.library_path / "b.osz").exists()
    assert (cfg.library_path / "a.osz").exists()
    db.close()


def test_run_lazer_export_helper_missing(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    monkeypatch.setattr(svc, "_lazer_helper", lambda: None)
    ok, detail = svc._run_lazer_export(tmp_path / "data", tmp_path / "out")
    assert ok is False and detail == "helper_missing"
    db.close()
