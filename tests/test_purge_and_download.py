# SPDX-License-Identifier: GPL-3.0-or-later
"""Purge marks only what was recycled; a download never leaves a stray .osz (issue #16)."""
import pytest

from rosu import api_mirror, config
from rosu.db import Database
from rosu.models import ParsedTrack
from rosu.services import Services


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def _row(db, bid, fn):
    tid, _ = db.upsert_track(ParsedTrack(beatmapset_id=bid, filename=fn, artist="A",
                                         title="B", display_name="A - B"), "t0")
    db.set_library_state(tid, True, "present", "t0")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    yield cfg, db, Services(cfg, db, DummyLog())
    db.close()


def test_purge_marks_only_recycled_files(env, monkeypatch):
    cfg, db, svc = env
    for bid in (1, 2, 3):
        fn = f"{bid} A - B.osz"
        (cfg.library_path / fn).write_bytes(b"PK")
        _row(db, bid, fn)

    def fake(path):
        if path.endswith("2 A - B.osz"):
            raise RuntimeError("locked")
    monkeypatch.setattr("send2trash.send2trash", fake)
    assert svc.purge_library_files()["deleted"] == 2
    assert db.find_track_row(2, "")["in_library"] == 1
    for bid in (1, 3):
        row = db.find_track_row(bid, "")
        assert row["in_library"] == 0 and row["library_status"] == "memory"


def test_mark_library_memory_by_filename(tmp_path):
    db = Database(tmp_path / "m.db")
    _row(db, 1, "a.osz")
    _row(db, 2, "b.osz")
    assert db.mark_library_memory("t", []) == 0
    assert db.mark_library_memory("t", ["a.osz"]) == 1
    assert db.find_track_row(1, "")["in_library"] == 0
    assert db.find_track_row(2, "")["in_library"] == 1
    db.close()


class _FakeResp:
    def __init__(self, headers, chunks):
        self.status = 200
        self.headers = headers
        self._chunks = list(chunks)

    def read(self, n=8192):
        return self._chunks.pop(0) if self._chunks else b""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_download_temp_file_is_not_an_osz(tmp_path, monkeypatch):
    data = [b"x" * 100, b"y" * 100]
    monkeypatch.setattr(api_mirror.urllib.request, "urlopen", lambda req, timeout=30:
                        _FakeResp({"Content-Length": "200"}, data + [b""]))
    dest = tmp_path / "out.osz"
    seen = []
    assert api_mirror.download_osz(1, dest, progress=lambda ev: seen.append(
        [p.name for p in tmp_path.iterdir()]))
    assert seen
    for names in seen:
        assert not any(n.endswith(".osz") for n in names)
        assert sum(n.endswith(".osz.part") for n in names) == 1
    assert list(tmp_path.iterdir()) == [dest]

    dest.unlink()
    monkeypatch.setattr(api_mirror, "_MAX_DOWNLOAD_BYTES", 150)
    monkeypatch.setattr(api_mirror.urllib.request, "urlopen", lambda req, timeout=30:
                        _FakeResp({}, data + [b""]))
    assert api_mirror.download_osz(1, dest) is False
    assert list(tmp_path.iterdir()) == []
