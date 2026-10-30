# SPDX-License-Identifier: GPL-3.0-or-later
"""Free-space pre-flight for large writes, and disk-full detection.

Qt-free and stdlib only. ``shutil.disk_usage`` is called through the module so
tests can monkeypatch it.
"""
from __future__ import annotations

import errno
import shutil
from pathlib import Path
from typing import NamedTuple

MARGIN = 256 * 1024 * 1024   # headroom so a run never fills the drive to the last byte


class Space(NamedTuple):
    free: int | None    # None when the drive could not be read
    total: int | None
    fits: bool
    drive: str          # the anchor (e.g. "D:\\"), never the full user path


def space(path, need: int, margin: int = MARGIN) -> Space:
    """Free space on the drive holding ``path`` (or its nearest existing
    ancestor), and whether ``need`` bytes plus ``margin`` fit. An unreadable
    drive never blocks: ``fits`` is True and ``free``/``total`` are None."""
    p = Path(path)
    try:
        p = p.resolve()
        while not p.exists() and p.parent != p:
            p = p.parent
        usage = shutil.disk_usage(p)
    except OSError:
        return Space(None, None, True, p.anchor)
    return Space(usage.free, usage.total, usage.free >= need + margin, p.anchor)


def shortfall(places, margin: int = MARGIN) -> dict | None:
    """Check ``(path, need)`` places at once: needs on the same drive add up and
    each drive is checked once. ``None`` when every drive fits, else
    ``{"drive", "need" (with the margin), "free"}`` for the first that doesn't.
    A place with ``need <= 0`` is ignored; an unreadable drive never blocks."""
    drives: dict[str, list] = {}
    for path, need in places:
        if need > 0:
            drives.setdefault(space(path, 0).drive, [path, 0])[1] += need
    for path, need in drives.values():
        sp = space(path, need, margin)
        if not sp.fits:
            return {"drive": sp.drive, "need": need + margin, "free": sp.free}
    return None


def is_disk_full(exc: BaseException) -> bool:
    """True for an OSError meaning "no space left": ENOSPC, or Windows
    ERROR_DISK_FULL (112) / ERROR_HANDLE_DISK_FULL (39)."""
    return isinstance(exc, OSError) and (
        exc.errno == errno.ENOSPC or getattr(exc, "winerror", None) in (112, 39))


class NotEnoughSpace(Exception):
    """A pre-flight refusal. Deliberately not an OSError, so ``except OSError``
    handlers can't swallow it. ``need`` includes the margin."""

    def __init__(self, drive: str, need: int, free: int):
        super().__init__(f"Not enough free space on {drive}: {need} bytes needed, "
                         f"{free} bytes free")
        self.drive = drive
        self.need = need
        self.free = free
