# SPDX-License-Identifier: GPL-3.0-or-later
"""Remove-from-osu! dialog (v1.8, HANDOFF 4.1): pick a client, which sets, and
whether to save them to the Library first; see exactly what would go; confirm
through a countdown.

Like the Prune dialog it only *plans*: on confirmation it exposes :attr:`plan`
and the Shortcuts tab queues the work as a job.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QProgressBar, QPushButton, QRadioButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from .. import client_remove
from ..workers import Worker
from .copy_table import SortItem
from .countdown_dialog import CountdownConfirmDialog
from .links import plain_tip

_MIB = 1024 ** 2
_GIB = 1024 ** 3


def _fmt_size(n: int) -> str:
    n = int(n or 0)
    if n >= _GIB:
        return f"{n / _GIB:,.2f} GB"
    return f"{n / _MIB:,.1f} MB"


class RemoveDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.plan: dict | None = None
        self._all_sets: list[dict] = []
        self._shown: list[dict] = []
        self._worker: Worker | None = None
        self._src_worker: Worker | None = None
        self._closed = False
        self._scan_seq = 0
        self._rescan_pending = False
        self._sources: dict = {}
        t = ctx.t

        self.setWindowTitle(t("rm_title"))
        self.setMinimumSize(680, 420)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        intro = QLabel(t("rm_intro"), objectName="status")
        intro.setWordWrap(True)
        root.addWidget(intro)

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel(t("rm_source")))
        self.cbo_source = QComboBox()
        for key in ("stable", "lazer"):
            self.cbo_source.addItem(t(f"prune_source_{key}"), key)
        self.cbo_source.setEnabled(False)   # until the sources are known
        src_row.addWidget(self.cbo_source, 1)
        root.addLayout(src_row)

        self.lbl_source_note = QLabel(objectName="status")
        self.lbl_source_note.setWordWrap(True)
        root.addWidget(self.lbl_source_note)

        # -- how: save first (default) or remove only --------------------------
        self.rb_save = QRadioButton(t("rm_mode_save"))
        self.rb_save.setToolTip(t("rm_mode_save_tip"))
        self.rb_only = QRadioButton(t("rm_mode_only"))
        self.rb_only.setToolTip(t("rm_mode_only_tip"))
        self.rb_save.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.rb_save)
        grp.addButton(self.rb_only)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.rb_save)
        mode_row.addWidget(self.rb_only)
        mode_row.addStretch(1)
        root.addLayout(mode_row)

        # -- which / order / limit ---------------------------------------------
        pick_row = QHBoxLayout()
        pick_row.addWidget(QLabel(t("rm_which")))
        self.cbo_which = QComboBox()
        for f in client_remove.FILTERS:
            self.cbo_which.addItem(t(f"rm_which_{f}"), f)
        pick_row.addWidget(self.cbo_which)
        pick_row.addSpacing(12)
        pick_row.addWidget(QLabel(t("prune_order")))
        self.cbo_sort = QComboBox()
        for srt in client_remove.SORTS:
            self.cbo_sort.addItem(t(f"rm_sort_{srt}"), srt)
        pick_row.addWidget(self.cbo_sort)
        pick_row.addSpacing(12)
        pick_row.addWidget(QLabel(t("prune_limit")))
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(0, 100000)
        self.spin_limit.setSpecialValueText(t("prune_limit_all"))
        pick_row.addWidget(self.spin_limit)
        pick_row.addStretch(1)
        self.btn_scan = QPushButton(t("prune_scan"), objectName="secondary")
        pick_row.addWidget(self.btn_scan)
        root.addLayout(pick_row)

        self.bar = QProgressBar()
        self.bar.setVisible(False)
        root.addWidget(self.bar)
        self.lbl_status = QLabel(objectName="status")
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)
        self.lbl_total = QLabel(objectName="h2")
        self.lbl_total.setWordWrap(True)
        root.addWidget(self.lbl_total)
        self.lbl_warn = QLabel(objectName="status")
        self.lbl_warn.setWordWrap(True)
        root.addWidget(self.lbl_warn)

        self.chk_list = QCheckBox(t("prune_show_list"))
        self.chk_list.toggled.connect(self._toggle_list)
        root.addWidget(self.chk_list)
        self.table = QTableWidget(0, 3)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels([t("col_name"), t("col_size"), t("rm_col_in_library")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setVisible(False)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_close = QPushButton(t("btn_close"), objectName="secondary")
        self.btn_close.clicked.connect(self.reject)
        self.btn_run = QPushButton(t("rm_run"))
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._confirm)
        bottom.addWidget(self.btn_close)
        bottom.addWidget(self.btn_run)
        root.addLayout(bottom)

        self.cbo_source.currentIndexChanged.connect(self._on_source_changed)
        for w in (self.cbo_which, self.cbo_sort):
            w.currentIndexChanged.connect(lambda _=0: self._refill())
        self.spin_limit.valueChanged.connect(lambda _=0: self._refill())
        self.rb_save.toggled.connect(lambda _=False: self._refill())
        self.btn_scan.clicked.connect(self.scan)
        self.btn_scan.setEnabled(False)
        self._load_sources()

    # -- source ----------------------------------------------------------------
    def _load_sources(self) -> None:
        """Which clients can be removed from — off the UI thread: asking the lazer
        helper what it supports starts a process."""
        self.lbl_status.setText(self.ctx.t("rm_checking"))
        services = self.ctx.services
        w = Worker(lambda progress=None: services.removal_sources())
        self._src_worker = w
        w.succeeded.connect(self._apply_sources)
        w.failed.connect(self._on_sources_failed)
        w.start()

    def _on_sources_failed(self, msg: str) -> None:
        self._apply_sources([])
        self.lbl_status.setText(msg)

    def _apply_sources(self, sources) -> None:
        if self._closed:
            return
        t = self.ctx.t
        self._sources = {s["key"]: s for s in (sources or [])}
        for i in range(self.cbo_source.count()):
            info = self._sources.get(self.cbo_source.itemData(i)) or {"reason": "disabled"}
            item = self.cbo_source.model().item(i)
            item.setEnabled(bool(info.get("available")))
            self.cbo_source.setItemData(
                i, None if info.get("available")
                else t(f"rm_why_{info.get('reason') or 'disabled'}"), Qt.ToolTipRole)
        self.cbo_source.setEnabled(True)
        self.lbl_status.setText("")
        self._select_first_available()
    def _note_for(self, key) -> str:
        info = self._sources.get(key) or {}
        if not info.get("available"):
            return self.ctx.t(f"rm_why_{info.get('reason') or 'disabled'}")
        return self.ctx.t(f"rm_how_{key}")

    def _select_first_available(self) -> None:
        for i in range(self.cbo_source.count()):
            if (self._sources.get(self.cbo_source.itemData(i)) or {}).get("available"):
                self.cbo_source.blockSignals(True)
                self.cbo_source.setCurrentIndex(i)
                self.cbo_source.blockSignals(False)
                self._on_source_changed()
                return
        self.lbl_source_note.setText(self._note_for(self.cbo_source.currentData()))
        self.lbl_status.setText(self.ctx.t("rm_no_source"))
        self.btn_scan.setEnabled(False)

    def _on_source_changed(self, _i=0) -> None:
        key = self.cbo_source.currentData()
        self.lbl_source_note.setText(self._note_for(key))
        # osu!lazer purges removed sets on its next start: always save first.
        lazer = key == "lazer"
        if lazer:
            self.rb_save.setChecked(True)
        self.rb_only.setEnabled(not lazer)
        self.rb_only.setToolTip(self.ctx.t("rm_mode_only_lazer" if lazer else "rm_mode_only_tip"))
        self._all_sets = []
        self._refill()
        if (self._sources.get(key) or {}).get("available"):
            self.btn_scan.setEnabled(True)
            self.scan()

    # -- scan (off the UI thread) ------------------------------------------------
    def scan(self) -> None:
        key = self.cbo_source.currentData()
        if not (self._sources.get(key) or {}).get("available"):
            return
        self._scan_seq += 1
        if self._worker is not None and self._worker.isRunning():
            self._rescan_pending = True
            self.ctx.services.cancel_removal_scan()
            return
        self._all_sets = []
        self._refill()
        self.btn_scan.setEnabled(False)
        self.bar.setRange(0, 0)
        self.bar.setVisible(True)
        self.lbl_status.setText(self.ctx.t("prune_scanning"))
        seq = self._scan_seq
        w = Worker(self.ctx.services.removal_scan, key)
        self._worker = w
        w.progressed.connect(self._on_progress)
        w.succeeded.connect(lambda res, s=seq: self._on_scanned(res, s))
        w.failed.connect(self._on_failed)
        w.finished.connect(self._clear_worker)
        w.start()

    def _on_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("kind") == "remove_scan":
            total = msg.get("total") or 0
            if total:
                self.bar.setRange(0, total)
                self.bar.setValue(msg.get("done") or 0)
            self.lbl_status.setText(self.ctx.t(
                "prune_scanning_n", done=msg.get("done") or 0, total=total))

    def _on_scanned(self, res: dict, seq: int) -> None:
        if seq != self._scan_seq:
            return
        self.bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        if res.get("error"):
            self.lbl_status.setText(self.ctx.t(f"rm_err_{res['error']}"))
            self._all_sets = []
        else:
            self._all_sets = res.get("sets") or []
            backed = sum(1 for s in self._all_sets if s.get("backed_up"))
            self.lbl_status.setText(self.ctx.t(
                "rm_scanned", n=len(self._all_sets), backed=backed,
                size=_fmt_size(sum(s.get("size") or 0 for s in self._all_sets))))
        self._refill()

    def _on_failed(self, msg: str) -> None:
        self.bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.lbl_status.setText(msg)

    def _clear_worker(self) -> None:
        self._worker = None
        if self._rescan_pending:
            self._rescan_pending = False
            self._scan_seq -= 1
            self.scan()

    # -- table -------------------------------------------------------------------
    def _toggle_list(self, on: bool) -> None:
        self.table.setVisible(bool(on))
        self.adjustSize()

    def _refill(self) -> None:
        t = self.ctx.t
        self._shown = client_remove.select(
            self._all_sets, which=self.cbo_which.currentData() or "all",
            sort=self.cbo_sort.currentData() or "largest",
            limit=self.spin_limit.value() or None)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._shown))
        for r, s in enumerate(self._shown):
            name = QTableWidgetItem(str(s["name"]))
            name.setToolTip(plain_tip(s["name"]))
            size = SortItem(_fmt_size(s.get("size") or 0), s.get("size") or 0)
            size.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            backed = QTableWidgetItem("✓" if s.get("backed_up") else "—")
            backed.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 0, name)
            self.table.setItem(r, 1, size)
            self.table.setItem(r, 2, backed)
        self.table.setSortingEnabled(True)
        total = sum(s.get("size") or 0 for s in self._shown)
        self.lbl_total.setText(t("rm_total", n=len(self._shown), size=_fmt_size(total)))
        unbacked = sum(1 for s in self._shown if not s.get("backed_up"))
        if not self._shown:
            self.lbl_warn.setText("")
        elif self.rb_save.isChecked():
            self.lbl_warn.setText(t("rm_warn_save", n=unbacked) if unbacked else "")
        else:
            self.lbl_warn.setText(t("rm_warn_only", n=unbacked) if unbacked else "")
        self.btn_run.setEnabled(bool(self._shown))
        self.btn_run.setText(t("rm_run") if not self._shown else t("rm_run_n", n=len(self._shown)))

    # -- confirm -----------------------------------------------------------------
    def _confirm(self) -> None:
        if not self._shown:
            return
        t = self.ctx.t
        source = self.cbo_source.currentData()
        save_first = self.rb_save.isChecked()
        unbacked = sum(1 for s in self._shown if not s.get("backed_up"))
        body = t("rm_confirm_body", n=len(self._shown),
                 source=t(f"prune_source_{source}"),
                 mode=t("rm_mode_save" if save_first else "rm_mode_only"),
                 recovery=t(f"rm_recovery_{source}"))
        if not save_first and unbacked:
            body += "\n\n" + t("rm_warn_only", n=unbacked)
        dlg = CountdownConfirmDialog(self, t("rm_title"), body, t("rm_run"), t("btn_cancel"))
        if dlg.exec() != QDialog.Accepted:
            return
        self.plan = {"source": source, "save_first": save_first,
                     "keys": [s["key"] for s in self._shown]}
        self.accept()

    def _stop_scan(self) -> None:
        # No waiting: the scan stops at its next item and the Worker keeps itself
        # alive until then (see workers._live).
        self._closed = True
        if self._worker is not None and self._worker.isRunning():
            self.ctx.services.cancel_removal_scan()

    def reject(self) -> None:
        self._stop_scan()
        super().reject()

    def accept(self) -> None:
        self._stop_scan()
        super().accept()
