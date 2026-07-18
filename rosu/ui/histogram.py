# SPDX-License-Identifier: GPL-3.0-or-later
"""A minimal, theme-aware, INTERACTIVE bar histogram widget (no chart library).

Draws ``[(bin_lo, bin_hi, count), ...]`` bars using the active palette's Highlight
(accent) for the bars — so it follows every theme in light and dark. Interaction:
click a bar to select it (drag across bars to select a range), which emits
``barSelected(lo, hi, count, percent)``; double-click a bar emits
``barActivated(lo, hi)`` (the Search tab uses these to jump to a star range).
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

_M_LEFT = _M_RIGHT = 10
_M_TOP, _M_BOTTOM = 12, 22
_GAP = 2.0


class Histogram(QWidget):
    barSelected = Signal(float, float, int, float)   # lo, hi, count, percent
    barActivated = Signal(float, float)              # lo, hi (double-click)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bins: list = []
        self._total = 0
        self._sel: set = set()          # selected bin indices (a contiguous range)
        self._drag_anchor: int | None = None
        self.setMinimumHeight(190)
        self.setMouseTracking(True)

    def set_bins(self, bins) -> None:
        self._bins = list(bins or [])
        self._total = sum(c for _, _, c in self._bins)
        self._sel = set()
        self._drag_anchor = None
        self.update()

    def selection_range(self) -> tuple[float, float] | None:
        if not self._sel:
            return None
        idxs = sorted(self._sel)
        return (self._bins[idxs[0]][0], self._bins[idxs[-1]][1])

    # -- geometry / hit-testing ---------------------------------------------
    def _bar_width(self) -> float:
        n = len(self._bins)
        if n == 0:
            return 0.0
        w = self.rect().width() - _M_LEFT - _M_RIGHT
        return max(1.0, (w - _GAP * (n - 1)) / n)

    def _bar_at(self, x: float) -> int | None:
        n = len(self._bins)
        if n == 0:
            return None
        bar_w = self._bar_width()
        i = int((x - _M_LEFT) / (bar_w + _GAP))
        return i if 0 <= i < n else None

    # -- painting ------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()
        pal = self.palette()
        p.fillRect(rect, pal.base())

        if not self._bins:
            p.setPen(pal.windowText().color())
            p.drawText(rect, Qt.AlignCenter, "—")
            p.end()
            return

        h = rect.height() - _M_TOP - _M_BOTTOM
        n = len(self._bins)
        max_count = max((c for _, _, c in self._bins), default=0) or 1
        bar_w = self._bar_width()
        accent = pal.highlight().color()
        dim = pal.highlight().color()
        dim.setAlpha(90)   # unselected bars dim when a selection is active
        for i, (_lo, _hi, count) in enumerate(self._bins):
            bh = (count / max_count) * h
            x = _M_LEFT + i * (bar_w + _GAP)
            y = _M_TOP + (h - bh)
            col = accent if (not self._sel or i in self._sel) else dim
            p.fillRect(QRectF(x, y, bar_w, bh), col)

        p.setPen(pal.windowText().color())
        base_y = rect.height() - _M_BOTTOM
        w = rect.width() - _M_LEFT - _M_RIGHT
        p.drawText(QRectF(_M_LEFT, base_y, w / 2, _M_BOTTOM),
                   Qt.AlignLeft | Qt.AlignVCenter, f"{self._bins[0][0]:.1f}★")
        p.drawText(QRectF(_M_LEFT + w / 2, base_y, w / 2, _M_BOTTOM),
                   Qt.AlignRight | Qt.AlignVCenter, f"{self._bins[-1][1]:.1f}★")
        p.end()

    # -- interaction ---------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        i = self._bar_at(event.position().x())
        if i is None:
            return
        self._drag_anchor = i
        self._sel = {i}
        self.update()
        self._emit_selection()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_anchor is None:
            return
        i = self._bar_at(event.position().x())
        if i is None:
            return
        lo, hi = sorted((self._drag_anchor, i))
        new = set(range(lo, hi + 1))
        if new != self._sel:
            self._sel = new
            self.update()
            self._emit_selection()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_anchor = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        i = self._bar_at(event.position().x())
        if i is None:
            return
        self.barActivated.emit(self._bins[i][0], self._bins[i][1])

    def _emit_selection(self) -> None:
        if not self._sel:
            return
        idxs = sorted(self._sel)
        lo = self._bins[idxs[0]][0]
        hi = self._bins[idxs[-1]][1]
        count = sum(self._bins[i][2] for i in idxs)
        pct = (count / self._total * 100) if self._total else 0.0
        self.barSelected.emit(lo, hi, count, pct)
