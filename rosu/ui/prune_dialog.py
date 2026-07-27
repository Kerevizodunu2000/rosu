# SPDX-License-Identifier: GPL-3.0-or-later
"""Space-saving (Prune) dialog — pick a source, a mode, how many and in what
order, see exactly what would go, then confirm.

This replaces a single button that silently used whatever ``prune_mode`` happened
to be set in Settings, ran over the whole Library, and showed only a count and a
total once it had already decided. Every choice is now made at the point of use
and previewed per set before anything is touched.

The dialog only *plans*: on confirmation it exposes :attr:`plan` and the caller
queues the destructive work as a job, so it runs off the UI thread with the
queue's normal cancel and progress.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from .. import prune as prune_mod
from ..workers import Worker
from .copy_table import SortItem
from .countdown_dialog import CountdownConfirmDialog

_MIB = 1024 ** 2
_GIB = 1024 ** 3

# Source order in the picker. lazer is listed even though it cannot be pruned —
# hiding it would leave the user wondering whether Rosu simply forgot about it.
_SOURCES = ("library", "stable", "lazer")


def _fmt_size(n: int) -> str:
    n = int(n or 0)
    if n >= _GIB:
        return f"{n / _GIB:,.2f} GB"
    return f"{n / _MIB:,.1f} MB"


class PruneDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.plan: dict | None = None      # set only on confirmed accept()
        self._all_sets: list[dict] = []    # last scan, unsorted/unlimited
        self._shown: list[dict] = []       # what the table currently lists
        self._worker: Worker | None = None
        self._scan_seq = 0                 # drop results from a superseded scan
        self._rescan_pending = False       # a newer scan is waiting for this one
        self._sources = {s["key"]: s for s in ctx.services.prune_sources()}
        t = ctx.t

        self.setWindowTitle(t("prune_title"))
        # Compact by default now the per-set list starts hidden.
        self.setMinimumSize(680, 400)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        intro = QLabel(objectName="status")
        intro.setWordWrap(True)
        intro.setText(t("prune_intro"))
        root.addWidget(intro)

        # -- source ----------------------------------------------------------
        src_row = QHBoxLayout()
        src_row.addWidget(QLabel(t("prune_source")))
        self.cbo_source = QComboBox()
        for key in _SOURCES:
            info = self._sources.get(key) or {"available": False, "sets": 0}
            label = t(f"prune_source_{key}")
            if info.get("available"):
                label += f"  ({t('prune_n_sets', n=info.get('sets', 0))})"
            self.cbo_source.addItem(label, key)
            idx = self.cbo_source.count() - 1
            reason = info.get("reason") or "no_stable"
            if not info.get("available"):
                self.cbo_source.setItemData(idx, t(f"prune_why_{reason}"),
                                            Qt.ToolTipRole)
                # lazer stays SELECTABLE even though it cannot be pruned here:
                # picking it is how the user gets sent to the steps that DO prune
                # it. A source with genuinely nothing behind it (stable not
                # installed) is disabled, because there is nowhere to send them.
                if reason != "lazer_realm":
                    self.cbo_source.model().item(idx).setEnabled(False)
        src_row.addWidget(self.cbo_source, 1)
        root.addLayout(src_row)

        self.lbl_source_note = QLabel(objectName="status")
        self.lbl_source_note.setWordWrap(True)
        root.addWidget(self.lbl_source_note)

        # Shown only for lazer: the way to actually prune it.
        self.btn_lazer_steps = QPushButton(t("prune_open_lazer_steps"))
        self.btn_lazer_steps.setVisible(False)
        self.btn_lazer_steps.clicked.connect(self._open_lazer_steps)
        root.addWidget(self.btn_lazer_steps)

        # -- mode ------------------------------------------------------------
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(t("prune_mode")))
        self.cbo_mode = QComboBox()
        for mode in prune_mod.MODES:
            self.cbo_mode.addItem(t(f"prune_mode_{mode}"), mode)
            self.cbo_mode.setItemData(self.cbo_mode.count() - 1,
                                      t(f"prune_mode_{mode}_tip"), Qt.ToolTipRole)
        start_mode = getattr(ctx.cfg, "prune_mode", "video_only")
        i = self.cbo_mode.findData(start_mode)
        self.cbo_mode.setCurrentIndex(i if i >= 0 else 0)
        mode_row.addWidget(self.cbo_mode, 1)
        root.addLayout(mode_row)

        self.lbl_mode_note = QLabel(objectName="status")
        self.lbl_mode_note.setWordWrap(True)
        root.addWidget(self.lbl_mode_note)

        # -- order + limit ---------------------------------------------------
        pick_row = QHBoxLayout()
        pick_row.addWidget(QLabel(t("prune_order")))
        self.cbo_sort = QComboBox()
        for s in prune_mod.SORTS:
            self.cbo_sort.addItem(t(f"prune_sort_{s}"), s)
        pick_row.addWidget(self.cbo_sort)
        pick_row.addSpacing(16)
        pick_row.addWidget(QLabel(t("prune_limit")))
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(0, 100000)
        self.spin_limit.setValue(0)
        self.spin_limit.setSpecialValueText(t("prune_limit_all"))  # 0 = everything
        self.spin_limit.setToolTip(t("prune_limit_tip"))
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

        # The per-set list is HIDDEN by default. Scrolling 1922 rows is not how
        # anyone decides whether to prune — the totals line above is. It stays one
        # click away, because "these exact sets will change" is still the thing a
        # destructive action has to be able to show.
        self.chk_list = QCheckBox(t("prune_show_list"))
        self.chk_list.setToolTip(t("prune_show_list_tip"))
        self.chk_list.toggled.connect(self._toggle_list)
        root.addWidget(self.chk_list)

        self.table = QTableWidget(0, 3)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setVisible(False)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_close = QPushButton(t("btn_close"), objectName="secondary")
        self.btn_close.clicked.connect(self.reject)
        self.btn_prune = QPushButton(t("prune_run"))
        self.btn_prune.setEnabled(False)
        self.btn_prune.clicked.connect(self._confirm)
        bottom.addWidget(self.btn_close)
        bottom.addWidget(self.btn_prune)
        root.addLayout(bottom)

        self.retranslate()
        self.cbo_source.currentIndexChanged.connect(self._on_source_changed)
        self.cbo_mode.currentIndexChanged.connect(lambda _=0: self.scan())
        self.cbo_sort.currentIndexChanged.connect(lambda _=0: self._refill())
        self.spin_limit.valueChanged.connect(lambda _=0: self._refill())
        self.btn_scan.clicked.connect(self.scan)

        self._select_first_available()

    # -- i18n -----------------------------------------------------------------
    def retranslate(self) -> None:
        t = self.ctx.t
        self.table.setHorizontalHeaderLabels(
            [t("col_name"), t("col_size"), t("prune_col_freed")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._update_notes()

    def _update_notes(self) -> None:
        t = self.ctx.t
        key = self.cbo_source.currentData()
        info = self._sources.get(key) or {}
        reason = info.get("reason") or "no_stable"
        self.lbl_source_note.setText(
            "" if info.get("available") else t(f"prune_why_{reason}"))
        is_lazer = (not info.get("available")) and reason == "lazer_realm"
        if hasattr(self, "btn_lazer_steps"):
            self.btn_lazer_steps.setVisible(is_lazer)
        self.lbl_mode_note.setText(t(f"prune_mode_{self.cbo_mode.currentData()}_tip"))

    def _open_lazer_steps(self) -> None:
        """Picking osu!lazer sends the user to the steps that really prune it —
        refusing and stopping there would leave them with no way forward."""
        from .lazer_slim_dialog import LazerSlimDialog
        self._stop_scan()
        LazerSlimDialog(self.ctx, self.parent()).exec()
        self.reject()

    def _select_first_available(self) -> None:
        for i in range(self.cbo_source.count()):
            key = self.cbo_source.itemData(i)
            if (self._sources.get(key) or {}).get("available"):
                self.cbo_source.setCurrentIndex(i)
                self.scan()
                return
        self._update_notes()
        self.lbl_status.setText(self.ctx.t("prune_no_source"))

    # -- scanning (off the UI thread) ----------------------------------------
    def _on_source_changed(self, _i=0) -> None:
        self._update_notes()
        key = self.cbo_source.currentData()
        if (self._sources.get(key) or {}).get("available"):
            self.scan()
        else:
            self._all_sets = []
            self._refill()

    def scan(self) -> None:
        key = self.cbo_source.currentData()
        if not (self._sources.get(key) or {}).get("available"):
            return
        self._scan_seq += 1
        if self._worker is not None and self._worker.isRunning():
            # Changing the source or mode mid-scan must NOT silently keep showing
            # the previous source's results. Stop the running scan and re-run as
            # soon as its thread lets go; the sequence number drops its result.
            self._rescan_pending = True
            self.ctx.services.cancel_prune_scan()
            return
        self._update_notes()
        self._all_sets = []
        self._refill()
        self.btn_scan.setEnabled(False)
        self.bar.setRange(0, 0)
        self.bar.setVisible(True)
        self.lbl_status.setText(self.ctx.t("prune_scanning"))
        seq = self._scan_seq
        w = Worker(self.ctx.services.prune_scan, key, self.cbo_mode.currentData())
        self._worker = w
        w.progressed.connect(self._on_progress)
        w.succeeded.connect(lambda res, s=seq: self._on_scanned(res, s))
        w.failed.connect(self._on_failed)
        w.finished.connect(self._clear_worker)
        w.start()

    def _on_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("kind") == "prune_scan":
            total = msg.get("total") or 0
            if total:
                self.bar.setRange(0, total)
                self.bar.setValue(msg.get("done") or 0)
            self.lbl_status.setText(self.ctx.t(
                "prune_scanning_n", done=msg.get("done") or 0, total=total))

    def _on_scanned(self, res: dict, seq: int | None = None) -> None:
        if seq is not None and seq != self._scan_seq:
            return          # a newer scan superseded this one — drop its result
        self.bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self._all_sets = res.get("sets") or []
        self.lbl_status.setText(self.ctx.t(
            "prune_scanned", scanned=res.get("scanned", 0),
            n=len(self._all_sets), size=_fmt_size(res.get("total_bytes", 0))))
        self._refill()

    def _on_failed(self, msg: str) -> None:
        self.bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.lbl_status.setText(msg)

    def _clear_worker(self) -> None:
        self._worker = None
        if self._rescan_pending:
            self._rescan_pending = False
            self._scan_seq -= 1     # scan() bumps it again for the real run
            self.scan()

    # -- table ----------------------------------------------------------------
    def _toggle_list(self, on: bool) -> None:
        self.table.setVisible(bool(on))
        self.adjustSize()

    def _refill(self) -> None:
        """Re-apply order + limit to the last scan. Pure and instant — changing
        the order must not re-read the disk."""
        t = self.ctx.t
        limit = self.spin_limit.value() or None
        self._shown = prune_mod.select_targets(
            self._all_sets, sort=self.cbo_sort.currentData() or "largest",
            limit=limit)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._shown))
        for r, s in enumerate(self._shown):
            name = QTableWidgetItem(str(s["name"]))
            name.setToolTip(str(s["name"]))
            size = SortItem(_fmt_size(s["size"]), s["size"])
            freed = SortItem(_fmt_size(s["freed"]), s["freed"])
            for item in (size, freed):
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 0, name)
            self.table.setItem(r, 1, size)
            self.table.setItem(r, 2, freed)
        self.table.setSortingEnabled(True)
        total_freed = sum(s["freed"] for s in self._shown)
        self.lbl_total.setText(t("prune_total", n=len(self._shown),
                                 size=_fmt_size(total_freed)))
        self.btn_prune.setEnabled(bool(self._shown))
        self.btn_prune.setText(t("prune_run") if not self._shown
                               else t("prune_run_n", n=len(self._shown)))

    # -- confirm --------------------------------------------------------------
    def _confirm(self) -> None:
        if not self._shown:
            return
        t = self.ctx.t
        source = self.cbo_source.currentData()
        mode = self.cbo_mode.currentData()
        total_freed = sum(s["freed"] for s in self._shown)
        body = t("prune_confirm_body", n=len(self._shown),
                 size=_fmt_size(total_freed),
                 source=t(f"prune_source_{source}"),
                 mode=t(f"prune_mode_{mode}"),
                 recovery=t("prune_recovery_osz" if source == "library"
                            else "prune_recovery_folder"))
        dlg = CountdownConfirmDialog(self, t("prune_title"), body,
                                     t("prune_run"), t("btn_cancel"))
        if dlg.exec() != QDialog.Accepted:
            return
        self.plan = {"source": source, "mode": mode,
                     "keys": [s["key"] for s in self._shown],
                     "freed_estimate": total_freed}
        self.accept()

    def _stop_scan(self) -> None:
        """Never leave a scan thread running against a closing dialog. Trips only
        the prune token, so an import or Drive upload alongside it is untouched."""
        if self._worker is not None and self._worker.isRunning():
            self.ctx.services.cancel_prune_scan()
            self._worker.wait(5000)

    def reject(self) -> None:
        self._stop_scan()
        super().reject()

    def accept(self) -> None:
        self._stop_scan()
        super().accept()
