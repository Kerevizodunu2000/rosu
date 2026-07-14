# SPDX-License-Identifier: GPL-3.0-or-later
"""Integration test for Services.backup_to_drive with a fake Drive client."""
from rosu import config
from rosu.db import Database
from rosu.drive import manifest
from rosu.models import ParsedTrack
from rosu.services import Services


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


class FakeAuth:
    def is_connected(self):
        return True

    def is_configured(self):
        return True


class FakeClient:
    def __init__(self):
        self.uploads = []
        self.folder_ensured = False
        self.deleted = []
        self._folder = []   # file names currently in the Drive folder

    def ensure_folder(self, name="Rosu", parent=None):
        self.folder_ensured = True
        return "FOLDER"

    def upload_file(self, path, name, parent, progress=None, cancel=None, **kw):
        self.uploads.append(name)
        self._folder.append(name)
        return "id-" + name

    def find_file(self, name, parent):
        return ("id-" + name) if name in self._folder else None

    def list_folder(self, parent):
        return [{"id": "id-" + n, "name": n, "size": 1} for n in self._folder]

    def delete_file(self, file_id):
        self.deleted.append(file_id)
        self._folder = [n for n in self._folder if ("id-" + n) != file_id]


def _make_services(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)  # no repo side effect
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.device_id = "devTEST"
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    svc = Services(cfg, db, DummyLog())
    svc._drive_auth = lambda: FakeAuth()
    return cfg, db, svc


def _add_library_track(cfg, db, beatmapset_id, filename, blob=b"osz-bytes"):
    osz = cfg.library_path / filename
    osz.write_bytes(blob)
    t = ParsedTrack(beatmapset_id=beatmapset_id, filename=filename, artist="A",
                    title="T", display_name="A - T", size_bytes=osz.stat().st_size)
    tid, _ = db.upsert_track(t, "when")
    db.set_library_state(tid, True, "present", "when")
    return osz


