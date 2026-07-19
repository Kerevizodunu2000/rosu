# SPDX-License-Identifier: GPL-3.0-or-later
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
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import __version__
from .models import MODE_NAMES
from .parsing import parse_pack_name

TOKEN_URL = "https://osu.ppy.sh/oauth/token"
API_BASE = "https://osu.ppy.sh/api/v2"
PACK_TYPES = ("standard", "featured", "tournament", "loved", "spotlight",
              "theme", "artist", "chart")

# osu!'s ToU asks callers to identify themselves and stay under ~60 req/min. We
# send a descriptive User-Agent and pace requests to ~2-3/s (well under the cap,
# without making a large scan painfully slow).
USER_AGENT = f"Rosu/{__version__} (+https://github.com/Kerevizodunu2000/rosu)"
_MIN_INTERVAL = 0.35


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
                 "Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())["access_token"]
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        raise OsuApiError(f"authentication failed: {exc}") from exc


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}",
                      "Accept": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise OsuApiError(f"malformed API response from {url}") from exc


def _get_json(url: str, token: str) -> tuple[dict | None, int, int | None]:
    """GET a URL → ``(body_or_None, http_status, retry_after_seconds)``. Never
    raises: a 404/other HTTP error returns ``(None, code, retry_after)`` and a
    transport failure returns ``(None, 0, None)``, so one blip degrades one id
    instead of aborting a whole enrichment scan."""
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                      "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read()), resp.status, None
    except urllib.error.HTTPError as exc:
        ra = exc.headers.get("Retry-After") if exc.headers else None
        return None, exc.code, (int(ra) if (ra and str(ra).isdigit()) else None)
    except (urllib.error.URLError, ValueError):
        return None, 0, None


def _status_code(url: str, token: str) -> tuple[int, int | None]:
    """GET a URL and return ``(http_status, retry_after_seconds)``. Never raises:
    an HTTP error status is returned as its code, and a transport failure (DNS,
    reset, timeout, TLS) is returned as ``0`` so a single blip degrades one id to
    'unknown' instead of aborting a whole scan."""
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                      "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, None
    except urllib.error.HTTPError as exc:
        ra = exc.headers.get("Retry-After") if exc.headers else None
        return exc.code, (int(ra) if (ra and str(ra).isdigit()) else None)
    except urllib.error.URLError:
        return 0, None


def _interruptible_sleep(seconds: float, cancel=None) -> None:
    """Sleep up to ``seconds`` in short slices, returning early once ``cancel``
    turns True — so a rate-limit backoff never delays a Cancel by more than ~0.5s."""
    slept = 0.0
    while slept < seconds:
        if cancel is not None and cancel():
            return
        step = min(0.5, seconds - slept)
        time.sleep(step)
        slept += step


def beatmapset_availability(ids, client_id: str, client_secret: str,
                            progress=None, max_calls: int = 500,
                            cancel=None) -> dict[int, str]:
    """Check whether each owned beatmapset still exists on osu! (item F, v1.0).

    Returns ``{beatmapset_id: 'available' | 'gone' | 'unknown'}`` — 200 means the
    set is live, 404 means it was taken down / deleted (unrecoverable from osu!).
    Capped at ``max_calls`` per run and gentle (small delay + 429 backoff) so a
    large library never hammers the API. ``cancel`` is polled between ids.
    """
    unique = [i for i in dict.fromkeys(ids) if i]
    token = _token(client_id, client_secret)
    out: dict[int, str] = {}
    total = min(len(unique), max_calls)
    for bid in unique:
        if cancel is not None and cancel():
            break
        if len(out) >= max_calls:
            break
        url = f"{API_BASE}/beatmapsets/{bid}"
        retries = 0
        while True:
            if cancel is not None and cancel():
                return out          # stop promptly, keeping the partial results
            code, retry_after = _status_code(url, token)
            if code == 429 and retries < 5:
                _interruptible_sleep(min(retry_after or 2 ** retries, 60), cancel)
                retries += 1
                continue
            break
        # 200 = live, 404 = gone for good, anything else (incl. 0 = transport
        # error) = unknown, so one network blip degrades one id, not the scan.
        out[bid] = ("available" if code == 200
                    else "gone" if code == 404 else "unknown")
        if progress:
            progress({"kind": "lostmap", "done": len(out), "total": total})
        _interruptible_sleep(_MIN_INTERVAL, cancel)  # ~2-3/s, a good API citizen
    return out


