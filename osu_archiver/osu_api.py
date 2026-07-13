"""Optional osu! API v2 client: fetch the authoritative beatmap-pack list.

With a reference of every published pack we can tell, for *any* category
(including Spotlights), whether a red row is genuinely missing — instead of
guessing. Uses the client-credentials grant (scope ``public``); the user
registers an OAuth app once at https://osu.ppy.sh/home/account/edit and pastes
the client id + secret into Settings.

Stdlib only (urllib), so no extra dependency and it bundles cleanly.
"""
from __future__ import annotations

import datetime as _dt
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .models import MODE_NAMES
from .parsing import parse_pack_name

TOKEN_URL = "https://osu.ppy.sh/oauth/token"
API_BASE = "https://osu.ppy.sh/api/v2"
PACK_TYPES = ("standard", "featured", "tournament", "loved", "spotlight",
              "theme", "artist", "chart")


class OsuApiError(RuntimeError):
    pass


def _token(client_id: str, client_secret: str) -> str:
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": "public",
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())["access_token"]
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        raise OsuApiError(f"authentication failed: {exc}") from exc


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}",
                      "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def fetch_reference(client_id: str, client_secret: str, progress=None) -> dict:
    """Fetch every pack across all types. Returns a reference dict."""
    token = _token(client_id, client_secret)
    packs: list[dict] = []
    for pack_type in PACK_TYPES:
        cursor = None
        while True:
            query = {"type": pack_type}
            if cursor:
                query["cursor_string"] = cursor
            url = f"{API_BASE}/beatmaps/packs?" + urllib.parse.urlencode(query)
            try:
                data = _get(url, token)
            except urllib.error.HTTPError as exc:
                if exc.code in (404, 422):
                    break
                raise OsuApiError(f"{pack_type}: HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                raise OsuApiError(f"{pack_type}: {exc}") from exc

            for bp in data.get("beatmap_packs", []):
                packs.append(_normalize(bp, pack_type))
            if progress:
                progress(f"{pack_type}: {len(packs)}")
            cursor = data.get("cursor_string")
            if not cursor:
                break
    return {
        "fetched_at": _dt.datetime.now().replace(microsecond=0).isoformat(),
        "count": len(packs),
        "packs": packs,
    }


def _normalize(bp: dict, pack_type: str) -> dict:
    tag = bp.get("tag") or ""
    name = bp.get("name") or ""
    pp = parse_pack_name(f"{tag} - {name}.zip") if tag else None
    mode = (pp.mode if pp else None) or MODE_NAMES.get(bp.get("ruleset_id"))
    return {
        "code": tag,
        "name": name,
        "type": pack_type,
        "series": pp.series if pp else None,
        "number": pp.number if pp else None,
        "category": pp.category if pp else "Other",
        "mode": mode,
        "year": pp.year if pp else None,
        "season": pp.season if pp else None,
        "date": bp.get("date"),
    }


def save_reference(reference: dict, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")


def load_reference(path: Path) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def reference_by_series(reference: dict | None) -> dict[str, list[dict]]:
    """Group reference packs by series prefix for gap validation."""
    out: dict[str, list[dict]] = {}
    if not reference:
        return out
    for entry in reference.get("packs", []):
        series = entry.get("series")
        if series:
            out.setdefault(series, []).append(entry)
    return out