def test_backup_uploads_and_records(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    _add_library_track(cfg, db, 555, "song.osz")
    fake = FakeClient()
    svc._make_drive_client = lambda: fake

    res = svc.backup_to_drive()
    assert res["uploaded"] == 1 and res["chunks"] == 1
    assert fake.folder_ensured
    assert "chunk-devTEST-0000.zip" in fake.uploads
    assert manifest.shard_name("devTEST") in fake.uploads   # shard published

    row = db.find_track_row(555, "song.osz")
    assert row["in_drive"] == 1
    assert row["drive_chunk"] == "chunk-devTEST-0000.zip"
    assert row["drive_hash"]

    shard = cfg.drive_cache_path / manifest.shard_name("devTEST")
    entries = manifest.load_shard(shard)
    assert manifest.make_key(555, "song.osz") in entries
    db.close()


def test_backup_is_incremental(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    _add_library_track(cfg, db, 555, "song.osz")
    svc._make_drive_client = lambda: FakeClient()
    assert svc.backup_to_drive()["uploaded"] == 1

    # second run: nothing new -> no client work at all
    fake2 = FakeClient()
    svc._make_drive_client = lambda: fake2
    res2 = svc.backup_to_drive()
    assert res2["uploaded"] == 0
    assert fake2.uploads == [] and fake2.folder_ensured is False
    db.close()


def test_backup_skips_memory_only_tracks(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    # a memory-only row (no physical .osz on disk)
    t = ParsedTrack(beatmapset_id=999, filename="ghost.osz", artist="A",
                    title="T", display_name="A - T", size_bytes=10)
    tid, _ = db.upsert_track(t, "when")
    db.set_library_state(tid, True, "memory", "when")
    fake = FakeClient()
    svc._make_drive_client = lambda: fake

    res = svc.backup_to_drive()
    assert res["uploaded"] == 0
    assert fake.uploads == []          # nothing uploaded, no crash on missing file
    db.close()


def test_backup_requires_connection(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)

    class Disconnected:
        def is_connected(self):
            return False

    svc._drive_auth = lambda: Disconnected()
    assert svc.backup_to_drive() == {"error": "not_connected"}
    db.close()


def test_request_cancel_sets_both_tokens(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    svc.request_cancel()
    assert svc._cancel.is_set() and svc._drive_cancel.is_set()
    assert svc._lostmap_cancel.is_set()
    db.close()


def test_backup_plan_counts_new_sets(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    _add_library_track(cfg, db, 555, "a.osz")
    _add_library_track(cfg, db, 556, "b.osz")
    plan = svc.backup_plan()
    assert plan["count"] == 2 and plan["total_bytes"] > 0
    assert plan["chunk_bytes"] == cfg.drive_chunk_bytes
    db.close()


def test_backup_plan_gated_when_not_connected(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)

    class NC:
        def is_connected(self):
            return False

    svc._drive_auth = lambda: NC()
    assert svc.backup_plan() == {"error": "not_connected"}
    db.close()


def test_backup_max_sets_limits_upload(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    for bid, fn in [(1, "a.osz"), (2, "b.osz"), (3, "c.osz")]:
        _add_library_track(cfg, db, bid, fn)
    fake = FakeClient()
    svc._make_drive_client = lambda: fake
    res = svc.backup_to_drive(max_sets=1)
    assert res["uploaded"] == 1          # capped, not all 3
    db.close()


def test_dispose_archive_to_drive_uploads_and_removes(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    zip_path = cfg.packs_path / "S1 - Pack.zip"
    zip_path.write_bytes(b"archive-bytes")
    fake = FakeClient()
    svc._make_drive_client = lambda: fake
    action = svc._dispose_archive_to_drive(zip_path)
    assert action == "ZIP_TO_DRIVE"
    assert "S1 - Pack.zip" in fake.uploads     # uploaded to Drive
    assert not zip_path.exists()               # removed locally to reclaim disk
    db.close()


def test_dispose_archive_to_drive_falls_back_when_disconnected(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    zip_path = cfg.packs_path / "S2 - Pack.zip"
    zip_path.write_bytes(b"archive-bytes")

    class NC:
        def is_connected(self):
            return False

    svc._drive_auth = lambda: NC()
    action = svc._dispose_archive_to_drive(zip_path)
    assert action == "ZIP_MOVED"                                    # safe fallback
    assert not zip_path.exists()
    assert (cfg.root_path / "Processed" / "S2 - Pack.zip").exists()  # never lost
    db.close()


def test_backup_individual_uploads_each_file(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    for bid, fn in [(1, "a.osz"), (2, "b.osz")]:
        _add_library_track(cfg, db, bid, fn)
    fake = FakeClient()
    svc._make_drive_client = lambda: fake
    res = svc.backup_to_drive(chunk_bytes=0)   # individual mode
    assert res["uploaded"] == 2 and res["chunks"] == 0
    assert "a.osz" in fake.uploads and "b.osz" in fake.uploads   # by .osz name
    # each set is recorded as stored under its own filename (not a chunk archive)
    row = db.find_track_row(1, "a.osz")
    assert row["in_drive"] == 1 and row["drive_chunk"] == "a.osz"
    db.close()


def test_connect_drive_does_not_wipe_import_cancel(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)

    class LoginAuth:
        def is_connected(self):
            return True

        def is_configured(self):
            return True

        def login(self, cancel=None):
            pass  # no-op consent

    svc._drive_auth = lambda: LoginAuth()
    svc._cancel.set()             # a pending osu!-import cancel
    svc.connect_drive()
    assert svc._cancel.is_set()   # the Drive login must NOT clear it
    db.close()


def test_backup_reports_cancelled(tmp_path, monkeypatch):
    from rosu.drive.auth import DriveCancelled
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    _add_library_track(cfg, db, 1, "a.osz")
    _add_library_track(cfg, db, 2, "b.osz")

    class CancelClient(FakeClient):
        def upload_file(self, path, name, parent, progress=None, cancel=None, **kw):
            raise DriveCancelled("cancelled")

    svc._make_drive_client = lambda: CancelClient()
    res = svc.backup_to_drive()
    assert res["cancelled"] is True
    assert res["uploaded"] == 0 and res["chunks"] == 0
    db.close()


def test_backup_lost_cache_does_not_reuse_chunk_index(tmp_path, monkeypatch):
    """A cleared local shard must not restart chunk numbering at 0 and collide
    (by name) with a chunk already in the shared Drive folder."""
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    _add_library_track(cfg, db, 1, "a.osz")
    fake = FakeClient()
    svc._make_drive_client = lambda: fake
    svc.backup_to_drive()
    assert "chunk-devTEST-0000.zip" in fake.uploads

    # simulate a lost/cleared local cache, then a new track appears
    (cfg.drive_cache_path / manifest.shard_name("devTEST")).unlink()
    _add_library_track(cfg, db, 2, "b.osz")
    svc.backup_to_drive()

    # numbering continues past the chunk already in the folder — 0000 not reused
    assert "chunk-devTEST-0001.zip" in fake.uploads
    assert sum(1 for n in fake.uploads if n == "chunk-devTEST-0000.zip") == 1
    db.close()
