# SPDX-License-Identifier: GPL-3.0-or-later
"""Cover art for the Search gallery (v1.9) — Qt-free.

A set's cover is the background image its ``.osu`` names in ``[Events]``
(``0,0,"bg.jpg",0,0``). This module only *finds and reads* those bytes out of
a Library ``.osz``, under size caps; decoding and thumbnailing happen in the UI
layer (Qt), and thumbnails are cached under ``data/covers``.
"""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from .zipread import read_capped

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp")
_OSU_CAP = 4 * 1024 * 1024       # the .osu read to find the background
_IMAGE_CAP = 12 * 1024 * 1024    # a background bigger than this is not decoded


def background_name(osu_text: str) -> str | None:
    """The background image an ``.osu`` names in ``[Events]`` (first one), with
    ``/`` separators; None when it names none."""
    section = ""
    for raw in osu_text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "Events" or not line.startswith("0,"):
            continue
        parts = line.split(",")
        if len(parts) >= 3:
            name = parts[2].strip().strip('"').replace("\\", "/")
            if name.lower().endswith(IMAGE_EXTS):
                return name
    return None


def cover_bytes(osz_path) -> bytes | None:
    """The cover image bytes inside a ``.osz`` — the background its first
    ``.osu`` names, else its largest image under the cap. None when there is
    none or the archive cannot be read."""
    try:
        with zipfile.ZipFile(osz_path) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            by_name = {i.filename.replace("\\", "/").lower(): i for i in infos}
            chosen = None
            for info in sorted(infos, key=lambda i: i.filename.lower()):
                if not info.filename.lower().endswith(".osu") or info.file_size > _OSU_CAP:
                    continue
                bg = background_name(read_capped(zf, info, _OSU_CAP).decode("utf-8", errors="replace"))
                if bg:
                    chosen = by_name.get(bg.lower())
                    if chosen is not None:
                        break
            if chosen is None:
                images = [i for i in infos if i.filename.lower().endswith(IMAGE_EXTS)
                          and 0 < i.file_size <= _IMAGE_CAP]
                chosen = max(images, key=lambda i: i.file_size, default=None)
            if chosen is None or not 0 < chosen.file_size <= _IMAGE_CAP:
                return None
            return read_capped(zf, chosen, _IMAGE_CAP)
    except Exception:   # unreadable, truncated, encrypted, bad compression…
        return None


def cache_name(path) -> str | None:
    """A cache file name that changes whenever the archive does (name, size,
    modification time) — a re-downloaded or pruned set gets a fresh thumbnail."""
    try:
        st = Path(path).stat()
    except OSError:
        return None
    key = f"{Path(path).name}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8", "replace")
    return hashlib.sha1(key).hexdigest() + ".jpg"


def prune_cache(cache_dir, keep: int = 4000) -> int:
    """Keep the ``keep`` most recently used thumbnails; returns how many went."""
    try:
        files = sorted(Path(cache_dir).glob("*.jpg"), key=lambda p: p.stat().st_mtime,
                       reverse=True)
    except OSError:
        return 0
    removed = 0
    for p in files[keep:]:
        try:
            p.unlink()
            removed += 1
        except OSError:
            pass
    return removed
