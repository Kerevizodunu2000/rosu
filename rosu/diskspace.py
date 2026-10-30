# SPDX-License-Identifier: GPL-3.0-or-later
"""Free-space pre-flight for large writes, and disk-full detection.

Qt-free and stdlib only. ``shutil.disk_usage`` is called through the module so
tests can monkeypatch it.
"""
from __future__ import annotations

import errno
import os
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


LOW_PCT = 0.10                 # a drive is "low" under 10% free ...
LOW_BYTES = 5 * 1024 ** 3      # ... or under 5 GiB free


def usage(places) -> list[dict]:
    """Per-drive usage for ``(label, path)`` pairs: one entry per distinct drive,
    ``{"drive", "labels", "used", "total", "free", "readable", "low"}``. A ``None``
    or missing path is skipped. Never raises; an unreadable drive has ``None``
    numbers and ``low=False``."""
    drives: dict[str, dict] = {}
    for label, path in places:
        try:
            if path is None or not Path(path).exists():
                continue
        except OSError:
            continue
        sp = space(path, 0)
        d = drives.setdefault(sp.drive, {"drive": sp.drive, "labels": [], "used": None,
                                         "total": sp.total, "free": sp.free,
                                         "readable": sp.free is not None, "low": False})
        d["labels"].append(label)
    for d in drives.values():
        if d["readable"]:
            d["used"] = d["total"] - d["free"]
            d["low"] = d["free"] < d["total"] * LOW_PCT or d["free"] < LOW_BYTES
    return list(drives.values())


def tree_size(path, cancel=None) -> int:
    """Total bytes of the files under ``path`` from directory metadata only (no
    opens, no symlinks followed). 0 for a missing path; stops early when
    ``cancel()`` is true."""
    total = 0
    todo = [str(path)]
    while todo:
        if cancel is not None and cancel():
            break
        try:
            with os.scandir(todo.pop()) as it:
                for e in it:
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            todo.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total


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
