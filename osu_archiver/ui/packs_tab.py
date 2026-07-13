"""Packs tab: every pack grouped by category, with confirmed red gaps, search."""
from __future__ import annotations

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QVBoxLayout, QWidget,
)

from ..gaps import _present_row
from .copy_table import CopyTable, SortItem

_RED_BG = QColor("#FFC7CE")
_RED_FG = QColor("#9C0006")
_COLS = ["Category", "Series", "Number / Season", "Code", "Title", "Mode", "Tracks", "Extracted At"]


class PacksTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.ctx = main_window.ctx
        self._rows: list = []

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.textChanged.connect(self._apply_filter)
        self.cb_missing = QCheckBox()
        self.cb_missing.toggled.connect(self._apply_filter)
        self.filter = QComboBox()
        self.filter.currentIndexChanged.connect(self._apply_filter)
        top.addWidget(self.search, 1)
        top.addWidget(self.cb_missing)
        top.addWidget(self.filter)
        root.addLayout(top)

        self.hint = QLabel(objectName="status")
        root.addWidget(self.hint)

        self.table = CopyTable(name_column=3)  # Code column
        self.table.setColumnCount(len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        root.addWidget(self.table, 1)

    def retranslate(self) -> None:
        self.search.setPlaceholderText(self.ctx.t("packs_search_placeholder"))
        self.cb_missing.setText(self.ctx.t("only_missing"))
        self.hint.setText(self.ctx.t("copy_hint"))
        self.table.set_menu_labels(self.ctx.t("copy_names_action"),
                                   self.ctx.t("copy_table_action"))
        self._reload_filter_options()

    def on_shown(self) -> None:
        self.reload()

    def focus_missing(self) -> None:
        """Jump here from the Dashboard banner showing only the missing rows
        (item 12): reset category to All and tick 'Only missing'."""
        self.filter.blockSignals(True)
        self.filter.setCurrentIndex(0)  # "All"
        self.filter.blockSignals(False)
        self.search.clear()
        self.cb_missing.setChecked(True)  # triggers _apply_filter
        self._apply_filter()

    def _reload_filter_options(self) -> None:
        current = self.filter.currentText()
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItems(["All"] + self.ctx.db.category_list())
        idx = self.filter.findText(current)
        if idx >= 0:
            self.filter.setCurrentIndex(idx)
        self.filter.blockSignals(False)

    def _collect(self) -> list:
        db = self.ctx.db
        rows = []  # (category, GapRow, full_name)
        for s in db.series_list():
            present = db.packs_for_series(s)
            category = present[0]["category"] if present else "Other"
            code_full = {p["code"]: p["full_name"] for p in present}
            for gr in self.ctx.services.series_rows(s):
                rows.append((category, gr, code_full.get(gr.code)))
        for p in db.packs_for_category("Other"):
            if p.get("series") is None:
                rows.append(("Other", _present_row(None, p), p["full_name"]))
        return rows

    def reload(self) -> None:
        self._reload_filter_options()
        self._rows = self._collect()
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self.search.text().strip().casefold()
        cat = self.filter.currentText() or "All"
        missing_only = self.cb_missing.isChecked()
        shown = []
        for category, gr, full in self._rows:
            if missing_only and gr.present:
                continue
            if cat not in ("All", category):
                continue
            if text:
                hay = " ".join(str(x) for x in
                               (category, gr.series, gr.code, gr.title, gr.mode) if x)
                if text not in hay.casefold():
                    continue
            shown.append((category, gr, full))
        self._render(shown)

    def _render(self, rows: list) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, (category, gr, full) in enumerate(rows):
            if gr.series == "R" or gr.year is not None:
                key_txt = " ".join(str(x) for x in (gr.year, gr.season) if x is not None)
            else:
                key_txt = "" if gr.number is None else str(gr.number)
            values = [category, gr.series or "", key_txt, gr.code or "",
                      gr.title or "", gr.mode or "",
                      "" if not gr.present else (gr.track_count or ""),
                      gr.extracted_at or ""]
            for c, v in enumerate(values):
                sort_val = gr.number if c == 2 and gr.number is not None else None
                item = SortItem("" if v is None else str(v), sort_val)
                if not gr.present:
                    item.setBackground(QBrush(_RED_BG))
                    item.setForeground(QBrush(_RED_FG))
                self.table.setItem(r, c, item)
            self.table.set_clean_name(r, full if (gr.present and full) else (gr.code or ""))
        self.table.setSortingEnabled(True)
        header = self.table.horizontalHeader()
        self.table.resizeColumnsToContents()
        header.setSectionResizeMode(4, QHeaderView.Stretch)
