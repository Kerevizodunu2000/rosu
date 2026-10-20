# SPDX-License-Identifier: GPL-3.0-or-later
"""Cover gallery (v1.9): the Search results as a grid of background art.

Thumbnails are made off the UI thread — read from the Library ``.osz``
(:mod:`rosu.covers`), decoded and cropped with Qt, and cached as small JPEGs
under ``data/covers`` so a second look is instant.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QListView, QListWidget, QListWidgetItem

from .. import covers
from ..columns import has_library_copy
from ..workers import Worker
from .links import plain_tip

THUMB_W, THUMB_H = 240, 135        # 16:9, osu!'s background shape
GALLERY_CAP = 500                  # covers per view; the table still lists everything
_MAX_PIXELS = 40_000_000           # refuse to decode absurd images


def cover_crop(img: QImage, w: int = THUMB_W, h: int = THUMB_H) -> QImage:
    """Scale ``img`` to fill ``w``×``h`` and crop the middle (no letterboxing)."""
    scaled = img.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = max(0, (scaled.width() - w) // 2)
    y = max(0, (scaled.height() - h) // 2)
    return scaled.copy(x, y, w, h)


def thumbnail(osz_path: Path, cache_dir: Path) -> QImage | None:
    """The cached thumbnail for ``osz_path``, made (and cached) when missing."""
    name = covers.cache_name(osz_path)
    if name is None:
        return None
    cached = cache_dir / name
    if cached.exists():
        img = QImage(str(cached))
        if not img.isNull():
            try:
                os.utime(cached)          # most recently used: kept by prune_cache
            except OSError:
                pass
            return img
    data = covers.cover_bytes(osz_path)
    if not data:
        return None
    img = QImage.fromData(data)
    if img.isNull() or img.width() * img.height() > _MAX_PIXELS:
        return None
    img = cover_crop(img)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        img.save(str(cached), "JPG", 85)
    except OSError:
        pass
    return img


class CoverGallery(QListWidget):
    rowActivated = Signal(int)    # index into the rows given to set_rows

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._loader: Worker | None = None
        self._stop = [False]
        self._gen = 0                 # thumbnails from an older result set are dropped
        self._pruned = False
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideRight)
        self.setIconSize(QSize(THUMB_W, THUMB_H))
        self.setGridSize(QSize(THUMB_W + 18, THUMB_H + 48))
        self.setSpacing(4)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.itemActivated.connect(lambda item: self.rowActivated.emit(int(item.data(Qt.UserRole))))
        self._placeholder = self._make_placeholder()

    def _make_placeholder(self) -> QIcon:
        pm = QPixmap(THUMB_W, THUMB_H)
        pm.fill(QColor(128, 128, 128, 40))
        p = QPainter(pm)
        p.setPen(QColor(128, 128, 128, 160))
        p.drawText(pm.rect(), Qt.AlignCenter, "♪")
        p.end()
        return QIcon(pm)

    def stop(self) -> None:
        """Stop filling thumbnails (the loader ends at its next set)."""
        self._stop[0] = True

    def set_rows(self, rows: list[dict]) -> None:
        self.stop()
        self._gen += 1
        gen = self._gen
        self.clear()
        lib = self.ctx.cfg.library_path
        jobs: list[tuple[int, Path]] = []
        for i, row in enumerate(rows[:GALLERY_CAP]):
            artist = row.get("artist") or ""
            title = row.get("title") or row.get("display_name") or ""
            label = f"{artist} - {title}" if artist else title
            item = QListWidgetItem(self._placeholder, label)
            item.setData(Qt.UserRole, i)
            item.setToolTip(plain_tip(label))
            self.addItem(item)
            if row.get("filename") and has_library_copy(row):
                jobs.append((i, lib / row["filename"]))
        if not jobs:
            return
        stop = [False]
        self._stop = stop
        cache = self.ctx.cfg.data_path / "covers"
        prune = not self._pruned
        self._pruned = True

        def load(progress=None):
            if prune:
                covers.prune_cache(cache)
            for idx, path in jobs:
                if stop[0]:
                    return
                img = thumbnail(path, cache)
                if img is not None and not stop[0]:
                    progress((gen, idx, img))

        w = Worker(load)
        self._loader = w
        w.progressed.connect(self._on_thumb)
        w.start()

    def _on_thumb(self, payload) -> None:
        gen, idx, img = payload
        item = self.item(idx) if gen == self._gen else None
        if item is not None:
            item.setIcon(QIcon(QPixmap.fromImage(img)))
