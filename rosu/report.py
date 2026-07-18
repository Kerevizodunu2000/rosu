# SPDX-License-Identifier: GPL-3.0-or-later
"""Bug-report / contact submission — POSTs a JSON form to Rosu's hosted endpoint
(the ``rosu-web`` Next.js backend on Vercel: it validates + rate-limits, stores
the report in Postgres and any screenshot on Drive; see ``rosu-web/``).

Stdlib HTTP only (urllib), matching ``osu_api`` / ``update_check`` / ``drive.auth``.
The endpoint URL is NOT a secret — it is a public write endpoint, like any
contact-form action — so it can live in the source; ``https://`` is required.
Everything sent is either typed by the user or basic diagnostics (app version,
OS, UI language); there is no telemetry and nothing is sent unless the user
submits the form. (Live since v1.4.0: Settings → "Report a problem" opens
:mod:`rosu.ui.report_dialog`, which submits here.)
"""
from __future__ import annotations

import base64
import json
import os
import platform
import sys
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__

# Rosu's report endpoint — the rosu-web ``POST /api/report`` (a public write
# endpoint, not a secret). ``https://`` only. Overridable at runtime via the
# ``ROSU_REPORT_ENDPOINT`` env var or an explicit ``endpoint=`` argument (tests).
REPORT_ENDPOINT = "https://rosu-web.vercel.app/api/report"

# Shared token the endpoint checks — FRICTION, not real auth (the honeypot +
# per-IP/global rate limits do the real work). Kept OUT of the public source:
# CI writes ``rosu/report_token.txt`` from the ``ROSU_REPORT_TOKEN`` secret at
# build time (gitignored). Resolved at runtime by ``_resolve_token`` (env var →
# bundled file → this empty default, so a source/dev build simply sends "").
REPORT_TOKEN = ""

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_MAX_IMAGE_BYTES = 3 * 1024 * 1024   # 3 MB decoded (~4 MB base64): the rosu-web
#                                      endpoint rejects decoded images over 3 MB,
#                                      so cap here and never hit its 413.
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}


class ReportError(Exception):
    """A client-side problem detected before sending (e.g. an oversized image).
    Its ``args[0]`` is a stable i18n-friendly reason string."""


def read_image_for_report(path) -> tuple[bytes, str, str]:
    """Read an image file for attachment, enforcing the type + size cap. Returns
    ``(bytes, filename, mime)``. Raises :class:`ReportError` (``"not_image"`` /
    ``"image_too_big"``) so the UI can show a precise message."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in _IMAGE_EXTS:
        raise ReportError("not_image")
    try:
        if p.stat().st_size > _MAX_IMAGE_BYTES:   # reject big files WITHOUT reading them
            raise ReportError("image_too_big")
        data = p.read_bytes()
    except OSError as exc:
        raise ReportError("read_failed") from exc
    if len(data) > _MAX_IMAGE_BYTES:              # belt-and-suspenders (file grew)
        raise ReportError("image_too_big")
    return data, p.name, _MIME.get(ext, "image/png")


def _resolve_endpoint(override: str | None) -> str:
    return override or os.environ.get("ROSU_REPORT_ENDPOINT") or REPORT_ENDPOINT


def _bundled_token() -> str:
    """Read the shared token from the file CI injects at build time (from the
    ``ROSU_REPORT_TOKEN`` secret). Gitignored, so open-source/local builds
    without the secret just send an empty token."""
    name = "report_token.txt"
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "rosu" / name)
    candidates.append(Path(__file__).resolve().parent / name)
    for p in candidates:
        try:
            if p.exists():
                return p.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return ""


def _resolve_token() -> str:
    return os.environ.get("ROSU_REPORT_TOKEN") or _bundled_token() or REPORT_TOKEN


def _os_string() -> str:
    try:
        return f"{platform.system()} {platform.release()}".strip()
    except Exception:
        return "unknown"


def submit_report(title, description, *, image_bytes=None, image_name=None,
                  image_mime=None, contact="", lang="", endpoint=None,
                  timeout=30, progress=None) -> dict:
    """POST a bug report / feedback message to the hosted endpoint.

    Builds a JSON body with the user's text, light diagnostics (app version, OS,
    UI language) and an optional base64-encoded image. Returns
    ``{"ok": True, "id": ...}`` on success, else ``{"ok": False, "error": ...}``:
    ``"empty"`` (missing title/description), ``"not_configured"`` (no endpoint
    baked in yet), ``"offline"`` (no network), ``"http"`` (non-2xx),
    ``"bad_reply"`` (unparseable response), or the server's own error string.
    Never raises on a network problem (mirrors ``update_check``)."""
    title = (title or "").strip()
    description = (description or "").strip()
    if not title or not description:
        return {"ok": False, "error": "empty"}
    url = _resolve_endpoint(endpoint)
    if not url:
        return {"ok": False, "error": "not_configured"}
    if not url.lower().startswith("https://"):
        # Refuse a plain-http (or schemeless) endpoint so a misconfig can't send
        # the user's text + contact + screenshot in cleartext.
        return {"ok": False, "error": "bad_endpoint"}

    payload = {
        "title": title,
        "description": description,
        "contact": (contact or "").strip(),
        "app_version": __version__,
        "os": _os_string(),
        "lang": lang or "",
        "token": _resolve_token(),
        "hp": "",   # honeypot: always empty from the real client
    }
    if image_bytes:
        payload["image_b64"] = base64.b64encode(image_bytes).decode("ascii")
        payload["image_name"] = image_name or "screenshot.png"
        payload["image_mime"] = image_mime or "image/png"

    if progress:
        progress("report_sending")
    body = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(   # a schemeless URL raises ValueError HERE
            url, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Accept": "application/json",
                     "User-Agent": f"Rosu/{__version__}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        # The endpoint returns structured JSON errors on non-2xx too (413
        # too_large, 429 rate_minute/rate_day/rate_global, 400 missing_fields/
        # bad_json, 500 server). Surface the specific reason when present so the
        # UI can explain it (e.g. rate-limited) instead of a generic failure.
        try:
            err = json.loads(exc.read().decode("utf-8", "replace")).get("error")
        except Exception:
            err = None
        return {"ok": False, "error": err or "http", "status": exc.code}
    except (urllib.error.URLError, OSError):
        return {"ok": False, "error": "offline"}
    except ValueError:
        # urlopen raises a bare ValueError for a malformed endpoint (no scheme) —
        # honour the "never raises on a network problem" contract.
        return {"ok": False, "error": "bad_endpoint"}
    try:
        data = json.loads(raw)
    except ValueError:
        return {"ok": False, "error": "bad_reply"}
    if data.get("ok"):
        return {"ok": True, "id": data.get("id")}
    return {"ok": False, "error": data.get("error", "server")}
