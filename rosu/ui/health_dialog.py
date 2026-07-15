# SPDX-License-Identifier: GPL-3.0-or-later
"""Library Health dialog (v1.1): read-only integrity, disk usage & scrub.

Shows where the Library's disk space goes (total + biggest sets) and reconciles
the DB "memory" with what's actually on disk (orphans / dead links). A separate
**Verify (SHA-256)** action re-hashes each backed-up set and flags corruption or
drift. Nothing here modifies or deletes a beatmap.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from ..workers import Worker


def _fmt_size(n: int) -> str:
    n = int(n or 0)
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:,.2f} GB"
    return f"{n / 1024 ** 2:,.1f} MB"


class HealthDialog(QDialog):
    def __init__(self, ctx, report: dict, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._report = report
        self._worker: Worker | None = None
        t = ctx.t

        self.setWindowTitle(t("health_title"))
        self.setMinimumSize(560, 520)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        self.usage_label = QLabel(objectName="h1")
        self.usage_label.setWordWrap(True)
        root.addWidget(self.usage_label)

        self.scrub_label = QLabel()
        self.scrub_label.setWordWrap(True)
        root.addWidget(self.scrub_label)

        self.biggest_label = QLabel(objectName="status")
        root.addWidget(self.biggest_label)
        self.table = QTableWidget(0, 2)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

        verify_row = QHBoxLayout()
        self.btn_verify = QPushButton()
        self.btn_verify.clicked.connect(self._on_verify)
        self.btn_cancel = QPushButton(objectName="secondary")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._on_cancel)
        verify_row.addWidget(self.btn_verify)
        verify_row.addWidget(self.btn_cancel)
        verify_row.addStretch(1)
        root.addLayout(verify_row)

        self.verify_status = QLabel(objectName="status")
        self.verify_status.setWordWrap(True)
        root.addWidget(self.verify_status)
        self.busy = QProgressBar()
        self.busy.setVisible(False)
        root.addWidget(self.busy)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

        self.retranslate()
        self._populate()

    # -- i18n ----------------------------------------------------------------
    def retranslate(self) -> None:
        t = self.ctx.t
        self.setWindowTitle(t("health_title"))
        self.btn_verify.setText(t("btn_verify"))
        self.btn_verify.setToolTip(t("tip_verify"))
        self.btn_cancel.setText(t("btn_cancel"))
        self.biggest_label.setText(t("health_biggest"))
        self.table.setHorizontalHeaderLabels([t("col_name"), t("col_size")])

    # -- render the report ---------------------------------------------------
    def _populate(self) -> None:
        t = self.ctx.t
        usage = self._report.get("usage", {})
        scrub = self._report.get("scrub", {})
        biggest = self._report.get("biggest", [])

        self.usage_label.setText(t("health_usage", files=usage.get("files", 0),
                                   size=_fmt_size(usage.get("total_bytes", 0))))
        self.scrub_label.setText(t(
            "health_scrub", present=scrub.get("present", 0),
            orphans=len(scrub.get("orphans", [])),
            dead=len(scrub.get("dead_links", [])),
            memory=scrub.get("memory", 0)))

        self.table.setRowCount(len(biggest))
        for r, s in enumerate(biggest):
            name = s.get("display_name") or s.get("filename") or "?"
            name_item = QTableWidgetItem(str(name))
            name_item.setToolTip(str(s.get("filename") or name))
            size_item = QTableWidgetItem(_fmt_size(s.get("size_bytes", 0)))
            size_item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.table.setItem(r, 0, name_item)
            self.table.setItem(r, 1, size_item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

    # -- SHA-256 verify (off the UI thread) ----------------------------------
    def _on_verify(self) -> None:
        self.btn_verify.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.busy.setRange(0, 0)
        self.busy.setVisible(True)
        self.verify_status.setText(self.ctx.t("health_verifying"))
        self._worker = Worker(self.ctx.services.verify_library)
        self._worker.progressed.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_verified)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()

    def _on_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("kind") == "verify":
            total = msg.get("total") or 0
            done = msg.get("done") or 0
            if total:
                self.busy.setRange(0, total)
                self.busy.setValue(done)
            self.verify_status.setText(self.ctx.t(
                "health_verify_progress", done=done, total=total))

    def _on_verified(self, res: dict) -> None:
        t = self.ctx.t
        self.busy.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.btn_verify.setEnabled(True)
        if res.get("cancelled"):
            self.verify_status.setText(t("health_verify_cancelled",
                                         checked=res.get("checked", 0)))
            return
        self.verify_status.setText(t(
            "health_verify_done", checked=res.get("checked", 0),
            ok=res.get("ok", 0), mismatch=res.get("mismatch", 0),
            unhashed=res.get("unhashed", 0), missing=res.get("missing", 0)))

    def _on_failed(self, msg: str) -> None:
        self.busy.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.btn_verify.setEnabled(True)
        self.verify_status.setText(msg)

    def _on_cancel(self) -> None:
        self.ctx.services.request_cancel()
        self.btn_cancel.setEnabled(False)

    def _clear_worker(self) -> None:
        self._worker = None

    def reject(self) -> None:
        # Don't leave a verify thread running against a closing dialog.
        if self._worker is not None and self._worker.isRunning():
            self.ctx.services.request_cancel()
            self._worker.wait(3000)
        super().reject()
