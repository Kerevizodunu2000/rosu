"""Search tab: relevance-ranked query over the music memory, with metadata."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from ..i18n import human_duration
from .copy_table import CopyTable, SortItem


class SearchTab(QWidget):
    _KEYS = ("col_name", "col_artist", "col_id", "col_bpm", "col_length",
             "col_mapper", "col_mode", "col_sources", "col_first_seen",
             "col_attempts", "col_lib_status")

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.ctx = main_window.ctx

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        row = QHBoxLayout()
        self.box = QLineEdit()
        self.box.returnPressed.connect(self.do_search)
        self.box.textChanged.connect(self._maybe_live)
        self.btn = QPushButton()
        self.btn.clicked.connect(self.do_search)
        row.addWidget(self.box, 1)
        row.addWidget(self.btn)
        root.addLayout(row)

        self.result = QLabel(objectName="status")
        root.addWidget(self.result)
        self.hint = QLabel(objectName="status")
        root.addWidget(self.hint)

        self.table = CopyTable(name_column=0)
        self.table.setColumnCount(len(self._KEYS))
        root.addWidget(self.table, 1)

    def retranslate(self) -> None:
        t = self.ctx.t
        self.box.setPlaceholderText(t("search_placeholder"))
        self.btn.setText(t("tab_search"))
        self.hint.setText(t("copy_hint"))
        self.table.setHorizontalHeaderLabels([t(k) for k in self._KEYS])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

    def _maybe_live(self, text: str) -> None:
        if len(text.strip()) >= 2:
            self.do_search()
        elif not text.strip():
            self.table.setRowCount(0)
            self.result.setText("")

    def do_search(self) -> None:
        query = self.box.text().strip()
        if not query:
            self.table.setRowCount(0)
            self.result.setText("")
            return
        rows = self.ctx.services.search(query)
        self._populate(rows)
        self.result.setText(self.ctx.t("search_have", n=len(rows)) if rows
                            else self.ctx.t("search_none"))

    def _populate(self, rows: list[dict]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            status = row.get("library_status") or "-"
            if status == "disappeared" and row.get("status_changed_at"):
                status = f"disappeared @ {row['status_changed_at']}"
            bpm = row.get("bpm")
            length = row.get("length_seconds")
            attempts = row.get("copy_attempts", 0)
            bid = row.get("beatmapset_id")
            cells = [
                (row.get("display_name", ""), None),
                (row.get("artist", ""), None),
                (str(bid) if bid is not None else "-", bid or 0),
                (f"{bpm:g}" if bpm else "", bpm or 0.0),
                (human_duration(length), length or 0),
                (row.get("creator") or "", None),
                (row.get("mode") or "", None),
                (", ".join(row.get("sources", [])), None),
                (row.get("first_seen_at", ""), None),
                (str(attempts), attempts),
                (status, None),
            ]
            for c, (text, sort_val) in enumerate(cells):
                item = SortItem(text, sort_val)
                if c in (2, 3, 4, 9):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, item)
            self.table.set_clean_name(r, row.get("display_name", ""))
            full = row.get("source_full") or []
            if full:
                self.table.set_copy_value(r, 7, "; ".join(full))
        self.table.setSortingEnabled(True)
        header = self.table.horizontalHeader()
        for c in range(1, len(self._KEYS)):
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
