# SPDX-License-Identifier: GPL-3.0-or-later
"""Read the shared (set-level) metadata from the .osu files inside an .osz.

This is now a thin wrapper over :mod:`rosu.beatmap`, which parses *every*
difficulty in one pass. ``read_osz_meta`` returns just the representative
:class:`~.models.TrackMeta` — the exact record older versions produced — so the
existing metadata-only call sites (extractor, library scan) are unchanged. Callers
that also need the per-difficulty data or the raw bytes use
:func:`rosu.beatmap.read_osz_full` directly.
"""
from __future__ import annotations

from pathlib import Path

from .beatmap import read_osz_full
from .models import TrackMeta


def read_osz_meta(osz_path: Path) -> TrackMeta:
    """Return :class:`TrackMeta` for an .osz file (best-effort, never raises)."""
    return read_osz_full(osz_path)[0]
