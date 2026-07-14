# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal Google Drive REST v3 client over stdlib urllib (v0.8).

Just the operations the backup needs: find/create the Rosu folder, resumable
upload of a chunk archive, list a folder, and download a file. No
google-api-python-client / requests — the same stdlib-only stance as osu_api.py,
so the frozen exe stays lean and TLS uses the system trust store.

The HTTP transport is injectable so folder/upload logic is unit-testable with a
fake, never touching the network.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from .auth import DriveAuth, DriveCancelled, DriveError

_API = "https://www.googleapis.com/drive/v3"
_UPLOAD = "https://www.googleapis.com/upload/drive/v3"
_FOLDER_MIME = "application/vnd.google-apps.folder"
_DL_BUF = 1024 * 1024


def _urllib_transport(method: str, url: str, headers: dict | None = None,
                      body: bytes | None = None, timeout: int = 120):
    """Return (status, headers_dict, body_bytes). 308 arrives as HTTPError."""
    req = urllib.request.Request(url, data=body, method=method,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()
    except urllib.error.URLError as exc:
        raise DriveError(f"network error: {exc.reason}") from exc


def _q_escape(value: str) -> str:
    """Escape a value for a Drive query literal (backslash + single quote)."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


class DriveClient:
    def __init__(self, auth: DriveAuth, transport: Callable | None = None):
        self._auth = auth
        self._transport = transport if transport is not None else _urllib_transport

    # -- low-level -----------------------------------------------------------
    def _api(self, method: str, path: str, body: bytes | None = None,
             content_type: str | None = None):
        token = self._auth.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        if content_type:
            headers["Content-Type"] = content_type
        status, hdrs, data = self._transport(method, _API + path,
                                              headers=headers, body=body)
        if not 200 <= status < 300:
            raise DriveError(f"Drive API {method} {path} -> {status}: {data[:200]!r}")
        return status, hdrs, data

    def _find(self, name: str, parent: str | None, folder: bool = False):
        parts = [f"name = '{_q_escape(name)}'", "trashed = false"]
        if folder:
            parts.append(f"mimeType = '{_FOLDER_MIME}'")
        if parent:
            parts.append(f"'{_q_escape(parent)}' in parents")
        params = urllib.parse.urlencode(
            {"q": " and ".join(parts), "fields": "files(id,name,size)",
             "pageSize": 10, "spaces": "drive"})
        _st, _h, data = self._api("GET", "/files?" + params)
        files = json.loads(data).get("files", [])
        return files[0]["id"] if files else None

    # -- operations ----------------------------------------------------------
    def ensure_folder(self, name: str = "Rosu",
                      parent: str | None = None) -> str:
        """Return the id of the named folder, creating it if absent."""
        existing = self._find(name, parent, folder=True)
        if existing:
            return existing
        meta: dict = {"name": name, "mimeType": _FOLDER_MIME}
        if parent:
            meta["parents"] = [parent]
        _st, _h, data = self._api(
            "POST", "/files?fields=id",
            body=json.dumps(meta).encode("utf-8"),
            content_type="application/json; charset=UTF-8")
        return json.loads(data)["id"]

    def find_file(self, name: str, parent: str | None) -> str | None:
        return self._find(name, parent, folder=False)

    def list_folder(self, parent: str) -> list[dict]:
        params = urllib.parse.urlencode(
            {"q": f"'{_q_escape(parent)}' in parents and trashed = false",
             "fields": "files(id,name,size)", "pageSize": 1000, "spaces": "drive"})
        _st, _h, data = self._api("GET", "/files?" + params)
        return json.loads(data).get("files", [])

    def delete_file(self, file_id: str) -> None:
        self._api("DELETE", f"/files/{urllib.parse.quote(file_id)}")

    def upload_file(self, path: Path, name: str, parent: str,
                    progress: Callable[[int, int], None] | None = None,
                    cancel: Callable[[], bool] | None = None,
                    chunk_size: int = 8 * 1024 * 1024) -> str:
        """Resumable-upload ``path`` as ``name`` into ``parent``; return file id.

        ``cancel`` (if given) is polled between blocks so a long upload aborts
        promptly with :class:`DriveCancelled` instead of blocking shutdown.
        """
        path = Path(path)
        size = path.stat().st_size
        token = self._auth.get_access_token()
        meta = json.dumps({"name": name, "parents": [parent]}).encode("utf-8")
        status, hdrs, body = self._transport(
            "POST", _UPLOAD + "/files?uploadType=resumable&fields=id",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json; charset=UTF-8",
                     "X-Upload-Content-Type": "application/zip",
                     "X-Upload-Content-Length": str(size)},
            body=meta)
        if not 200 <= status < 300:
            raise DriveError(f"resumable init failed: {status} {body[:200]!r}")
        session = hdrs.get("Location") or hdrs.get("location")
        if not session:
            raise DriveError("resumable upload: no session URI returned")

        sent = 0
        with open(path, "rb") as fh:
            while sent < size:
                if cancel and cancel():
                    raise DriveCancelled("upload cancelled")
                block = fh.read(chunk_size)
                if not block:
                    break
                start, end = sent, sent + len(block) - 1
                st, _h, bd = self._transport(
                    "PUT", session,
                    headers={"Content-Length": str(len(block)),
                             "Content-Range": f"bytes {start}-{end}/{size}"},
                    body=block)
                if 200 <= st < 300:
                    if progress:
                        progress(size, size)
                    return json.loads(bd or b"{}").get("id", "")
                if st == 308:                      # resume incomplete: continue
                    sent = end + 1
                    if progress:
                        progress(sent, size)
                    continue
                raise DriveError(f"upload chunk failed: {st} {bd[:200]!r}")
        raise DriveError("resumable upload did not complete")

    def download_file(self, file_id: str, dest: Path,
                      progress: Callable[[int], None] | None = None,
                      max_bytes: int | None = None) -> Path:
        """Stream a file to ``dest`` atomically (.part -> replace)."""
        token = self._auth.get_access_token()
        url = f"{_API}/files/{urllib.parse.quote(file_id)}?alt=media"
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp, \
                    open(tmp, "wb") as out:
                total = 0
                while True:
                    block = resp.read(_DL_BUF)
                    if not block:
                        break
                    total += len(block)
                    if max_bytes is not None and total > max_bytes:
                        raise DriveError("download exceeds size cap")
                    out.write(block)
                    if progress:
                        progress(total)
            tmp.replace(dest)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return dest
