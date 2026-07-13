"""A determinate 0→100 progress panel showing the current archive and beatmap.

    <archive>.zip
       <beatmap>.osz
    [=========------]  742 / 2140  35%
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class ProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(3)

        self.pack_label = QLabel(objectName="h1")
        self.pack_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.osz_label = QLabel(objectName="status")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(True)

        layout.addWidget(self.pack_label)
        layout.addWidget(self.osz_label)
        layout.addWidget(self.bar)
        self.setVisible(False)

    def start(self) -> None:
        self.setVisible(True)
        self.bar.setValue(0)
        self.pack_label.setText("")
        self.osz_label.setText("")

    def update_progress(self, done: int, total: int, pack: str, osz: str) -> None:
        pct = int(done * 100 / total) if total else 0
        self.bar.setValue(pct)
        self.bar.setFormat(f"{done} / {total}   %p%")
        self.pack_label.setText(pack)
        self.osz_label.setText(f"   {osz}")

    def finish(self) -> None:
        self.setVisible(False)
