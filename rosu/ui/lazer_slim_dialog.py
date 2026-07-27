# SPDX-License-Identifier: GPL-3.0-or-later
"""Guided osu!lazer slim-down — the round-trip that stands in for pruning lazer.

osu!lazer cannot be pruned in place: it stores every file under a content hash
and **shares one copy between all sets containing that asset**, so removing a
set's video can break other sets and leaves ``client.realm`` pointing at a file
that no longer exists. Instead of pretending otherwise, this walks the user
through the round-trip that gets the same result safely:

1. **Save** everything in lazer into the Rosu Library.
2. **Delete** the beatmaps inside lazer — done by the user, in lazer's own
   Maintenance screen, because that is the only code that may touch its database.
3. **Check** that it happened: lazer's file store is measured before and after.
4. **Prune** the Library (optional — opens the normal Prune dialog).
5. **Send back** the slimmed Library to lazer.

Every step is explained before it runs and confirmed before it acts; nothing
advances on its own. Steps 1 and 5 are long, so they run on a Worker with a
progress bar and a working Cancel.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout,
)

from ..workers import Worker

_MIB = 1024 ** 2
_GIB = 1024 ** 3

# The store has to lose at least this fraction before "did you delete them?" is
# answered with a yes. A handful of skin/replay files always remain.
_SHRINK_RATIO = 0.5

STEPS = ("intro", "save", "delete", "prune", "send", "done")


def _fmt_size(n: int) -> str:
    n = int(n or 0)
    if n >= _GIB:
        return f"{n / _GIB:,.2f} GB"
    return f"{n / _MIB:,.1f} MB"


class LazerSlimDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.step = "intro"
        self._worker: Worker | None = None
        self._before: dict | None = None   # lazer store size before the deletion
        self._saved: dict | None = None
        t = ctx.t

        self.setWindowTitle(t("lazer_slim_title"))
        self.setMinimumSize(620, 440)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        self.lbl_step = QLabel(objectName="h1")
        self.lbl_step.setWordWrap(True)
        root.addWidget(self.lbl_step)

        self.lbl_body = QLabel(objectName="status")
        self.lbl_body.setWordWrap(True)
        self.lbl_body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_body.setAlignment(Qt.AlignTop)
        root.addWidget(self.lbl_body, 1)

        self.bar = QProgressBar()
        self.bar.setVisible(False)
        root.addWidget(self.bar)

        self.lbl_status = QLabel(objectName="status")
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)

        bar = QHBoxLayout()
        self.btn_close = QPushButton(t("btn_close"), objectName="secondary")
        self.btn_close.clicked.connect(self.reject)
        self.btn_skip = QPushButton(t("lazer_slim_skip"), objectName="secondary")
        self.btn_skip.clicked.connect(self._skip)
        self.btn_next = QPushButton()
        self.btn_next.clicked.connect(self._advance)
        bar.addWidget(self.btn_close)
        bar.addStretch(1)
        bar.addWidget(self.btn_skip)
        bar.addWidget(self.btn_next)
        root.addLayout(bar)

        self._render()

    # -- rendering ------------------------------------------------------------
    def _render(self) -> None:
        t = self.ctx.t
        self.bar.setVisible(False)
        self.btn_skip.setVisible(self.step == "prune")
        self.lbl_step.setText(t(f"lazer_slim_h_{self.step}"))
        self.lbl_body.setText(t(f"lazer_slim_b_{self.step}"))
        self.btn_next.setText(t(f"lazer_slim_btn_{self.step}"))
        self.btn_next.setEnabled(self.step != "done")
        self.btn_close.setText(t("btn_close") if self.step != "done"
                               else t("lazer_slim_finish"))
        if self.step == "done":
            self.btn_next.setVisible(False)

    def _busy(self, on: bool, key: str = "working") -> None:
        self.btn_next.setEnabled(not on)
        self.btn_close.setEnabled(not on)
        self.bar.setRange(0, 0)
        self.bar.setVisible(on)
        if on:
            self.lbl_status.setText(self.ctx.t(key))

    # -- flow -----------------------------------------------------------------
    def _advance(self) -> None:
        handler = {"intro": self._start_save, "save": self._start_save,
                   "delete": self._check_deleted, "prune": self._open_prune,
                   "send": self._start_send}.get(self.step)
        if handler is not None:
            handler()

    def _skip(self) -> None:
        if self.step == "prune":
            self.step = "send"
            self.lbl_status.setText(self.ctx.t("lazer_slim_prune_skipped"))
            self._render()

    # -- step 1: save everything from lazer into the Library ------------------
    def _start_save(self) -> None:
        t = self.ctx.t
        if not self.ctx.services.client_enabled("lazer"):
            self.lbl_status.setText(t("lazer_slim_disabled"))
            return
        self.step = "save"
        self._render()
        self._busy(True, "lazer_slim_saving")
        w = Worker(self.ctx.services.import_from_lazer)
        self._worker = w
        w.progressed.connect(self._on_progress)
        w.succeeded.connect(self._on_saved)
        w.failed.connect(self._on_failed)
        w.finished.connect(self._clear_worker)
        w.start()

    def _on_saved(self, res: dict) -> None:
        t = self.ctx.t
        self._busy(False)
        if not res.get("found"):
            self.lbl_status.setText(t("lazer_slim_not_found"))
            return
        if res.get("cancelled"):
            self.lbl_status.setText(t("lazer_slim_cancelled"))
            return
        if res.get("error"):
            # Say WHICH failure. Collapsing every error into "close lazer and try
            # again" sent the user off to do something that could not possibly
            # help — a missing helper is not a locked database.
            if res["error"] == "helper_missing":
                self.lbl_status.setText(t("lazer_slim_helper_missing"))
            else:
                detail = str(res.get("detail") or "").strip()
                self.lbl_status.setText(
                    t("lazer_slim_save_failed")
                    + (f"\n\n{detail}" if detail else ""))
            return
        # HARD GATE. The next step tells the user to delete their beatmaps out of
        # lazer, so it must not be reachable until every set lazer exported is
        # provably in the Library. "N new sets added" is not proof — an already
        # known set counts as a duplicate and a failed copy counts as nothing.
        missing = res.get("missing") or []
        if missing:
            shown = ", ".join(missing[:5]) + (", …" if len(missing) > 5 else "")
            self.lbl_status.setText(t("lazer_slim_not_all_saved",
                                      n=len(missing), names=shown))
            return
        if not res.get("exported"):
            self.lbl_status.setText(t("lazer_slim_nothing_there"))
            return
        self._saved = res
        # Measure the store BEFORE the user deletes anything, so step 3 has a
        # baseline to compare against.
        self._before = self.ctx.services.lazer_store_stats()
        self.step = "delete"
        self._render()
        self.lbl_status.setText(t(
            "lazer_slim_saved", new=res.get("new", 0),
            total=res.get("exported", 0),
            size=_fmt_size((self._before or {}).get("bytes", 0))))

    # -- step 2/3: the user deletes in lazer, we verify ------------------------
    def _check_deleted(self) -> None:
        t = self.ctx.t
        after = self.ctx.services.lazer_store_stats()
        before_bytes = (self._before or {}).get("bytes", 0)
        if not after.get("found"):
            self.lbl_status.setText(t("lazer_slim_not_found"))
            return
        if before_bytes and after["bytes"] > before_bytes * _SHRINK_RATIO:
            # Not obviously emptied. Say what was measured rather than guessing —
            # and let the user insist, since only they can see lazer's screen.
            self.lbl_status.setText(t(
                "lazer_slim_still_there", before=_fmt_size(before_bytes),
                after=_fmt_size(after["bytes"])))
            from PySide6.QtWidgets import QMessageBox
            if QMessageBox.question(
                    self, t("app_title"), t("lazer_slim_force_continue"),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No) != QMessageBox.Yes:
                return
        else:
            self.lbl_status.setText(t(
                "lazer_slim_emptied", before=_fmt_size(before_bytes),
                after=_fmt_size(after["bytes"])))
        self.step = "prune"
        self._render()

    # -- step 4: optional Library prune ---------------------------------------
    def _open_prune(self) -> None:
        from .prune_dialog import PruneDialog
        dlg = PruneDialog(self.ctx, self)
        if dlg.exec() == QDialog.Accepted and dlg.plan:
            plan = dlg.plan
            job = self.ctx.services.build_prune_apply_job(
                plan["source"], plan["mode"], plan["keys"], plan["freed_estimate"])
            # Runs in the Shortcuts queue like any other prune, so it keeps its
            # progress, cancel and result dialog.
            parent = self.parent()
            if parent is not None and hasattr(parent, "_enqueue"):
                parent._enqueue(job, ("prune", plan["source"], plan["mode"],
                                      tuple(plan["keys"])))
            self.lbl_status.setText(self.ctx.t("lazer_slim_prune_queued",
                                               n=len(plan["keys"])))
        self.step = "send"
        self._render()

    # -- step 5: send the Library back to lazer -------------------------------
    def _start_send(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        t = self.ctx.t
        if QMessageBox.question(
                self, t("app_title"), t("lazer_slim_send_confirm"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) != QMessageBox.Yes:
            return
        self._busy(True, "lazer_slim_sending")
        w = Worker(self.ctx.services.send_library_to_client, "lazer",
                   skip_existing=False)
        self._worker = w
        w.progressed.connect(self._on_progress)
        w.succeeded.connect(self._on_sent)
        w.failed.connect(self._on_failed)
        w.finished.connect(self._clear_worker)
        w.start()

    def _on_sent(self, res: dict) -> None:
        self._busy(False)
        self.step = "done"
        self._render()
        self.lbl_status.setText(self.ctx.t(
            "lazer_slim_sent", sent=res.get("sent", 0)))

    # -- plumbing -------------------------------------------------------------
    def _on_progress(self, msg) -> None:
        if isinstance(msg, dict):
            total = msg.get("total") or 0
            if total:
                self.bar.setRange(0, total)
                self.bar.setValue(msg.get("done") or 0)

    def _on_failed(self, msg: str) -> None:
        self._busy(False)
        self.lbl_status.setText(msg)

    def _clear_worker(self) -> None:
        self._worker = None

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.ctx.services.request_cancel()
            self._worker.wait(5000)
        super().reject()
