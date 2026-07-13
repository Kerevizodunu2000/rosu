# SPDX-License-Identifier: GPL-3.0-or-later
"""A confirm dialog whose action button is gated behind a visible countdown.

Used for a destructive, irreversible-feeling action (deleting the Library's
physical .osz copies — item 17). The user counts down 3 · 2 · 1, but each number
is shown for 1.4 s, so ~4.2 s really elapses before the button unlocks: a
perceived-3-seconds / actual-4-seconds pause that makes the choice deliberate.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)


class CountdownConfirmDialog(QDialog):
    def __init__(self, parent, title: str, body: str, confirm_label: str,
                 cancel_label: str, count: int = 3, tick_ms: int = 1400):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self._confirm_label = confirm_label
        self._remaining = count

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(14)
        msg = QLabel(body)
        msg.setWordWrap(True)
        msg.setMinimumWidth(380)
        root.addWidget(msg)

        self._count = QLabel(str(self._remaining), objectName="h1")
        self._count.setAlignment(Qt.AlignCenter)
        root.addWidget(self._count)

        row = QHBoxLayout()
        row.addStretch(1)
        self._cancel = QPushButton(cancel_label, objectName="secondary")
        self._cancel.clicked.connect(self.reject)
        self._ok = QPushButton(f"{confirm_label} ({self._remaining})")
        self._ok.setEnabled(False)
        self._ok.clicked.connect(self.accept)
        row.addWidget(self._cancel)
        row.addWidget(self._ok)
        root.addLayout(row)

        self._timer = QTimer(self)
        self._timer.setInterval(tick_ms)   # 3 × 1400ms = 4.2s real, shown as 3·2·1
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining > 0:
            self._count.setText(str(self._remaining))
            self._ok.setText(f"{self._confirm_label} ({self._remaining})")
        else:
            self._timer.stop()
            self._count.setText("")
            self._ok.setText(self._confirm_label)
            self._ok.setEnabled(True)
            self._ok.setDefault(True)
