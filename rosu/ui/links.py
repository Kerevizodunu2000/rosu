# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared link helpers: show a link's destination while hovering it (app-wide),
so the user always sees where a link goes before clicking."""
from __future__ import annotations

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QToolTip


def wire_link_hover(*widgets):
    """Connect each widget's ``linkHovered`` signal so hovering a link shows its
    URL as a tooltip. Works for any widget with a ``linkHovered`` signal (QLabel
    with RichText, QTextBrowser). Returns the widgets for chaining."""
    def _on(url: str) -> None:
        if url:
            QToolTip.showText(QCursor.pos(), url)
        else:
            QToolTip.hideText()
    for w in widgets:
        sig = getattr(w, "linkHovered", None)
        if sig is not None:
            sig.connect(_on)
    return widgets
