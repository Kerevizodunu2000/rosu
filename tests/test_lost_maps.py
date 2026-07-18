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


def test_status_code_maps_transport_error_to_zero(monkeypatch):
    import urllib.error

    def boom(req, timeout=60):
        raise urllib.error.URLError("connection reset")
    monkeypatch.setattr(osu_api.urllib.request, "urlopen", boom)
    assert osu_api._status_code("https://x/1", "tok") == (0, None)


def test_beatmapset_availability_transport_error_is_unknown(monkeypatch):
    # A transport blip on an id must degrade THAT id to 'unknown', not abort the
    # whole scan or discard results already gathered.
    monkeypatch.setattr(osu_api, "_token", lambda cid, cs: "tok")
    monkeypatch.setattr(osu_api, "_status_code", lambda url, token: (0, None))
    _no_sleep(monkeypatch)
    assert osu_api.beatmapset_availability([1, 2], "id", "secret") == {
        1: "unknown", 2: "unknown"}


def test_interruptible_sleep_returns_early_on_cancel(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def cancel():
        calls["n"] += 1
        return True
    osu_api._interruptible_sleep(60, cancel)   # would be 60s; must return at once
    assert calls["n"] == 1


def test_beatmapset_availability_cancel_during_backoff(monkeypatch):
    # Passes the outer per-id cancel check, then cancels inside the retry loop.
    monkeypatch.setattr(osu_api, "_token", lambda cid, cs: "tok")
    monkeypatch.setattr(osu_api, "_status_code", lambda url, token: (429, None))
    _no_sleep(monkeypatch)
    state = {"polls": 0}

    def cancel():
        state["polls"] += 1
        return state["polls"] >= 2
    assert osu_api.beatmapset_availability([1], "id", "secret", cancel=cancel) == {}


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
    assert res == {"checked": 2, "gone": 1, "total": 2, "remaining": 0}
    assert db.lost_map_count() == 1
    db.close()


def test_scan_lost_maps_unchecked_first_and_remaining(tmp_path, monkeypatch):
    """Repeated runs must walk the whole library: never-checked sets are asked
    about FIRST (before re-verifying already-checked ones), and the result says
    how many unchecked sets are still left after the capped batch (v1.4)."""
    cfg, db, svc = _svc(tmp_path)
    cfg.osu_client_id = "id"
    cfg.osu_client_secret = "secret"
    for bid in (301, 302, 303):
        t = ParsedTrack(beatmapset_id=bid, filename=f"{bid} A - B.osz",
                        artist="A", title="T", display_name="A - T", size_bytes=1)
        tid, _ = db.upsert_track(t, "when")
        db.set_library_state(tid, True, "backed", "when")
    db.set_availability(301, "available")   # 301 was checked in an earlier run

    seen = {}

    def fake_avail(ids, *a, max_calls=500, **k):
        seen["ids"] = list(ids)
        checked = list(ids)[:max_calls]
        return {b: "available" for b in checked}

    monkeypatch.setattr(osu_api, "beatmapset_availability", fake_avail)
    res = svc.scan_lost_maps(max_calls=1)
    assert seen["ids"][-1] == 301          # previously-checked id comes LAST
    assert set(seen["ids"][:2]) == {302, 303}   # never-checked ones first
    assert res["checked"] == 1
    assert res["total"] == 3
    assert res["remaining"] == 1           # one never-checked set still left
    db.close()
