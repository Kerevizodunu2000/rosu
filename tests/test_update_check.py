# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the update check (item E, v1.0; rosu-web first since v1.8). No real
network — urlopen / the fetchers are mocked, so responses/errors are simulated."""
import json
import urllib.error

from rosu import update_check


def test_is_newer():
    assert update_check.is_newer("v1.1.0", "1.0.0")
    assert update_check.is_newer("1.0.1", "1.0.0")
    assert not update_check.is_newer("v1.0.0", "1.0.0")
    assert not update_check.is_newer("v0.9.0", "1.0.0")


def test_parse_version_handles_junk():
    assert update_check._parse_version("garbage") == (0,)
    assert update_check._parse_version("v2.3") == (2, 3)
    assert update_check._parse_version("v10.0.0") == (10, 0, 0)


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, *_):
        return self._payload


def test_latest_release_parses(monkeypatch):
    page = "https://github.com/Kerevizodunu2000/rosu/releases/tag/v1.2.0"
    payload = json.dumps({"tag_name": "v1.2.0", "html_url": page}).encode()
    monkeypatch.setattr(update_check.urllib.request, "urlopen",
                        lambda req, timeout=10: _FakeResp(payload))
    assert update_check.latest_release() == {"tag": "v1.2.0", "url": page}
    payload = json.dumps({"tag_name": "v1.2.0", "html_url": "https://x/rel"}).encode()
    assert update_check.latest_release()["url"].endswith("/rosu/releases/latest")   # foreign link


def test_latest_release_network_error_returns_none(monkeypatch):
    def boom(req, timeout=10):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(update_check.urllib.request, "urlopen", boom)
    assert update_check.latest_release() is None


def test_latest_release_missing_tag_returns_none(monkeypatch):
    payload = json.dumps({"name": "no tag here"}).encode()
    monkeypatch.setattr(update_check.urllib.request, "urlopen",
                        lambda req, timeout=10: _FakeResp(payload))
    assert update_check.latest_release() is None


def test_check_reports_newer(monkeypatch):
    monkeypatch.setattr(update_check, "latest_from_site", lambda **_: None)
    monkeypatch.setattr(update_check, "latest_release",
                        lambda owner=None, repo=None: {"tag": "v9.9.9", "url": "u"})
    assert update_check.check("1.0.0") == {"newer": True, "tag": "v9.9.9", "url": "u",
                                           "download_url": None, "notes": ""}


def test_check_none_when_unreachable(monkeypatch):
    monkeypatch.setattr(update_check, "latest_from_site", lambda **_: None)
    monkeypatch.setattr(update_check, "latest_release",
                        lambda owner=None, repo=None: None)
    assert update_check.check("1.0.0") is None


_REL = "https://github.com/Kerevizodunu2000/rosu/releases/"


def test_site_reply_is_preferred_and_carries_the_download(monkeypatch):
    site = {"ok": True, "tag": "v1.8.0", "url": _REL + "tag/v1.8.0",
            "download_url": _REL + "download/v1.8.0/rosu-v1.8.0-win64.exe", "notes": "- x"}
    monkeypatch.setattr(update_check.urllib.request, "urlopen",
                        lambda req, timeout=10: _FakeResp(json.dumps(site).encode()))
    monkeypatch.setattr(update_check, "latest_release",
                        lambda owner=None, repo=None: (_ for _ in ()).throw(AssertionError))
    res = update_check.check("1.7.1")
    assert res == {"newer": True, "tag": "v1.8.0", "url": site["url"],
                   "download_url": site["download_url"], "notes": "- x"}


def test_site_reply_validation_rejects_foreign_links():
    ok = {"ok": True, "tag": "v1.8.0", "url": _REL + "tag/v1.8.0"}
    assert update_check.parse_site_reply(ok)["download_url"] is None
    assert update_check.parse_site_reply({**ok, "url": "https://evil.example/x"}) is None
    assert update_check.parse_site_reply({**ok, "tag": "latest"}) is None
    assert update_check.parse_site_reply({**ok, "ok": False}) is None
    assert update_check.parse_site_reply("nope") is None
    bad_dl = update_check.parse_site_reply({**ok, "download_url": "https://evil.example/x.exe"})
    assert bad_dl["download_url"] is None
    for sneaky in (_REL + "../../../evil/x.exe", _REL + "%2e%2e/%2e%2e/evil/x.exe",
                   _REL + "download/v1.8.0/..", _REL + "tag/v1.8.0/../../x",
                   _REL + "download/v1.8.0/x.exe?y=1", _REL[:-1] + "s/x"):
        assert update_check.parse_site_reply({**ok, "download_url": sneaky})["download_url"] is None
        assert update_check.parse_site_reply({**ok, "url": sneaky}) is None


def test_site_failure_falls_back_to_github(monkeypatch):
    def boom(req, timeout=10):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(update_check.urllib.request, "urlopen", boom)
    monkeypatch.setattr(update_check, "latest_release",
                        lambda owner=None, repo=None: {"tag": "v1.0.0", "url": "u"})
    assert update_check.check("1.0.0")["newer"] is False
