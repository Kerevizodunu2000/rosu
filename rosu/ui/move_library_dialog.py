# SPDX-License-Identifier: GPL-3.0-or-later
"""Move-the-Library dialog (v1.9): pick a destination, see the plan (files,
size, free space, anything in the way), choose whether the old copies go to
the Recycle Bin afterwards, confirm through a countdown. The move itself runs
as a queued job (:meth:`LibraryMoveMixin.move_library`)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QPushButton, QVBoxLayout,
)

from ..workers import Worker
from .countdown_dialog import CountdownConfirmDialog


def _fmt_size(n) -> str:
    n = int(n or 0)
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:,.2f} GB"
    return f"{n / 1024 ** 2:,.1f} MB"


class MoveLibraryDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.plan: dict | None = None
        self._preview: dict | None = None
        self._worker: Worker | None = None
        self._seq = 0
        t = ctx.t
        self.setWindowTitle(t("mv_title"))
        self.setMinimumWidth(620)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        intro = QLabel(t("mv_intro"), objectName="status")
        intro.setWordWrap(True)
        root.addWidget(intro)
        current = QLabel(t("mv_current", path=str(ctx.cfg.library_path)))
        current.setTextFormat(Qt.PlainText)
        current.setWordWrap(True)
        root.addWidget(current)

        row = QHBoxLayout()
        self.dest = QLineEdit()
        self.dest.setPlaceholderText(t("mv_dest_placeholder"))
        self.dest.editingFinished.connect(self.check)
        browse = QPushButton(t("btn_browse"), objectName="secondary")
        browse.clicked.connect(self._browse)
        row.addWidget(self.dest, 1)
        row.addWidget(browse)
        root.addLayout(row)

        self.bar = QProgressBar()
        self.bar.setVisible(False)
        root.addWidget(self.bar)
        self.lbl_plan = QLabel(objectName="status")
        self.lbl_plan.setWordWrap(True)
        self.lbl_plan.setTextFormat(Qt.PlainText)   # file names from disk
        root.addWidget(self.lbl_plan)

        self.chk_remove_old = QCheckBox(t("mv_remove_old"))
        self.chk_remove_old.setToolTip(t("tip_mv_remove_old"))
        root.addWidget(self.chk_remove_old)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = QPushButton(t("btn_close"), objectName="secondary")
        close.clicked.connect(self.reject)
        self.btn_move = QPushButton(t("mv_run"))
        self.btn_move.setEnabled(False)
        self.btn_move.clicked.connect(self._confirm)
        bottom.addWidget(close)
        bottom.addWidget(self.btn_move)
        root.addLayout(bottom)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, self.ctx.t("mv_title"),
                                                  self.dest.text() or "")
        if chosen:
            self.dest.setText(chosen)
            self.check()

    def check(self) -> None:
        dest = self.dest.text().strip()
        self._preview = None
        self.btn_move.setEnabled(False)
        if not dest:
            self.lbl_plan.setText("")
            return
        self._seq += 1
        seq = self._seq
        self.bar.setRange(0, 0)
        self.bar.setVisible(True)
        self.lbl_plan.setText(self.ctx.t("mv_checking"))
        w = Worker(self.ctx.services.library_move_plan, dest)
        self._worker = w
        w.progressed.connect(self._on_progress)
        w.succeeded.connect(lambda res, s=seq: self._on_plan(res, s))
        w.failed.connect(lambda msg: self.lbl_plan.setText(msg))
        w.start()

    def _on_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("total"):
            self.bar.setRange(0, msg["total"])
            self.bar.setValue(msg.get("done") or 0)

    def _on_plan(self, res: dict, seq: int) -> None:
        if seq != self._seq:
            return
        t = self.ctx.t
        self.bar.setVisible(False)
        if res.get("error"):
            self.lbl_plan.setText(t(f"mv_err_{res['error']}"))
            return
        lines = [t("mv_plan", n=res["files"], size=_fmt_size(res["bytes"]),
                   free=_fmt_size(res["free"]) if res["free"] is not None else "?")]
        if res["same"]:
            lines.append(t("mv_plan_same", n=res["same"]))
        if res["subfolders"]:
            lines.append(t("mv_plan_subfolders", names=", ".join(res["subfolders"][:5])))
        if res.get("links"):
            lines.append(t("mv_plan_links", n=len(res["links"])))
        if res["conflicts"]:
            lines.append(t("mv_err_conflicts", n=len(res["conflicts"]),
                           names=", ".join(res["conflicts"][:5])))
        elif not res["enough_space"]:
            lines.append(t("mv_err_no_space"))
        self.lbl_plan.setText("\n".join(lines))
        if res["files"] and not res["conflicts"] and res["enough_space"]:
            self._preview = res
            self.btn_move.setEnabled(True)

    def _confirm(self) -> None:
        if not self._preview:
            return
        t = self.ctx.t
        remove_old = self.chk_remove_old.isChecked()
        body = t("mv_confirm", n=self._preview["files"], size=_fmt_size(self._preview["bytes"]),
                 dest=self._preview["dest"])
        body += "\n\n" + t("mv_confirm_old_recycle" if remove_old else "mv_confirm_old_kept")
        dlg = CountdownConfirmDialog(self, t("mv_title"), body, t("mv_run"), t("btn_cancel"))
        if dlg.exec() != QDialog.Accepted:
            return
        self.plan = {"dest": self._preview["dest"], "remove_old": remove_old}
        self.accept()
