# SPDX-License-Identifier: GPL-3.0-or-later
"""A QTableWidget with several clipboard behaviours and typed sorting.

* **Single click** on a row copies a clean name (for a red "missing" row this is
  the code/name that *should* be there; for a normal row it's the full archive
  name). Works for single or multi selection — one name per line.
* **Double click** on a cell copies just that cell's value (id, source, bpm…),
  so you can grab one specific field (item 3).
* **Right click** → "Copy names" copies the selected rows' names, one per line —
  a reliable way to grab a multi-selection's names (item 13).
* **Ctrl+C** copies the selected rows as tab-separated values (Excel-pasteable),
  every column included.

``SortItem`` carries a separate sort key so numeric columns (BPM, length, song
count) sort numerically even when displayed as formatted text.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QHeaderView, QMenu, QTableWidget,
    QTableWidgetItem,
)

_CLEAN_ROLE = Qt.UserRole + 11  # per-row clean copy name (single-click copy)
_COPY_ROLE = Qt.UserRole + 12   # per-cell TSV copy override (Ctrl+C / double-click)
_PATH_ROLE = Qt.UserRole + 13   # per-row file path for "Open file location" (v1.3)
_URL_ROLE = Qt.UserRole + 14    # per-row web URL ("Open osu! page", v1.4.1)
_URL_PRIMARY_ROLE = Qt.UserRole + 15  # True → clicks act on the URL (missing rows)


class SortItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value=None):
        super().__init__(text)
        self._sort = sort_value if sort_value is not None else text

    def __lt__(self, other):
        # NEVER call super().__lt__(other) here: PySide6's virtual trampoline
        # re-enters this very override for QTableWidgetItem::__lt__, so on a
        # fallback path it recurses into itself until RecursionError (seen
        # sorting a 14000-row table with mismatched/None sort keys). Instead,
        # pull a comparable key straight out of `other` and fall back to a
        # plain string compare if the keys turn out to be incomparable.
        if isinstance(other, SortItem):
            other_key = other._sort
        elif isinstance(other, QTableWidgetItem):
            other_key = other.text()
        else:
            other_key = other
        try:
            return self._sort < other_key
        except TypeError:
            return str(self._sort) < str(other_key)


class CopyTable(QTableWidget):
    openLocationRequested = Signal(str)   # emitted with a file path (v1.3)

    def __init__(self, name_column: int = 0, parent=None):
        super().__init__(parent)
        self._name_column = name_column
        self._menu_names = "Copy names"          # overridable via set_menu_labels
        self._menu_table = "Copy as table (Ctrl+C)"
        self._menu_open_location = ""            # set via retranslate; empty = hidden
        self._menu_open_url = ""                 # set via retranslate; empty = hidden
        self._widths_seeded = False
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(30)  # a touch taller = legible (item 15)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        # Columns are user-resizable: keep sections Interactive (Qt's default, which
        # Stretch/ResizeToContents used to disable) and let the last one fill leftover
        # width, so drag-to-resize works in every table (item 16).
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.cellClicked.connect(self._on_cell_clicked)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    def set_menu_labels(self, copy_names: str, copy_table: str) -> None:
        self._menu_names = copy_names
        self._menu_table = copy_table

    def seed_widths_once(self, name_min: int = 260, col_max: int = 300) -> None:
        """Set sensible initial column widths the first time rows exist, then leave
        them alone so the user's manual drags (item 16) survive later re-populates.

        Every column is capped at ``col_max`` so one very long cell (a long artist
        or source list) can't blow a column out and push the rest off-screen; the
        name column is then floored at ``name_min``. Users can still drag any
        column wider, and full text is available on hover."""
        if self._widths_seeded or self.rowCount() == 0:
            return
        self.resizeColumnsToContents()
        for c in range(self.columnCount()):
            if self.columnWidth(c) > col_max:
                self.setColumnWidth(c, col_max)
        nc = self._name_column
        if 0 <= nc < self.columnCount() and self.columnWidth(nc) < name_min:
            self.setColumnWidth(nc, name_min)
        self._widths_seeded = True

    def set_clean_name(self, row: int, name: str) -> None:
        """Set the clean name copied when the row is clicked."""
        item = self.item(row, self._name_column)
        if item is not None:
            item.setData(_CLEAN_ROLE, name)

    def set_copy_value(self, row: int, col: int, text: str) -> None:
        """Override what Ctrl+C copies for a cell (e.g. full archive names)."""
        item = self.item(row, col)
        if item is not None:
            item.setData(_COPY_ROLE, text)

    def set_row_path(self, row: int, path) -> None:
        """Attach a file path to this row for the "Open file location" context
        menu entry (v1.3). Stored on the name-column item, same as the other
        per-row roles."""
        item = self.item(row, self._name_column)
        if item is not None:
            item.setData(_PATH_ROLE, str(path))

    def _row_path(self, row: int) -> str:
        item = self.item(row, self._name_column)
        if item is None:
            return ""
        val = item.data(_PATH_ROLE)
        return val if val else ""

    def set_row_url(self, row: int, url: str, primary: bool = False) -> None:
        """Attach a web URL to this row (v1.4.1 — the Packs tab's osu! pack
        pages). Every URL row gains an "Open osu! page" context-menu entry.
        With ``primary=True`` (missing packs) the URL also becomes what clicks
        act on: single-click copies the link (multi-select collects one per
        line) and double-click opens the page in the browser."""
        item = self.item(row, self._name_column)
        if item is not None:
            item.setData(_URL_ROLE, url)
            item.setData(_URL_PRIMARY_ROLE, bool(primary))

    def _row_url(self, row: int) -> str:
        item = self.item(row, self._name_column)
        if item is None:
            return ""
        return item.data(_URL_ROLE) or ""

    def _row_url_primary(self, row: int) -> bool:
        item = self.item(row, self._name_column)
        return bool(item is not None and item.data(_URL_PRIMARY_ROLE))

    @staticmethod
    def _open_url(url: str) -> None:
        if url.startswith("https://"):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(url))

    def _clean_name(self, row: int) -> str:
        item = self.item(row, self._name_column)
        if item is None:
            return ""
        val = item.data(_CLEAN_ROLE)
        return val if val else item.text()

    def _selected_rows(self) -> list[int]:
        return sorted({idx.row() for idx in self.selectedIndexes()})

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        rows = self._selected_rows() or [row]
        self._copy_names(rows)

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        """A primary-URL row (missing pack) opens its osu! page in the browser;
        otherwise copy just this one cell's value — its Ctrl+C override if set
        (e.g. the full source names), else the shown text (item 3)."""
        if self._row_url_primary(row):
            self._open_url(self._row_url(row))
            return
        item = self.item(row, col)
        if item is None:
            return
        value = item.data(_COPY_ROLE) or item.text()
        if value:
            QApplication.clipboard().setText(str(value))

    def _copy_names(self, rows: list[int]) -> None:
        """Single-click copy: one line per selected row — the download URL for a
        primary-URL (missing) row, the clean name for everything else. A Ctrl
        multi-select over missing rows therefore collects all their links."""
        out = []
        for r in rows:
            if self._row_url_primary(r) and self._row_url(r):
                out.append(self._row_url(r))
            elif self._clean_name(r):
                out.append(self._clean_name(r))
        if out:
            QApplication.clipboard().setText("\n".join(out))

    def _show_menu(self, pos) -> None:
        rows = self._selected_rows()
        if not rows:
            idx = self.indexAt(pos)
            if idx.isValid():
                rows = [idx.row()]
        if not rows:
            return
        menu = QMenu(self)
        act_names = QAction(self._menu_names, self)
        act_names.triggered.connect(lambda: self._copy_names(rows))
        act_table = QAction(self._menu_table, self)
        act_table.triggered.connect(self._copy_rows_tsv)
        menu.addAction(act_names)
        menu.addAction(act_table)
        if len(rows) == 1 and self._menu_open_location:
            path = self._row_path(rows[0])
            if path:
                menu.addSeparator()
                act_open = QAction(self._menu_open_location, self)
                act_open.triggered.connect(
                    lambda: self.openLocationRequested.emit(path))
                menu.addAction(act_open)
        if len(rows) == 1 and self._menu_open_url:
            url = self._row_url(rows[0])
            if url:
                menu.addSeparator()
                act_url = QAction(self._menu_open_url, self)
                act_url.triggered.connect(lambda: self._open_url(url))
                menu.addAction(act_url)
        menu.exec(self.viewport().mapToGlobal(pos))

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.Copy):
            self._copy_rows_tsv()
            event.accept()
            return
        super().keyPressEvent(event)

    def _copy_rows_tsv(self) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        headers = [self.horizontalHeaderItem(c).text() if self.horizontalHeaderItem(c)
                   else "" for c in range(self.columnCount())]
        lines = ["\t".join(headers)]
        for r in rows:
            cells = []
            for c in range(self.columnCount()):
                it = self.item(r, c)
                if it is None:
                    cells.append("")
                    continue
                override = it.data(_COPY_ROLE)
                cells.append(override if override else it.text())
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))
