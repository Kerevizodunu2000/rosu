# SPDX-License-Identifier: GPL-3.0-or-later
"""Local star-rating computation via rosu-pp-py (import-guarded, best-effort).

rosu-pp-py is a compiled (Rust / PyO3) wheel — Rosu's one non-pure-Python
*computation* dependency. It is OPTIONAL: if it is not installed (a bare dev env,
or a frozen build whose ``.pyd`` an over-eager antivirus stripped), the whole app
must still run — just without locally-computed stars, which the osu! API can then
fill in as a fallback. Every entry point here degrades gracefully and never raises,
so one bad or missing engine can never abort a whole-library scan.
"""
from __future__ import annotations

from dataclasses import dataclass

try:
    import rosu_pp_py as _rpp
    _AVAILABLE = True
except Exception:  # ImportError, or a broken/half-stripped compiled extension
    _rpp = None
    _AVAILABLE = False


@dataclass
class RatingResult:
    stars: float | None
    error: str | None = None


def available() -> bool:
    """True when rosu-pp-py imported and local star ratings are possible."""
    return _AVAILABLE


def star_rating(osu_bytes: bytes, mods: int = 0) -> RatingResult:
    """Star rating for a difficulty from its raw ``.osu`` bytes.

    ``mods`` is an osu! mod bitflag (0 = nomod; v1.5 only computes nomod). Never
    raises: an unavailable engine, a map rosu-pp flags as pathological, or a parse
    failure each return ``RatingResult(None, <reason>)``.
    """
    if not _AVAILABLE:
        return RatingResult(None, "rosu-pp-py not installed")
    try:
        bm = _rpp.Beatmap(bytes=osu_bytes)
        # Skip maps rosu-pp flags as suspicious (pathological object counts →
        # extremely slow calc): not worth stalling a whole-library scan for one.
        if bm.is_suspicious():
            return RatingResult(None, "suspicious map")
        attrs = _rpp.Difficulty(mods=mods).calculate(bm)
        return RatingResult(float(attrs.stars))
    except Exception as exc:  # rosu-pp ParseError / ArgsError / etc.
        return RatingResult(None, f"{type(exc).__name__}: {exc}")


def stars_for_diffs(diffs: list, raw_by_name: dict, mods: int = 0) -> dict:
    """Map each diff's ``filename`` → its computed star (or ``None``).

    Shared by the ingest hooks (unpack, library refresh) and the whole-library
    ``compute_ratings`` scan. When the engine is unavailable every value is ``None``
    (:func:`star_rating` short-circuits), so callers need not guard on
    :func:`available` — the ``None`` entries simply leave those stars for the osu!
    API fallback to fill.
    """
    out: dict = {}
    for d in diffs:
        raw = raw_by_name.get(d.filename)
        out[d.filename] = star_rating(raw, mods).stars if raw is not None else None
    return out
