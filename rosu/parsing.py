# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure parsing helpers: pack .zip names and .osz entries -> structured data.

Kept free of I/O so it can be unit-tested exhaustively. Everything here is a
string-in / dataclass-out transformation.
"""
from __future__ import annotations

import re

from .models import (
    CAT_ARTIST, CAT_FEATURED, CAT_LOVED, CAT_OTHER, CAT_SPOTLIGHTS,
    CAT_STANDARD, CAT_THEME, CAT_TOURNAMENT, UNKNOWN_ARTIST, ParsedPack, ParsedTrack,
)

# --- Pack filename ----------------------------------------------------------
# "S1819 - osu! Beatmap Pack #1819", "R338 - ... (osu!mania) (1)", "FQ94 - MIMI Pack"
# Letters = series, digits = number, remainder = title. A trailing " (N)" is a
# browser duplicate-download marker and is stripped from the title.
_PACK_RE = re.compile(r"^([A-Za-z]+)(\d+)\s*-\s*(.+?)(?:\s+\((\d+)\))?$")

# Season + year + game mode inside a Spotlights title. The osu! exporter uses
# "_" where a ":" would be (Windows-illegal), so we allow "_" and spaces.
_SPOTLIGHT_RE = re.compile(
    r"(Winter|Spring|Summer|Autumn|Fall)\s+(\d{4})", re.IGNORECASE)
_MODE_RE = re.compile(r"\((osu!(?:mania|taiko|catch)?)\)", re.IGNORECASE)

# Series letter -> implied game mode for the standard packs.
_SERIES_MODE = {
    "S": "osu!",
    "SM": "osu!mania",
    "ST": "osu!taiko",
    "SC": "osu!catch",
}

# Series prefix -> osu! pack category. Known multi-letter prefixes are listed
# explicitly; anything else recognised as "<letters><digits>" but not below
# falls back to Other (listed, never flagged red).
_SERIES_CATEGORY = {
    "S": CAT_STANDARD, "SM": CAT_STANDARD, "ST": CAT_STANDARD, "SC": CAT_STANDARD,
    "F": CAT_FEATURED, "FM": CAT_FEATURED, "FQ": CAT_FEATURED, "FA": CAT_FEATURED,
    "R": CAT_SPOTLIGHTS,
    "P": CAT_TOURNAMENT,
    "L": CAT_LOVED, "SL": CAT_LOVED,
    "T": CAT_THEME,
    "A": CAT_ARTIST,
}


def pack_category(series: str | None) -> str:
    return _SERIES_CATEGORY.get(series or "", CAT_OTHER)


def series_mode(series: str | None) -> str | None:
    """Implied game mode for a standard series prefix (S/SM/ST/SC), else None."""
    return _SERIES_MODE.get(series or "")

# --- .osz entry -------------------------------------------------------------
# "2138180 Luna - Toki to Uta.osz" -> id 2138180, rest "Luna - Toki to Uta"
_OSZ_RE = re.compile(r"^(\d+)\s+(.+)\.osz$", re.IGNORECASE)


# archive suffixes we recognise (longest first so ".tar.gz" wins over ".gz")
_ARCHIVE_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz",
                     ".zip", ".7z", ".tar")


def _strip_ext(name: str) -> str:
    low = name.lower()
    for suf in _ARCHIVE_SUFFIXES:
        if low.endswith(suf):
            return name[:-len(suf)]
    return name


def parse_pack_name(zip_filename: str) -> ParsedPack:
    """Parse a pack .zip filename into a :class:`ParsedPack`.

    Never returns ``None``: a name that doesn't match the official
    ``<letters><number> - <title>`` scheme (e.g. an unofficially named pack) is
    kept as an "Other" pack (no series/number) so it is still imported and
    listed, just never flagged as a red gap.
    """
    source_zip = zip_filename
    stem = _strip_ext(zip_filename).strip()
    m = _PACK_RE.match(stem)
    if not m:
        return ParsedPack(
            code=stem, series=None, number=None, title=stem,
            full_name=stem, source_zip=source_zip, category=CAT_OTHER,
        )
    series = m.group(1).upper()
    number = int(m.group(2))
    title = m.group(3).strip()
    code = f"{series}{number}"
    category = pack_category(series)

    mode = _SERIES_MODE.get(series)
    season = year = None
    if series == "R":
        mode_m = _MODE_RE.search(title)
        if mode_m:
            mode = mode_m.group(1).lower()
        sp = _SPOTLIGHT_RE.search(title)
        if sp:
            season = sp.group(1).capitalize()
            if season == "Fall":
                season = "Autumn"
            year = int(sp.group(2))

    return ParsedPack(
        code=code, series=series, number=number, title=title,
        full_name=stem, source_zip=source_zip, category=category,
        mode=mode, season=season, year=year,
    )


def split_artist_title(rest: str) -> tuple[str, str]:
    """Split "Artist - Title" on the first " - "; best-effort."""
    idx = rest.find(" - ")
    if idx == -1:
        return "", rest
    return rest[:idx].strip(), rest[idx + 3:].strip()


def parse_osz_entry(entry_path: str, size_bytes: int = 0) -> ParsedTrack | None:
    """Parse one .osz path from inside a zip.

    ``entry_path`` may contain a single leading folder (e.g.
    ``"osu!mania/539179 cosMo - Oceanus.osz"``); the folder is recorded as the
    ``subfolder`` and stripped from the flattened filename.
    """
    normalized = entry_path.replace("\\", "/")
    if normalized.endswith("/"):
        return None  # directory entry
    parts = normalized.split("/")
    filename = parts[-1]
    subfolder = parts[-2] if len(parts) >= 2 else None
    if not filename.lower().endswith(".osz"):
        return None
    # Security: reject a drive-relative / alternate-data-stream name such as
    # "D:evil.osz" — with no "/" to split on it would survive as the flattened
    # filename and, joined as ``output_dir / filename`` on Windows, escape Output.
    if ":" in filename:
        return None

    m = _OSZ_RE.match(filename)
    if m:
        beatmapset_id: int | None = int(m.group(1))
        rest = m.group(2)
    else:
        beatmapset_id = None
        rest = filename[:-4]  # drop ".osz"
    artist, title = split_artist_title(rest)
    # A malformed name with no " - " has no artist: record it as Unknown and
    # keep the whole thing as the title, so the import never fails.
    if not artist:
        artist = UNKNOWN_ARTIST
    return ParsedTrack(
        beatmapset_id=beatmapset_id,
        filename=filename,
        artist=artist,
        title=title,
        display_name=rest,
        subfolder=subfolder,
        size_bytes=size_bytes,
    )
