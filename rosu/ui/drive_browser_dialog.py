# SPDX-License-Identifier: GPL-3.0-or-later
"""Drive backup browser (v1.8, HANDOFF 4.2): every set the Google Drive backup
holds — from this PC and any other — with a filter, and a way to bring chosen
sets back into the Library.

Read-only until the user confirms; the restore itself is queued as a job by the
Shortcuts tab (download on the Drive lane, import on the disk lane).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from ..workers import Worker
from .copy_table import SortItem

_MIB = 1024 ** 2
_GIB = 1024 ** 3


def _fmt_size(n: int) -> str:
    n = int(n or 0)
    if n >= _GIB:
        return f"{n / _GIB:,.2f} GB"
    return f"{n / _MIB:,.1f} MB"


def filter_entries(entries: list[dict], text: str = "", hide_in_library: bool = True) -> list[dict]:
    """What the table shows. Pure (tested): every word of ``text`` must appear in
    the artist, title or file name; ``hide_in_library`` drops sets the Library
    already has (restoring those would be a no-op)."""
    words = [w for w in (text or "").lower().split() if w]
    out = []
    for e in entries:
        if hide_in_library and e.get("in_library"):
            continue
        hay = f"{e.get('artist', '')} {e.get('title', '')} {e.get('name', '')}".lower()
        if all(w in hay for w in words):
            out.append(e)
    return out


class DriveBrowserDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.plan: list[dict] | None = None
        self._entries: list[dict] = []
        self._shown: list[dict] = []
        self._worker: Worker | None = None
        t = ctx.t
        self.setWindowTitle(t("drv_title"))
        self.setMinimumSize(820, 520)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        intro = QLabel(t("drv_intro"), objectName="status")
        intro.setWordWrap(True)
        root.addWidget(intro)

        row = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(t("drv_filter"))
        self.filter.textChanged.connect(lambda _=None: self._refill())
        row.addWidget(self.filter, 1)
        self.chk_hide = QCheckBox(t("drv_hide_in_library"))
        self.chk_hide.setChecked(True)
        self.chk_hide.toggled.connect(lambda _=False: self._refill())
        row.addWidget(self.chk_hide)
        self.btn_reload = QPushButton("⟳", objectName="iconbtn")
        self.btn_reload.setFixedSize(36, 30)
        self.btn_reload.setToolTip(t("drv_reload"))
        self.btn_reload.clicked.connect(self.load)
        row.addWidget(self.btn_reload)
        root.addLayout(row)

        self.bar = QProgressBar()
        self.bar.setVisible(False)
        root.addWidget(self.bar)
        self.lbl_status = QLabel(objectName="status")
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)

        self.table = QTableWidget(0, 5)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels([
            t("col_artist"), t("col_title"), t("col_size"), t("drv_col_from"), t("drv_col_state")])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._update_button)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.btn_all = QPushButton(t("drv_select_all"), objectName="secondary")
        self.btn_all.clicked.connect(self.table.selectAll)
        bottom.addWidget(self.btn_all)
        bottom.addStretch(1)
        self.btn_close = QPushButton(t("btn_close"), objectName="secondary")
        self.btn_close.clicked.connect(self.reject)
        self.btn_restore = QPushButton(t("drv_restore"))
        self.btn_restore.setEnabled(False)
        self.btn_restore.clicked.connect(self._confirm)
        bottom.addWidget(self.btn_close)
        bottom.addWidget(self.btn_restore)
        root.addLayout(bottom)

        self.load()

    # -- loading -----------------------------------------------------------------
    def load(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.btn_reload.setEnabled(False)
        self.bar.setRange(0, 0)
        self.bar.setVisible(True)
        self.lbl_status.setText(self.ctx.t("drv_loading"))
        w = Worker(self.ctx.services.drive_catalog)
        self._worker = w
        w.progressed.connect(self._on_progress)
        w.succeeded.connect(self._on_loaded)
        w.failed.connect(self._on_failed)
        w.finished.connect(self._clear_worker)
        w.start()

    def _on_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("total"):
            self.bar.setRange(0, msg["total"])
            self.bar.setValue(msg.get("done") or 0)

    def _on_loaded(self, res: dict) -> None:
        self.bar.setVisible(False)
        t = self.ctx.t
        if res.get("error"):
            self._entries = []
            self.lbl_status.setText(t("drv_err_not_connected") if res["error"] == "not_connected"
                                    else t("drv_err", detail=res.get("detail", "")))
        else:
            self._entries = res.get("entries") or []
            in_lib = sum(1 for e in self._entries if e.get("in_library"))
            text = t("drv_summary", n=len(self._entries), devices=res.get("devices", 0),
                     in_lib=in_lib)
            if res.get("missing"):
                text += " " + t("drv_missing", n=res["missing"])
            if res.get("orphans"):
                text += " " + t("drv_orphans", n=len(res["orphans"]))
            self.lbl_status.setText(text)
        self._refill()

    def _on_failed(self, msg: str) -> None:
        self.bar.setVisible(False)
        self.lbl_status.setText(msg)

    def _clear_worker(self) -> None:
        self._worker = None
        self.btn_reload.setEnabled(True)

    # -- table -------------------------------------------------------------------
    def _refill(self) -> None:
        t = self.ctx.t
        self._shown = filter_entries(self._entries, self.filter.text(), self.chk_hide.isChecked())
        self.table.setSortingEnabled(False)
        self.table.clearSelection()
        self.table.setRowCount(len(self._shown))
        for r, e in enumerate(self._shown):
            artist = QTableWidgetItem(str(e.get("artist") or "—"))
            title = QTableWidgetItem(str(e.get("title") or e.get("name") or ""))
            title.setToolTip(str(e.get("name") or ""))
            title.setData(Qt.UserRole, r)          # survives sorting: index into _shown
            size = SortItem(_fmt_size(e.get("size") or 0), e.get("size") or 0)
            size.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            frm = QTableWidgetItem(t("drv_from_here") if e.get("this_device") or not e.get("device")
                                   else t("drv_from_other"))
            if not e.get("on_drive"):
                state = t("drv_state_missing")
            elif e.get("in_library"):
                state = t("drv_state_in_library")
            else:
                state = t("drv_state_restorable")
            st = QTableWidgetItem(state)
            for c, item in enumerate((artist, title, size, frm, st)):
                self.table.setItem(r, c, item)
        self.table.setSortingEnabled(True)
        self._update_button()

    def _selected(self) -> list[dict]:
        rows = {i.row() for i in self.table.selectedItems()}
        out = []
        for row in sorted(rows):
            item = self.table.item(row, 1)
            idx = item.data(Qt.UserRole) if item is not None else None
            if isinstance(idx, int) and 0 <= idx < len(self._shown):
                e = self._shown[idx]
                if e.get("on_drive"):
                    out.append(e)
        return out

    def _update_button(self) -> None:
        n = len(self._selected())
        self.btn_restore.setEnabled(n > 0)
        self.btn_restore.setText(self.ctx.t("drv_restore_n", n=n) if n else self.ctx.t("drv_restore"))

    def _confirm(self) -> None:
        chosen = self._selected()
        if not chosen:
            return
        t = self.ctx.t
        size = sum(int(e.get("size") or 0) for e in chosen)
        chunks = len({e.get("chunk") for e in chosen})
        if QMessageBox.question(
                self, t("drv_title"),
                t("drv_confirm", n=len(chosen), size=_fmt_size(size), archives=chunks),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.plan = chosen
        self.accept()

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(5000)
        super().reject()
