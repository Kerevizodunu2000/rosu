# SPDX-License-Identifier: GPL-3.0-or-later
"""Shortcuts (Kısayollar) tab: installed-music summary + one-click flows —
lazer↔stable transfer, save-to-Library, unpack→import, export, and dedup (v1.2).

Thin UI: every action runs a :class:`~rosu.services.Services` method off the UI
thread via :class:`~rosu.workers.Worker`, mirroring the Dashboard tab.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ..workers import Worker
from .progress_panel import ProgressPanel

_GIB = 1024 ** 3
_MIB = 1024 ** 2


def _fmt_size(n: int) -> str:
    return f"{n / _MIB:,.1f} MB"


class ShortcutsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.ctx = main_window.ctx
        self.services = self.ctx.services
        self._threads: list[Worker] = []
        self._summary: dict | None = None
        self._status_key: str | None = "ready"   # remembered so a language change
        self._status_kwargs: dict = {}            # can re-render the status message

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        self.title = QLabel(objectName="h1")
        root.addWidget(self.title)

        # -- installed-music summary -------------------------------------------
        self.summary_box = QGroupBox()
        sgrid = QGridLayout(self.summary_box)
        self.sum_labels: dict = {}
        for col, key in enumerate(("lazer", "stable", "library", "drive")):
            head = QLabel(objectName="status")
            val = QLabel(objectName="h1")
            self.sum_labels[key] = (head, val)
            sgrid.addWidget(head, 0, col)
            sgrid.addWidget(val, 1, col)
        root.addWidget(self.summary_box)

        # -- transfer between clients (① ②) ------------------------------------
        self.transfer_box = QGroupBox()
        trow = QHBoxLayout(self.transfer_box)
        self.btn_l2s = QPushButton(objectName="secondary")
        self.btn_s2l = QPushButton(objectName="secondary")
        self.btn_l2s.clicked.connect(lambda: self.on_transfer("lazer", "stable"))
        self.btn_s2l.clicked.connect(lambda: self.on_transfer("stable", "lazer"))
        trow.addWidget(self.btn_l2s)
        trow.addWidget(self.btn_s2l)
        trow.addStretch(1)
        root.addWidget(self.transfer_box)

        # -- save installed → Library (③) --------------------------------------
        self.save_box = QGroupBox()
        srow = QHBoxLayout(self.save_box)
        self.btn_save_lazer = QPushButton(objectName="secondary")
        self.btn_save_stable = QPushButton(objectName="secondary")
        self.btn_save_lazer.clicked.connect(lambda: self.on_save(["lazer"]))
        self.btn_save_stable.clicked.connect(lambda: self.on_save(["stable"]))
        srow.addWidget(self.btn_save_lazer)
        srow.addWidget(self.btn_save_stable)
        srow.addStretch(1)
        root.addWidget(self.save_box)

        # -- unpack Packs → import (⑤) -----------------------------------------
        self.unpack_box = QGroupBox()
        urow = QHBoxLayout(self.unpack_box)
        self.btn_unpack_lazer = QPushButton(objectName="secondary")
        self.btn_unpack_stable = QPushButton(objectName="secondary")
        self.btn_unpack_both = QPushButton(objectName="secondary")
        self.btn_unpack_lazer.clicked.connect(lambda: self.on_unpack(["lazer"]))
        self.btn_unpack_stable.clicked.connect(lambda: self.on_unpack(["stable"]))
        self.btn_unpack_both.clicked.connect(
            lambda: self.on_unpack(["lazer", "stable"]))
        for b in (self.btn_unpack_lazer, self.btn_unpack_stable, self.btn_unpack_both):
            urow.addWidget(b)
        urow.addStretch(1)
        root.addWidget(self.unpack_box)

        # -- export (④) --------------------------------------------------------
        self.export_box = QGroupBox()
        erow = QHBoxLayout(self.export_box)
        self.export_source = QComboBox()
        self.export_format = QComboBox()
        self.export_split = QComboBox()
        self.export_drive = QCheckBox()
        self.export_share = QCheckBox()
        self.export_drive.toggled.connect(self._on_drive_toggled)
        self.export_share.toggled.connect(self._on_share_toggled)
        self.btn_export = QPushButton(objectName="secondary")
        self.btn_export.clicked.connect(self.on_export)
        for w in (self.export_source, self.export_format, self.export_split,
                  self.export_drive, self.export_share, self.btn_export):
            erow.addWidget(w)
        erow.addStretch(1)
        root.addWidget(self.export_box)

        # -- dedup Library extra -----------------------------------------------
        drow = QHBoxLayout()
        self.btn_dedup = QPushButton(objectName="secondary")
        self.btn_dedup.clicked.connect(self.on_dedup)
        drow.addWidget(self.btn_dedup)
        drow.addStretch(1)
        root.addLayout(drow)

        # -- progress / status -------------------------------------------------
        self.progress_panel = ProgressPanel()
        root.addWidget(self.progress_panel)
        root.addStretch(1)

        bottom = QHBoxLayout()
        self.status = QLabel(objectName="status")
        self.btn_cancel = QPushButton(objectName="secondary")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._on_cancel)
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.btn_cancel)
        root.addLayout(bottom)

    # -- i18n ------------------------------------------------------------------
    def retranslate(self) -> None:
        t = self.ctx.t
        self.title.setText(t("tab_shortcuts"))
        self.summary_box.setTitle(t("sc_summary_title"))
        for key in ("lazer", "stable", "library", "drive"):
            head, _val = self.sum_labels[key]
            head.setText(t(f"sc_{key}"))
        self.transfer_box.setTitle(t("sc_transfer_title"))
        self.btn_l2s.setText(t("btn_transfer_l2s"))
        self.btn_s2l.setText(t("btn_transfer_s2l"))
        self.save_box.setTitle(t("sc_save_title"))
        self.btn_save_lazer.setText(t("btn_save_lib_lazer"))
        self.btn_save_stable.setText(t("btn_save_lib_stable"))
        self.unpack_box.setTitle(t("sc_unpack_title"))
        self.btn_unpack_lazer.setText(t("btn_unpack_lazer"))
        self.btn_unpack_stable.setText(t("btn_unpack_stable"))
        self.btn_unpack_both.setText(t("btn_unpack_both"))
        self.export_box.setTitle(t("sc_export_title"))
        self._fill_export_combos()
        self.export_drive.setText(t("sc_export_drive"))
        self.export_share.setText(t("sc_export_share"))
        self.btn_export.setText(t("btn_export"))
        self.btn_dedup.setText(t("btn_dedup"))
        self.btn_dedup.setToolTip(t("tip_dedup"))
        self.btn_cancel.setText(t("btn_cancel"))
        self._render_summary()
        self._sync_drive_controls()
        if self._status_key:                      # re-render the last status in the
            self.status.setText(t(self._status_key, **self._status_kwargs))  # new language
        elif not self.status.text():
            self.status.setText(t("ready"))

    def _fill_export_combos(self) -> None:
        t = self.ctx.t
        # preserve current selections across a language change
        keep = (self.export_source.currentData(), self.export_format.currentData(),
                self.export_split.currentData())
        for combo in (self.export_source, self.export_format, self.export_split):
            combo.blockSignals(True)
            combo.clear()
        for data, key in (("library", "sc_source_library"),
                          ("drive", "sc_source_drive"), ("lazer", "sc_source_lazer"),
                          ("stable", "sc_source_stable"),
                          ("merged", "sc_source_merged")):
            self.export_source.addItem(t(key), data)
        self.export_format.addItem("zip", "zip")
        self.export_format.addItem("7z", "7z")
        self.export_split.addItem(t("sc_split_none"), None)
        self.export_split.addItem(t("sc_split_1g"), _GIB)
        self.export_split.addItem(t("sc_split_500m"), 500 * _MIB)
        for combo, data in zip((self.export_source, self.export_format,
                                self.export_split), keep):
            i = combo.findData(data)
            if i >= 0:
                combo.setCurrentIndex(i)
            combo.blockSignals(False)

    # -- summary ---------------------------------------------------------------
    def on_shown(self) -> None:
        self._sync_drive_controls()
        self._start_worker(self.services.installed_summary,
                           on_success=self._on_summary)

    def _sync_drive_controls(self) -> None:
        """Keep the Drive controls consistent with the connection state. The boxes
        stay CLICKABLE (a disabled widget swallows clicks, so the user couldn't get
        an explanation) — instead the toggle handlers warn-and-revert on an invalid
        pick. Here we just refresh tooltips and uncheck anything no longer valid."""
        t = self.ctx.t
        connected = bool(self.ctx.cfg.drive_connected)
        self.export_drive.setToolTip("" if connected else t("drive_connect_first"))
        if not connected and self.export_drive.isChecked():
            self.export_drive.blockSignals(True)
            self.export_drive.setChecked(False)
            self.export_drive.blockSignals(False)
        self.export_share.setToolTip(
            "" if self.export_drive.isChecked() else t("sc_share_needs_upload"))
        if not self.export_drive.isChecked() and self.export_share.isChecked():
            self.export_share.blockSignals(True)
            self.export_share.setChecked(False)
            self.export_share.blockSignals(False)

    def _on_drive_toggled(self, checked: bool) -> None:
        if checked and not self.ctx.cfg.drive_connected:
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("drive_connect_first"))
            self.export_drive.setChecked(False)   # can't upload without Drive
            return
        self._sync_drive_controls()

    def _on_share_toggled(self, checked: bool) -> None:
        if checked and not self.export_drive.isChecked():
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("sc_share_needs_upload"))
            self.export_share.setChecked(False)   # a link needs the upload

    def _on_summary(self, summary) -> None:
        self._summary = summary
        self._render_summary()

    def _render_summary(self) -> None:
        t = self.ctx.t
        s = self._summary
        for key in ("lazer", "stable", "library", "drive"):
            _head, val = self.sum_labels[key]
            if s is None:
                val.setText("—")
                continue
            info = s.get(key, {})
            if key in ("library", "drive"):
                val.setText(t("sc_count_fmt", n=info.get("count", 0)))
            elif not info.get("installed"):
                val.setText(t("sc_not_installed"))
            elif info.get("count") is None:
                val.setText(t("sc_installed"))
            else:
                val.setText(t("sc_count_fmt", n=info["count"]))

    # -- actions ---------------------------------------------------------------
    def on_transfer(self, source: str, target: str) -> None:
        self._busy()
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setVisible(True)
        self._start_worker(
            lambda progress=None: self.services.transfer_between_clients(
                source, target, progress),
            on_success=self._after_transfer)

    def _after_transfer(self, res) -> None:
        self._idle()
        t = self.ctx.t
        if res.get("error") == "same_client":
            return
        if res.get("error") == "no_target_exe":
            QMessageBox.warning(self, t("app_title"), t("sc_no_target_exe"))
            self._set_status("sc_no_target_exe")
            return
        if res.get("cancelled"):
            self._set_status("sc_cancelled")
            self.on_shown()
            return
        self._set_status("sc_transfer_done", found=res["found"],
                         transferred=res["transferred"], skipped=res["skipped"])
        self.on_shown()

    def on_save(self, sources) -> None:
        self._busy()
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setVisible(True)
        self._start_worker(
            lambda progress=None: self.services.save_installed_to_library(
                sources, progress),
            on_success=self._after_save)

    def _after_save(self, res) -> None:
        self._idle()
        if any(isinstance(v, dict) and v.get("cancelled") for v in res.values()):
            self._set_status("sc_cancelled")
            self.on_shown()
            return
        new = sum(v.get("new", 0) for v in res.values() if isinstance(v, dict))
        self._set_status("sc_save_done", new=new)
        self.mw.search.reload()
        self.on_shown()

    def on_unpack(self, targets) -> None:
        t = self.ctx.t
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(t("app_title"))
        box.setText(t("sc_unpack_dupe_prompt"))
        only_new = box.addButton(t("sc_unpack_only_new"), QMessageBox.AcceptRole)
        box.addButton(t("sc_unpack_all"), QMessageBox.ActionRole)
        box.addButton(t("btn_cancel"), QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is None or box.buttonRole(clicked) == QMessageBox.RejectRole:
            return
        skip = clicked is only_new   # "Only new" skips sets already in the target
        self._busy()
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setVisible(True)
        self._start_worker(
            lambda progress=None: self.services.unpack_and_import(
                targets, skip, progress),
            on_success=self._after_unpack)

    def _after_unpack(self, res) -> None:
        self._idle()
        if res.get("cancelled"):
            self._set_status("sc_cancelled")
            self.on_shown()
            return
        ex = res.get("extract", {})
        skipped = sum(v.get("skipped", 0) for v in res.get("imports", {}).values())
        self._set_status("sc_unpack_done2", tracks=ex.get("tracks", 0), skipped=skipped)
        self.mw.search.reload()
        self.on_shown()

    def on_export(self) -> None:
        t = self.ctx.t
        source = self.export_source.currentData()
        fmt = self.export_format.currentData() or "zip"
        split = self.export_split.currentData()
        upload = self.export_drive.isChecked()
        share = self.export_share.isChecked()
        if upload and not self.services.drive_status().get("connected"):
            QMessageBox.information(self, t("app_title"), t("drive_connect_first"))
            return
        suffix = ".7z" if fmt == "7z" else ".zip"
        default_name = f"rosu-export-{source}{suffix}"   # e.g. rosu-export-lazer.zip
        path, _ = QFileDialog.getSaveFileName(
            self, t("sc_export_choose"), default_name, f"Archive (*{suffix})")
        if not path:
            return
        dest_base = Path(path)
        if dest_base.suffix.lower() in (".zip", ".7z"):
            dest_base = dest_base.with_suffix("")   # exporter re-appends the suffix
        self._busy()
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setVisible(True)
        self._start_worker(
            lambda progress=None: self.services.export_sets(
                source, dest_base, fmt, split, upload, share, progress),
            on_success=self._after_export)

    def _after_export(self, res) -> None:
        self._idle()
        t = self.ctx.t
        if res.get("cancelled"):
            self._set_status("sc_cancelled")
            return
        if res.get("count", 0) == 0:
            self._set_status("sc_export_empty")
            return
        archives = res.get("archives", [])
        location = str(Path(archives[0]).parent) if archives else ""
        msg = t("sc_export_done", count=res["count"], archives=len(archives))
        self._set_status_lit(msg + "  " + t("sc_export_saved_to", path=location))
        drive = res.get("drive") or {}
        dfiles = drive.get("files", [])
        links = [f["link"] for f in dfiles if f.get("link")]
        shared_no_link = [f for f in dfiles if f.get("shared") and not f.get("link")]
        # Completion dialog: exactly WHERE it went + the archive filenames (+ links).
        body = [msg, "", t("sc_export_saved_to", path=location)]
        body += [f"• {Path(a).name}" for a in archives]
        if drive.get("error"):
            body += ["", t("sc_export_upload_failed")]
        if links:
            body += ["", t("sc_export_link")] + links
        QMessageBox.information(self, t("app_title"), "\n".join(body))
        if shared_no_link:
            # The file(s) were made public but the link couldn't be fetched — the
            # user must know so they can review/revoke the share in Drive.
            QMessageBox.warning(self, t("app_title"), t("sc_export_shared_no_link"))

    def on_dedup(self) -> None:
        """Preview what dedup would recycle, confirm (explaining the criterion),
        then remove — never delete files without an explicit OK (240-file safety)."""
        self._busy()
        self._start_worker(self.services.dedup_library_plan,
                           on_success=self._after_dedup_plan)

    def _after_dedup_plan(self, plan) -> None:
        self._idle()
        t = self.ctx.t
        if plan.get("count", 0) == 0:
            self._set_status("sc_dedup_none")
            return
        reply = QMessageBox.question(
            self, t("app_title"),
            t("sc_dedup_confirm", count=plan["count"],
              freed=_fmt_size(plan["freed_bytes"])),
            QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel)
        if reply != QMessageBox.Ok:
            self._set_status("ready")
            return
        names = plan["names"]
        self._busy()
        self._start_worker(
            lambda progress=None: self.services.dedup_library(names, progress),
            on_success=self._after_dedup)

    def _after_dedup(self, res) -> None:
        self._idle()
        if res.get("removed", 0) == 0:
            self._set_status("sc_dedup_none")
        else:
            self._set_status("sc_dedup_done", removed=res["removed"],
                             freed=_fmt_size(res["freed_bytes"]))
        self.on_shown()

    # -- worker plumbing -------------------------------------------------------
    def _set_status(self, key: str, **kwargs) -> None:
        """Set a translatable status message, remembering it so a later language
        change re-renders it in the new language (retranslate)."""
        self._status_key, self._status_kwargs = key, kwargs
        self.status.setText(self.ctx.t(key, **kwargs))

    def _set_status_lit(self, text: str) -> None:
        """Set a non-translatable status line (an error message or a path)."""
        self._status_key, self._status_kwargs = None, {}
        self.status.setText(text)

    def _busy(self) -> None:
        self._lock(True)
        self.progress_panel.start()
        self._set_status("working")

    def _lock(self, locked: bool) -> None:
        for b in (self.btn_l2s, self.btn_s2l, self.btn_save_lazer,
                  self.btn_save_stable, self.btn_unpack_lazer, self.btn_unpack_stable,
                  self.btn_unpack_both, self.btn_export, self.btn_dedup):
            b.setEnabled(not locked)

    def _idle(self) -> None:
        self._lock(False)
        self.progress_panel.finish()
        self.btn_cancel.setVisible(False)

    def _start_worker(self, fn, *args, on_success=None) -> None:
        w = Worker(fn, *args)
        self._threads.append(w)
        w.progressed.connect(self._on_progress)
        if on_success:
            w.succeeded.connect(on_success)
        w.failed.connect(self._on_failed)
        w.finished.connect(
            lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_progress(self, msg) -> None:
        if isinstance(msg, dict):
            if msg.get("kind") == "phase":
                self.status.setText(self.ctx.t(msg.get("key", "")))
            elif "total" in msg:
                done = msg.get("done", msg.get("batch", 0))
                self.progress_panel.update_progress(
                    done, msg.get("total", 0),
                    str(msg.get("name") or msg.get("pack") or ""),
                    str(msg.get("osz") or ""))
            elif msg.get("name"):
                self.status.setText(str(msg["name"]))
        else:
            self.status.setText(str(msg))

    def _on_failed(self, msg: str) -> None:
        self._idle()
        self._set_status_lit(msg)
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    def _on_cancel(self) -> None:
        self.services.request_cancel()
        self.btn_cancel.setEnabled(False)
