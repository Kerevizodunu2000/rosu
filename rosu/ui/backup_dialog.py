# SPDX-License-Identifier: GPL-3.0-or-later
"""Pre-backup options: how many new sets to upload this run + the chunk size."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QSpinBox,
    QVBoxLayout,
)

_CHUNK_CHOICES_MB = (256, 512, 1024, 2048)


def _fmt_mb(n_bytes: int) -> str:
    return f"{n_bytes / (1024 * 1024):,.0f} MB"


class BackupOptionsDialog(QDialog):
    """Returns (max_sets, chunk_bytes) via :meth:`choices` when accepted."""

    def __init__(self, ctx, count: int, total_bytes: int, chunk_bytes: int,
                 parent=None):
        super().__init__(parent)
        t = ctx.t
        self.setWindowTitle(t("backup_opts_title"))
        self.setMinimumWidth(430)
        root = QVBoxLayout(self)

        summary = QLabel(t("backup_opts_summary", n=count, size=_fmt_mb(total_bytes)))
        summary.setWordWrap(True)
        root.addWidget(summary)

        form = QFormLayout()
        self.count = QSpinBox()
        self.count.setRange(1, max(1, count))
        self.count.setValue(max(1, count))          # default: upload all
        form.addRow(t("backup_opts_count"), self.count)

        self.chunk = QComboBox()
        for mb in _CHUNK_CHOICES_MB:
            self.chunk.addItem(_fmt_mb(mb * 1024 * 1024), mb * 1024 * 1024)
        idx = self.chunk.findData(chunk_bytes)
        self.chunk.setCurrentIndex(idx if idx >= 0 else 2)   # default 1 GB
        form.addRow(t("backup_opts_chunk"), self.chunk)
        root.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("backup_opts_start"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def choices(self) -> tuple[int, int]:
        return self.count.value(), self.chunk.currentData()
