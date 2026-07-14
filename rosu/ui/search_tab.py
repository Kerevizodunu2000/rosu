# SPDX-License-Identifier: GPL-3.0-or-later
"""Search tab: relevance-ranked query over the music memory, with metadata.

Search runs off the UI thread and is debounced, so typing never freezes the app
even on a large library (item 10). An empty box lists everything so the library
is browsable (item 11).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from ..i18n import human_duration
from ..workers import Worker
from .copy_table import CopyTable, SortItem


class SearchTab(QWidget):
    _KEYS = ("col_name", "col_artist", "col_id", "col_bpm", "col_length",
             "col_mapper", "col_mode", "col_sources", "col_first_seen",
             "col_attempts", "col_lib_status", "col_location")

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.ctx = main_window.ctx
        self._threads: list[Worker] = []
        self._search_seq = 0        # ignore results from superseded searches
        self._loaded_once = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        row = QHBoxLayout()
        self.box = QLineEdit()
        self.box.returnPressed.connect(self.do_search)          # Enter = search now
        self.btn = QPushButton()
        self.btn.clicked.connect(self.do_search)
        self.btn_reload = QPushButton(objectName="secondary")
        self.btn_reload.clicked.connect(self.do_search)         # re-pull the list live
        row.addWidget(self.box, 1)
        row.addWidget(self.btn)
        row.addWidget(self.btn_reload)
        root.addLayout(row)

        self.result = QLabel(objectName="status")
        root.addWidget(self.result)
        self.hint = QLabel(objectName="status")
        root.addWidget(self.hint)

        self.table = CopyTable(name_column=0)
        self.table.setColumnCount(len(self._KEYS))
        root.addWidget(self.table, 1)

        # Debounced live search: wait until typing pauses (~250 ms) before running.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self.do_search)
        self.box.textChanged.connect(lambda _=None: self._debounce.start())

    def retranslate(self) -> None:
        t = self.ctx.t
        self.box.setPlaceholderText(t("search_placeholder"))
        self.btn.setText(t("tab_search"))
        self.btn_reload.setText(t("btn_reload"))
        self.hint.setText(t("copy_hint"))
        self.box.setToolTip(t("tip_search_box"))
        self.btn.setToolTip(t("tip_search_btn"))
        self.btn_reload.setToolTip(t("tip_reload"))
        self.table.setHorizontalHeaderLabels([t(k) for k in self._KEYS])
        self.table.set_menu_labels(t("copy_names_action"), t("copy_table_action"))

    def on_shown(self) -> None:
        # First time the tab is opened, show the full library so it's browsable.
        if not self._loaded_once:
            self._loaded_once = True
            self.do_search()

    def reload(self) -> None:
        """Re-run the current query after the library changed elsewhere (item 7)."""
        if self._loaded_once:
            self.do_search()

    def do_search(self) -> None:
        self._debounce.stop()
        query = self.box.text().strip()
        self._search_seq += 1
        seq = self._search_seq
        self.result.setText(self.ctx.t("working"))
        w = Worker(self.ctx.services.search, query)
        self._threads.append(w)
        w.succeeded.connect(lambda rows, s=seq, q=query: self._on_results(rows, s, q))
        w.failed.connect(self._on_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_failed(self, msg: str) -> None:
        self.result.setText(msg)

    def _on_results(self, rows: list[dict], seq: int, query: str) -> None:
        if seq != self._search_seq:
            return  # a newer search already ran; drop this stale result
        self._populate(rows)
        if not query:
            self.result.setText(self.ctx.t("browse_all", n=len(rows)))
        else:
            self.result.setText(self.ctx.t("search_have", n=len(rows)) if rows
                                else self.ctx.t("search_none"))

    def _populate(self, rows: list[dict]) -> None:
        self.table.setUpdatesEnabled(False)   # coalesce paints while filling (item 10)
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                status = row.get("library_status") or "-"
                if status == "disappeared" and row.get("status_changed_at"):
                    status = f"disappeared @ {row['status_changed_at']}"
                bpm = row.get("bpm")
                length = row.get("length_seconds")
                attempts = row.get("copy_attempts", 0)
                bid = row.get("beatmapset_id")
                loc_marks = []
                if row.get("in_osu"):
                    loc_marks.append("🎮")
                if row.get("in_library"):
                    loc_marks.append("💾")
                if row.get("in_drive"):
                    loc_marks.append("☁️")
                loc_weight = ((4 if row.get("in_osu") else 0)
                              + (2 if row.get("in_library") else 0)
                              + (1 if row.get("in_drive") else 0))
                cells = [
                    # Show the title only — the artist is its own column, so
                    # "Artist - Title" here was redundant and ate width. The full
                    # "Artist - Title" is still what a click/Ctrl+C copies (below).
                    (row.get("title") or row.get("display_name", ""), None),
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
                    (" ".join(loc_marks) if loc_marks else "-", loc_weight),
                ]
                for c, (text, sort_val) in enumerate(cells):
                    item = SortItem(text, sort_val)
                    if c in (0, 1) and text:
                        item.setToolTip(text)      # full name/artist on hover (item 15)
                    if c in (2, 3, 4, 9):
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.table.setItem(r, c, item)
                self.table.set_clean_name(r, row.get("display_name", ""))
                full = row.get("source_full") or []
                if full:
                    self.table.set_copy_value(r, 7, "; ".join(full))
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)
        self.table.seed_widths_once(name_min=260)   # title-only name column
