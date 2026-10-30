# SPDX-License-Identifier: GPL-3.0-or-later
"""Drive storage quota: reading it, the pre-backup check, a Drive filling up
mid-backup, and publishing the shard without deleting the old one first.
Fake transport and fake clients only; no network."""
import pytest

from rosu.drive import client, manifest
from rosu.drive.auth import DriveError, DriveQuotaExceeded
from rosu.services import export_svc
from test_drive_backup import FakeClient, _add_library_track, _make_services

_FULL = (b'{"error":{"code":403,"errors":[{"domain":"usageLimits",'
         b'"reason":"storageQuotaExceeded"}]}}')
_RATE = (b'{"error":{"code":403,"errors":[{"domain":"usageLimits",'
         b'"reason":"userRateLimitExceeded"}]}}')


class FakeAuth:
    def get_access_token(self, now=None):
        return "tok"


def _quota_client(reply, urls=None):
    def transport(method, url, headers=None, body=None):
        assert method == "GET"
        if urls is not None:
            urls.append(url)
        return 200, {}, reply
    return client.DriveClient(FakeAuth(), transport=transport)


# 1
def test_storage_quota_parses_string_ints_and_asks_for_quota_only():
    urls = []
    c = _quota_client(b'{"storageQuota":{"limit":"16106127360","usage":"5368709120",'
                      b'"usageInDrive":"1073741824","usageInDriveTrash":"1024"}}', urls)
    assert c.storage_quota() == {"limit": 16106127360, "usage": 5368709120,
                                 "usage_in_drive": 1073741824,
                                 "usage_in_drive_trash": 1024}
    assert len(urls) == 1
    assert "/about" in urls[0] and "fields=storageQuota" in urls[0]
    assert "user" not in urls[0]


# 2
def test_storage_quota_without_limit_is_unlimited():
    c = _quota_client(b'{"storageQuota":{"usage":"10"}}')
    assert c.storage_quota() == {"limit": None, "usage": 10, "usage_in_drive": 0,
                                 "usage_in_drive_trash": 0}


# 3
@pytest.mark.parametrize("body", [
    b"<html>oops</html>",
    b"{}",
    b'{"storageQuota":"nope"}',
    b'{"storageQuota":{"limit":"100"}}',
    b'{"storageQuota":{"usage":"abc"}}',
    b'{"storageQuota":{"usage":"1","limit":"12.5"}}',
    b'{"storageQuota":{"usage":"1","usageInDriveTrash":true}}',
])
def test_storage_quota_malformed_raises_drive_error(body):
    with pytest.raises(DriveError):
        _quota_client(body).storage_quota()


def _upload(tmp_path, init, put, chunk_size=10):
    f = tmp_path / "c.zip"
    f.write_bytes(b"Z" * 20)
    puts = []

    def transport(method, url, headers=None, body=None):
        if method == "POST":
            return init
        puts.append(url)
        return put if len(puts) == 2 else (308, {}, b"")

    c = client.DriveClient(FakeAuth(), transport=transport)
    return c.upload_file(f, "c.zip", "FOLDER", chunk_size=chunk_size)


_OK_INIT = (200, {"Location": "https://sess/1"}, b"")


# 4
def test_quota_exceeded_at_resumable_init(tmp_path):
    with pytest.raises(DriveQuotaExceeded):
        _upload(tmp_path, (403, {}, _FULL), None)


def test_quota_exceeded_at_chunk_put(tmp_path):
    with pytest.raises(DriveQuotaExceeded):
        _upload(tmp_path, _OK_INIT, (403, {}, _FULL))


# 5
@pytest.mark.parametrize("body", [_RATE, b"<html>Forbidden</html>", b'{"error":"x"}'])
def test_other_403_is_a_plain_drive_error(tmp_path, body):
    for init, put in [((403, {}, body), None), (_OK_INIT, (403, {}, body))]:
        with pytest.raises(DriveError) as info:
            _upload(tmp_path, init, put)
        assert not isinstance(info.value, DriveQuotaExceeded)


class QuotaClient(FakeClient):
    def __init__(self, quota):
        super().__init__()
        self.quota = quota

    def storage_quota(self):
        if isinstance(self.quota, Exception):
            raise self.quota
        return self.quota


_MIB = 1024 * 1024


