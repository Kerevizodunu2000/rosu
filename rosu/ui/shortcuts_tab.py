# SPDX-License-Identifier: GPL-3.0-or-later
"""Shortcuts (Kısayollar) tab: installed-music summary + one-click flows —
lazer↔stable transfer, save-to-Library, unpack→import, export, and dedup.

v1.3 turns every action into a **queued job** (İş Kuyruğu): each button builds a
:class:`~rosu.jobs.Job` and hands it to a :class:`~rosu.ui.job_queue.JobQueueController`,
which runs the job's sub-steps with live status, per-item cancel, and DISK/DRIVE
concurrency (a disk op runs while a Drive upload runs). The buttons stay live so
several jobs can be queued at once.
"""
from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)

from .. import config
from ..jobs import State
from ..workers import Worker
from .job_queue import JobQueueController

_GIB = 1024 ** 3
_MIB = 1024 ** 2

# Glyphs kept to characters present in essentially every font (the heavier
# ✕/✗ variants render as an empty box in some themes).
_GLYPH = {State.PENDING: "○", State.RUNNING: "▸", State.DONE: "✓",
          State.FAILED: "×", State.CANCELLED: "–", State.SKIPPED: "–"}
_STATE_KEY = {
    State.PENDING: "job_state_pending", State.RUNNING: "job_state_running",
    State.DONE: "job_state_done", State.FAILED: "job_state_failed",
    State.CANCELLED: "job_state_cancelled", State.SKIPPED: "job_state_cancelled"}


def _fmt_size(n: int) -> str:
    return f"{n / _MIB:,.1f} MB"


