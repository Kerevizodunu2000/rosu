# SPDX-License-Identifier: GPL-3.0-or-later
"""Export search results as CSV or JSON (v1.9) — Qt-free.

One record per beatmap set with the facts the Search tab shows, in plain
language-neutral values (numbers stay numbers in JSON). CSV cells that a
spreadsheet would run as a formula (a title starting with ``=``, ``+``, ``-``,
``@``…) are neutralised with a leading apostrophe.
"""
from __future__ import annotations

import csv
import io
import json

from .columns import has_library_copy

FIELDS = ("beatmapset_id", "artist", "title", "creator", "bpm", "length_seconds",
          "modes", "stars", "keys", "sources", "in_library", "library_file",
          "in_osu_stable", "in_osu_lazer", "library_status", "filename",
          "first_seen_at")


def record(row: dict) -> dict:
    """One set's export record from a Search row (with its ``difficulties``)."""
    diffs = row.get("difficulties") or []
    modes = sorted({d["mode"] for d in diffs if d.get("mode")}) or (
        [row["mode"]] if row.get("mode") else [])
    stars = sorted({round(d["star_rating"], 2) for d in diffs
                    if d.get("star_rating") is not None})
    keys = sorted({d["keycount"] for d in diffs if d.get("keycount")})
    return {
        "beatmapset_id": row.get("beatmapset_id"),
        "artist": row.get("artist") or "",
        "title": row.get("title") or row.get("display_name") or "",
        "creator": row.get("creator") or "",
        "bpm": row.get("bpm"),
        "length_seconds": row.get("length_seconds"),
        "modes": modes,
        "stars": stars,
        "keys": keys,
        "sources": list(row.get("sources") or []),
        "in_library": bool(row.get("in_library")),
        "library_file": has_library_copy(row),   # memory-only sets have none
        "in_osu_stable": bool(row.get("in_osu_stable")),
        "in_osu_lazer": bool(row.get("in_osu_lazer")),
        "library_status": row.get("library_status") or "",
        "filename": row.get("filename") or "",
        "first_seen_at": row.get("first_seen_at") or "",
    }


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        value = "; ".join(str(v) for v in value)
    text = str(value)
    if text and text[0] in "=+-@\t\r" and not _is_number(text):
        return "'" + text   # never a live spreadsheet formula
    return text


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(FIELDS)
    for row in rows:
        rec = record(row)
        w.writerow([_cell(rec[f]) for f in FIELDS])
    return buf.getvalue()


def to_json(rows: list[dict], query: str = "") -> str:
    return json.dumps({"query": query, "count": len(rows),
                       "sets": [record(r) for r in rows]},
                      ensure_ascii=False, indent=2)


def write(path, rows: list[dict], query: str = "") -> int:
    """Write ``rows`` to ``path`` — JSON for ``*.json``, CSV otherwise (UTF-8
    with a BOM so Excel reads non-ASCII names correctly). Returns the count."""
    from pathlib import Path
    path = Path(path)
    if path.suffix.lower() == ".json":
        path.write_text(to_json(rows, query), encoding="utf-8")
    else:
        path.write_text(to_csv(rows), encoding="utf-8-sig", newline="")
    return len(rows)
