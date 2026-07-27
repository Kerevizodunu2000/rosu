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
import math
import os
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

_STAR_CAP = 12.0   # star-range export: max = cap = "no upper bound"

from .. import config
from ..jobs import State
from ..workers import Worker
from .job_queue import JobQueueController
from .links import wire_link_hover

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


def _norm_path(p) -> str:
    """Compare two destinations the way the filesystem does — absolute, and
    case-insensitively on Windows, so ``C:\\x\\Pack`` and ``c:/x/pack`` are not
    mistaken for two different export targets."""
    return os.path.normcase(os.path.abspath(str(p)))


def _copy_to_clipboard(text: str) -> bool:
    """Put ``text`` on the clipboard; ``False`` if this platform has none (the
    offscreen Qt plugin used by the tests, for instance). Never raises — a
    missing clipboard must not take the dialog down with it."""
    try:
        cb = QGuiApplication.clipboard()
    except Exception:
        return False
    if cb is None:
        return False
    cb.setText(text)
    return True


def _describe_job(job, t) -> str:
    """One line spelling out every choice behind a queued job.

    The row title carries only a job's kind and (for exports) the archive name, so
    two exports that differ in random-N, star range, split size or upload/share
    rendered as identical rows — the user had no way to tell which was which, or
    even that the second one had really been queued. Built from ``job.ctx["options"]``
    (plain data written by the service layer) and translated here, so switching
    language re-renders it correctly.
    """
    opts = job.ctx.get("options") or {}
    if not opts:
        return ""
    bits: list[str] = []
    if job.kind == "export":
        bits.append(t(f"sc_source_{opts['source']}"))
        bits.append((opts.get("fmt") or "zip").upper())
        limit = opts.get("limit")
        bits.append(t("job_opt_random", n=limit) if limit else t("job_opt_all"))
        rng = opts.get("star_range")
        if rng:
            lo, hi = rng
            bits.append(t("job_opt_stars_min", lo=f"{lo:.2f}") if math.isinf(hi)
                        else t("job_opt_stars", lo=f"{lo:.2f}", hi=f"{hi:.2f}"))
        if opts.get("split_bytes"):
            bits.append(t("job_opt_split", size=_fmt_size(opts["split_bytes"])))
        if opts.get("upload"):
            bits.append(t("job_opt_upload"))
        if opts.get("share"):
            bits.append(t("job_opt_share"))
        if opts.get("archive_name"):
            bits.append(str(opts["archive_name"]))
        if opts.get("dest"):
            bits.append(t("job_opt_dest", path=opts["dest"]))
    elif job.kind == "unpack":
        bits.append(t("job_opt_only_new") if opts.get("skip_duplicates")
                    else t("job_opt_every_set"))
    elif job.kind == "prune":
        if opts.get("prune_source"):
            bits.append(t(f"prune_source_{opts['prune_source']}"))
        if opts.get("mode"):
            bits.append(t(f"prune_mode_{opts['mode']}"))
        if opts.get("sets"):
            bits.append(t("prune_n_sets", n=opts["sets"]))
        if opts.get("freed_estimate"):
            bits.append(t("prune_frees", size=_fmt_size(opts["freed_estimate"])))
    elif job.kind == "restore" and opts.get("restore_sets"):
        bits.append(t("prune_n_sets", n=opts["restore_sets"]))
    if not bits:
        return ""
    line = "   ·   ".join(bits)
    # Once it has finished, show the link it actually produced.
    drive = (job.result or {}).get("drive") or {}
    links = [f["link"] for f in drive.get("files", []) if f.get("link")]
    if links:
        line += "\n" + t("job_opt_link", url=links[0])
    return line


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
        # #iconbtn, not #secondary: the base QPushButton rule has 16px side
        # padding, so a 30px-wide button had no room left for its label and
        # drew as an empty box.
        self.btn_cancel = QPushButton("×", objectName="iconbtn")
        self.btn_cancel.setFixedSize(30, 26)
        self.btn_cancel.setToolTip(ctx.t("job_cancel_tip"))
        self.btn_cancel.clicked.connect(lambda: self.controller.cancel_job(self.job))
        head.addWidget(self.lbl_title, 1)
        head.addWidget(self.lbl_state)
        head.addWidget(self.btn_cancel)
        lay.addLayout(head)

        self.lbl_detail = QLabel(objectName="status")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setContentsMargins(16, 0, 0, 0)
        self.lbl_detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_detail.setVisible(False)
        lay.addWidget(self.lbl_detail)

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
            skip = QPushButton("×", objectName="iconbtn")
            skip.setFixedSize(26, 22)
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
        detail = _describe_job(self.job, t)
        self.lbl_detail.setText(detail)
        self.lbl_detail.setVisible(bool(detail))
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
        self._last_signature = None               # guards a CONSECUTIVE repeat only

        self.queue = JobQueueController(self)
        self.queue.changed.connect(self._refresh_queue)
        self.queue.job_finished.connect(self._on_job_finished)
        self.queue.job_failed.connect(self._on_job_failed)
        self.queue.gate_needed.connect(self._on_gate_needed)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)   # match every other tab's root spacing

        header = QHBoxLayout()
        self.title = QLabel(objectName="h1")
        header.addWidget(self.title, 1)
        # Manual summary refresh — the only way to update the counts when the
        # "auto-refresh a tab on entry" setting is turned off and no job has run.
        self.btn_refresh = QPushButton("⟳", objectName="iconbtn")
        self.btn_refresh.setFixedSize(36, 30)
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

        # Why-is-something-missing hint (v1.4): when a client is turned off in
        # Settings its buttons vanish — this line says so, so the user is never
        # left staring at a tab that silently lost half its controls.
        self.disabled_hint = QLabel(objectName="status")
        self.disabled_hint.setWordWrap(True)
        self.disabled_hint.setVisible(False)
        root.addWidget(self.disabled_hint)

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
        # v1.6: star-range export — keep only Library sets whose hardest diff's star
        # is in [★≥, ★≤]. lo=0 & hi=cap → no star filter. Prefilled from the Search
        # histogram's "Export this range".
        self.export_star_lo = QDoubleSpinBox()
        self.export_star_lo.setRange(0.0, _STAR_CAP)
        self.export_star_lo.setDecimals(1)
        self.export_star_lo.setSingleStep(0.1)
        self.export_star_lo.setPrefix("★≥ ")
        self.export_star_lo.setSpecialValueText("★≥ —")
        self.export_star_hi = QDoubleSpinBox()
        self.export_star_hi.setRange(0.0, _STAR_CAP)
        self.export_star_hi.setDecimals(1)
        self.export_star_hi.setSingleStep(0.1)
        self.export_star_hi.setPrefix("★≤ ")
        self.export_star_hi.setValue(_STAR_CAP)
        self.btn_export = QPushButton(objectName="secondary")
        self.btn_export.clicked.connect(self.on_export)
        for w in (self.export_source, self.export_format, self.export_split,
                  self.export_drive, self.export_share, self.export_random,
                  self.export_random_n, self.export_star_lo, self.export_star_hi,
                  self.btn_export):
            erow.addWidget(w)
        erow.addStretch(1)
        root.addWidget(self.export_box)

        # -- dedup Library extra -----------------------------------------------
        drow = QHBoxLayout()
        self.btn_dedup = QPushButton(objectName="secondary")
        self.btn_dedup.clicked.connect(self.on_dedup)
        drow.addWidget(self.btn_dedup)
        
        self.btn_prune = QPushButton(objectName="secondary")
        self.btn_prune.clicked.connect(self.on_prune)
        drow.addWidget(self.btn_prune)

        # Undo prune in bulk. Prune's Recycle-Bin copy is the local undo, but it
        # only lasts until the bin is emptied — this re-downloads the full sets.
        self.btn_restore = QPushButton(objectName="secondary")
        self.btn_restore.clicked.connect(self.on_restore_pruned)
        drow.addWidget(self.btn_restore)

        # Guided lazer round-trip (save → you delete in lazer → verify → prune →
        # send back), since lazer itself cannot be pruned in place.
        self.btn_lazer_flow = QPushButton(objectName="secondary")
        self.btn_lazer_flow.clicked.connect(self.on_lazer_slim)
        drow.addWidget(self.btn_lazer_flow)
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
        # Always literal text: error strings can carry angle brackets (e.g. an
        # HTML-ish upstream error) and must never be auto-detected as rich text.
        self.status.setTextFormat(Qt.PlainText)
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
        self.export_star_lo.setToolTip(t("tip_export_star"))
        self.export_star_hi.setToolTip(t("tip_export_star"))
        self.btn_export.setText(t("btn_export"))
        self.btn_dedup.setText(t("btn_dedup"))
        self.btn_dedup.setToolTip(t("tip_dedup"))
        self.btn_prune.setText(t("btn_prune"))
        self.btn_prune.setToolTip(t("tip_prune"))
        self.btn_restore.setText(t("btn_restore_pruned"))
        self.btn_restore.setToolTip(t("tip_restore_pruned"))
        self.btn_lazer_flow.setText(t("btn_lazer_slim"))
        self.btn_lazer_flow.setToolTip(t("tip_lazer_slim"))
        self.jobqueue_box.setTitle(t("sc_jobqueue_title"))
        self.btn_clear_finished.setText(t("job_clear_finished"))
        self.queue_empty.setText(t("queue_empty"))
        self._render_summary()
        self.refresh_client_visibility()
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
        cfg = self.ctx.cfg
        for data, key in (("library", "sc_source_library"),
                          ("drive", "sc_source_drive"), ("lazer", "sc_source_lazer"),
                          ("stable", "sc_source_stable"),
                          ("merged", "sc_source_merged")):
            if data == "lazer" and not cfg.lazer_enabled:
                continue   # a disabled client isn't offered as an export source (v1.4)
            if data == "stable" and not cfg.stable_enabled:
                continue
            self.export_source.addItem(t(key), data)
        self.export_format.addItem("zip", "zip")
        self.export_format.addItem("7z", "7z")
        self.export_split.addItem(t("sc_split_none"), None)
        self.export_split.addItem(t("sc_split_1g"), _GIB)
        self.export_split.addItem(t("sc_split_500m"), 500 * _MIB)
        for combo, data in zip((self.export_source, self.export_format,
                                self.export_split), keep, strict=True):
            i = combo.findData(data)
            if i >= 0:
                combo.setCurrentIndex(i)
            combo.blockSignals(False)

    # -- summary ---------------------------------------------------------------
    def on_shown(self) -> None:
        self.refresh_client_visibility()
        self._sync_drive_controls()
        # Make the refresh VISIBLE: blank the counts to a loading marker and
        # disable ⟳ until the fresh numbers land, so pressing it clearly does
        # something even when the re-count is near-instant.
        self.btn_refresh.setEnabled(False)
        for key in ("lazer", "stable", "library", "drive"):
            self.sum_labels[key][1].setText("…")
        self._start_worker(self.services.installed_summary,
                           on_success=self._on_summary,
                           on_failure=self._summary_failed)

    def _summary_failed(self, msg: str) -> None:
        self.btn_refresh.setEnabled(True)
        self._render_summary()          # restore the last known numbers
        self._on_failed(msg)

    def refresh_client_visibility(self) -> None:
        """A disabled client's controls VANISH (v1.4 per-client on/off) — its
        summary column, its save/unpack buttons, both transfer directions
        (transfer needs both clients) and its export-source entry — and a hint
        line explains what's hidden and why, so nothing looks silently broken."""
        t = self.ctx.t
        cfg = self.ctx.cfg
        lz, st = cfg.lazer_enabled, cfg.stable_enabled
        both = lz and st
        for key, on in (("lazer", lz), ("stable", st)):
            head, val = self.sum_labels[key]
            head.setVisible(on)
            val.setVisible(on)
        for b, on in ((self.btn_save_lazer, lz), (self.btn_save_stable, st),
                      (self.btn_unpack_lazer, lz), (self.btn_unpack_stable, st),
                      (self.btn_unpack_both, both),
                      (self.btn_l2s, both), (self.btn_s2l, both)):
            b.setVisible(bool(on))
        self.transfer_box.setVisible(both)     # transfer needs BOTH clients
        self.save_box.setVisible(lz or st)
        self.unpack_box.setVisible(lz or st)
        disabled = [n for n, on in (("osu!lazer", lz), ("osu!(stable)", st)) if not on]
        self.disabled_hint.setVisible(bool(disabled))
        if disabled:
            self.disabled_hint.setText(
                t("sc_client_hidden", clients=" + ".join(disabled)))
        self._fill_export_combos()             # drop a disabled client as a source

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
        if not checked:
            return
        if not self.export_drive.isChecked():
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("sc_share_needs_upload"))
            self.export_share.setChecked(False)   # a link needs the upload
            return
        # "Anyone with the link" is a PUBLIC share of copyrighted beatmap content —
        # require an informed opt-in every time it's enabled.
        if QMessageBox.question(
                self, self.ctx.t("app_title"), self.ctx.t("sc_share_public_warn"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            self.export_share.blockSignals(True)
            self.export_share.setChecked(False)
            self.export_share.blockSignals(False)

    def _on_summary(self, summary) -> None:
        self.btn_refresh.setEnabled(True)
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
            elif key == "lazer" and info.get("from_library"):
                # Show it as "N recorded" (not a plain total) + explain in the tooltip,
                # since Rosu can't read osu!lazer's real library size.
                val.setText(t("sc_count_recorded", n=info["count"]))
                tip = t("sc_lazer_from_library")
            else:
                val.setText(t("sc_count_fmt", n=info["count"]))
            head.setToolTip(tip)
            val.setToolTip(tip)

    # -- actions: build a job and queue it -------------------------------------
    def on_transfer(self, source: str, target: str) -> None:
        t = self.ctx.t
        if source == target:
            return
        if not (self.services.client_enabled(source)
                and self.services.client_enabled(target)):
            QMessageBox.warning(self, t("app_title"), t("sc_client_disabled"))
            return
        # Validate up front (as services.transfer_between_clients did) so an
        # invalid pick is reported immediately instead of failing in the queue.
        target_exe = (self.ctx.cfg.osu_stable_exe or config.detect_stable_exe()
                      if target == "stable"
                      else self.ctx.cfg.osu_lazer_exe or config.detect_osu_exe())
        if not target_exe or not Path(target_exe).exists():
            QMessageBox.warning(self, t("app_title"), t("sc_no_target_exe"))
            return
        self._enqueue(self.services.build_transfer_job(source, target),
                      ("transfer", source, target))

    def on_save(self, sources) -> None:
        self._enqueue(self.services.build_save_job(sources),
                      ("save", tuple(sources)))

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
        self._enqueue(self.services.build_unpack_job(targets, skip),
                      ("unpack", tuple(targets), skip))

    def on_export(self) -> None:
        t = self.ctx.t
        source = self.export_source.currentData()
        fmt = self.export_format.currentData() or "zip"
        split = self.export_split.currentData()
        upload = self.export_drive.isChecked()
        share = self.export_share.isChecked()
        limit = self.export_random_n.value() if self.export_random.isChecked() else None
        lo = self.export_star_lo.value()
        hi = self.export_star_hi.value()
        # ★≤ left at the cap (or 0 = its "off" special value) means NO upper bound —
        # use +inf, not the literal 12★ cap, so maps above 12★ aren't silently dropped.
        upper = hi if 0 < hi < _STAR_CAP else float("inf")
        star_range = None if (lo <= 0 and upper == float("inf")) else (lo, upper)
        if upload and not self.services.drive_status().get("connected"):
            QMessageBox.information(self, t("app_title"), t("drive_connect_first"))
            return
        suffix = ".7z" if fmt == "7z" else ".zip"
        # Timestamped: the default used to be a constant per source
        # ("rosu-export-library.zip"), so accepting it twice sent both jobs to the
        # SAME path — and since the DRIVE lane overlaps the DISK lane, job 2's
        # archive could land on the very file job 1 was still uploading.
        stamp = time.strftime("%Y%m%d-%H%M%S")
        default_name = f"rosu-export-{source}-{stamp}{suffix}"
        path, _ = QFileDialog.getSaveFileName(
            self, t("sc_export_choose"), default_name, f"Archive (*{suffix})")
        if not path:
            return
        dest_base = Path(path)
        if dest_base.suffix.lower() in (".zip", ".7z"):
            dest_base = dest_base.with_suffix("")   # exporter re-appends the suffix
        if self._dest_in_use(dest_base):
            # Belt and braces: even a hand-typed name can collide with a job that
            # is still queued or uploading. Refuse rather than clobber it.
            QMessageBox.warning(self, t("app_title"),
                                t("sc_export_dest_busy", name=dest_base.name))
            return
        if split and not self._confirm_volume_overwrite(dest_base, suffix):
            return
        job = self.services.build_export_job(source, dest_base, fmt, split,
                                             upload, share, limit, star_range)
        src_label = t(f"sc_source_{source}")
        job.title_kwargs["source"] = src_label              # translated in the title
        for st in job.steps:
            if st.key == "job_step_gather":
                st.label_kwargs["source"] = src_label       # ...and in the gather step
        # Signature deliberately EXCLUDES the destination: it now carries a
        # timestamp, so two otherwise-identical exports would never match.
        self._enqueue(job, ("export", source, fmt, split, upload, share, limit,
                            star_range))

    def on_restore_pruned(self) -> None:
        """Bulk-undo prune: re-download every pruned set at full size."""
        t = self.ctx.t
        n = self.services.pruned_count()
        if n == 0:
            QMessageBox.information(self, t("app_title"), t("sc_restore_none"))
            return
        if QMessageBox.question(
                self, t("app_title"), t("sc_restore_confirm", n=n),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) != QMessageBox.Yes:
            return
        self._enqueue(self.services.build_restore_pruned_job(), ("restore", n))

    def on_lazer_slim(self) -> None:
        """The guided osu!lazer round-trip (see :mod:`rosu.ui.lazer_slim_dialog`)."""
        from .lazer_slim_dialog import LazerSlimDialog
        LazerSlimDialog(self.ctx, self).exec()
        self.on_shown()

    def _enqueue(self, job, signature=None) -> bool:
        """Queue a job — but if this is the IDENTICAL action the user just queued,
        ask first.

        Only a *consecutive* repeat is questioned. If anything else was queued in
        between, repeating an action is almost certainly deliberate (export ten
        different ranges in a row) and must not nag. Comparing against the last
        enqueued signature alone keeps that rule exact and stateless.
        """
        if signature is not None and signature == self._last_signature:
            t = self.ctx.t
            if QMessageBox.question(
                    self, t("app_title"), t("sc_job_repeat_confirm"),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No) != QMessageBox.Yes:
                return False
        self._last_signature = signature
        self.queue.enqueue(job)
        self._set_status("job_added")
        return True

    def _dest_in_use(self, dest_base: Path) -> bool:
        """Is another export job — queued, running or uploading — already writing
        to this destination? Two jobs sharing a destination means the second one's
        archive overwrites the first's *while the first is being uploaded*, so the
        bytes that reach Drive are not the bytes that job exported."""
        target = _norm_path(dest_base)
        for job in self.queue.jobs:
            if job.kind != "export" or job.state in (
                    State.DONE, State.FAILED, State.CANCELLED):
                continue
            other = job.ctx.get("dest_base")
            if other and _norm_path(other) == target:
                return True
        return False

    def _confirm_volume_overwrite(self, dest_base: Path, suffix: str) -> bool:
        """A split export writes ``<stem>.partNN<suffix>`` volumes, which the save
        dialog never vets (it only checked the single name the user typed). Ask
        before overwriting any that already exist."""
        prefix = f"{dest_base.stem}.part"
        try:
            hits = sorted(p.name for p in dest_base.parent.iterdir()
                          if p.name.startswith(prefix)
                          and p.name.lower().endswith(suffix))
        except OSError:
            return True     # can't list the folder — the exporter will report it
        if not hits:
            return True
        t = self.ctx.t
        shown = ", ".join(hits[:5]) + (", …" if len(hits) > 5 else "")
        return QMessageBox.question(
            self, t("app_title"),
            t("sc_export_overwrite_volumes", n=len(hits), names=shown),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def prefill_star_range(self, lo: float, hi: float) -> None:
        """Set the export source to Library and fill the star range (from the Search
        histogram's 'Export this range'). The user then picks format/destination."""
        idx = self.export_source.findData("library")
        if idx >= 0:
            self.export_source.setCurrentIndex(idx)
        self.export_star_lo.setValue(max(0.0, min(lo, _STAR_CAP)))
        self.export_star_hi.setValue(max(0.0, min(hi, _STAR_CAP)))
        self._set_status("sc_export_star_prefilled")

    def on_dedup(self) -> None:
        """Queue a dedup job: it scans first, then WAITS at a gate for the preview
        confirmation before recycling anything (240-file safety)."""
        self._enqueue(self.services.build_dedup_job(), ("dedup",))

    def on_prune(self) -> None:
        """Open the Prune dialog — source, mode, how many, in what order, and a
        per-set preview — then queue only what the user confirmed there.

        The old button silently used the Settings ``prune_mode`` over the whole
        Library and showed nothing but a total after it had already decided.
        """
        from .prune_dialog import PruneDialog
        dlg = PruneDialog(self.ctx, self)
        if dlg.exec() != QDialog.Accepted or not dlg.plan:
            return
        plan = dlg.plan
        job = self.services.build_prune_apply_job(
            plan["source"], plan["mode"], plan["keys"], plan["freed_estimate"])
        self._enqueue(job, ("prune", plan["source"], plan["mode"],
                            tuple(plan["keys"])))

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
        if job.kind == "dedup":
            self._handle_dedup_gate(job)
        elif job.kind == "prune":
            self._handle_prune_gate(job)
            
    def _handle_dedup_gate(self, job) -> None:
        """A dedup job finished scanning - show the preview + confirm before it
        recycles anything. No duplicates -> skip the remove step cleanly."""
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

    def _handle_prune_gate(self, job) -> None:
        """A prune job finished scanning - show the preview + confirm."""
        t = self.ctx.t
        plan = job.ctx.get("plan", {})
        if plan.get("count", 0) == 0:
            self._set_status("sc_prune_none")
            self.queue.skip_gate(job)
            return
        reply = QMessageBox.question(
            self, t("app_title"),
            t("sc_prune_confirm", count=plan["count"], freed=_fmt_size(plan["total_bytes"])),
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
            "prune": self._present_prune,
            "restore": self._present_restore,
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
        body = [html.escape(msg), "", html.escape(t("sc_export_saved_to", path=location))]
        body += [f"• {html.escape(Path(a).name)}" for a in archives]
        if drive.get("error"):
            body += ["", html.escape(t("sc_export_upload_failed"))]
        if links:
            body += ["", html.escape(t("sc_export_link"))]
            body += [f'<a href="{html.escape(u, quote=True)}">{html.escape(u)}</a>'
                     for u in links]
        self._export_result_dialog("<br>".join(body), links)
        if shared_no_link:
            # The file(s) were made public but the link couldn't be fetched — the
            # user must know so they can review/revoke the share in Drive.
            QMessageBox.warning(self, t("app_title"), t("sc_export_shared_no_link"))

    def build_export_result_dialog(self, body_html: str, links: list[str]) -> QDialog:
        """Export-complete dialog whose share link is actually usable.

        This used to be ``QMessageBox.information``, which renders **plain text**:
        the URL had no anchor, could not be reliably selected, and never reached
        the clipboard — the link was correct and genuinely public, but inert. A
        rich-text QLabel with ``openExternalLinks`` gives a real clickable anchor
        (and ``wire_link_hover`` shows the target, as everywhere else in the app);
        the link is put on the clipboard the moment the dialog is built, with an
        explicit Copy button that does NOT close the dialog.

        Returns the dialog rather than showing it, so it can be built and
        inspected without a blocking ``exec()``.
        """
        t = self.ctx.t
        dlg = QDialog(self)
        dlg.setWindowTitle(t("app_title"))
        dlg.setMinimumWidth(460)
        lay = QVBoxLayout(dlg)
        label = QLabel(body_html)
        label.setTextFormat(Qt.RichText)
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(Qt.TextBrowserInteraction)  # clickable + selectable
        wire_link_hover(label)
        lay.addWidget(label)
        dlg.body_label = label     # named for the tests

        note = QLabel(objectName="status")
        note.setWordWrap(True)
        note.setVisible(bool(links))
        lay.addWidget(note)

        bar = QHBoxLayout()
        bar.addStretch(1)
        if links:
            def copy_links() -> None:
                if _copy_to_clipboard("\n".join(links)):
                    note.setText(t("sc_export_link_copied"))

            copy_links()   # already on the clipboard before the user asks
            btn_copy = QPushButton(t("btn_copy_link"), objectName="secondary")
            btn_copy.clicked.connect(copy_links)
            bar.addWidget(btn_copy)
        btn_close = QPushButton(t("btn_close"))
        btn_close.setDefault(True)
        btn_close.clicked.connect(dlg.accept)
        bar.addWidget(btn_close)
        lay.addLayout(bar)
        return dlg

    def _export_result_dialog(self, body_html: str, links: list[str]) -> None:
        self.build_export_result_dialog(body_html, links).exec()

    def _on_job_failed(self, job) -> None:
        """A job FAILED (a step raised). For an export whose archives were already
        written, tell the user the export itself is safe on disk and only the
        Drive upload failed — otherwise surface the error in the status line
        (the queue row shows the × and carries the detail as a tooltip)."""
        t = self.ctx.t
        err = job.error or ""
        if job.kind == "export" and job.ctx.get("written"):
            archives = [str(a) for a in job.ctx["written"]]
            location = str(Path(archives[0]).parent)
            body = [t("sc_export_done", count=len(job.ctx.get("files", [])),
                      archives=len(archives)),
                    "", t("sc_export_saved_to", path=location)]
            body += [f"• {Path(a).name}" for a in archives]
            body += ["", t("sc_export_upload_failed")]
            if err:
                body.append(err)
            self._set_status("sc_export_upload_failed")
            # PlainText: the error detail comes from an exception string and must
            # not be auto-detected as rich text by QMessageBox's AutoText default.
            box = QMessageBox(QMessageBox.Warning, t("app_title"),
                              "\n".join(body), QMessageBox.Ok, self)
            box.setTextFormat(Qt.PlainText)
            box.exec()
        elif err:
            self._set_status_lit(err)
        self.on_shown()   # refresh the counts even after a failure

    def _present_dedup(self, res) -> None:
        if res.get("removed", 0) == 0:
            self._set_status("sc_dedup_none")
        else:
            self._set_status("sc_dedup_done", removed=res["removed"],
                             freed=_fmt_size(res["freed_bytes"]))

    def _present_restore(self, res) -> None:
        repaired = res.get("repaired", 0)
        failed = len(res.get("failed", []))
        if repaired and not failed:
            self._set_status("sc_restore_done", n=repaired)
        elif repaired:
            self._set_status("sc_restore_partial", n=repaired, failed=failed)
        else:
            self._set_status("sc_restore_failed", failed=failed)
        self.mw.search.reload()

    def _present_prune(self, res) -> None:
        if res.get("pruned", 0) == 0:
            self._set_status("sc_prune_none")
        else:
            self._set_status("sc_prune_done", pruned=res["pruned"],
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

    def _start_worker(self, fn, *args, on_success=None, on_failure=None) -> None:
        w = Worker(fn, *args)
        self._threads.append(w)
        if on_success:
            w.succeeded.connect(on_success)
        w.failed.connect(on_failure or self._on_failed)
        w.finished.connect(
            lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_failed(self, msg: str) -> None:
        self._set_status_lit(msg)
