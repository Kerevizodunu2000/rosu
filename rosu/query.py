# SPDX-License-Identifier: GPL-3.0-or-later
"""Query-syntax parsing for the Search box (v1.5).

Splits a raw query into structured FILTERS (``star>5``, ``mode=mania``, ``key=7``,
``bpm>=180``, ``status=ranked``, …) and the remaining FREE TEXT. Filters are
stripped BEFORE the free text reaches :func:`rosu.search.tokenize` — otherwise
``>``/``<``/``=`` (not ``\\w`` characters) would corrupt ``star>5`` into the tokens
``["star", "5"]`` and poison the AND-matching. A word that looks like a filter but
has a bad value (``star>abc``) is left verbatim in the free text, so nothing is
silently dropped.

The parser is pure and I/O-free; :meth:`rosu.db.Database._build_filter_sql` turns
these :class:`Filter` objects into SQL (diff-level fields collapse into one
``EXISTS`` subquery so several diff constraints must hold on the *same* chart).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_NUM_FIELDS = {"star", "bpm", "cs", "ar", "od", "hp", "length"}
_INT_FIELDS = {"key", "keys"}
_ENUM_FIELDS = {"mode", "status"}
# Free-text "contains" fields — a structured alternative to the free-text box, so
# `artist=camellia` matches only the artist column (not tags/title). '=' means
# "contains" here (case-insensitive substring).
_TEXT_FIELDS = {"artist", "mapper", "creator", "name", "source", "title", "tags"}
_ALL_FIELDS = _NUM_FIELDS | _INT_FIELDS | _ENUM_FIELDS | _TEXT_FIELDS

# Accept the ways players name the four rulesets; normalize to MODE_NAMES vocab.
_MODE_ALIASES = {
    "std": "osu!", "standard": "osu!", "osu": "osu!", "osu!": "osu!",
    "taiko": "osu!taiko", "osu!taiko": "osu!taiko",
    "catch": "osu!catch", "ctb": "osu!catch", "fruits": "osu!catch",
    "osu!catch": "osu!catch",
    "mania": "osu!mania", "osu!mania": "osu!mania",
}

_FILTER_RE = re.compile(r"(?P<key>[A-Za-z]+)(?P<op>>=|<=|>|<|=)(?P<val>\S+)")


@dataclass
class Filter:
    field: str      # normalized: star/bpm/cs/ar/od/hp/length/key/mode/status
    op: str         # one of > >= < <= =
    value: object   # float (numeric), int (key), or str (mode/status)


@dataclass
class ParsedQuery:
    filters: list = field(default_factory=list)
    free_text: str = ""


def parse(raw_query: str) -> ParsedQuery:
    """Split ``raw_query`` into (filters, free_text)."""
    filters: list = []
    leftovers: list = []
    for part in (raw_query or "").split():
        m = _FILTER_RE.fullmatch(part)
        f = _to_filter(m) if m else None
        if f is not None:
            filters.append(f)
        else:
            leftovers.append(part)
    return ParsedQuery(filters=filters, free_text=" ".join(leftovers))


def _parse_length(val: str) -> float | None:
    """Accept ``mm:ss`` (``4:03``) OR bare seconds (``243``) → seconds."""
    if ":" in val:
        parts = val.split(":")
        if len(parts) != 2:
            return None
        try:
            minutes, seconds = int(parts[0]), int(parts[1])
        except ValueError:
            return None
        if seconds >= 60 or minutes < 0 or seconds < 0:
            return None
        return float(minutes * 60 + seconds)
    try:
        return float(val)
    except ValueError:
        return None


def _to_filter(m) -> Filter | None:
    key = m.group("key").lower()
    op = m.group("op")
    val = m.group("val")
    if key not in _ALL_FIELDS:
        return None
    if key == "length":
        secs = _parse_length(val)   # mm:ss or bare seconds
        return Filter("length", op, secs) if secs is not None else None
    if key in _NUM_FIELDS:
        try:
            return Filter(key, op, float(val))
        except ValueError:
            return None
    if key in _INT_FIELDS:
        try:
            return Filter("key", op, int(val))   # keycount is an integer column
        except ValueError:
            return None
    # enum + text fields: only '=' is meaningful
    if op != "=":
        return None
    if key == "mode":
        mapped = _MODE_ALIASES.get(val.lower())
        return Filter("mode", "=", mapped) if mapped else None
    if key == "status":
        return Filter("status", "=", val.lower())
    # text "contains" fields — normalize the field aliases to real column intents
    field = {"mapper": "creator", "name": "title"}.get(key, key)
    return Filter(field, "contains", val)
