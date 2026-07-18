# SPDX-License-Identifier: GPL-3.0-or-later
"""Tiny pure-Python statistics helpers (no numpy — the PyInstaller spec excludes it)."""
from __future__ import annotations


def histogram_bins(values, bins: int = 20) -> list[tuple[float, float, int]]:
    """Bin ``values`` into ``[(bin_lo, bin_hi, count), ...]``.

    Degenerate inputs are safe: an empty/all-None list yields ``[]``; when every
    value is identical, one unit-width bin is returned so the caller still has a
    bar to draw. Never divides by zero.
    """
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
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
