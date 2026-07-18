# SPDX-License-Identifier: GPL-3.0-or-later
"""Full .osu / .osz parsing — per-difficulty metadata for EVERY chart in a set.

``osz_meta.py`` historically read only ONE representative ``.osu`` for the shared
beatmapset fields (artist/title/creator/source/tags + dominant BPM + length). v1.5
needs every difficulty: mania key count, per-diff mode, CS/AR/OD/HP, the diff name,
and an MD5 checksum to cross-reference the osu! API. This module opens the zip
**once**, parses every ``.osu``, and returns the same representative
:class:`~.models.TrackMeta` PLUS a :class:`~.models.DiffMeta` per file PLUS the raw
bytes (so :mod:`rosu.ratings` can compute a star rating without a second read).

Everything is best-effort: a corrupt zip yields empties, and a single bad ``.osu``
degrades only that difficulty — never the whole set, never an exception. Star
ratings are NOT computed here (that is rosu-pp's job in :mod:`rosu.ratings`); this
module only reads what the file literally contains.

Reference: https://osu.ppy.sh/wiki/en/Client/File_formats/osu_%28file_format%29
"""
from __future__ import annotations

import hashlib
import zipfile
from collections import Counter
from pathlib import Path

from .models import MODE_NAMES, DiffMeta, TrackMeta

# A real .osu is text and well under 1 MB even for dense marathon maps; cap the
# uncompressed read so a crafted .osz can't decompression-bomb us into OOM now
# that we read EVERY .osu (the old code read only one). An oversized entry is
# skipped, degrading that one difficulty rather than the whole scan.
_MAX_OSU_BYTES = 16 * 1024 * 1024

# [Metadata] keys that map onto TrackMeta (the shared, set-level fields).
_META_KEYS = {
    "Artist": "artist",
    "Title": "title",
    "Creator": "creator",
    "Source": "source",
    "Tags": "tags",
}


def _dominant_bpm(beat_lengths: list[float]) -> float | None:
    if not beat_lengths:
        return None
    dominant = Counter(round(b, 3) for b in beat_lengths).most_common(1)[0][0]
    if dominant > 0:
        return round(60000.0 / dominant, 1)
    return None


def parse_osu_sections(text: str) -> dict:
    """Single-pass, section-aware scan of one ``.osu`` file's text.

    Returns a dict with ``meta`` (first-non-empty ``[Metadata]`` values, keyed by
    the raw osu! key), ``mode_int``, ``difficulty`` (the ``[Difficulty]`` floats),
    ``bpm`` (dominant), and ``length_seconds`` (last hit-object time). Best-effort:
    malformed lines are skipped; never raises.
    """
    meta_vals: dict[str, str] = {}
    mode_int: int | None = None
    diff_vals: dict[str, float] = {}
    beat_lengths: list[float] = []
    last_time = 0
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue

        if section == "General":
            if line.startswith("Mode:"):
                try:
                    mode_int = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
        elif section == "Metadata":
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if key and value and key not in meta_vals:  # first non-empty wins
                    meta_vals[key] = value
        elif section == "Difficulty":
            if ":" in line:
                key, _, value = line.partition(":")
                try:
                    diff_vals[key.strip()] = float(value.strip())
                except ValueError:
                    pass
        elif section == "TimingPoints":
            parts = line.split(",")
            if len(parts) >= 2:
                try:
                    beat = float(parts[1])
                except ValueError:
                    continue
                if beat > 0:  # uninherited (a real BPM point)
                    beat_lengths.append(beat)
        elif section == "HitObjects":
            parts = line.split(",")
            if len(parts) >= 3:
                try:
                    last_time = max(last_time, int(parts[2]))
                except ValueError:
                    pass

    return {
        "meta": meta_vals,
        "mode_int": mode_int,
        "difficulty": diff_vals,
        "bpm": _dominant_bpm(beat_lengths),
        "length_seconds": round(last_time / 1000) if last_time > 0 else None,
    }


