# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the Drive REST client (fake transport, no network)."""
import pytest

from rosu.drive import client
from rosu.drive.auth import DriveCancelled, DriveError


class FakeAuth:
    def get_access_token(self, now=None):
        return "tok"


def test_ensure_folder_found():
    calls = []

    def transport(method, url, headers=None, body=None):
        calls.append((method, url))
        assert method == "GET" and "/files?" in url
        assert headers["Authorization"] == "Bearer tok"
        return 200, {}, b'{"files":[{"id":"FOLDER1","name":"Rosu"}]}'

    c = client.DriveClient(FakeAuth(), transport=transport)
    assert c.ensure_folder("Rosu") == "FOLDER1"
    assert len(calls) == 1          # found -> no create POST


def test_ensure_folder_creates_when_absent():
    seq = []

    def transport(method, url, headers=None, body=None):
        seq.append(method)
        if method == "GET":
            return 200, {}, b'{"files":[]}'
        return 200, {}, b'{"id":"NEWID"}'

    c = client.DriveClient(FakeAuth(), transport=transport)
    assert c.ensure_folder("Rosu") == "NEWID"
    assert seq == ["GET", "POST"]


def test_api_error_raises():
    def transport(method, url, headers=None, body=None):
        return 403, {}, b'{"error":"forbidden"}'

    c = client.DriveClient(FakeAuth(), transport=transport)
    with pytest.raises(DriveError):
        c.list_folder("FOLDER1")


def test_upload_file_resumable(tmp_path):
    f = tmp_path / "chunk-0000.zip"
    f.write_bytes(b"X" * 100)
    prog = []

    def transport(method, url, headers=None, body=None):
        if method == "POST":
            assert "uploadType=resumable" in url
            assert headers["X-Upload-Content-Length"] == "100"
            return 200, {"Location": "https://sess/upload/1"}, b""
        assert method == "PUT" and url == "https://sess/upload/1"
        assert headers["Content-Range"] == "bytes 0-99/100"
        return 200, {}, b'{"id":"UP1"}'

    c = client.DriveClient(FakeAuth(), transport=transport)
    fid = c.upload_file(f, "chunk-0000.zip", "FOLDER1",
                        progress=lambda done, total: prog.append((done, total)))
    assert fid == "UP1"
    assert prog[-1] == (100, 100)


def test_upload_file_multi_chunk_with_308(tmp_path):
    f = tmp_path / "chunk-0001.zip"
    f.write_bytes(b"Y" * 20)
    ranges = []

    def transport(method, url, headers=None, body=None):
        if method == "POST":
            return 200, {"Location": "https://sess/2"}, b""
        ranges.append(headers["Content-Range"])
        # first PUT: incomplete; second: done
        if len(ranges) == 1:
            return 308, {}, b""
        return 201, {}, b'{"id":"UP2"}'

    c = client.DriveClient(FakeAuth(), transport=transport)
    fid = c.upload_file(f, "chunk-0001.zip", "FOLDER1", chunk_size=10)
    assert fid == "UP2"
    assert ranges == ["bytes 0-9/20", "bytes 10-19/20"]


def test_list_folder_follows_pagination():
    # A folder with >1 page must be fully enumerated — chunk-index reconciliation
    # relies on seeing every name, so a truncated listing could reuse a name.
    pages = [
        (200, {}, b'{"nextPageToken":"TOK2","files":[{"id":"a","name":"chunk-dev-0000.zip"}]}'),
        (200, {}, b'{"files":[{"id":"b","name":"chunk-dev-0001.zip"}]}'),
    ]
    urls = []

    def transport(method, url, headers=None, body=None):
        urls.append(url)
        return pages.pop(0)

    c = client.DriveClient(FakeAuth(), transport=transport)
    files = c.list_folder("FOLDER1")
    assert [f["name"] for f in files] == ["chunk-dev-0000.zip", "chunk-dev-0001.zip"]
    assert len(urls) == 2                              # both pages fetched
    assert "TOK2" in urls[1] and "TOK2" not in urls[0]  # 2nd request carried token


def test_upload_file_cancelled_aborts_before_put(tmp_path):
    f = tmp_path / "chunk-0000.zip"
    f.write_bytes(b"X" * 100)

    def transport(method, url, headers=None, body=None):
        if method == "POST":
            return 200, {"Location": "https://sess/1"}, b""
        raise AssertionError("PUT must not run once cancelled")

    c = client.DriveClient(FakeAuth(), transport=transport)
    with pytest.raises(DriveCancelled):
        c.upload_file(f, "chunk-0000.zip", "FOLDER1", cancel=lambda: True)
