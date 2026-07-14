# SPDX-License-Identifier: GPL-3.0-or-later
"""About / Licenses dialog: app version, the GPL summary, and the bundled
third-party notices (satisfies the LGPL/etc. "appropriate legal notices")."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout,
)

from .. import __version__


def _bundled_text(name: str) -> str:
    """Read a notices file that ships beside the code (repo root in the dev tree,
    the PyInstaller _MEIPASS root in the frozen exe)."""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / name)
    candidates.append(Path(__file__).resolve().parent.parent.parent / name)
    for p in candidates:
        try:
            if p.exists():
                return p.read_text(encoding="utf-8")
        except OSError:
            pass
    return ""


class AboutDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        t = ctx.t
        self.setWindowTitle(t("about_title"))
        self.setMinimumSize(560, 520)
        root = QVBoxLayout(self)

        title = QLabel(f"Rosu  v{__version__}", objectName="h1")
        root.addWidget(title)

        lic = QLabel(t("about_license"))
        lic.setWordWrap(True)
        lic.setTextFormat(Qt.RichText)
        lic.setOpenExternalLinks(True)
        root.addWidget(lic)

        root.addWidget(QLabel(t("about_third_party")))
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText(_bundled_text("THIRD-PARTY-LICENSES.md")
                          or t("about_third_party_missing"))
        root.addWidget(view, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)
