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

from .. import config, extractor, osu_import
from ..i18n import human_duration
from ..workers import Worker
from .progress_panel import ProgressPanel
from .reveal import reveal_in_explorer


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
        self._output: list[dict] = []
        self._known_paths: list[str] = []   # scanned archives already in the DB
        self._view = "packs"   # "packs" (scan) or "output" (unpacked .osz)

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
        self.btn_import_lazer = QPushButton()
        self.btn_import_stable = QPushButton()
        self.btn_refresh = QPushButton()
        self.btn_backup = QPushButton()
        self.btn_health = QPushButton()
        for b in (self.btn_copy, self.btn_import_lazer, self.btn_import_stable,
                  self.btn_refresh, self.btn_backup, self.btn_health):
            b.setObjectName("secondary")
        for b in (self.btn_extract, self.btn_copy, self.btn_import_lazer,
                  self.btn_import_stable, self.btn_refresh, self.btn_backup,
                  self.btn_health):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        self.btn_purge_known = QPushButton(objectName="secondary")
        self.btn_purge_known.setVisible(False)   # only when known archives are present
        self.btn_purge_known.clicked.connect(self.on_purge_known)
        btn_row.addWidget(self.btn_purge_known)
        self.btn_clear_output = QPushButton(objectName="secondary")
        self.btn_clear_output.setVisible(False)   # only in the Output view with files
        self.btn_clear_output.clicked.connect(self.on_clear_output)
        btn_row.addWidget(self.btn_clear_output)
        self.btn_rescan = QPushButton(objectName="secondary")
        btn_row.addWidget(self.btn_rescan)
        root.addLayout(btn_row)

        self.btn_extract.clicked.connect(self.on_extract)
        self.btn_copy.clicked.connect(self.on_copy)
        self.btn_import_lazer.clicked.connect(lambda: self.on_import("lazer"))
        self.btn_import_stable.clicked.connect(lambda: self.on_import("stable"))
        self.btn_refresh.clicked.connect(self.on_refresh)
        self.btn_backup.clicked.connect(self.on_backup)
        self.btn_health.clicked.connect(self.on_health)
        self.btn_rescan.clicked.connect(self.refresh_scan)

        self.table = QTableWidget(0, 5)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self._on_row_activated)
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
        self.btn_import_lazer.setText(t("btn_import_to_lazer"))
        self.btn_import_stable.setText(t("btn_import_to_stable"))
        self.btn_refresh.setText(t("btn_refresh"))
        self.btn_backup.setText(t("btn_backup_drive"))
        self.btn_health.setText(t("btn_library_health"))
        self.btn_purge_known.setText(t("btn_purge_known"))
        self.btn_clear_output.setText(t("btn_clear_output"))
        self.btn_rescan.setText(t("btn_rescan"))
        self.btn_cancel.setText(t("btn_cancel"))
        self.btn_extract.setToolTip(t("tip_extract"))
        self.btn_copy.setToolTip(t("tip_copy_library"))
        self.btn_import_lazer.setToolTip(t("tip_import_to_lazer"))
        self.btn_import_stable.setToolTip(t("tip_import_to_stable"))
        self.btn_refresh.setToolTip(t("tip_refresh"))
        self.btn_backup.setToolTip(t("tip_backup_drive"))
        self.btn_health.setToolTip(t("tip_library_health"))
        self.btn_purge_known.setToolTip(t("tip_purge_known"))
        self.btn_clear_output.setToolTip(t("tip_clear_output"))
        self.btn_rescan.setToolTip(t("tip_rescan"))
        self.btn_cancel.setToolTip(t("tip_cancel"))
        self._populate_table()   # headers + rows follow the current view + language
        self._update_count()
        self._update_banner()
        self._sync_auto_copy()
        self._sync_import_buttons()
        if not self.status.text():
            self.status.setText(t("ready"))

    def _sync_auto_copy(self) -> None:
        """Hide the manual 'Copy to Library' button when auto-copy-after-unpack is
        enabled — it's redundant then, and hiding it avoids accidental repeat
        copies. Called on retranslate and whenever the setting is toggled."""
        self.btn_copy.setVisible(not self.ctx.cfg.auto_backup_after_extract)

    def _sync_import_buttons(self) -> None:
        """Show an import button only for an osu! client that's actually installed
        or configured — a user may have only one of lazer / stable."""
        for btn, target in ((self.btn_import_lazer, "lazer"),
                            (self.btn_import_stable, "stable")):
            exe = self._import_exe(target)
            btn.setVisible(bool(exe and Path(exe).exists()))

    def on_shown(self) -> None:
        self.refresh_scan()
        self._sync_import_buttons()   # a client may have been configured meanwhile

    # -- scanning ------------------------------------------------------------
    def refresh_scan(self) -> None:
        self._scan = self.services.scan()
        self._known_paths = [str(p) for p, parsed in self._scan
                             if self.ctx.db.get_pack_by_code(parsed.code) is not None]
        self.btn_purge_known.setVisible(bool(self._known_paths))
        if self._scan:
            self._view = "packs"
            self._output = []
        else:
            # Packs is empty (e.g. right after unpacking) — show the Output
            # beatmaps instead of a blank table (item D).
            self._output = self.services.output_listing()
            self._view = "output" if self._output else "packs"
        self._populate_table()
        self._update_count()
        self._update_banner()

    def _populate_table(self) -> None:
        if self._view == "output":
            self._populate_output_table()
        else:
            self._populate_packs_table()
        # "Clear Output" only makes sense while the Output view has files.
        self.btn_clear_output.setVisible(self._view == "output" and bool(self._output))

    def _populate_packs_table(self) -> None:
        t = self.ctx.t
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            t("col_code"), t("col_series"), t("col_title"), t("col_size"), t("col_state")])
        self.table.setRowCount(len(self._scan))
        for r, (path, parsed) in enumerate(self._scan):
            known = self.ctx.db.get_pack_by_code(parsed.code) is not None
            state = t("state_known") if known else t("state_new")
            try:
                size = _fmt_size(path.stat().st_size)
            except OSError:
                size = "—"   # a scanned archive vanished (moved/deleted) before repaint
            values = [parsed.code, parsed.series or parsed.category, parsed.title,
                      size, state]
            for c, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                if c == 3:
                    item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)

    def _populate_output_table(self) -> None:
        t = self.ctx.t
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([t("col_title"), t("col_size")])
        self.table.setRowCount(len(self._output))
        for r, row in enumerate(self._output):
            name_item = QTableWidgetItem(str(row["name"]))
            size_item = QTableWidgetItem(_fmt_size(row["size_bytes"]))
            size_item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.table.setItem(r, 0, name_item)
            self.table.setItem(r, 1, size_item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

    def _on_row_activated(self, row: int, _col: int) -> None:
        """Double-click a row: reveal its file in the OS file manager (v1.3)."""
        if self._view == "output":
            if not (0 <= row < len(self._output)):
                return
            path = self.ctx.cfg.output_path / self._output[row]["name"]
        else:
            if not (0 <= row < len(self._scan)):
                return
            path = self._scan[row][0]
        reveal_in_explorer(self, self.ctx, path)

    def _update_count(self) -> None:
        if self._view == "output":
            self.count_label.setText(self.ctx.t("output_count", n=len(self._output)))
        else:
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
        for b in (self.btn_extract, self.btn_copy, self.btn_import_lazer,
                  self.btn_import_stable, self.btn_refresh, self.btn_backup,
                  self.btn_health, self.btn_purge_known, self.btn_clear_output,
                  self.btn_rescan):
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
            elif msg.get("kind") == "backup":
                self.progress_panel.update_progress(
                    msg["done"], msg["total"], msg.get("name", ""), "")
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
        # loose .osz dropped straight into Packs count as work too (moved to Output)
        if not self._scan and not self.services.has_loose_osz():
            self._handle_empty_packs()
            return
        self._busy_generic("working")
        self._start_worker(self.services.prescan_all, on_success=self._after_prescan)

    def on_purge_known(self) -> None:
        """Recycle/move/delete the archives that are already in the library, per
        the user's zip_disposal setting — clears clutter so Unpack can offer the
        picker for new archives (user feedback)."""
        if not self._known_paths:
            return
        t = self.ctx.t
        reply = QMessageBox.question(
            self, t("app_title"), t("purge_known_confirm", n=len(self._known_paths)),
            QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Ok)
        if reply != QMessageBox.Ok:
            return
        n = self.services.dispose_archives(list(self._known_paths))
        self.status.setText(t("purge_known_done", n=n))
        self.refresh_scan()

    def on_clear_output(self) -> None:
        """Recycle the .osz still in Output/ once a batch is done (copied to the
        Library and/or imported into osu!) — a manual 'empty staging' action."""
        if not self._output:
            return
        t = self.ctx.t
        reply = QMessageBox.question(
            self, t("app_title"), t("clear_output_confirm", n=len(self._output)),
            QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Ok)
        if reply != QMessageBox.Ok:
            return
        n = self.services.clear_output()
        self.status.setText(t("clear_output_done", n=n))
        self.refresh_scan()

    def _offer_pick_archives(self) -> None:
        """Nothing new to unpack — let the user pick archives from elsewhere
        (so the picker is reachable even when Packs isn't empty)."""
        t = self.ctx.t
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(t("app_title"))
        box.setText(t("nothing_to_unpack"))
        browse = box.addButton(t("btn_browse_archives"), QMessageBox.AcceptRole)
        box.addButton(t("btn_cancel"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is browse:
            self._import_external_archives()

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
            target = dest / Path(f).name
            try:
                if target.exists():
                    continue          # already in Packs — don't move over it
                shutil.move(str(f), str(target))   # move, not copy (user feedback)
                n += 1
            except OSError:
                pass
        self.status.setText(t("imported_to_packs", n=n))
        self.refresh_scan()
        if self._scan:
            self.on_extract()  # proceed straight into unpacking

    def _after_prescan(self, plans) -> None:
        approved = self._resolve_plans(plans)
        if not approved and not self.services.has_loose_osz():
            self._idle()
            self.status.setText(self.ctx.t("done"))
            self.refresh_scan()
            self._offer_pick_archives()   # nothing new to unpack — offer the picker
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
        if result.get("loose"):
            msg += "  " + self.ctx.t("loose_done", n=result["loose"])
        if "backup" in result:
            b = result["backup"]
            msg += "  " + self.ctx.t("library_done", new=b["new"], dup=b["duplicates"])
        rejected = result.get("rejected") or []
        if rejected:
            msg += "  " + self.ctx.t("archive_rejected", n=len(rejected))
        self.status.setText(msg)
        self.refresh_scan()
        self.mw.packs.reload()
        self.mw.search.reload()          # reflect newly-added tracks live (item 7)
        if rejected:
            self._warn_rejected(rejected)

    def _warn_rejected(self, rejected: list) -> None:
        """Show which packs were refused as unsafe (zip-bomb / traversal) and why."""
        t = self.ctx.t
        lines = []
        for r in rejected:
            reason = t(f"archive_reason_{r.get('reason', 'unsafe')}")
            line = f"• {r.get('code', '?')} — {reason}"
            if not r.get("quarantined", True):
                line += "  " + t("archive_not_moved")
            lines.append(line)
        QMessageBox.warning(self, t("archive_rejected_title"),
                            t("archive_rejected_body", items="\n".join(lines)))

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
        if res["new"] == 0 and res["duplicates"] > 0:
            # Nothing new — everything in Output was already in the Library. Say so
            # plainly instead of a bare "0 added" (spamming Copy is otherwise silent).
            self.status.setText(self.ctx.t("library_all_present", n=res["duplicates"]))
        else:
            self.status.setText(self.ctx.t("library_done", new=res["new"], dup=res["duplicates"]))
        self.mw.search.reload()          # reflect the new library rows live (item 7)

    # -- Import to osu! (lazer / stable) -------------------------------------
    def _import_exe(self, target: str) -> str:
        cfg = self.ctx.cfg
        if target == "stable":
            return cfg.osu_stable_exe or config.detect_stable_exe()
        return cfg.osu_lazer_exe or config.detect_osu_exe()

    def on_import(self, target: str = "lazer") -> None:
        files = osu_import.output_osz_files(self.ctx.cfg.output_path)
        if not files:
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("nothing_in_output"))
            return
        exe = self._import_exe(target)
        if not exe or not Path(exe).exists():
            key = "import_no_stable_exe" if target == "stable" else "import_no_lazer_exe"
            QMessageBox.warning(self, self.ctx.t("app_title"), self.ctx.t(key))
            return
        plan = self.services.import_plan(target)
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
        self._start_worker(self.services.import_osu, target, on_success=self._after_import)

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
        self.mw.search.reload()          # reflect refreshed library rows live (item 7)

    # -- Back up to Google Drive (item 11) -----------------------------------
    def on_backup(self) -> None:
        t = self.ctx.t
        st = self.services.drive_status()
        if not st["configured"]:
            QMessageBox.information(self, t("app_title"), t("drive_not_configured"))
            return
        if not st["connected"]:
            QMessageBox.information(self, t("app_title"), t("drive_connect_first"))
            return
        plan = self.services.backup_plan()
        if plan.get("error") == "not_connected":
            QMessageBox.information(self, t("app_title"), t("drive_connect_first"))
            return
        if not plan.get("count"):
            QMessageBox.information(self, t("app_title"), t("drive_nothing_new"))
            return
        from .backup_dialog import BackupOptionsDialog
        dlg = BackupOptionsDialog(self.ctx, plan["count"], plan["total_bytes"],
                                  plan["chunk_bytes"], self)
        if not dlg.exec():
            return
        max_sets, chunk_bytes = dlg.choices()
        self._lock(True)
        self.busy_bar.setVisible(False)
        self.progress_panel.start()
        self.status.setText(t("drive_backing_up"))
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setVisible(True)
        self._start_worker(
            lambda progress=None: self.services.backup_to_drive(
                progress, max_sets=max_sets, chunk_bytes=chunk_bytes),
            on_success=self._after_backup)

    def _after_backup(self, res) -> None:
        self._idle()
        t = self.ctx.t
        if res.get("error") == "not_connected":
            self.status.setText(t("drive_connect_first"))
            return
        if res.get("error"):
            self.status.setText(t("drive_backup_failed"))
            QMessageBox.critical(self, t("app_title"),
                                 res.get("detail") or t("drive_backup_failed"))
            return
        if res.get("cancelled"):
            self.status.setText(t("drive_backup_cancelled", uploaded=res["uploaded"],
                                    chunks=res["chunks"]))
            return
        self.status.setText(t("drive_backup_done", uploaded=res["uploaded"],
                                chunks=res["chunks"]))

    # -- Library Health (v1.1) ----------------------------------------------
    def on_health(self) -> None:
        """Compute the read-only Library health report off-thread, then show it
        in a dialog (from which the user can run a SHA-256 verify)."""
        self._busy_generic("working")
        self._start_worker(self.services.library_health,
                           on_success=self._after_health)

    def _after_health(self, report) -> None:
        self._idle()
        self.status.setText(self.ctx.t("health_done",
                                       files=report["usage"]["files"]))
        from .health_dialog import HealthDialog
        HealthDialog(self.ctx, report, self).exec()