def fill_track_meta(text: str, meta: TrackMeta) -> None:
    """Fill a representative :class:`TrackMeta` from one ``.osu``'s text.

    This preserves the exact behaviour the old ``osz_meta._parse_osu`` had, so the
    set-level record is unchanged from prior versions.
    """
    parsed = parse_osu_sections(text)
    if parsed["mode_int"] is not None:
        meta.mode = MODE_NAMES.get(parsed["mode_int"])
    for key, attr in _META_KEYS.items():
        if getattr(meta, attr) in (None, "") and key in parsed["meta"]:
            setattr(meta, attr, parsed["meta"][key] or None)
    if parsed["bpm"] is not None:
        meta.bpm = parsed["bpm"]
    if parsed["length_seconds"] is not None:
        meta.length_seconds = parsed["length_seconds"]


def read_osu_diff(raw: bytes, filename: str) -> DiffMeta:
    """Parse ONE ``.osu`` file's bytes into a :class:`~.models.DiffMeta`.

    Mania key count is ``round(CircleSize)`` (NULL for the other modes). The
    checksum is the MD5 of the raw bytes — osu!'s own per-difficulty hash, matching
    the osu! API's ``beatmaps[].checksum``. Never raises.
    """
    checksum = hashlib.md5(raw).hexdigest()
    try:
        parsed = parse_osu_sections(raw.decode("utf-8", errors="replace"))
    except Exception:
        return DiffMeta(filename=filename, checksum=checksum)
    mode_int = parsed["mode_int"]
    diff = parsed["difficulty"]
    cs = diff.get("CircleSize")
    keycount = round(cs) if (mode_int == 3 and cs is not None) else None
    return DiffMeta(
        filename=filename,
        version=parsed["meta"].get("Version"),   # [Metadata] Version = diff name
        mode_int=mode_int,
        mode=MODE_NAMES.get(mode_int) if mode_int is not None else None,
        keycount=keycount,
        cs=cs,
        ar=diff.get("ApproachRate"),
        od=diff.get("OverallDifficulty"),
        hp=diff.get("HPDrainRate"),
        bpm=parsed["bpm"],
        length_seconds=parsed["length_seconds"],
        checksum=checksum,
    )


def read_osz_full(osz_path: Path) -> tuple[TrackMeta, list[DiffMeta], dict[str, bytes]]:
    """Open an ``.osz`` once → ``(TrackMeta, [DiffMeta...], {filename: raw_bytes})``.

    The ``TrackMeta`` is the same representative record older versions produced
    (from the alphabetically-first ``.osu``); the ``DiffMeta`` list covers **every**
    difficulty; the bytes map lets the caller feed :mod:`rosu.ratings` without a
    second decompression. Best-effort — a bad zip yields ``(TrackMeta(), [], {})``.
    """
    try:
        with zipfile.ZipFile(osz_path) as zf:
            osu_names = [n for n in zf.namelist() if n.lower().endswith(".osu")]
            meta = TrackMeta(diff_count=len(osu_names))
            if not osu_names:
                return meta, [], {}
            raw_by_name: dict[str, bytes] = {}
            diffs: list[DiffMeta] = []
            for name in osu_names:
                try:
                    if zf.getinfo(name).file_size > _MAX_OSU_BYTES:
                        continue   # implausibly large .osu — skip (bomb guard)
                    raw = zf.read(name)
                except (KeyError, zipfile.BadZipFile, OSError):
                    continue
                raw_by_name[name] = raw
                diffs.append(read_osu_diff(raw, name))
            rep = sorted(osu_names)[0]  # unchanged representative selection
            if rep in raw_by_name:
                fill_track_meta(raw_by_name[rep].decode("utf-8", errors="replace"), meta)
            return meta, diffs, raw_by_name
    except (zipfile.BadZipFile, OSError, KeyError, ValueError):
        return TrackMeta(), [], {}
