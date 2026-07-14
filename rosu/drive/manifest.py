# SPDX-License-Identifier: GPL-3.0-or-later
"""Drive backup manifest — the cross-device source of truth (v0.8).

Each device writes its own shard ``manifest-<deviceId>.json`` and never touches
another device's shard, so shards are conflict-free; the *effective* manifest is
the union of all shards. A shard maps a stable per-track key to the chunk archive
that stores it, plus size/hash and a metadata snapshot (so a fresh machine can
rebuild its tracking DB from the manifest before downloading any .osz).

Keys are prefixed so a numeric beatmapset id can never collide with an .osz whose
filename happens to be all digits:

* ``id:<beatmapset_id>``  when the set has a numeric id, else
* ``name:<filename>``     (matches the DB's nullable-id fallback).

Pure/stdlib only — no network, no keyring; unit-tested in isolation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

# Track fields snapshotted into each entry so search/artists/gaps work on a new
# machine straight from the manifest (before any .osz is downloaded).
_META_FIELDS = (
    "artist", "title", "display_name", "creator", "source", "tags",
    "bpm", "length_seconds", "mode", "diff_count",
)

SHARD_PREFIX = "manifest-"
SHARD_SUFFIX = ".json"


def shard_name(device_id: str) -> str:
    return f"{SHARD_PREFIX}{device_id}{SHARD_SUFFIX}"


def make_key(beatmapset_id: int | None, filename: str) -> str:
    """Stable manifest key. Mirrors the DB dedup identity (id, else filename)."""
    if beatmapset_id is not None:
        return f"id:{int(beatmapset_id)}"
    return f"name:{filename}"


def track_key(track: dict) -> str:
    return make_key(track.get("beatmapset_id"), track.get("filename") or "")


def entry_from_track(track: dict, chunk: str, size: int, sha: str) -> dict:
    """Build a manifest entry for a track stored in ``chunk``."""
    return {
        "chunk": chunk,
        "name": track.get("filename"),
        "size": int(size),
        "hash": sha,
        "beatmapset_id": track.get("beatmapset_id"),
        "metadata": {k: track.get(k) for k in _META_FIELDS},
    }


def load_shard(path: Path) -> dict:
    """Load a shard's entry map; return ``{}`` if missing or unreadable."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return {}
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, dict) else {}


def save_shard(path: Path, device_id: str, entries: dict) -> None:
    """Atomically write a shard (temp file + replace) — never a half file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"device_id": device_id, "version": 1, "entries": entries}
    tmp = path.with_name(path.name + ".part")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def merge_shards(shards: Iterable[dict]) -> dict:
    """Union of shard entry-maps into one effective manifest."""
    effective: dict = {}
    for entries in shards:
        if isinstance(entries, dict):
            effective.update(entries)
    return effective


def diff_to_upload(local_tracks: Iterable[dict], manifest: dict) -> list[dict]:
    """Return the local tracks that need uploading.

    A track is uploaded when its key is absent from ``manifest`` (new), or when
    its key is present but the file's size differs from the recorded entry
    (changed content — mirrors the Library's size-based refresh heuristic). When
    either size is unknown it falls back to presence-by-key.
    """
    out: list[dict] = []
    for t in local_tracks:
        entry = manifest.get(track_key(t))
        if not isinstance(entry, dict):
            out.append(t)          # new
            continue
        size, stored = t.get("size"), entry.get("size")
        if size is not None and stored is not None and int(size) != int(stored):
            out.append(t)          # changed content (size differs)
    return out
