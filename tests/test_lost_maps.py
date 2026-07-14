# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for lost-map detection (item F, v1.0). No real network is used — the
HTTP status layer is mocked, so 200/404/429 are simulated as plain values."""
from rosu import config, osu_api
from rosu.db import Database
from rosu.models import ParsedTrack
from rosu.services import Services


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def _no_sleep(monkeypatch):
    monkeypatch.setattr(osu_api.time, "sleep", lambda *_: None)


def test_beatmapset_availability_maps_status(monkeypatch):
    codes = {101: 200, 102: 404, 103: 500}
    monkeypatch.setattr(osu_api, "_token", lambda cid, cs: "tok")
    monkeypatch.setattr(osu_api, "_status_code",
                        lambda url, token: (codes[int(url.rsplit("/", 1)[1])], None))
    _no_sleep(monkeypatch)
    result = osu_api.beatmapset_availability([101, 102, 103], "id", "secret")
    assert result == {101: "available", 102: "gone", 103: "unknown"}


def test_beatmapset_availability_respects_max_calls(monkeypatch):
    monkeypatch.setattr(osu_api, "_token", lambda cid, cs: "tok")
    monkeypatch.setattr(osu_api, "_status_code", lambda url, token: (200, None))
    _no_sleep(monkeypatch)
    result = osu_api.beatmapset_availability([1, 2, 3, 4, 5], "id", "secret", max_calls=2)
    assert len(result) == 2


def test_beatmapset_availability_retries_on_429(monkeypatch):
    # First call 429, then 200 — must retry the same id, not drop it.
    seq = {1: [429, 200]}
    monkeypatch.setattr(osu_api, "_token", lambda cid, cs: "tok")

    def fake_status(url, token):
        bid = int(url.rsplit("/", 1)[1])
        return (seq[bid].pop(0), None)

    monkeypatch.setattr(osu_api, "_status_code", fake_status)
    _no_sleep(monkeypatch)
    assert osu_api.beatmapset_availability([1], "id", "secret") == {1: "available"}


def _svc(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    return cfg, db, Services(cfg, db, DummyLog())


def test_scan_lost_maps_gated_without_api(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    assert svc.scan_lost_maps() == {"error": "no_api"}
    db.close()


def test_scan_lost_maps_records_gone(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    cfg.osu_client_id = "id"
    cfg.osu_client_secret = "secret"
    for bid, fn in [(201, "201 A - B.osz"), (202, "202 C - D.osz")]:
        t = ParsedTrack(beatmapset_id=bid, filename=fn, artist="A", title="T",
                        display_name="A - T", size_bytes=1)
        tid, _ = db.upsert_track(t, "when")
        db.set_library_state(tid, True, "backed", "when")
    monkeypatch.setattr(osu_api, "beatmapset_availability",
                        lambda *a, **k: {201: "available", 202: "gone"})
    res = svc.scan_lost_maps()
    assert res == {"checked": 2, "gone": 1}
    assert db.lost_map_count() == 1
    db.close()
