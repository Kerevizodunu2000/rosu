# SPDX-License-Identifier: GPL-3.0-or-later
"""Logs tab: a filterable table of any day's log (today's grows live), plus
links to the format doc and the Excel report."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import logsvc
from .copy_table import CopyTable

MAX_ROWS = 5000
_ERROR_FG = QColor("#e5534b")   # readable on both the dark and the light theme
_COLS = ("log_col_time", "log_col_level", "log_col_action", "log_col_fields",
         "log_col_message")


class LogsTab(QWidget):
    # Emitted for every new log line; a queued connection marshals the append
    # onto the UI thread even when the log originates in a worker thread.
    line_logged = Signal(str)

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.ctx = main_window.ctx
        self._entries: list[dict] = []    # the selected day, oldest first (capped)

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
        self.cbo_day = QComboBox()
        self.cbo_day.currentIndexChanged.connect(lambda _=0: self._load_day())
        row.addWidget(self.cbo_day)
        self.chk_errors = QCheckBox()
        self.chk_errors.toggled.connect(lambda _=False: self._refill())
        row.addWidget(self.chk_errors)
        self.filter = QLineEdit()
        self.filter.setClearButtonEnabled(True)
        self.filter.setMinimumWidth(220)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._refill)
        self.filter.textChanged.connect(lambda _=None: self._debounce.start())
        row.addWidget(self.filter)
        root.addLayout(row)

        self.count = QLabel(objectName="status")
        root.addWidget(self.count)
        self.table = CopyTable(name_column=4)
        self.table.setColumnCount(len(_COLS))
        self.table.setSortingEnabled(False)   # a log reads in time order
        root.addWidget(self.table, 1)

        self.line_logged.connect(self._on_live_line)

    def retranslate(self) -> None:
        t = self.ctx.t
        self.btn_formats.setText(t("open_formats"))
        self.btn_excel.setText(t("open_excel"))
        self.btn_formats.setToolTip(t("tip_open_formats"))
        self.btn_excel.setToolTip(t("tip_open_excel"))
        self.chk_errors.setText(t("log_errors_only"))
        self.filter.setPlaceholderText(t("log_filter"))
        self.table.setHorizontalHeaderLabels([t(k) for k in _COLS])
        self.table.set_menu_labels(t("copy_names_action"), t("copy_table_action"))
        self._update_count()

    def on_shown(self) -> None:
        self._fill_days()
        self._load_day()

    # -- days ------------------------------------------------------------------
    @staticmethod
    def _today() -> str:
        return _dt.date.today().isoformat()

    def _fill_days(self) -> None:
        current = self.cbo_day.currentData() or self._today()
        days = logsvc.log_days(self.ctx.cfg.logs_path)
        if self._today() not in days:
            days.insert(0, self._today())
        self.cbo_day.blockSignals(True)
        self.cbo_day.clear()
        for d in days:
            self.cbo_day.addItem(d, d)
        idx = self.cbo_day.findData(current)
        self.cbo_day.setCurrentIndex(max(0, idx))
        self.cbo_day.blockSignals(False)

    def _day(self) -> str:
        return self.cbo_day.currentData() or self._today()

    def _load_day(self) -> None:
        self._entries = logsvc.read_day(self.ctx.cfg.logs_path, self._day(), MAX_ROWS)
        self._refill()

    # -- table -----------------------------------------------------------------
    def _filter_args(self) -> tuple[list[str], bool]:
        return self.filter.text().lower().split(), self.chk_errors.isChecked()

    def _refill(self) -> None:
        words, errors = self._filter_args()
        shown = [e for e in self._entries if logsvc.entry_matches(e, words, errors)]
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(0)
            self.table.setRowCount(len(shown))
            for r, e in enumerate(shown):
                self._set_row(r, e)
        finally:
            self.table.setUpdatesEnabled(True)
        self.table.seed_widths_once(name_min=320)
        self.table.scrollToBottom()
        self._update_count(len(shown))

    def _set_row(self, r: int, e: dict) -> None:
        for c, key in enumerate(("time", "level", "action", "fields", "message")):
            item = QTableWidgetItem(e[key])
            if c in (3, 4) and e[key]:
                item.setToolTip(e[key])
            if c == 1 and e["level"] in ("ERROR", "WARN"):
                item.setForeground(QBrush(_ERROR_FG))
            self.table.setItem(r, c, item)
        self.table.set_clean_name(r, e["raw"])   # a click copies the whole line

    def _update_count(self, shown: int | None = None) -> None:
        if shown is None:
            shown = self.table.rowCount()
        self.count.setText(self.ctx.t("log_count", shown=shown, total=len(self._entries)))

    def append_line(self, line: str) -> None:
        """Live sink called by the LogService (possibly from a worker thread)."""
        self.line_logged.emit(line)

    def _on_live_line(self, line: str) -> None:
        if self._day() != self._today():
            return
        e = logsvc.parse_line(line)
        self._entries.append(e)
        if len(self._entries) > MAX_ROWS:
            del self._entries[0]
            if self.table.rowCount() >= MAX_ROWS:
                self.table.removeRow(0)
        words, errors = self._filter_args()
        if logsvc.entry_matches(e, words, errors):
            bar = self.table.verticalScrollBar()
            at_bottom = bar.value() >= bar.maximum() - 2
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._set_row(r, e)
            if at_bottom:
                self.table.scrollToBottom()
        self._update_count()

    # -- links -------------------------------------------------------------------
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
