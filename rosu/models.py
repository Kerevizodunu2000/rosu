# SPDX-License-Identifier: GPL-3.0-or-later
"""Plain data structures shared across modules."""
from __future__ import annotations

from dataclasses import dataclass, field


# Seasonal ordering used for spotlight gap detection.
SEASONS = ("Winter", "Spring", "Summer", "Autumn")
SEASON_INDEX = {s: i for i, s in enumerate(SEASONS)}

# Pack categories (osu! beatmap pack listing).
CAT_STANDARD = "Standard"
CAT_FEATURED = "Featured"
CAT_SPOTLIGHTS = "Spotlights"
CAT_TOURNAMENT = "Tournament"
CAT_LOVED = "Loved"
CAT_THEME = "Theme"
CAT_ARTIST = "Artist"
CAT_OTHER = "Other"

# Only these categories are numbered gaplessly by upload order, so an interior
# numeric gap is *genuinely* a real published pack the user is missing. Every
# other category needs the osu! API reference to know a red is real.
CONFIDENT_GAP_CATEGORIES = frozenset({CAT_STANDARD})

# Game mode display names by osu! mode id (used by .osu metadata parsing).
MODE_NAMES = {0: "osu!", 1: "osu!taiko", 2: "osu!catch", 3: "osu!mania"}

UNKNOWN_ARTIST = "Unknown"


@dataclass
class ParsedPack:
    """Result of parsing a pack .zip filename."""
    code: str            # e.g. "S1819", "R290", "FQ94", or the full name for Other
    series: str | None   # letter prefix: S, SM, R, FM, FQ, ... (None for Other)
    number: int | None   # numeric part (None for Other)
    title: str           # descriptive part after " - " (or the whole name)
    full_name: str       # original name without extension
    source_zip: str      # original file name (with extension)
    category: str = CAT_OTHER
    mode: str | None = None      # osu! / osu!mania / osu!taiko / osu!catch
    season: str | None = None    # Winter/Spring/Summer/Autumn (spotlights)
    year: int | None = None      # spotlight year

    @property
    def is_spotlight(self) -> bool:
        return self.series == "R"


@dataclass
class ParsedTrack:
    """Result of parsing a single .osz entry inside a pack."""
    beatmapset_id: int | None
    filename: str        # flattened .osz filename (no folder prefix)
    artist: str
    title: str
    display_name: str    # "Artist - Title"
    subfolder: str | None = None  # e.g. "osu!mania" when nested in a pack
    size_bytes: int = 0


@dataclass
class TrackMeta:
    """Rich metadata read from the .osu files inside an .osz beatmap set."""
    artist: str | None = None
    title: str | None = None
    creator: str | None = None       # mapper
    source: str | None = None
    tags: str | None = None
    bpm: float | None = None         # dominant BPM
    length_seconds: int | None = None
    mode: str | None = None          # osu!/osu!taiko/osu!catch/osu!mania
    diff_count: int = 0              # number of .osu difficulties


@dataclass
class DiffMeta:
    """Per-difficulty metadata read from ONE .osu file inside an .osz (v1.5).

    Unlike :class:`TrackMeta` (one aggregate per beatmapset), there is one
    ``DiffMeta`` per ``.osu``. The star rating is NOT here — it is computed
    separately by :mod:`rosu.ratings` (rosu-pp) and stored alongside these fields.
    """
    filename: str                    # the .osu member name inside the .osz
    version: str | None = None       # difficulty name ("Insane", "7K Oni", ...)
    mode_int: int | None = None      # 0/1/2/3 from [General] Mode
    mode: str | None = None          # display name (MODE_NAMES vocabulary)
    keycount: int | None = None      # mania only: round(CircleSize); None otherwise
    cs: float | None = None
    ar: float | None = None
    od: float | None = None
    hp: float | None = None
    bpm: float | None = None         # this diff's own dominant BPM
    length_seconds: int | None = None
    checksum: str | None = None      # MD5 of the raw .osu bytes = osu!'s per-diff hash


@dataclass
class GapRow:
    """A row in a series listing: either a present pack or a missing gap."""
    series: str
    present: bool
    number: int | None = None
    code: str | None = None
    title: str | None = None
    mode: str | None = None
    year: int | None = None
    season: str | None = None
    track_count: int | None = None
    extracted_at: str | None = None
    status: str | None = None
    extra_count: int = 0   # non-music files the source archive also held (item 25)


@dataclass
class ExtractPlan:
    """Pre-scan decision for one pack before extraction."""
    parsed: ParsedPack
    zip_path: str
    track_ids: list[int] = field(default_factory=list)
    known_before: bool = False        # pack code already in memory
    new_ids: list[int] = field(default_factory=list)   # ids not yet in memory
    known_ids: list[int] = field(default_factory=list)  # ids already in memory
    # kind is one of: "new", "all_present", "some_missing"
    kind: str = "new"
