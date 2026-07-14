# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional, best-effort update check against the GitHub Releases API.

Stdlib only (urllib), runs off the UI thread, and fails silently on any error
(offline, rate-limited, private repo) — a missed check must never disrupt the
app. No token is sent; the public "latest release" endpoint is enough.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

OWNER = "Kerevizodunu2000"
REPO = "rosu"
_API = "https://api.github.com/repos/{owner}/{repo}/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    """Turn 'v1.2.3' / '1.2.3' into a comparable (1, 2, 3); junk -> (0,)."""
    nums = re.findall(r"\d+", tag or "")
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(latest_tag: str, current: str) -> bool:
    """True if ``latest_tag`` is a strictly higher version than ``current``."""
    return _parse_version(latest_tag) > _parse_version(current)


def latest_release(owner: str = OWNER, repo: str = REPO,
                   timeout: int = 10) -> dict | None:
    """GET the latest published release. Returns ``{'tag', 'url'}`` or ``None``
    on any failure (network, parse, missing tag)."""
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
            "url": data.get("html_url")
            or f"https://github.com/{owner}/{repo}/releases/latest"}


def check(current: str, owner: str = OWNER, repo: str = REPO,
          progress=None) -> dict | None:
    """Full check used by the UI worker. Returns
    ``{'newer': bool, 'tag': str, 'url': str}`` or ``None`` if it couldn't run."""
    rel = latest_release(owner, repo)
    if not rel:
        return None
    return {"newer": is_newer(rel["tag"], current),
            "tag": rel["tag"], "url": rel["url"]}
