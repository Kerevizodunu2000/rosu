# SPDX-License-Identifier: GPL-3.0-or-later
"""Tiny pure-Python statistics helpers (no numpy — the PyInstaller spec excludes it)."""
from __future__ import annotations

import math

# Binning modes for :func:`histogram_bins`.
#   "auto"    — split the observed min..max range into ``bins`` equal parts. Uses
#               the full width of the chart but yields ranges like 3.94–4.55.
#   "integer" — plain 1★-wide buckets (0–1, 1–2, 2–3 …). Easier to read and to
#               reason about ("how many 5★ maps do I have?"), which is what the
#               owner asked for after seeing the data-driven edges.
MODES = ("auto", "integer")


def histogram_bins(values, bins: int = 20,
                   mode: str = "auto") -> list[tuple[float, float, int]]:
    """Bin ``values`` into ``[(bin_lo, bin_hi, count), ...]``.

    Degenerate inputs are safe: an empty/all-None list yields ``[]``; when every
    value is identical, one unit-width bin is returned so the caller still has a
    bar to draw. Never divides by zero.
    """
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
    if mode == "integer":
        return _integer_bins(vals, lo, hi)
    bins = max(1, int(bins))
    if hi <= lo:
        return [(lo, lo + 1.0, len(vals))]
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in vals:
        idx = int((v - lo) / width)
        if idx >= bins:      # the maximum lands exactly on the top edge
            idx = bins - 1
        counts[idx] += 1
    return [(lo + i * width, lo + (i + 1) * width, counts[i]) for i in range(bins)]


def _integer_bins(vals: list[float], lo: float,
                  hi: float) -> list[tuple[float, float, int]]:
    """1-wide buckets spanning ``floor(lo) .. ceil(hi)``.

    Empty buckets inside the range are kept so the axis reads continuously
    (0–1, 1–2, 2–3 …) instead of skipping a star nobody has.
    """
    start = math.floor(lo)
    end = math.ceil(hi)
    if end <= start:         # every value is a whole number, or all identical
        end = start + 1
    n = end - start
    counts = [0] * n
    for v in vals:
        idx = int(math.floor(v)) - start
        if idx >= n:         # the maximum lands exactly on the top edge
            idx = n - 1
        elif idx < 0:
            idx = 0
        counts[idx] += 1
    return [(float(start + i), float(start + i + 1), counts[i]) for i in range(n)]
