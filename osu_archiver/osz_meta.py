"""Read rich metadata from the .osu difficulty files inside an .osz beatmap set.

An ``.osz`` is a zip whose ``.osu`` files are plain-text beatmaps. We read a
representative difficulty for the shared fields (artist/title/creator/source/
tags/mode) and derive BPM and length. Everything is best-effort: a corrupt or
unusual set simply yields ``None`` fields and never raises.

Reference: https://osu.ppy.sh/wiki/en/Client/File_formats/osu_%28file_format%29
"""
from __future__ import annotations

import zipfile
from collections import Counter
from pathlib import Path

from .models import MODE_NAMES, TrackMeta

_META_KEYS = {
    "Artist": "artist",
    "Title": "title",
    "Creator": "creator",
    "Source": "source",
    "Tags": "tags",
}


def read_osz_meta(osz_path: Path) -> TrackMeta:
    """Return :class:`TrackMeta` for an .osz file (best-effort, never raises)."""
    try:
        with zipfile.ZipFile(osz_path) as zf:
            osu_names = [n for n in zf.namelist() if n.lower().endswith(".osu")]
            meta = TrackMeta(diff_count=len(osu_names))
            if not osu_names:
                return meta
            rep = sorted(osu_names)[0]
            with zf.open(rep) as fh:
                text = fh.read().decode("utf-8", errors="replace")
            _parse_osu(text, meta)
            return meta
    except (zipfile.BadZipFile, OSError, KeyError, ValueError):
        return TrackMeta()


def _parse_osu(text: str, meta: TrackMeta) -> None:
    section = ""
    beat_lengths: list[float] = []
    last_time = 0
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
                    meta.mode = MODE_NAMES.get(int(line.split(":", 1)[1].strip()))
                except ValueError:
                    pass
        elif section == "Metadata":
            if ":" in line:
                key, _, value = line.partition(":")
                attr = _META_KEYS.get(key.strip())
                if attr and getattr(meta, attr) in (None, ""):
                    setattr(meta, attr, value.strip() or None)
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

    if beat_lengths:
        dominant = Counter(round(b, 3) for b in beat_lengths).most_common(1)[0][0]
        if dominant > 0:
            meta.bpm = round(60000.0 / dominant, 1)
    if last_time > 0:
        meta.length_seconds = round(last_time / 1000)
