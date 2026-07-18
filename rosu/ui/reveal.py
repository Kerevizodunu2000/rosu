# SPDX-License-Identifier: GPL-3.0-or-later
"""Reveal a file in the OS file manager (v1.3). On Windows it selects the file
in Explorer; elsewhere it opens the containing folder. Missing files are
reported, not silently ignored."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox


def reveal_in_explorer(parent, ctx, path) -> None:
    """Open ``path``'s location. ``parent`` is the calling QWidget (for the
    warning dialog), ``ctx`` is the AppContext (for ``ctx.t`` translations).

    Callers pass internally-derived paths (scanned archives, Output/Library
    files) — this does not sanitise free-form input. Args go to ``Popen`` as a
    list (never ``shell=True``), so there is no shell-injection surface."""
    p = Path(path)
    if not p.exists():
        QMessageBox.information(parent, ctx.t("app_title"),
                                ctx.t("file_missing", path=str(p)))
        return
    if sys.platform.startswith("win"):
        try:
            # Reliable reveal-and-select is: explorer /select,"C:\dir\file" — the
            # switch OUTSIDE the quotes, the path INSIDE. Passing ["explorer",
            # "/select,<path>"] as a list quotes the WHOLE token when the path has
            # spaces ("/select,C:\...\a b.osz"), so Explorer treats it as a path,
            # fails, and just opens Documents. A raw command string goes straight
            # to CreateProcess (no shell); Windows file names can't contain '"',
            # so there is no injection surface. Use the fully-qualified path to
            # explorer.exe so a planted "explorer.exe" on the search path/CWD
            # can't be picked up instead.
            explorer = os.path.join(
                os.environ.get("WINDIR", r"C:\Windows"), "explorer.exe")
            subprocess.Popen(f'"{explorer}" /select,"{p}"')
            return
        except OSError:
            pass   # fall through to opening the containing folder
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))
