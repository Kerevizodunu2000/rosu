# SPDX-License-Identifier: GPL-3.0-or-later
"""Dashboard tab: scan count, the four action buttons, and progress feedback."""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .. import extractor, osu_import
from ..i18n import human_duration
from ..workers import Worker
from .progress_panel import ProgressPanel


def _fmt_size(n: int) -> str:
    return f"{n / (1024 * 1024):,.1f} MB"


class DashboardTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.ctx = main_window.ctx
        self.services = self.ctx.services
        self._threads: list[Worker] = []
        self._scan: list[tuple[Path, object]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        self.title = QLabel(objectName="h1")
        root.addWidget(self.title)
        self.count_label = QLabel(objectName="h1")
        root.addWidget(self.count_label)
        self.banner = QLabel(objectName="banner")
        self.banner.setWordWrap(True)
        self.banner.linkActivated.connect(lambda _: self.mw.show_missing_packs())
        root.addWidget(self.banner)

        btn_row = QHBoxLayout()
        self.btn_extract = QPushButton()
        self.btn_copy = QPushButton()
        self.btn_import = QPushButton()
        self.btn_refresh = QPushButton()
        for b in (self.btn_copy, self.btn_import, self.btn_refresh):
            b.setObjectName("secondary")
        for b in (self.btn_extract, self.btn_copy, self.btn_import, self.btn_refresh):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        self.btn_rescan = QPushButton(objectName="secondary")
        btn_row.addWidget(self.btn_rescan)
        root.addLayout(btn_row)

        self.btn_extract.clicked.connect(self.on_extract)
        self.btn_copy.clicked.connect(self.on_copy)
        self.btn_import.clicked.connect(self.on_import)
        self.btn_refresh.clicked.connect(self.on_refresh)
        self.btn_rescan.clicked.connect(self.refresh_scan)

        self.table = QTableWidget(0, 5)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

        # progress feedback
        self.progress_panel = ProgressPanel()
        root.addWidget(self.progress_panel)
        self.busy_bar = QProgressBar()
        self.busy_bar.setVisible(False)
        root.addWidget(self.busy_bar)

        bottom = QHBoxLayout()
        self.status = QLabel(objectName="status")
        self.btn_cancel = QPushButton(objectName="secondary")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._on_cancel)
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.btn_cancel)
        root.addLayout(bottom)

        self.refresh_scan()

    # -- i18n ----------------------------------------------------------------
    def retranslate(self) -> None:
        t = self.ctx.t
        self.title.setText(t("app_title"))
        self.btn_extract.setText(t("btn_extract"))
        self.btn_copy.setText(t("btn_copy_library"))
        self.btn_import.setText(t("btn_import_osu"))
        self.btn_refresh.setText(t("btn_refresh"))
        self.btn_rescan.setText(t("btn_rescan"))
        self.btn_cancel.setText(t("btn_cancel"))
        self.table.setHorizontalHeaderLabels([
            t("col_code"), t("col_series"), t("col_title"), t("col_size"), t("col_state")])
        self._update_count()
        self._update_banner()
        if not self.status.text():
            self.status.setText(t("ready"))

    def on_shown(self) -> None:
        self.refresh_scan()

    # -- scanning ------------------------------------------------------------
    def refresh_scan(self) -> None:
        self._scan = self.services.scan()
        self._populate_table()
        self._update_count()
        self._update_banner()

    def _populate_table(self) -> None:
        t = self.ctx.t
        self.table.setRowCount(len(self._scan))
        for r, (path, parsed) in enumerate(self._scan):
            known = self.ctx.db.get_pack_by_code(parsed.code) is not None
            state = t("state_known") if known else t("state_new")
            values = [parsed.code, parsed.series or parsed.category, parsed.title,
                      _fmt_size(path.stat().st_size), state]
            for c, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                if c == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)

    def _update_count(self) -> None:
        self.count_label.setText(self.ctx.t("loaded_count", n=len(self._scan)))

    def _update_banner(self) -> None:
        numbered = self.services.compute_missing()
        items: list[str] = []
        for series, miss in sorted(numbered.items()):
            items += [f"{series}{n}" for n in miss]
        if items:
            shown = ", ".join(items[:14])
            if len(items) > 14:
                shown += f"  (+{len(items) - 14})"
            link = self.ctx.t("missing_show_link")
            self.banner.setText(self.ctx.t("missing_banner", items=shown)
                                + f"  <a href='#missing'>{link}</a>")
            self.banner.setVisible(True)
        else:
            self.banner.setVisible(False)

    # -- busy state ----------------------------------------------------------
    def _lock(self, locked: bool) -> None:
        for b in (self.btn_extract, self.btn_copy, self.btn_import,
                  self.btn_refresh, self.btn_rescan):
            b.setEnabled(not locked)

    def _busy_generic(self, status_key: str) -> None:
        self._lock(True)
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setVisible(True)
        self.status.setText(self.ctx.t(status_key))

    def _idle(self) -> None:
        self._lock(False)
        self.busy_bar.setVisible(False)
        self.progress_panel.finish()
        self.btn_cancel.setVisible(False)

    def _start_worker(self, fn, *args, on_success=None) -> None:
        w = Worker(fn, *args)
        self._threads.append(w)
        w.progressed.connect(self._on_progress)
        if on_success:
            w.succeeded.connect(on_success)
        w.failed.connect(self._on_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_progress(self, msg) -> None:
        if isinstance(msg, dict):
            if msg.get("kind") == "extract":
                self.progress_panel.update_progress(
                    msg["done"], msg["total"], msg["pack"], msg["osz"])
            elif msg.get("kind") == "import":
                self.status.setText(self.ctx.t(
                    "import_dispatching", batch=msg["batch"], total=msg["total"]))
        else:
            self.status.setText(str(msg))

    def _on_failed(self, msg: str) -> None:
        self._idle()
        self.status.setText(msg)
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    def _on_cancel(self) -> None:
        self.services.request_cancel()
        self.btn_cancel.setEnabled(False)

    # -- Unpack Archives -----------------------------------------------------
    def on_extract(self) -> None:
        if not self._scan:
            self._handle_empty_packs()
            return
        self._busy_generic("working")
        self._start_worker(self.services.prescan_all, on_success=self._after_prescan)

    def _handle_empty_packs(self) -> None:
        """Packs is empty: explain, and offer a native picker to import archives
        from anywhere (item 4). QFileDialog is native on Windows and macOS."""
        t = self.ctx.t
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(t("app_title"))
        box.setText(t("packs_empty"))
        browse = box.addButton(t("btn_browse_archives"), QMessageBox.AcceptRole)
        box.addButton(t("btn_cancel"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is browse:
            self._import_external_archives()

    def _import_external_archives(self) -> None:
        t = self.ctx.t
        files, _ = QFileDialog.getOpenFileNames(
            self, t("select_archives"), "", extractor.archive_dialog_filter())
        if not files:
            return
        dest = self.ctx.cfg.packs_path
        dest.mkdir(parents=True, exist_ok=True)
        n = 0
        for f in files:
            try:
                shutil.copy2(f, dest / Path(f).name)
                n += 1
            except OSError:
                pass
        self.status.setText(t("imported_to_packs", n=n))
        self.refresh_scan()
        if self._scan:
            self.on_extract()  # proceed straight into unpacking

    def _after_prescan(self, plans) -> None:
        approved = self._resolve_plans(plans)
        if not approved:
            self._idle()
            self.status.setText(self.ctx.t("done"))
            self.refresh_scan()
            return
        self.busy_bar.setVisible(False)
        self.progress_panel.start()
        self.status.setText(self.ctx.t("extracting"))
        self._start_worker(self.services.extract, approved,
                           on_success=self._after_extract)

    def _resolve_plans(self, plans) -> list:
        approved = []
        apply_all_decision = None
        for plan in plans:
            if plan.kind == "new":
                approved.append((Path(plan.zip_path), plan.parsed))
                continue
            if apply_all_decision is not None:
                decision = apply_all_decision
            else:
                decision, apply_all = self._ask_readd(plan)
                if apply_all:
                    apply_all_decision = decision
            if decision:
                approved.append((Path(plan.zip_path), plan.parsed))
                self.ctx.log.info("READD_EXTRACT", code=plan.parsed.code)
            else:
                self.ctx.log.info("READD_SKIP", code=plan.parsed.code)
        return approved

    def _ask_readd(self, plan) -> tuple[bool, bool]:
        t = self.ctx.t
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(t("readd_title"))
        if plan.kind == "all_present":
            box.setText(t("readd_all_present", code=plan.parsed.code))
        else:
            box.setText(t("readd_some_missing", code=plan.parsed.code, n=len(plan.new_ids)))
        checkbox = QCheckBox(t("readd_apply_all"))
        box.setCheckBox(checkbox)
        yes = box.addButton(t("btn_extract_anyway"), QMessageBox.AcceptRole)
        box.addButton(t("btn_skip"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() == yes, checkbox.isChecked()

    def _after_extract(self, result) -> None:
        self._idle()
        msg = self.ctx.t("extract_done", packs=result["packs"], tracks=result["tracks"])
        if "backup" in result:
            b = result["backup"]
            msg += "  " + self.ctx.t("library_done", new=b["new"], dup=b["duplicates"])
        self.status.setText(msg)
        self.refresh_scan()
        self.mw.packs.reload()

    # -- Copy to Library -----------------------------------------------------
    def on_copy(self) -> None:
        if not osu_import.output_osz_files(self.ctx.cfg.output_path):
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("nothing_in_output"))
            return
        self._busy_generic("working")
        self._start_worker(self.services.copy_library, on_success=self._after_copy)

    def _after_copy(self, res) -> None:
        self._idle()
        self.status.setText(self.ctx.t("library_done", new=res["new"], dup=res["duplicates"]))

    # -- Import to osu! ------------------------------------------------------
    def on_import(self) -> None:
        files = osu_import.output_osz_files(self.ctx.cfg.output_path)
        if not files:
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("nothing_in_output"))
            return
        exe = self.ctx.cfg.osu_exe
        if not exe or not Path(exe).exists():
            QMessageBox.warning(self, self.ctx.t("app_title"),
                                self.ctx.t("osu_not_found"))
            return
        plan = self.services.import_plan()
        reply = QMessageBox.question(
            self, self.ctx.t("import_confirm_title"),
            self.ctx.t("import_confirm_body", files=plan["files"],
                       batches=plan["batches"], eta=human_duration(plan["eta_s"])),
            QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Ok)
        if reply != QMessageBox.Ok:
            return
        self._busy_generic("working")
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setVisible(True)
        self._start_worker(self.services.import_osu, on_success=self._after_import)

    def _after_import(self, res) -> None:
        self._idle()
        if res.get("cancelled"):
            self.status.setText(self.ctx.t("import_cancelled",
                                           sent=res.get("sent", 0), total=res["files"]))
        else:
            self.status.setText(self.ctx.t("import_done", files=res["files"],
                                           batches=res["batches"]))
            # osu! keeps importing in the background after dispatch (item 18).
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("osu_keep_open"))

    # -- Refresh Library -----------------------------------------------------
    def on_refresh(self) -> None:
        self._busy_generic("working")
        self._start_worker(self.services.refresh, on_success=self._after_refresh)

    def _after_refresh(self, res) -> None:
        self._idle()
        self.status.setText(self.ctx.t("refresh_done", added=res["added"],
                                       enriched=res.get("enriched", 0),
                                       disappeared=res["disappeared"],
                                       present=res["present"]))
        self._update_banner()