# 6
def test_precheck_refuses_when_backup_does_not_fit(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    _add_library_track(cfg, db, 1, "a.osz", blob=b"x" * 9)
    fake = QuotaClient({"limit": 100 * _MIB, "usage": 60 * _MIB,
                        "usage_in_drive": 50 * _MIB, "usage_in_drive_trash": 7 * _MIB})
    svc._make_drive_client = lambda: fake
    res = svc.backup_to_drive()
    assert export_svc._QUOTA_MARGIN == 64 * 1024 * 1024
    assert res == {"error": "drive_full", "needed": 9 + 64 * _MIB,
                   "free": 40 * _MIB, "trash": 7 * _MIB}
    assert fake.uploads == [] and fake.deleted == []
    assert fake.folder_ensured is False
    assert not (cfg.drive_cache_path / manifest.shard_name("devTEST")).exists()
    assert db.find_track_row(1, "a.osz")["in_drive"] == 0
    db.close()


def test_precheck_free_space_never_negative(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    _add_library_track(cfg, db, 1, "a.osz")
    svc._make_drive_client = lambda: QuotaClient(
        {"limit": 10, "usage": 50, "usage_in_drive": 0, "usage_in_drive_trash": 0})
    assert svc.backup_to_drive()["free"] == 0
    db.close()


# 7
@pytest.mark.parametrize("quota", [
    {"limit": None, "usage": 10**15, "usage_in_drive": 0, "usage_in_drive_trash": 0},
    DriveError("about.get -> 403"),
    {"limit": 1024 * _MIB, "usage": 0, "usage_in_drive": 0, "usage_in_drive_trash": 0},
])
def test_precheck_proceeds(tmp_path, monkeypatch, quota):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    _add_library_track(cfg, db, 1, "a.osz")
    fake = QuotaClient(quota)
    svc._make_drive_client = lambda: fake
    res = svc.backup_to_drive()
    assert res["uploaded"] == 1 and "error" not in res
    assert fake.folder_ensured
    db.close()


class FillsUpClient(QuotaClient):
    """Drive fills up on the second upload of an .osz or a chunk."""

    def __init__(self):
        super().__init__({"limit": None, "usage": 0, "usage_in_drive": 0,
                          "usage_in_drive_trash": 0})
        self.data_uploads = 0

    def upload_file(self, path, name, parent, progress=None, cancel=None, **kw):
        if name != manifest.shard_name("devTEST"):
            self.data_uploads += 1
            if self.data_uploads == 2:
                raise DriveQuotaExceeded("upload chunk failed: 403")
        return super().upload_file(path, name, parent, progress, cancel, **kw)


# 8
@pytest.mark.parametrize("chunk_bytes,first,chunks", [
    (1, "chunk-devTEST-0000.zip", 1),   # one set per chunk
    (0, "a.osz", 0),                    # individual mode
])
def test_quota_running_out_mid_backup_keeps_what_was_uploaded(
        tmp_path, monkeypatch, chunk_bytes, first, chunks):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    _add_library_track(cfg, db, 1, "a.osz")
    _add_library_track(cfg, db, 2, "b.osz")
    fake = FillsUpClient()
    svc._make_drive_client = lambda: fake
    res = svc.backup_to_drive(chunk_bytes=chunk_bytes)
    assert res == {"error": "drive_full", "uploaded": 1, "chunks": chunks}
    shard = manifest.shard_name("devTEST")
    assert fake.uploads == [first, shard]          # the shard is published
    entries = manifest.load_shard(cfg.drive_cache_path / shard)
    assert manifest.make_key(1, "a.osz") in entries
    assert manifest.make_key(2, "b.osz") not in entries
    assert db.find_track_row(1, "a.osz")["in_drive"] == 1
    assert db.find_track_row(2, "b.osz")["in_drive"] == 0
    assert fake.deleted == []
    assert not list(cfg.drive_cache_path.glob("chunk-*"))   # staging zips removed
    db.close()


class ListingClient(QuotaClient):
    def __init__(self, quota, folders):
        super().__init__(quota)
        self.folders = folders
        self.listed = []

    def list_folder(self, parent):
        self.listed.append(parent)
        return self.folders[parent]


_QUOTA = {"limit": 1000, "usage": 400, "usage_in_drive": 300, "usage_in_drive_trash": 20}


# 9
def test_drive_storage_sums_rosu_folder_and_subfolders(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    cfg.drive_folder_id = "ROSU"
    fake = ListingClient(_QUOTA, {
        "ROSU": [{"id": "c0", "name": "chunk-devTEST-0000.zip", "size": "100"},
                 {"id": "s", "name": "manifest-devTEST.json", "size": "3"},
                 {"id": "E", "name": "Exports"}, {"id": "P", "name": "Packs"},
                 {"id": "X", "name": "Other"}],
        "E": [{"id": "e1", "name": "x.zip", "size": "10"}],
        "P": [{"id": "p1", "name": "y.zip", "size": "5"}, {"id": "p2", "name": "z"}],
    })
    svc._make_drive_client = lambda: fake
    assert svc.drive_storage() == {**_QUOTA, "rosu": 118}
    assert fake.listed == ["ROSU", "E", "P"]
    assert fake.folder_ensured is False
    db.close()


def test_drive_storage_without_folder_lists_nothing(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    cfg.drive_folder_id = ""
    fake = ListingClient(_QUOTA, {})
    svc._make_drive_client = lambda: fake
    assert svc.drive_storage() == {**_QUOTA, "rosu": 0}
    assert fake.listed == [] and fake.folder_ensured is False
    db.close()


def test_drive_storage_errors(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    svc._make_drive_client = lambda: ListingClient(DriveError("-> 403"), {})
    assert svc.drive_storage() == {"error": "drive"}

    class Disconnected:
        def is_connected(self):
            return False

    svc._drive_auth = lambda: Disconnected()
    assert svc.drive_storage() == {"error": "not_connected"}
    db.close()


class ShardClient:
    """A Drive folder that gives every upload its own id, so same-named shard
    copies are told apart, and logs every call in order."""

    def __init__(self, files, fail_upload=False, fail_delete=(), new_id=None):
        self.files = list(files)
        self.ops = []
        self.fail_upload = fail_upload
        self.fail_delete = set(fail_delete)
        self.new_id = new_id
        self.n = 0

    def upload_file(self, path, name, parent, progress=None, cancel=None, **kw):
        self.ops.append("upload")
        if self.fail_upload:
            raise DriveQuotaExceeded("full")
        self.n += 1
        fid = f"new{self.n}"
        self.files.append({"id": fid, "name": name})
        return fid if self.new_id is None else self.new_id

    def list_folder(self, parent):
        self.ops.append("list")
        return [dict(f) for f in self.files]

    def delete_file(self, file_id):
        self.ops.append("delete " + file_id)
        if file_id in self.fail_delete:
            raise DriveError("delete -> 500")
        self.files = [f for f in self.files if f["id"] != file_id]


class RecLog:
    def __init__(self):
        self.errors = []

    def info(self, *a, **k):
        pass

    def error(self, where, detail):
        self.errors.append((where, detail))


def _shard(tmp_path, monkeypatch):
    cfg, db, svc = _make_services(tmp_path, monkeypatch)
    svc.log = RecLog()
    shard = cfg.drive_cache_path / manifest.shard_name("devTEST")
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard.write_text("{}")
    return db, svc, shard


# 10
def test_push_shard_uploads_then_deletes_every_stale_copy(tmp_path, monkeypatch):
    db, svc, shard = _shard(tmp_path, monkeypatch)
    fake = ShardClient([{"id": "old1", "name": shard.name},
                        {"id": "old2", "name": shard.name},
                        {"id": "c0", "name": "chunk-devTEST-0000.zip"}])
    svc._push_shard(fake, shard, "FOLDER")
    assert fake.ops[0] == "upload"                   # before any delete
    assert sorted(fake.ops[2:]) == ["delete old1", "delete old2"]
    assert fake.files == [{"id": "c0", "name": "chunk-devTEST-0000.zip"},
                          {"id": "new1", "name": shard.name}]
    assert svc.log.errors == []
    db.close()


def test_push_shard_keeps_old_copies_when_the_upload_fails(tmp_path, monkeypatch):
    db, svc, shard = _shard(tmp_path, monkeypatch)
    fake = ShardClient([{"id": "old1", "name": shard.name}], fail_upload=True)
    svc._push_shard(fake, shard, "FOLDER")           # never raises
    assert fake.ops == ["upload"]
    assert fake.files == [{"id": "old1", "name": shard.name}]
    db.close()


def test_push_shard_deletes_nothing_without_the_new_id(tmp_path, monkeypatch):
    db, svc, shard = _shard(tmp_path, monkeypatch)
    fake = ShardClient([{"id": "old1", "name": shard.name}], new_id="")
    svc._push_shard(fake, shard, "FOLDER")
    assert fake.ops == ["upload"]
    db.close()


def test_push_shard_retries_a_failed_delete_next_time(tmp_path, monkeypatch):
    db, svc, shard = _shard(tmp_path, monkeypatch)
    fake = ShardClient([{"id": "old1", "name": shard.name},
                        {"id": "old2", "name": shard.name}], fail_delete={"old2"})
    svc._push_shard(fake, shard, "FOLDER")
    assert [f["id"] for f in fake.files] == ["old2", "new1"]
    assert svc.log.errors == [("drive:shard", "1 of 2 old shard copies not deleted")]

    fake.fail_delete.clear()
    svc._push_shard(fake, shard, "FOLDER")           # the next backup's push
    assert [f["id"] for f in fake.files] == ["new2"]
    db.close()
