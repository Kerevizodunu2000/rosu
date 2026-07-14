# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the GitHub update check (item E, v1.0). No real network — urlopen
is mocked, so responses/errors are simulated."""
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

    def read(self):
        return self._payload


def test_latest_release_parses(monkeypatch):
    payload = json.dumps({"tag_name": "v1.2.0", "html_url": "https://x/rel"}).encode()
    monkeypatch.setattr(update_check.urllib.request, "urlopen",
                        lambda req, timeout=10: _FakeResp(payload))
    assert update_check.latest_release() == {"tag": "v1.2.0", "url": "https://x/rel"}


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
    monkeypatch.setattr(update_check, "latest_release",
                        lambda owner=None, repo=None: {"tag": "v9.9.9", "url": "u"})
    assert update_check.check("1.0.0") == {"newer": True, "tag": "v9.9.9", "url": "u"}


def test_check_none_when_unreachable(monkeypatch):
    monkeypatch.setattr(update_check, "latest_release",
                        lambda owner=None, repo=None: None)
    assert update_check.check("1.0.0") is None
