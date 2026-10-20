# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the third-party mirror download client (v1.7).

No real network access — ``urlopen`` is monkeypatched with a fake response
that yields chunks from an in-memory buffer.
"""

from rosu import api_mirror


class _FakeResp:
    def __init__(self, status=200, headers=None, chunks=(b"",)):
        self.status = status
        self.headers = headers or {}
        self._chunks = list(chunks)

    def read(self, n=8192):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_urlopen(monkeypatch, resp):
    monkeypatch.setattr(api_mirror.urllib.request, "urlopen",
                        lambda req, timeout=30: resp)


def test_download_success(tmp_path, monkeypatch):
    data = b"fake-osz-bytes"
    resp = _FakeResp(headers={"Content-Length": str(len(data))},
                     chunks=[data, b""])
    _patch_urlopen(monkeypatch, resp)
    dest = tmp_path / "out.osz"
    progress_calls = []
    ok = api_mirror.download_osz(123, dest, progress=progress_calls.append)
    assert ok is True
    assert dest.read_bytes() == data
    assert progress_calls   # progress was reported at least once
    # no stray temp file left behind
    assert list(tmp_path.iterdir()) == [dest]


def test_download_non_200_status(tmp_path, monkeypatch):
    _patch_urlopen(monkeypatch, _FakeResp(status=404))
    dest = tmp_path / "out.osz"
    assert api_mirror.download_osz(123, dest) is False
    assert not dest.exists()
    assert list(tmp_path.iterdir()) == []   # no leftover temp file


def test_download_rejects_oversized_content_length(tmp_path, monkeypatch):
    huge = api_mirror._MAX_DOWNLOAD_BYTES + 1
    _patch_urlopen(monkeypatch, _FakeResp(headers={"Content-Length": str(huge)}))
    dest = tmp_path / "out.osz"
    assert api_mirror.download_osz(123, dest) is False
    assert not dest.exists()
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_stream_exceeding_cap_without_content_length(tmp_path, monkeypatch):
    # No (or a lying) Content-Length header — the running total must still be
    # capped as bytes actually arrive, so a malicious/huge stream can't fill disk.
    monkeypatch.setattr(api_mirror, "_MAX_DOWNLOAD_BYTES", 2048)
    chunk = b"x" * 1024
    resp = _FakeResp(headers={}, chunks=[chunk, chunk, chunk, b""])
    _patch_urlopen(monkeypatch, resp)
    dest = tmp_path / "out.osz"
    assert api_mirror.download_osz(123, dest) is False
    assert not dest.exists()
    assert list(tmp_path.iterdir()) == []


def test_download_urlopen_raises_is_handled(tmp_path, monkeypatch):
    def boom(req, timeout=30):
        raise OSError("network unreachable")
    monkeypatch.setattr(api_mirror.urllib.request, "urlopen", boom)
    dest = tmp_path / "out.osz"
    assert api_mirror.download_osz(123, dest) is False
    assert not dest.exists()
