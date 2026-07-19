# SPDX-License-Identifier: GPL-3.0-or-later
"""A minimal, theme-aware dual-handle range slider (v1.6).

Qt ships no range slider, so this is a small bespoke widget: a track with two
draggable handles selecting a ``[lo, hi]`` sub-range, painted from the active
palette (Highlight for the selected span/handles, mid for the track) so it follows
every theme — same style as :mod:`rosu.ui.histogram`. Emits ``rangeChanged(lo, hi)``
live while dragging. Used by the Search filters panel for the star range.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

_H = 6.0        # track thickness
_KNOB = 8.0     # handle radius


class RangeSlider(QWidget):
    rangeChanged = Signal(float, float)   # lo, hi

    def __init__(self, minimum=0.0, maximum=10.0, step=0.1, parent=None):
        super().__init__(parent)
        self._min = float(minimum)
        self._max = float(maximum)
        self._step = float(step)
        self._lo = self._min
        self._hi = self._max
        self._drag = None            # 'lo' | 'hi' | None
        self.setMinimumHeight(30)
        self.setMouseTracking(True)

    # -- state ---------------------------------------------------------------
    def set_range(self, minimum: float, maximum: float) -> None:
        self._min, self._max = float(minimum), float(maximum)
        self._lo = max(self._min, min(self._lo, self._max))
        self._hi = max(self._min, min(self._hi, self._max))
        self.update()

    def values(self) -> tuple[float, float]:
        return (self._lo, self._hi)

    def set_values(self, lo: float, hi: float, emit: bool = False) -> None:
        lo = self._snap(max(self._min, min(lo, self._max)))
        hi = self._snap(max(self._min, min(hi, self._max)))
        if lo > hi:
            lo, hi = hi, lo
        changed = (lo, hi) != (self._lo, self._hi)
        self._lo, self._hi = lo, hi
        self.update()
        if emit and changed:
            self.rangeChanged.emit(self._lo, self._hi)

    def _snap(self, v: float) -> float:
        return round(round(v / self._step) * self._step, 4)

    # -- geometry ------------------------------------------------------------
    def _span(self) -> float:
        return (self._max - self._min) or 1.0

    def _x_for(self, v: float) -> float:
        w = self.width() - 2 * _KNOB
        return _KNOB + (v - self._min) / self._span() * w

    def _v_for(self, x: float) -> float:
        w = self.width() - 2 * _KNOB
        return self._min + (x - _KNOB) / (w or 1.0) * self._span()

    # -- painting ------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        pal = self.palette()
        cy = self.height() / 2.0
        track = pal.mid().color()
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(_KNOB, cy - _H / 2, self.width() - 2 * _KNOB, _H),
                          _H / 2, _H / 2)
        accent = pal.highlight().color()
        xlo, xhi = self._x_for(self._lo), self._x_for(self._hi)
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(xlo, cy - _H / 2, xhi - xlo, _H), _H / 2, _H / 2)
        for x in (xlo, xhi):
            p.drawEllipse(QRectF(x - _KNOB, cy - _KNOB, 2 * _KNOB, 2 * _KNOB))
        p.end()

    # -- interaction ---------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        x = event.position().x()
        # pick the nearer handle
        self._drag = "lo" if abs(x - self._x_for(self._lo)) <= \
            abs(x - self._x_for(self._hi)) else "hi"
        self._drag_to(x)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag:
            self._drag_to(event.position().x())

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag = None

    def _drag_to(self, x: float) -> None:
        v = self._snap(self._v_for(x))
        if self._drag == "lo":
            self.set_values(min(v, self._hi), self._hi, emit=True)
        else:
            self.set_values(self._lo, max(v, self._lo), emit=True)
