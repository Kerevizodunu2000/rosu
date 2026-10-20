# SPDX-License-Identifier: GPL-3.0-or-later
"""Drive backup browser + restore (v1.8, HANDOFF 4.2), against a fake Drive."""
import hashlib
import io
import json
import zipfile

import pytest

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


def _osz(text="osu file format v14\n[Metadata]\nTitle:T\nArtist:A\n"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("A - T [x].osu", text)
    return buf.getvalue()


class FakeDrive:
    """Files by name → bytes; ids are 'id-<name>'."""
    def __init__(self, files):
        self.files = dict(files)
        self.downloads = []

    def ensure_folder(self, name="Rosu", parent=None):
        return "FOLDER"

    def list_folder(self, parent):
        return [{"id": "id-" + n, "name": n, "size": len(b)} for n, b in self.files.items()]

    def download_file(self, file_id, dest, progress=None, max_bytes=None):
        name = file_id[3:]
        data = self.files[name]
        if max_bytes is not None and len(data) > max_bytes:
            raise RuntimeError("cap")
        self.downloads.append(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return dest


def _chunk(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


def _entry(chunk, name, data, bid, artist="A", title="T", sha=None):
    return {"chunk": chunk, "name": name, "size": len(data),
            "hash": sha if sha is not None else hashlib.sha256(data).hexdigest(),
            "beatmapset_id": bid, "metadata": {"artist": artist, "title": title}}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.device_id = "devHERE"
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    svc = Services(cfg, db, DummyLog())
    svc._drive_auth = lambda: FakeAuth()
    yield cfg, db, svc
    db.close()


def _shard(device, entries):
    return json.dumps({"device_id": device, "version": 1, "entries": entries}).encode()


def test_catalog_merges_every_device_and_flags_state(env):
    cfg, db, svc = env
    a, b = _osz(), _osz("osu file format v14\n[Metadata]\nTitle:U\n")
    here = {"id:1": _entry("chunk-devHERE-0000.zip", "1 A - T.osz", a, 1)}
    other = {"id:2": _entry("chunk-devOTHER-0000.zip", "2 B - U.osz", b, 2, "B", "U"),
             "id:3": _entry("chunk-devOTHER-0001.zip", "3 gone.osz", b, 3)}
    drive = FakeDrive({
        "chunk-devHERE-0000.zip": _chunk({"1 A - T.osz": a}),
        "chunk-devOTHER-0000.zip": _chunk({"2 B - U.osz": b}),
        "chunk-devOTHER-9999.zip": b"orphan",
        manifest.shard_name("devHERE"): _shard("devHERE", here),
        manifest.shard_name("devOTHER"): _shard("devOTHER", other),
    })
    svc._make_drive_client = lambda: drive
    # Set 1 is already in the Library.
    (cfg.library_path / "1 A - T.osz").write_bytes(a)
    tid, _ = db.upsert_track(ParsedTrack(beatmapset_id=1, filename="1 A - T.osz", artist="A", title="T", display_name="A - T"), "when")
    db.set_library_state(tid, True, "present", "when")

    res = svc.drive_catalog()
    by = {e["beatmapset_id"]: e for e in res["entries"]}
    assert res["devices"] == 2
    assert by[1]["in_library"] and by[1]["this_device"] and by[1]["on_drive"]
    assert not by[2]["in_library"] and not by[2]["this_device"] and by[2]["on_drive"]
    assert by[3]["on_drive"] is False and res["missing"] == 1
    assert res["orphans"] == ["chunk-devOTHER-9999.zip"]


def test_restore_extracts_verifies_and_imports_only_the_chosen_sets(env):
    cfg, db, svc = env
    a, b = _osz(), _osz("osu file format v14\n[Metadata]\nTitle:U\n")
    chunk = "chunk-devOTHER-0000.zip"
    drive = FakeDrive({chunk: _chunk({"10 A - T.osz": a, "11 B - U.osz": b})})
    svc._make_drive_client = lambda: drive
    res = svc.drive_restore([_entry(chunk, "10 A - T.osz", a, 10)])
    assert res["restored"] == 1 and res["failed"] == []
    assert (cfg.library_path / "10 A - T.osz").exists()
    assert not (cfg.library_path / "11 B - U.osz").exists()     # not chosen
    row = db.find_track_row(10, "10 A - T.osz")
    assert row["in_drive"] == 1 and row["drive_chunk"] == chunk
    assert not (cfg.data_path / "_drive_restore").exists() or not any(
        (cfg.data_path / "_drive_restore").rglob("*.osz"))       # staging cleaned up


def test_restore_rejects_tampered_unsafe_and_missing(env):
    cfg, db, svc = env
    a = _osz()
    chunk = "chunk-devX-0000.zip"
    drive = FakeDrive({chunk: _chunk({"20 A.osz": a, "21 B.osz": a})})
    svc._make_drive_client = lambda: drive
    res = svc.drive_restore([
        _entry(chunk, "20 A.osz", a, 20, sha="0" * 64),            # wrong fingerprint
        _entry(chunk, "../../evil.osz", a, 22),                     # unsafe name
        _entry(chunk, "23 missing.osz", a, 23),                     # not in the archive
        _entry("chunk-devX-0001.zip", "24 gone.osz", a, 24),        # archive not on Drive
    ])
    reasons = {f["name"]: f["reason"] for f in res["failed"]}
    assert reasons == {"20 A.osz": "hash_mismatch", "../../evil.osz": "bad_name",
                       "23 missing.osz": "not_in_archive", "24 gone.osz": "not_on_drive"}
    assert res["restored"] == 0
    assert not list(cfg.library_path.glob("*.osz"))


def test_restore_individual_mode_file(env):
    cfg, db, svc = env
    a = _osz()
    drive = FakeDrive({"30 Solo.osz": a})
    svc._make_drive_client = lambda: drive
    res = svc.drive_restore([_entry("30 Solo.osz", "30 Solo.osz", a, 30)])
    assert res["restored"] == 1
    assert (cfg.library_path / "30 Solo.osz").exists()


def test_restore_job_downloads_on_drive_lane_and_imports_on_disk_lane(env):
    from rosu import jobs
    cfg, db, svc = env
    a = _osz()
    chunk = "chunk-devX-0000.zip"
    svc._make_drive_client = lambda: FakeDrive({chunk: _chunk({"40 A.osz": a})})
    job = svc.build_drive_restore_job([_entry(chunk, "40 A.osz", a, 40)])
    assert [s.lane for s in job.steps] == [jobs.Lane.DRIVE, jobs.Lane.DISK]
    res = jobs.run_job_sync(job)
    assert res["restored"] == 1


def test_not_connected(env):
    cfg, db, svc = env

    class Off:
        def is_connected(self):
            return False
    svc._drive_auth = lambda: Off()
    assert svc.drive_catalog() == {"error": "not_connected"}
    assert svc.drive_restore([])["error"] == "not_connected"


def test_restore_never_overwrites_a_library_file(env):
    cfg, db, svc = env
    a = _osz()
    mine = _osz("osu file format v14\n[Metadata]\nTitle:my edit\n")
    chunk = "chunk-devX-0000.zip"
    drive = FakeDrive({chunk: _chunk({"50 A.osz": a, "51 B.osz": a})})
    svc._make_drive_client = lambda: drive
    (cfg.library_path / "50 A.osz").write_bytes(mine)        # a different version
    (cfg.library_path / "51 B.osz").write_bytes(a)           # the same bytes
    res = svc.drive_restore([_entry(chunk, "50 A.osz", a, 50), _entry(chunk, "51 B.osz", a, 51)])
    assert res["failed"] == [{"name": "50 A.osz", "reason": "library_conflict"}]
    assert res["restored"] == 0 and res["already"] == 1
    assert (cfg.library_path / "50 A.osz").read_bytes() == mine


def test_restore_keeps_a_real_file_with_memory_only_imports(env):
    cfg, db, svc = env
    cfg.library_physical_copy = False
    a = _osz()
    chunk = "chunk-devX-0000.zip"
    svc._make_drive_client = lambda: FakeDrive({chunk: _chunk({"55 A.osz": a})})
    assert svc.drive_restore([_entry(chunk, "55 A.osz", a, 55)])["restored"] == 1
    assert (cfg.library_path / "55 A.osz").read_bytes() == a


def test_one_bad_member_or_entry_never_sinks_the_rest(env, monkeypatch):
    cfg, db, svc = env
    a = _osz()
    chunk = "chunk-devX-0000.zip"
    drive = FakeDrive({chunk: _chunk({"60 A.osz": a, "61 B.osz": a}),
                       manifest.shard_name("devX"): _shard("devX", {
                           "id:60": _entry(chunk, "60 A.osz", a, 60),
                           "bad1": {**_entry(chunk, "61 B.osz", a, 61), "size": "abc",
                                    "beatmapset_id": "61"},
                           "bad2": {"chunk": 5, "name": None},
                           "bad3": "not an entry"})})
    svc._make_drive_client = lambda: drive
    res = svc.drive_catalog()
    assert {e["name"] for e in res["entries"]} == {"60 A.osz", "61 B.osz"}
    monkeypatch.setattr(zipfile.ZipFile, "open", _raise_for("60 A.osz", zipfile.ZipFile.open))
    res = svc.drive_restore([_entry(chunk, "60 A.osz", a, 60), _entry(chunk, "61 B.osz", a, 61)])
    assert res["failed"] == [{"name": "60 A.osz", "reason": "corrupt"}]
    assert res["restored"] == 1


def _raise_for(name, original):
    import zlib

    def opener(self, member, *a, **k):
        if getattr(member, "filename", member) == name:
            raise zlib.error("Error -3 while decompressing data")
        return original(self, member, *a, **k)
    return opener


def test_restore_refuses_when_the_disk_is_too_full(env, monkeypatch):
    from rosu.services import drive_restore_svc
    cfg, db, svc = env
    a = _osz()
    chunk = "chunk-devX-0000.zip"
    svc._make_drive_client = lambda: FakeDrive({chunk: _chunk({"70 A.osz": a})})
    monkeypatch.setattr(drive_restore_svc, "_free_bytes", lambda path: 1024)
    res = svc.drive_restore([_entry(chunk, "70 A.osz", a, 70)])
    assert res["failed"] == [{"name": "70 A.osz", "reason": "disk_full"}]
    assert not list(cfg.library_path.glob("*.osz"))


def test_member_names_reject_windows_devices_and_paths():
    from rosu.services.drive_restore_svc import _safe_member_name
    assert _safe_member_name("12 A - B.osz") == "12 A - B.osz"
    for bad in ("NUL.osz", "con.osz", "COM1.osz", "a/b.osz", "a\\b.osz", "c:x.osz",
                "x?.osz", "x.txt", "", None, "a\x01.osz"):
        assert _safe_member_name(bad) is None, bad
