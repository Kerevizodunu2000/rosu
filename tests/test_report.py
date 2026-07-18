# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the bug-report submission (v1.4). No real network — urlopen is
mocked, so responses and errors are simulated."""
import base64
import json
import urllib.error

import pytest

from rosu import report


class _FakeResp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._payload


def _capture(monkeypatch, payload=b'{"ok":true,"id":7}'):
    """Patch urlopen to capture the outgoing Request and return ``payload``."""
    box = {}

    def fake_urlopen(req, timeout=30):
        box["req"] = req
        box["body"] = json.loads(req.data.decode("utf-8"))
        box["headers"] = req.headers
        return _FakeResp(payload)

    monkeypatch.setattr(report.urllib.request, "urlopen", fake_urlopen)
    return box


def test_submit_report_success_and_payload(monkeypatch):
    box = _capture(monkeypatch)
    res = report.submit_report("Crash on import", "steps here",
                               image_bytes=b"\x89PNG\r\n", image_name="s.png",
                               contact="me@x.com", lang="tr",
                               endpoint="https://x/exec")
    assert res == {"ok": True, "id": 7}
    body = box["body"]
    assert body["title"] == "Crash on import"
    assert body["description"] == "steps here"
    assert body["app_version"] == report.__version__
    assert body["os"]                         # diagnostics are non-empty
    assert body["lang"] == "tr"
    assert body["contact"] == "me@x.com"
    assert body["hp"] == ""                   # honeypot empty from a real client
    assert body["image_name"] == "s.png"
    assert base64.b64decode(body["image_b64"]) == b"\x89PNG\r\n"


def test_submit_report_trims_and_requires_fields():
    assert report.submit_report("", "x", endpoint="https://x/exec")["error"] == "empty"
    assert report.submit_report("t", "   ", endpoint="https://x/exec")["error"] == "empty"


def test_submit_report_not_configured(monkeypatch):
    # With the baked default cleared and no env override / arg, it never touches
    # the network.
    monkeypatch.setattr(report, "REPORT_ENDPOINT", "")
    monkeypatch.delenv("ROSU_REPORT_ENDPOINT", raising=False)
    assert report.submit_report("t", "d", endpoint="")["error"] == "not_configured"


def test_submit_report_rejects_non_https(monkeypatch):
    # A plain-http endpoint must be refused so nothing is sent in cleartext.
    monkeypatch.setattr(report, "REPORT_ENDPOINT", "http://insecure/api")
    monkeypatch.delenv("ROSU_REPORT_ENDPOINT", raising=False)
    assert report.submit_report("t", "d")["error"] == "bad_endpoint"


def test_submit_report_sends_resolved_token(monkeypatch):
    # The shared token (env → bundled file → default) flows into the payload.
    monkeypatch.setenv("ROSU_REPORT_TOKEN", "sekret")
    box = _capture(monkeypatch)
    report.submit_report("t", "d", endpoint="https://x/api/report")
    assert box["body"]["token"] == "sekret"


def test_submit_report_malformed_endpoint_never_raises():
    # A malformed endpoint (missing scheme) makes urlopen raise a bare ValueError;
    # submit_report must still return a dict, honouring "never raises".
    res = report.submit_report("t", "d", endpoint="bad-url-no-scheme")
    assert res == {"ok": False, "error": "bad_endpoint"}


def test_submit_report_offline(monkeypatch):
    def boom(req, timeout=30):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(report.urllib.request, "urlopen", boom)
    assert report.submit_report("t", "d", endpoint="https://x/exec") == {
        "ok": False, "error": "offline"}


def test_submit_report_http_error(monkeypatch):
    def boom(req, timeout=30):
        raise urllib.error.HTTPError("u", 500, "err", {}, None)
    monkeypatch.setattr(report.urllib.request, "urlopen", boom)
    res = report.submit_report("t", "d", endpoint="https://x/exec")
    assert res["ok"] is False and res["error"] == "http" and res["status"] == 500


def test_submit_report_surfaces_server_error_on_http_status(monkeypatch):
    # Non-2xx responses (e.g. 429) still carry a JSON error — surface it so the
    # UI can explain a rate-limit instead of a generic failure.
    import io

    def boom(req, timeout=30):
        raise urllib.error.HTTPError(
            "u", 429, "Too Many Requests", {},
            io.BytesIO(b'{"ok":false,"error":"rate_minute"}'))
    monkeypatch.setattr(report.urllib.request, "urlopen", boom)
    res = report.submit_report("t", "d", endpoint="https://x/api/report")
    assert res == {"ok": False, "error": "rate_minute", "status": 429}


def test_submit_report_bad_reply(monkeypatch):
    _capture(monkeypatch, payload=b"not json")
    assert report.submit_report("t", "d", endpoint="https://x/exec") == {
        "ok": False, "error": "bad_reply"}


def test_submit_report_server_error_passthrough(monkeypatch):
    _capture(monkeypatch, payload=b'{"ok":false,"error":"rate_limited"}')
    assert report.submit_report("t", "d", endpoint="https://x/exec") == {
        "ok": False, "error": "rate_limited"}


def test_read_image_size_cap(tmp_path):
    big = tmp_path / "big.png"
    big.write_bytes(b"x" * (report._MAX_IMAGE_BYTES + 1))
    with pytest.raises(report.ReportError) as exc:
        report.read_image_for_report(big)
    assert exc.value.args[0] == "image_too_big"


def test_read_image_rejects_non_image(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hi")
    with pytest.raises(report.ReportError) as exc:
        report.read_image_for_report(f)
    assert exc.value.args[0] == "not_image"


def test_read_image_ok(tmp_path):
    p = tmp_path / "shot.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    data, name, mime = report.read_image_for_report(p)
    assert data == b"\x89PNG\r\n\x1a\n"
    assert name == "shot.png"
    assert mime == "image/png"
