"""A QTableWidget with two clipboard behaviours and typed sorting.

* **Single click** on a row copies a clean name (for a red "missing" row this is
  the code/name that *should* be there; for a normal row it's the full archive
  name). Works for single or multi selection — one name per line.
* **Ctrl+C** copies the selected rows as tab-separated values (Excel-pasteable),
  every column included.

``SortItem`` carries a separate sort key so numeric columns (BPM, length, song
count) sort numerically even when displayed as formatted text.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QAbstractItemView, QApplication, QTableWidget, QTableWidgetItem

_CLEAN_ROLE = Qt.UserRole + 11  # per-row clean copy name (single-click copy)
_COPY_ROLE = Qt.UserRole + 12   # per-cell TSV copy override (Ctrl+C)


class SortItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value=None):
        super().__init__(text)
        self._sort = sort_value if sort_value is not None else text

    def __lt__(self, other):
        try:
            return self._sort < other._sort
        except (TypeError, AttributeError):
            return super().__lt__(other)


class CopyTable(QTableWidget):
    def __init__(self, name_column: int = 0, parent=None):
        super().__init__(parent)
        self._name_column = name_column
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.cellClicked.connect(self._on_cell_clicked)

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
        names = [self._clean_name(r) for r in rows if self._clean_name(r)]
        if names:
            QApplication.clipboard().setText("\n".join(names))

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
