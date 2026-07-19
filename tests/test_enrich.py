# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for osu! API metadata enrichment (osu_api.beatmapset_details /
_normalize_beatmapset_details + services.enrich_metadata). No real network."""
import pytest

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


_SAMPLE = {
    "status": "ranked",
    "ranked_date": "2020-01-02T00:00:00Z",
    "submitted_date": "2019-12-01T00:00:00Z",
    "last_updated": "2020-01-01T00:00:00Z",
    "play_count": 12345,
    "favourite_count": 67,
    "genre": {"id": 5, "name": "Electronic"},
    "language": {"id": 2, "name": "English"},
    "beatmaps": [
        {"checksum": "abc", "version": "Easy", "mode_int": 3,
         "difficulty_rating": 2.1, "cs": 4.0, "ar": 5.0, "accuracy": 7.0,
         "drain": 6.0, "bpm": 180.0, "total_length": 100},
    ],
}


def test_get_malformed_body_raises_osu_api_error(monkeypatch):
    # A 200 whose body isn't JSON (Cloudflare interstitial, truncated reply) must
    # surface as OsuApiError with a readable message, not a raw JSONDecodeError.
    class FakeResp:
        status = 200

        def read(self):
            return b"<html>interstitial</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(osu_api.urllib.request, "urlopen",
                        lambda req, timeout=60: FakeResp())
    with pytest.raises(osu_api.OsuApiError, match="malformed"):
        osu_api._get("https://osu.ppy.sh/api/v2/x", "tok")


def test_normalize_extracts_fields_and_nested_names():
    n = osu_api._normalize_beatmapset_details(_SAMPLE)
    assert n["status"] == "ranked"
    assert n["play_count"] == 12345
    assert n["favourite_count"] == 67
    assert n["genre"] == "Electronic"      # nested {name:...} flattened
    assert n["language"] == "English"
    b = n["beatmaps"][0]
    assert b["checksum"] == "abc"
    assert b["od"] == 7.0                   # API 'accuracy' -> OD
    assert b["hp"] == 6.0                   # API 'drain' -> HP
    assert b["difficulty_rating"] == 2.1


def test_normalize_handles_missing_optional_fields():
    n = osu_api._normalize_beatmapset_details({})
    assert n["status"] is None and n["beatmaps"] == []


def test_normalize_survives_malformed_body():
    # Untrusted API JSON with wrong shapes must not raise (it would abort the
    # whole enrichment scan) — bad fields degrade to None/[] instead.
    n = osu_api._normalize_beatmapset_details(
        {"beatmaps": {"weird": "dict"}, "genre": ["a"], "language": 123})
    assert n["beatmaps"] == [] and n["genre"] is None and n["language"] is None
    n2 = osu_api._normalize_beatmapset_details(["not", "a", "dict"])
    assert n2["status"] is None and n2["beatmaps"] == []
    # a beatmaps list with a non-dict entry skips that entry, keeps the good one
    n3 = osu_api._normalize_beatmapset_details(
        {"beatmaps": ["junk", {"checksum": "x", "difficulty_rating": 3.0}]})
    assert len(n3["beatmaps"]) == 1 and n3["beatmaps"][0]["checksum"] == "x"


def test_beatmapset_details_200_and_404(monkeypatch):
    codes = {1: (_SAMPLE, 200, None), 2: (None, 404, None)}
    monkeypatch.setattr(osu_api, "_token", lambda cid, cs: "tok")
    monkeypatch.setattr(osu_api, "_get_json",
                        lambda url, token: codes[int(url.rsplit("/", 1)[1])])
    _no_sleep(monkeypatch)
    out = osu_api.beatmapset_details([1, 2], "id", "secret")
    assert out[1]["status"] == "ranked"
    assert out[2] is None            # 404 -> None (gone)


def test_beatmapset_details_respects_max_calls(monkeypatch):
    monkeypatch.setattr(osu_api, "_token", lambda cid, cs: "tok")
    monkeypatch.setattr(osu_api, "_get_json", lambda url, token: (_SAMPLE, 200, None))
    _no_sleep(monkeypatch)
    out = osu_api.beatmapset_details([1, 2, 3, 4], "id", "secret", max_calls=2)
    assert len(out) == 2


def test_beatmapset_details_retries_on_429(monkeypatch):
    seq = {1: [(None, 429, None), (_SAMPLE, 200, None)]}
    monkeypatch.setattr(osu_api, "_token", lambda cid, cs: "tok")
    monkeypatch.setattr(osu_api, "_get_json",
                        lambda url, token: seq[int(url.rsplit("/", 1)[1])].pop(0))
    _no_sleep(monkeypatch)
    out = osu_api.beatmapset_details([1], "id", "secret")
    assert out[1]["status"] == "ranked"


def _svc(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    return cfg, db, Services(cfg, db, DummyLog())


def test_enrich_metadata_gated_when_disabled(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    cfg.osu_client_id = "id"
    cfg.osu_client_secret = "secret"
    assert svc.enrich_metadata() == {"error": "disabled"}
    db.close()


def test_enrich_metadata_gated_without_creds(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    cfg.enrich_from_api_enabled = True
    assert svc.enrich_metadata() == {"error": "no_api"}
    db.close()


def test_enrich_metadata_applies_and_marks_gone(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    cfg.enrich_from_api_enabled = True
    cfg.osu_client_id = "id"
    cfg.osu_client_secret = "secret"
    for bid in (11, 22):
        t = ParsedTrack(beatmapset_id=bid, filename=f"{bid} A - B.osz",
                        artist="A", title="B", display_name="A - B", size_bytes=1)
        tid, _ = db.upsert_track(t, "when")
        db.set_library_state(tid, True, "present", "when")
    monkeypatch.setattr(osu_api, "beatmapset_details",
                        lambda *a, **k: {11: osu_api._normalize_beatmapset_details(_SAMPLE),
                                         22: None})
    res = svc.enrich_metadata()
    assert res["checked"] == 2 and res["updated"] == 1 and res["remaining"] == 0
    rows = {r["beatmapset_id"]: r for r in db.all_tracks()}
    assert rows[11]["ranked_status"] == "ranked"
    assert rows[11]["availability"] == "available"
    assert rows[22]["availability"] == "gone"      # the 404 set is flagged lost
    db.close()
