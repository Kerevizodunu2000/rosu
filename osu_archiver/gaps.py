"""Gap / "red row" detection — confidence aware.

A row is only shown red when we *genuinely know* a pack is missing:

* **Standard categories** (S/SM/ST/SC) are numbered gaplessly by osu! upload
  order, so an interior numeric gap between the smallest and largest owned
  number is a real published pack -> confident red, no network needed.
* **Every other category** (Featured, Spotlights, Theme, Artist, Loved,
  Tournament, Other) is listed only — never guessed red — because their numbers
  are unreliable (e.g. Spotlights share numbers across game modes). They become
  red *only* when validated against the osu! API reference (see build_reference_rows).

Pure functions: dicts in, :class:`GapRow` list out, so they unit-test without a DB.
"""
from __future__ import annotations

from .models import (
    CAT_SPOTLIGHTS, CONFIDENT_GAP_CATEGORIES, SEASON_INDEX, GapRow,
)
from .parsing import series_mode


# --- Numbered series --------------------------------------------------------
def missing_numbers(numbers: list[int]) -> list[int]:
    """Return the integers missing between min and max of ``numbers``."""
    if not numbers:
        return []
    have = set(numbers)
    lo, hi = min(numbers), max(numbers)
    return [n for n in range(lo, hi + 1) if n not in have]


def build_numbered_rows(series: str, present: list[dict],
                        show_gaps: bool = True) -> list[GapRow]:
    """Ordered rows for a numbered series; red gaps only when ``show_gaps``."""
    by_number = {p["number"]: p for p in present if p.get("number") is not None}
    rows: list[GapRow] = []
    if not by_number:
        return [_present_row(series, p) for p in present]
    lo, hi = min(by_number), max(by_number)
    for n in range(lo, hi + 1):
        p = by_number.get(n)
        if p is not None:
            rows.append(_present_row(series, p))
        elif show_gaps:
            # Fill Code (series+number) and Mode (from the series prefix) so a red
            # missing row isn't blank in those columns (item 8).
            rows.append(GapRow(series=series, present=False, number=n,
                               code=f"{series}{n}", mode=series_mode(series)))
    return rows


def _present_row(series: str, p: dict) -> GapRow:
    return GapRow(
        series=series, present=True, number=p.get("number"),
        code=p.get("code"), title=p.get("title"), mode=p.get("mode"),
        year=p.get("year"), season=p.get("season"),
        track_count=p.get("track_count"), extracted_at=p.get("extracted_at"),
        status=p.get("status"),
    )


# --- Spotlights (listed only, no guessed red) ------------------------------
def build_spotlight_rows(present: list[dict]) -> list[GapRow]:
    """List spotlight packs grouped by mode then chronologically (no red)."""
    rows = [GapRow(
        series="R", present=True, number=p.get("number"),
        year=p.get("year"), season=p.get("season"), mode=p.get("mode"),
        code=p.get("code"), title=p.get("title"),
        track_count=p.get("track_count"), extracted_at=p.get("extracted_at"),
    ) for p in present]

    rows.sort(key=lambda r: (
        r.mode or "",
        r.year if r.year is not None else 9999,
        SEASON_INDEX.get(r.season or "", 9),
        r.number if r.number is not None else 0,
    ))
    return rows


# --- Reference-validated rows (osu! API) -----------------------------------
def build_reference_rows(series: str, present: list[dict],
                         reference: list[dict]) -> list[GapRow]:
    """Rows validated against the authoritative osu! pack list.

    Red = a reference pack that really exists but isn't owned, within the owned
    number range and limited to the game modes the user actually collects (so
    e.g. taiko/catch spotlights the user skips are not flagged).
    """
    owned = {p["code"]: p for p in present}
    numbers = [p["number"] for p in present if p.get("number") is not None]
    collected_modes = {p.get("mode") for p in present if p.get("mode")}
    rows = [_present_row(series, p) for p in present]

    if numbers:
        lo, hi = min(numbers), max(numbers)
        for e in reference:
            code = e.get("code")
            num = e.get("number")
            if code in owned or num is None or not (lo <= num <= hi):
                continue
            if collected_modes and e.get("mode") and e["mode"] not in collected_modes:
                continue
            rows.append(GapRow(
                series=series, present=False, number=num, code=code,
                title=e.get("title"), mode=e.get("mode"),
                year=e.get("year"), season=e.get("season"),
            ))

    rows.sort(key=lambda r: (
        r.year if (series == "R" and r.year is not None) else 0,
        SEASON_INDEX.get(r.season or "", 0) if series == "R" else 0,
        r.number if r.number is not None else 0,
        0 if r.present else 1,
    ))
    return rows


def build_rows(series: str | None, category: str, present: list[dict],
               reference: list[dict] | None = None) -> list[GapRow]:
    """Dispatch to the right row builder for a series."""
    if reference:
        return build_reference_rows(series or "", present, reference)
    if category == CAT_SPOTLIGHTS or series == "R":
        return build_spotlight_rows(present)
    show_gaps = category in CONFIDENT_GAP_CATEGORIES
    return build_numbered_rows(series or "", present, show_gaps=show_gaps)


# --- Summary for logging ----------------------------------------------------
def gap_summary(numbered: dict[str, list[int]]) -> str:
    """Compact one-line summary for the GAP_DETECT log entry."""
    parts = [f"{s}=[{','.join(map(str, miss))}]"
             for s, miss in sorted(numbered.items()) if miss]
    return " ".join(parts) if parts else "none"
