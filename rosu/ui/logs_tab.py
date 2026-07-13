# SPDX-License-Identifier: GPL-3.0-or-later
"""Logs tab: live view of today's log file, links to the format doc and Excel."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)


class LogsTab(QWidget):
    # Emitted for every new log line; a queued connection marshals the append
    # onto the UI thread even when the log originates in a worker thread.
    line_logged = Signal(str)

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.ctx = main_window.ctx

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        row = QHBoxLayout()
        self.btn_formats = QPushButton(objectName="secondary")
        self.btn_excel = QPushButton(objectName="secondary")
        self.btn_formats.clicked.connect(self._open_formats)
        self.btn_excel.clicked.connect(self._open_excel)
        row.addWidget(self.btn_formats)
        row.addWidget(self.btn_excel)
        row.addStretch(1)
        root.addLayout(row)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(5000)
        root.addWidget(self.view, 1)

        self.line_logged.connect(self.view.appendPlainText)

    def retranslate(self) -> None:
        self.btn_formats.setText(self.ctx.t("open_formats"))
        self.btn_excel.setText(self.ctx.t("open_excel"))

    def on_shown(self) -> None:
        self._load_today()

    def _log_file(self) -> Path:
        day = _dt.date.today().isoformat()
        return self.ctx.cfg.logs_path / f"app-{day}.log"

    def _load_today(self) -> None:
        path = self._log_file()
        try:
            self.view.setPlainText(path.read_text(encoding="utf-8"))
        except OSError:
            self.view.setPlainText("")
        self.view.verticalScrollBar().setValue(
            self.view.verticalScrollBar().maximum())

    def append_line(self, line: str) -> None:
        """Live sink called by the LogService (possibly from a worker thread)."""
        self.line_logged.emit(line)

    def _open(self, path: Path) -> None:
        """Open a file, or warn clearly if it isn't there yet (item 5/20)."""
        if not Path(path).exists():
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("file_missing", path=path))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_formats(self) -> None:
        self._open(self.ctx.cfg.logs_path / "log_formats.md")

    def _open_excel(self) -> None:
        self._open(self.ctx.cfg.excel_path)
