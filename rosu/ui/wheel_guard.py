# SPDX-License-Identifier: GPL-3.0-or-later
"""Stop combo boxes from changing value on an accidental mouse-wheel scroll.

On a wheel event over a combo, instead of silently stepping through the options
(which is how settings get changed by accident while scrolling the page), we wait
~100 ms and then open the dropdown so every option is visible — the user notices
and changes the setting deliberately, if at all (item 16).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QComboBox

_guard: "_WheelGuard | None" = None


class _WheelGuard(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(100)  # brief delay so it's noticeable, not instant
        self._timer.timeout.connect(self._open_pending)
        self._pending: QComboBox | None = None

    def _open_pending(self) -> None:
        combo, self._pending = self._pending, None
        if combo is not None and combo.isVisible():
            combo.showPopup()

    def eventFilter(self, obj, ev) -> bool:
        if ev.type() == QEvent.Wheel and isinstance(obj, QComboBox):
            self._pending = obj          # reveal the options ~100 ms later
            self._timer.start()
            return True                   # never step the value on a wheel scroll
        return False


def guard(*combos: QComboBox) -> None:
    """Install the wheel guard on one or more combo boxes."""
    global _guard
    if _guard is None:
        _guard = _WheelGuard()
    for c in combos:
        c.installEventFilter(_guard)
