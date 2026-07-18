# SPDX-License-Identifier: GPL-3.0-or-later
"""About / Licenses dialog: app version, the GPL summary, and the bundled
third-party notices (satisfies the LGPL/etc. "appropriate legal notices")."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout,
)

from .. import __version__
from .links import wire_link_hover


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

        contact = QLabel(t("about_contact"))
        contact.setWordWrap(True)
        # Plain, selectable text — NOT a mailto: link. Launching mailto: crashes
        # with "no mail program installed" on machines without a mail client.
        contact.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(contact)

        # Social + legal are https:// — safe as clickable RichText (they open in
        # the browser via QDesktopServices; only mailto: crashes, which is why the
        # e-mail line above stays plain selectable text).
        website = QLabel(t("about_website"))
        website.setWordWrap(True)
        website.setTextFormat(Qt.RichText)
        website.setOpenExternalLinks(True)
        root.addWidget(website)

        social = QLabel(t("about_social"))
        social.setWordWrap(True)
        social.setTextFormat(Qt.RichText)
        social.setOpenExternalLinks(True)
        root.addWidget(social)

        legal = QLabel(t("about_legal"))
        legal.setWordWrap(True)
        legal.setTextFormat(Qt.RichText)
        legal.setOpenExternalLinks(True)
        root.addWidget(legal)

        # Every link shows where it goes on hover (app-wide convention).
        wire_link_hover(lic, website, social, legal)

        root.addWidget(QLabel(t("about_third_party")))
        view = QTextBrowser()   # render the .md as formatted text, not raw source
        view.setOpenExternalLinks(True)
        md = _bundled_text("THIRD-PARTY-LICENSES.md")
        if md:
            view.setMarkdown(md)
        else:
            view.setPlainText(t("about_third_party_missing"))
        wire_link_hover(view)
        root.addWidget(view, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)
