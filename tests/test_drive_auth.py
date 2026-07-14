# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for Drive OAuth logic (no browser/network/keyring)."""
import base64
import hashlib

import pytest

from rosu.drive import auth
from rosu.drive.auth import ClientConfig, DriveAuth, DriveAuthError, DriveNotConfigured


class FakeStore:
    def __init__(self, token=None):
        self.token = token
        self.deleted = False

    def get(self):
        return self.token

    def set(self, token):
        self.token = token

    def delete(self):
        self.token = None
        self.deleted = True


def _client():
    return ClientConfig("cid", "secret")


def test_make_pkce_is_s256():
    verifier, challenge = auth.make_pkce()
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected
    assert "=" not in verifier and "=" not in challenge   # base64url, unpadded


def test_parse_client_installed_web_and_missing():
    assert auth._parse_client('{"installed":{"client_id":"a","client_secret":"b"}}') \
        == ClientConfig("a", "b")
    assert auth._parse_client('{"web":{"client_id":"a","client_secret":"b"}}') \
        == ClientConfig("a", "b")
    with pytest.raises(DriveNotConfigured):
        auth._parse_client('{"installed":{"client_id":"a"}}')     # no secret
    with pytest.raises(DriveNotConfigured):
        auth._parse_client("{not json")


def test_load_client_config_from_env(monkeypatch):
    monkeypatch.setenv("ROSU_OAUTH_CLIENT_JSON",
                       '{"installed":{"client_id":"x","client_secret":"y"}}')
    assert auth.load_client_config() == ClientConfig("x", "y")


def test_get_access_token_refreshes_and_caches():
    calls = []

    def fake_post(url, fields):
        calls.append(fields)
        return {"access_token": "AT1", "expires_in": 3600}

    a = DriveAuth(client=_client(), token_store=FakeStore("REFRESH"),
                  http_post=fake_post)
    assert a.get_access_token(now=1000) == "AT1"
    assert calls[0]["grant_type"] == "refresh_token"
    # cached: no second network call while still valid
    assert a.get_access_token(now=1500) == "AT1"
    assert len(calls) == 1
    # expired: refreshes again
    a.get_access_token(now=1000 + 3600)
    assert len(calls) == 2


def test_get_access_token_without_token_raises():
    a = DriveAuth(client=_client(), token_store=FakeStore(None),
                  http_post=lambda u, f: {})
    with pytest.raises(DriveAuthError):
        a.get_access_token()


def test_invalid_grant_forces_logout():
    store = FakeStore("REFRESH")
    a = DriveAuth(client=_client(), token_store=store,
                  http_post=lambda u, f: {"error": "invalid_grant"})
    with pytest.raises(DriveAuthError):
        a.get_access_token()
    assert store.deleted and store.token is None   # revoked token cleared


def test_is_connected_and_logout():
    store = FakeStore("REFRESH")
    a = DriveAuth(client=_client(), token_store=store, http_post=lambda u, f: {})
    assert a.is_connected() is True
    a.logout()
    assert a.is_connected() is False
