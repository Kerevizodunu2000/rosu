# SPDX-License-Identifier: GPL-3.0-or-later
"""Where a pruned set comes back FROM — stated, and chosen by the user.

"Restore" silently downloading from a third-party mirror is not good enough:
the user should know where their files are coming from, and should be able to
use the free, exact, already-on-disk copy instead when it is still available.

Two routes, and the reason the obvious third one is missing:

* **Recycle Bin** — prune put each original there under its own name. Free,
  instant, byte-identical. Rosu opens the bin and says what to look for rather
  than restoring for you: Windows exposes no reliable per-file restore that
  Rosu could drive without shelling into the undocumented side of the Shell API,
  and silently poking at the bin is not something this app should do.
* **osu! mirror (catboy.best)** — an automatic re-download of the complete set.
  Third-party, not run by ppy.
* **Official osu! servers** — not offered, because beatmap downloads there
  require a signed-in osu! account; the public API has no download endpoint.
  Saying so is better than leaving the user wondering why it is missing.
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QHBoxLayout, QLabel, QPushButton, QRadioButton,
    QVBoxLayout,
)

# Chosen source, returned via `RestoreSourceDialog.choice`.
MIRROR = "mirror"
RECYCLE = "recycle"


def open_recycle_bin() -> bool:
    """Open the OS Recycle Bin / Trash. ``False`` if this platform has none we
    know how to open — the caller then just shows the instructions."""
    if sys.platform.startswith("win"):
        try:
            os.startfile("shell:RecycleBinFolder")   # noqa: S606 - fixed shell id
            return True
        except OSError:
            return False
    for path in ("~/.local/share/Trash", "~/.Trash"):
        p = os.path.expanduser(path)
        if os.path.isdir(p):
            return QDesktopServices.openUrl(QUrl.fromLocalFile(p))
    return False


class RestoreSourceDialog(QDialog):
    """Pick where the pruned sets come back from. ``choice`` is set on accept."""

    def __init__(self, ctx, count: int, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.choice: str | None = None
        t = ctx.t

        self.setWindowTitle(t("restore_title"))
        self.setMinimumWidth(560)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        head = QLabel(objectName="h2")
        head.setWordWrap(True)
        head.setText(t("restore_head", n=count))
        root.addWidget(head)

        self.rb_recycle = QRadioButton(t("restore_opt_recycle"))
        note_recycle = QLabel(objectName="status")
        note_recycle.setWordWrap(True)
        note_recycle.setContentsMargins(22, 0, 0, 6)
        note_recycle.setText(t("restore_opt_recycle_note"))

        self.rb_mirror = QRadioButton(t("restore_opt_mirror"))
        note_mirror = QLabel(objectName="status")
        note_mirror.setWordWrap(True)
        note_mirror.setContentsMargins(22, 0, 0, 6)
        note_mirror.setText(t("restore_opt_mirror_note", url=_mirror_host()))

        group = QButtonGroup(self)
        group.addButton(self.rb_recycle)
        group.addButton(self.rb_mirror)
        self.rb_recycle.setChecked(True)     # free and exact — the better default
        for w in (self.rb_recycle, note_recycle, self.rb_mirror, note_mirror):
            root.addWidget(w)

        official = QLabel(objectName="status")
        official.setWordWrap(True)
        official.setText(t("restore_why_not_official"))
        root.addWidget(official)

        bar = QHBoxLayout()
        bar.addStretch(1)
        btn_cancel = QPushButton(t("btn_cancel"), objectName="secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton(t("restore_go"))
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._accept)
        bar.addWidget(btn_cancel)
        bar.addWidget(btn_ok)
        root.addLayout(bar)

    def _accept(self) -> None:
        self.choice = RECYCLE if self.rb_recycle.isChecked() else MIRROR
        self.accept()


def _mirror_host() -> str:
    from ..api_mirror import MIRROR_URL
    return MIRROR_URL.split("//", 1)[-1].split("/", 1)[0]
