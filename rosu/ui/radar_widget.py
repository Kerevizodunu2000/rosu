# SPDX-License-Identifier: GPL-3.0-or-later
"""A minimal, theme-aware radar (spider) chart for Rosu Skillset Ratings (v1.6).

Draws one polygon over seven axes (Etterna's skillset names) from a
``{skill: value}`` map, auto-scaled to the map's own hardest skill so the *shape*
reads as the chart's skillset balance. Palette-driven (Highlight fill, WindowText
grid/labels, Base background) so it follows every theme in light and dark — same
bespoke-widget style as :mod:`rosu.ui.histogram`. No chart library.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPolygonF
from PySide6.QtWidgets import QWidget

from ..models import MsdResult

# Short axis labels in MsdResult.SKILLS order.
_LABELS = {
    "stream": "Stream", "jumpstream": "JS", "handstream": "HS",
    "stamina": "Stam", "jackspeed": "Jack", "chordjack": "CJ",
    "technical": "Tech",
}
_MARGIN = 34.0   # room for axis labels around the plot


class RadarChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: dict = {}
        self._max = 1.0
        self.setMinimumSize(240, 220)

    def set_values(self, skills: dict) -> None:
        """``skills`` maps each :data:`MsdResult.SKILLS` name to a float."""
        self._values = {k: float(skills.get(k) or 0.0) for k in MsdResult.SKILLS}
        peak = max(self._values.values(), default=0.0)
        # round the outer ring up to a tidy number so it's a readable reference
        self._max = max(1.0, math.ceil(peak + 1e-9))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()
        pal = self.palette()
        p.fillRect(rect, pal.base())

        axes = MsdResult.SKILLS
        n = len(axes)
        cx = rect.width() / 2.0
        cy = rect.height() / 2.0
        radius = max(10.0, min(cx, cy) - _MARGIN)

        grid = pal.windowText().color()
        grid.setAlpha(60)
        p.setPen(grid)
        # concentric grid rings
        for ring in range(1, 4):
            rr = radius * ring / 3.0
            pts = [QPointF(cx + rr * math.cos(_angle(i, n)),
                           cy + rr * math.sin(_angle(i, n))) for i in range(n)]
            p.drawPolygon(QPolygonF(pts))
        # spokes
        for i in range(n):
            a = _angle(i, n)
            p.drawLine(QPointF(cx, cy),
                       QPointF(cx + radius * math.cos(a), cy + radius * math.sin(a)))

        # value polygon
        vpts = []
        for i, k in enumerate(axes):
            frac = self._values.get(k, 0.0) / self._max if self._max else 0.0
            frac = max(0.0, min(1.0, frac))
            a = _angle(i, n)
            vpts.append(QPointF(cx + radius * frac * math.cos(a),
                                cy + radius * frac * math.sin(a)))
        accent = pal.highlight().color()
        fill = QColor(accent)
        fill.setAlpha(90)
        p.setBrush(fill)
        p.setPen(accent)
        p.drawPolygon(QPolygonF(vpts))
        p.setBrush(Qt.NoBrush)

        # axis labels + the outer-ring reference value
        p.setPen(pal.windowText().color())
        for i, k in enumerate(axes):
            a = _angle(i, n)
            lx = cx + (radius + 16) * math.cos(a)
            ly = cy + (radius + 16) * math.sin(a)
            p.drawText(QRectF(lx - 34, ly - 9, 68, 18), Qt.AlignCenter, _LABELS[k])
        ref = pal.windowText().color()
        ref.setAlpha(150)
        p.setPen(ref)
        p.drawText(QRectF(2, 2, rect.width() - 4, 16), Qt.AlignRight | Qt.AlignTop,
                   f"{self._max:.0f}★ max")
        p.end()


def _angle(i: int, n: int) -> float:
    """Angle for axis ``i`` of ``n`` — first axis points straight up."""
    return -math.pi / 2.0 + 2.0 * math.pi * i / n
