# SPDX-License-Identifier: GPL-3.0-or-later
"""Packs tab: every pack grouped by category, with confirmed red gaps, search."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QWidget,
)

from . import wheel_guard
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
        self.cb_extra = QCheckBox()
        self.cb_extra.toggled.connect(self._apply_filter)
        self.filter = QComboBox()
        self.filter.currentIndexChanged.connect(self._apply_filter)
        top.addWidget(self.search, 1)
        top.addWidget(self.cb_missing)
        top.addWidget(self.cb_extra)
        top.addWidget(self.filter)
        self.btn_reload = QPushButton(objectName="secondary")
        self.btn_reload.clicked.connect(self.refresh_now)
        top.addWidget(self.btn_reload)
        root.addLayout(top)
        wheel_guard.guard(self.filter)   # no accidental change on scroll (item 16)

        self.hint = QLabel(objectName="status")
        root.addWidget(self.hint)

        # Where the packs themselves come from: link to osu!'s official pack
        # listing so users know missing (red) rows are downloadable there.
        self.download_hint = QLabel(objectName="status")
        self.download_hint.setWordWrap(True)
        self.download_hint.setTextFormat(Qt.RichText)
        self.download_hint.setOpenExternalLinks(True)
        root.addWidget(self.download_hint)

        self.table = CopyTable(name_column=3)  # Code column
        self.table.setColumnCount(len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        root.addWidget(self.table, 1)

    def retranslate(self) -> None:
        self.search.setPlaceholderText(self.ctx.t("packs_search_placeholder"))
        self.btn_reload.setText(self.ctx.t("btn_reload"))
        self.btn_reload.setToolTip(self.ctx.t("tip_reload"))
        self.cb_missing.setText(self.ctx.t("only_missing"))
        self.cb_extra.setText(self.ctx.t("only_extra"))
        self.hint.setText(self.ctx.t("copy_hint"))
        self.download_hint.setText(self.ctx.t("packs_download_hint"))
        self.table.set_menu_labels(self.ctx.t("copy_names_action"),
                                   self.ctx.t("copy_table_action"))
        self.search.setToolTip(self.ctx.t("tip_packs_search"))
        self.cb_missing.setToolTip(self.ctx.t("tip_only_missing"))
        self.cb_extra.setToolTip(self.ctx.t("tip_only_extra"))
        self.filter.setToolTip(self.ctx.t("tip_packs_filter"))
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
        self.filter.addItems(["All"] + self.ctx.services.category_list())
        idx = self.filter.findText(current)
        if idx >= 0:
            self.filter.setCurrentIndex(idx)
        self.filter.blockSignals(False)

    def reload(self) -> None:
        self._reload_filter_options()
        self._rows = self.ctx.services.packs_overview()   # (category, GapRow, full_name)
        self._apply_filter()

    def refresh_now(self) -> None:
        """Explicit ⟳: empty the table for a beat before re-filling, so the
        refresh is visible instead of an apparent no-op (the reload itself is
        synchronous and would otherwise finish before the eye catches it)."""
        self.btn_reload.setEnabled(False)
        self.table.setRowCount(0)
        self.hint.setText(self.ctx.t("refreshing"))
        QTimer.singleShot(150, self._finish_refresh)

    def _finish_refresh(self) -> None:
        try:
            self.reload()
        finally:
            self.hint.setText(self.ctx.t("copy_hint"))
            self.btn_reload.setEnabled(True)

    def _apply_filter(self) -> None:
        text = self.search.text().strip().casefold()
        cat = self.filter.currentText() or "All"
        missing_only = self.cb_missing.isChecked()
        extra_only = self.cb_extra.isChecked()
        shown = []
        for category, gr, full in self._rows:
            if missing_only and gr.present:
                continue
            if extra_only and not getattr(gr, "extra_count", 0):
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
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(rows))
            for r, (category, gr, full) in enumerate(rows):
                if gr.series == "R" or gr.year is not None:
                    key_txt = " ".join(str(x) for x in (gr.year, gr.season) if x is not None)
                else:
                    key_txt = "" if gr.number is None else str(gr.number)
                title = gr.title or ""
                if getattr(gr, "extra_count", 0):
                    title += self.ctx.t("extra_marker", n=gr.extra_count)
                values = [category, gr.series or "", key_txt, gr.code or "",
                          title, gr.mode or "",
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
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)
        self.table.seed_widths_once(name_min=0)   # content-fit once, then resizable (item 16)