def beatmapset_details(ids, client_id: str, client_secret: str,
                       progress=None, max_calls: int = 500,
                       cancel=None) -> dict[int, dict | None]:
    """Fetch full osu!-API metadata for each owned beatmapset (v1.5 enrichment).

    Returns ``{beatmapset_id: normalized_dict | None}`` — ``None`` means a 404
    (deleted / taken down) or a transport blip. Same auth, pacing (~2-3/s), 429
    backoff, ``max_calls`` cap and ``cancel`` polling as
    :func:`beatmapset_availability`; the only difference is it parses and returns
    the response *body* (status/dates/counts/genre/language + per-diff attributes)
    instead of only the HTTP status.
    """
    unique = [i for i in dict.fromkeys(ids) if i]
    token = _token(client_id, client_secret)
    out: dict[int, dict | None] = {}
    total = len(unique) if max_calls is None else min(len(unique), max_calls)
    for bid in unique:
        if cancel is not None and cancel():
            break
        if max_calls is not None and len(out) >= max_calls:
            break
        url = f"{API_BASE}/beatmapsets/{bid}"
        retries = 0
        body = None
        while True:
            if cancel is not None and cancel():
                return out          # stop promptly, keeping partial results
            data, code, retry_after = _get_json(url, token)
            if code == 429 and retries < 5:
                _interruptible_sleep(min(retry_after or 2 ** retries, 60), cancel)
                retries += 1
                continue
            body = data if code == 200 else None
            break
        out[bid] = _normalize_beatmapset_details(body) if body is not None else None
        if progress:
            progress({"kind": "enrich", "done": len(out), "total": total})
        _interruptible_sleep(_MIN_INTERVAL, cancel)  # ~2-3/s, a good API citizen
    return out


def _normalize_beatmapset_details(data: dict) -> dict:
    """Pure: extract the fields Rosu stores from a ``/beatmapsets/{id}`` body.

    ``genre``/``language`` are nested ``{"name": …}`` objects; ``beatmaps[]``
    carries each difficulty's star rating + MD5 checksum + attributes (the API
    names OD ``accuracy`` and HP ``drain``). Unit-testable on a plain dict — no
    network, no clock (the caller stamps ``api_checked_at``).
    """
    # Defensive against a malformed/unexpected API body (untrusted external JSON):
    # never let a wrong shape (a non-dict, a genre that's a list, a beatmaps map
    # instead of a list) raise and abort the whole enrichment scan.
    def _obj_name(v):
        if isinstance(v, dict):
            v = v.get("name")
        return v if isinstance(v, str) else None

    if not isinstance(data, dict):
        data = {}
    beatmaps = []
    raw_beatmaps = data.get("beatmaps")
    for b in raw_beatmaps if isinstance(raw_beatmaps, list) else []:
        if not isinstance(b, dict):
            continue
        beatmaps.append({
            "checksum": b.get("checksum"),
            "version": b.get("version"),
            "mode_int": b.get("mode_int"),
            "difficulty_rating": b.get("difficulty_rating"),
            "cs": b.get("cs"),
            "ar": b.get("ar"),
            "od": b.get("accuracy"),      # the API names OD "accuracy"
            "hp": b.get("drain"),         # the API names HP "drain"
            "bpm": b.get("bpm"),
            "length_seconds": b.get("total_length"),
        })
    return {
        "status": data.get("status"),
        "ranked_date": data.get("ranked_date"),
        "submitted_date": data.get("submitted_date"),
        "last_updated": data.get("last_updated"),
        "play_count": data.get("play_count"),
        "favourite_count": data.get("favourite_count"),
        "genre": _obj_name(data.get("genre")),
        "language": _obj_name(data.get("language")),
        "beatmaps": beatmaps,
    }


def fetch_reference(client_id: str, client_secret: str, progress=None) -> dict:
    """Fetch every pack across all types. Returns a reference dict."""
    token = _token(client_id, client_secret)
    packs: list[dict] = []
    for pack_type in PACK_TYPES:
        cursor = None
        retries = 0
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
                if exc.code == 429 and retries < 5:
                    # rate limited — honour Retry-After (or exponential backoff)
                    # and retry the same page instead of discarding the whole sync.
                    ra = exc.headers.get("Retry-After") if exc.headers else None
                    delay = int(ra) if (ra and ra.isdigit()) else 2 ** retries
                    time.sleep(min(delay, 60))
                    retries += 1
                    continue
                raise OsuApiError(f"{pack_type}: HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                raise OsuApiError(f"{pack_type}: {exc}") from exc

            retries = 0
            for bp in data.get("beatmap_packs", []):
                packs.append(_normalize(bp, pack_type))
            if progress:
                progress(f"{pack_type}: {len(packs)}")
            cursor = data.get("cursor_string")
            if not cursor:
                break
            time.sleep(_MIN_INTERVAL)   # pace pagination under the API rate guidance
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