class JobRowWidget(QFrame):
    """One row in the İş Kuyruğu list: title + state chip + cancel, and a line
    per sub-step with a glyph and (for the active step) a thin progress bar.
    ``update_view`` re-reads the Job so a language change or a state change is
    reflected in place (no full rebuild, no flicker)."""

    def __init__(self, job, controller, ctx):
        super().__init__(objectName="jobrow")
        self.setFrameShape(QFrame.StyledPanel)
        self.job = job
        self.controller = controller
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        head = QHBoxLayout()
        self.lbl_title = QLabel(objectName="status")
        self.lbl_state = QLabel(objectName="status")
        self.btn_cancel = QPushButton("×", objectName="secondary")
        self.btn_cancel.setFixedWidth(30)
        self.btn_cancel.setToolTip(ctx.t("job_cancel_tip"))
        self.btn_cancel.clicked.connect(lambda: self.controller.cancel_job(self.job))
        head.addWidget(self.lbl_title, 1)
        head.addWidget(self.lbl_state)
        head.addWidget(self.btn_cancel)
        lay.addLayout(head)

        self.step_rows: list = []
        for step in job.steps:
            r = QHBoxLayout()
            r.setContentsMargins(16, 0, 0, 0)   # indent so steps sit under the title
            lbl = QLabel(objectName="status")
            lbl.setTextFormat(Qt.RichText)
            bar = QProgressBar()
            bar.setMaximumHeight(8)
            bar.setTextVisible(False)
            bar.setVisible(False)
            skip = QPushButton("×", objectName="secondary")
            skip.setFixedWidth(24)
            skip.setToolTip(ctx.t("job_step_skip"))
            skip.clicked.connect(
                lambda _=False, s=step: self.controller.skip_step(self.job, s))
            r.addWidget(lbl, 3)
            r.addWidget(bar, 2)
            r.addWidget(skip)
            lay.addLayout(r)
            self.step_rows.append((step, lbl, bar, skip))

    def update_view(self) -> None:
        t = self.ctx.t
        self.lbl_title.setText(
            f"{_GLYPH.get(self.job.state, '')} "
            + t(self.job.title_key, **self.job.title_kwargs))
        self.lbl_state.setText(t(_STATE_KEY.get(self.job.state, "job_state_pending")))
        self.btn_cancel.setVisible(self.job.state in (State.PENDING, State.RUNNING))
        self.setToolTip(self.job.error or self.job.tooltip or "")
        for step, lbl, bar, skip in self.step_rows:
            # The label is rich text (for the strikethrough), and label_kwargs can
            # carry a user-chosen filename — escape it so an '&' or '<' in the name
            # can't corrupt the render.
            label = html.escape(t(step.key, **step.label_kwargs))
            text = f"{_GLYPH.get(step.state, '○')} {label}"
            if step.state in (State.SKIPPED, State.CANCELLED):
                text = f"<s>{text}</s>"          # struck through — removed / cancelled
            lbl.setText(text)
            if step.state == State.RUNNING and step.total:
                bar.setMaximum(step.total)
                bar.setValue(step.done)
                bar.setVisible(True)
            else:
                bar.setVisible(False)
            # A step can be individually removed only while it's queued or running.
            skip.setVisible(step.state in (State.PENDING, State.RUNNING))


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
        self._rows: dict = {}                     # job.id -> JobRowWidget

        self.queue = JobQueueController(self)
        self.queue.changed.connect(self._refresh_queue)
        self.queue.job_finished.connect(self._on_job_finished)
        self.queue.gate_needed.connect(self._on_gate_needed)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        self.title = QLabel(objectName="h1")
        header.addWidget(self.title, 1)
        # Manual summary refresh — the only way to update the counts when the
        # "auto-refresh a tab on entry" setting is turned off and no job has run.
        self.btn_refresh = QPushButton("⟳", objectName="secondary")
        self.btn_refresh.setFixedWidth(36)
        self.btn_refresh.clicked.connect(self.on_shown)
        header.addWidget(self.btn_refresh)
        root.addLayout(header)

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
        self.export_random = QCheckBox()
        self.export_random_n = QSpinBox()
        self.export_random_n.setRange(1, 100000)
        self.export_random_n.setValue(10)
        self.export_random_n.setEnabled(False)
        self.export_random.toggled.connect(self.export_random_n.setEnabled)
        self.btn_export = QPushButton(objectName="secondary")
        self.btn_export.clicked.connect(self.on_export)
        for w in (self.export_source, self.export_format, self.export_split,
                  self.export_drive, self.export_share, self.export_random,
                  self.export_random_n, self.btn_export):
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

        # -- İş Kuyruğu / job queue --------------------------------------------
        self.jobqueue_box = QGroupBox()
        qlay = QVBoxLayout(self.jobqueue_box)
        self.queue_empty = QLabel(objectName="status")
        qlay.addWidget(self.queue_empty)
        self.queue_container = QWidget()
        self.queue_list = QVBoxLayout(self.queue_container)
        self.queue_list.setContentsMargins(0, 0, 0, 0)
        self.queue_list.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.queue_container)
        scroll.setMinimumHeight(150)
        qlay.addWidget(scroll)
        qbtns = QHBoxLayout()
        qbtns.addStretch(1)
        self.btn_clear_finished = QPushButton(objectName="secondary")
        self.btn_clear_finished.clicked.connect(self.queue.clear_finished)
        qbtns.addWidget(self.btn_clear_finished)
        qlay.addLayout(qbtns)
        root.addWidget(self.jobqueue_box, 1)

        bottom = QHBoxLayout()
        self.status = QLabel(objectName="status")
        bottom.addWidget(self.status, 1)
        root.addLayout(bottom)

        self._refresh_queue()

    # -- i18n ------------------------------------------------------------------
    def retranslate(self) -> None:
        t = self.ctx.t
        self.title.setText(t("tab_shortcuts"))
        self.btn_refresh.setToolTip(t("sc_refresh"))
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
        self.export_random.setText(t("sc_export_random"))
        self.export_random.setToolTip(t("tip_export_random"))
        self.export_random_n.setToolTip(t("tip_export_random"))
        self.btn_export.setText(t("btn_export"))
        self.btn_dedup.setText(t("btn_dedup"))
        self.btn_dedup.setToolTip(t("tip_dedup"))
        self.jobqueue_box.setTitle(t("sc_jobqueue_title"))
        self.btn_clear_finished.setText(t("job_clear_finished"))
        self.queue_empty.setText(t("queue_empty"))
        self._render_summary()
        self._sync_drive_controls()
        self._refresh_queue()
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
            head, val = self.sum_labels[key]
            if s is None:
                val.setText("—")
                continue
            info = s.get(key, {})
            tip = ""
            if key in ("library", "drive"):
                val.setText(t("sc_count_fmt", n=info.get("count", 0)))
            elif not info.get("installed"):
                val.setText(t("sc_not_installed"))
            elif info.get("count") is None:
                val.setText(t("sc_installed"))
            else:
                val.setText(t("sc_count_fmt", n=info["count"]))
                if key == "lazer" and info.get("from_library"):
                    tip = t("sc_lazer_from_library")   # explain where the number came from
            head.setToolTip(tip)
            val.setToolTip(tip)

    # -- actions: build a job and queue it -------------------------------------
    def on_transfer(self, source: str, target: str) -> None:
        t = self.ctx.t
        if source == target:
            return
        # Validate up front (as services.transfer_between_clients did) so an
        # invalid pick is reported immediately instead of failing in the queue.
        target_exe = (self.ctx.cfg.osu_stable_exe or config.detect_stable_exe()
                      if target == "stable"
                      else self.ctx.cfg.osu_lazer_exe or config.detect_osu_exe())
        if not target_exe or not Path(target_exe).exists():
            QMessageBox.warning(self, t("app_title"), t("sc_no_target_exe"))
            return
        self.queue.enqueue(self.services.build_transfer_job(source, target))
        self._set_status("job_added")

    def on_save(self, sources) -> None:
        self.queue.enqueue(self.services.build_save_job(sources))
        self._set_status("job_added")

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
        self.queue.enqueue(self.services.build_unpack_job(targets, skip))
        self._set_status("job_added")

    def on_export(self) -> None:
        t = self.ctx.t
        source = self.export_source.currentData()
        fmt = self.export_format.currentData() or "zip"
        split = self.export_split.currentData()
        upload = self.export_drive.isChecked()
        share = self.export_share.isChecked()
        limit = self.export_random_n.value() if self.export_random.isChecked() else None
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
        job = self.services.build_export_job(source, dest_base, fmt, split,
                                             upload, share, limit)
        src_label = t(f"sc_source_{source}")
        job.title_kwargs["source"] = src_label              # translated in the title
        for st in job.steps:
            if st.key == "job_step_gather":
                st.label_kwargs["source"] = src_label       # ...and in the gather step
        self.queue.enqueue(job)
        self._set_status("job_added")

    def on_dedup(self) -> None:
        """Queue a dedup job: it scans first, then WAITS at a gate for the preview
        confirmation before recycling anything (240-file safety)."""
        self.queue.enqueue(self.services.build_dedup_job())
        self._set_status("job_added")

    # -- queue reactions -------------------------------------------------------
    def _refresh_queue(self) -> None:
        jobs = self.queue.jobs
        ids = {j.id for j in jobs}
        for jid in list(self._rows):
            if jid not in ids:
                w = self._rows.pop(jid)
                self.queue_list.removeWidget(w)
                w.deleteLater()
        for job in jobs:
            row = self._rows.get(job.id)
            if row is None:
                row = JobRowWidget(job, self.queue, self.ctx)
                self._rows[job.id] = row
                # insert above the trailing stretch so rows stack top-down
                self.queue_list.insertWidget(self.queue_list.count() - 1, row)
            row.update_view()
        self.queue_empty.setVisible(not jobs)

    def _on_gate_needed(self, job) -> None:
        """A dedup job finished scanning — show the preview + confirm before it
        recycles anything. No duplicates → skip the remove step cleanly."""
        t = self.ctx.t
        plan = job.ctx.get("plan", {})
        if plan.get("count", 0) == 0:
            self._set_status("sc_dedup_none")
            self.queue.skip_gate(job)
            return
        reply = QMessageBox.question(
            self, t("app_title"),
            t("sc_dedup_confirm", count=plan["count"],
              freed=_fmt_size(plan["freed_bytes"])),
            QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel)
        if reply == QMessageBox.Ok:
            self.queue.confirm_gate(job)
        else:
            self.queue.cancel_job(job)

    def _on_job_finished(self, job) -> None:
        """Route a completed job's result to the matching presenter (preserving
        the v1.2 completion dialogs), then refresh the installed-summary counts."""
        res = job.result or {}
        presenter = {
            "transfer": self._present_transfer, "save": self._present_save,
            "unpack": self._present_unpack, "export": self._present_export,
            "dedup": self._present_dedup,
        }.get(job.kind)
        if presenter is not None:
            presenter(res)
        self.on_shown()

    def _present_transfer(self, res) -> None:
        self._set_status("sc_transfer_done", found=res.get("found", 0),
                         transferred=res.get("transferred", 0),
                         skipped=res.get("skipped", 0))

    def _present_save(self, res) -> None:
        new = sum(v.get("new", 0) for v in res.values() if isinstance(v, dict))
        self._set_status("sc_save_done", new=new)
        self.mw.search.reload()

    def _present_unpack(self, res) -> None:
        ex = res.get("extract", {})
        skipped = sum(v.get("skipped", 0) for v in res.get("imports", {}).values())
        self._set_status("sc_unpack_done2", tracks=ex.get("tracks", 0), skipped=skipped)
        self.mw.search.reload()

    def _present_export(self, res) -> None:
        t = self.ctx.t
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

    def _present_dedup(self, res) -> None:
        if res.get("removed", 0) == 0:
            self._set_status("sc_dedup_none")
        else:
            self._set_status("sc_dedup_done", removed=res["removed"],
                             freed=_fmt_size(res["freed_bytes"]))

    # -- worker plumbing (summary refresh only) --------------------------------
    def _set_status(self, key: str, **kwargs) -> None:
        """Set a translatable status message, remembering it so a later language
        change re-renders it in the new language (retranslate)."""
        self._status_key, self._status_kwargs = key, kwargs
        self.status.setText(self.ctx.t(key, **kwargs))

    def _set_status_lit(self, text: str) -> None:
        """Set a non-translatable status line (an error message or a path)."""
        self._status_key, self._status_kwargs = None, {}
        self.status.setText(text)

    def _start_worker(self, fn, *args, on_success=None) -> None:
        w = Worker(fn, *args)
        self._threads.append(w)
        if on_success:
            w.succeeded.connect(on_success)
        w.failed.connect(self._on_failed)
        w.finished.connect(
            lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_failed(self, msg: str) -> None:
        self._set_status_lit(msg)
