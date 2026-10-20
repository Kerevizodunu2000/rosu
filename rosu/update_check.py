# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional, best-effort update check.

Asks Rosu's own site first (``rosu-web`` ``GET /api/latest-version`` — CDN
cached, and it also hands back the direct ``.exe`` download link and a notes
excerpt), then falls back to the GitHub Releases API if the site is unreachable.

Stdlib only (urllib), runs off the UI thread, and fails silently on any error
(offline, rate-limited) — a missed check must never disrupt the app. Nothing
about the user is sent: a plain GET with a ``Rosu/<version>`` User-Agent.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

OWNER = "Kerevizodunu2000"
REPO = "rosu"
_API = "https://api.github.com/repos/{owner}/{repo}/releases/latest"
SITE_LATEST = "https://rosu-web.vercel.app/api/latest-version"
# The only links the UI may show: this repo's latest/tag pages and its release
# assets. Matched whole, from a closed character set — no "..", "%2e" or "\\"
# can steer a browser to another repository.
_RELEASE_LINK = re.compile(
    rf"https://github\.com/{OWNER}/{REPO}/releases/"
    r"(?:latest|tag/v?\d+\.\d+\.\d+|download/v?\d+\.\d+\.\d+/[A-Za-z0-9][A-Za-z0-9._-]*)")
_NOTES_MAX = 1500


def _parse_version(tag: str) -> tuple[int, ...]:
    """Turn 'v1.2.3' / '1.2.3' into a comparable (1, 2, 3); junk -> (0,)."""
    nums = re.findall(r"\d+", tag or "")
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(latest_tag: str, current: str) -> bool:
    """True if ``latest_tag`` is a strictly higher version than ``current``."""
    return _parse_version(latest_tag) > _parse_version(current)


def _get_json(url: str, timeout: int, user_agent: str):
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read(256 * 1024))


def _release_link(url) -> str | None:
    """Only ever hand the UI a link into this project's own GitHub releases."""
    return url if isinstance(url, str) and _RELEASE_LINK.fullmatch(url) else None


def parse_site_reply(data) -> dict | None:
    """Validate the rosu-web reply → ``{'tag','url','download_url','notes'}``."""
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    tag = data.get("tag")
    if not isinstance(tag, str) or not re.fullmatch(r"v?\d+\.\d+\.\d+", tag):
        return None
    url = _release_link(data.get("url"))
    if not url:
        return None
    notes = data.get("notes") if isinstance(data.get("notes"), str) else ""
    return {"tag": tag, "url": url,
            "download_url": _release_link(data.get("download_url")),
            "notes": notes[:_NOTES_MAX]}


def latest_from_site(timeout: int = 10, user_agent: str = "Rosu") -> dict | None:
    try:
        return parse_site_reply(_get_json(SITE_LATEST, timeout, user_agent))
    except (urllib.error.URLError, ValueError, OSError):
        return None


def latest_release(owner: str = OWNER, repo: str = REPO,
                   timeout: int = 10) -> dict | None:
    """GET the latest published release from GitHub directly. Returns
    ``{'tag', 'url'}`` or ``None`` on any failure (network, parse, missing tag)."""
    url = _API.format(owner=owner, repo=repo)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "rosu-update-check",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, ValueError, OSError):
        return None
    tag = data.get("tag_name")
    if not tag:
        return None
    return {"tag": tag,
            "url": _release_link(data.get("html_url"))
            or f"https://github.com/{owner}/{repo}/releases/latest"}


def check(current: str, owner: str = OWNER, repo: str = REPO,
          progress=None) -> dict | None:
    """Full check used by the UI worker. Returns ``{'newer': bool, 'tag', 'url',
    'download_url', 'notes'}`` or ``None`` if it couldn't run."""
    rel = latest_from_site(user_agent=f"Rosu/{current}") or latest_release(owner, repo)
    if not rel:
        return None
    return {"newer": is_newer(rel["tag"], current), "tag": rel["tag"], "url": rel["url"],
            "download_url": rel.get("download_url"), "notes": rel.get("notes", "")}
