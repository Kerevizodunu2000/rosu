# SPDX-License-Identifier: GPL-3.0-or-later
"""What the Mode / Where / Library columns show for one set (pure, Qt-free).

The Search and Artists tables used to read these straight off the ``tracks``
row, and three of them disagreed with what the rest of the app stores:

* ``tracks.mode`` is the mode of the alphabetically-first ``.osu`` only, and it
  is written once (``COALESCE``). A set with an osu! and a mania difficulty
  showed just one of them, while ``mode=mania`` and the Filters panel count
  match on *any* difficulty. The Mode column now lists every difficulty's mode.
* ``in_library=1`` is also written for memory-only sets (no ``.osz`` kept), so
  the 💾 marker and "Open location" claimed a file that does not exist.
* ``library_status`` is a raw DB token ("present", "memory", "disappeared")
  that was shown untranslated.
"""
from __future__ import annotations

from typing import Callable

# library_status values that mean "the DB knows there is no .osz on disk".
_NO_COPY_STATUSES = frozenset({"memory", "disappeared"})


def has_library_copy(row: dict) -> bool:
    """True when the set's ``.osz`` should physically be in the Library folder.

    ``in_library`` alone is not enough: a memory-only import stores
    ``in_library=1, library_status='memory'`` while a purge stores
    ``in_library=0, library_status='memory'`` for the same situation.
    """
    return bool(row.get("in_library")) and \
        row.get("library_status") not in _NO_COPY_STATUSES


def mode_text(diffs: list[dict], fallback: str | None = None) -> str:
    """Every distinct game mode among a set's difficulties, in osu!'s mode order
    ("osu!, osu!mania"). ``fallback`` (the stored ``tracks.mode``) is used only
    for a set whose difficulties were never parsed."""
    seen: dict[str, int] = {}
    for d in diffs:
        m = d.get("mode")
        if m and m not in seen:
            mi = d.get("mode_int")
            seen[m] = mi if isinstance(mi, int) else 99
    if not seen:
        return fallback or ""
    return ", ".join(sorted(seen, key=lambda m: (seen[m], m)))


def where_marks(row: dict) -> tuple[list[str], int]:
    """(icons, sort weight) for the Where column.

    The weight is built from the same flags as the icons, so sorting the column
    groups rows exactly the way they look.
    """
    marks: list[str] = []
    weight = 0
    in_lazer = bool(row.get("in_osu_lazer"))
    in_stable = bool(row.get("in_osu_stable"))
    if in_lazer or (row.get("in_osu") and not in_stable):
        # A bare legacy ``in_osu`` flag predates per-client tracking (v1.0); the
        # single osu! target back then is the one config migrates to osu!lazer.
        marks.append("🎮")
        weight += 8
    if in_stable:
        marks.append("🕹️")
        weight += 4
    if has_library_copy(row):
        marks.append("💾")
        weight += 2
    if row.get("in_drive"):
        marks.append("☁️")
        weight += 1
    return marks, weight


def library_status_text(row: dict, t: Callable[..., str]) -> str:
    """The Library column's text, translated. Unknown tokens pass through."""
    status = row.get("library_status")
    if not status:
        return "-"
    if status == "disappeared" and row.get("status_changed_at"):
        return t("lib_status_disappeared_at", when=row["status_changed_at"])
    if status in ("present", "memory", "disappeared"):
        return t(f"lib_status_{status}")
    return status
