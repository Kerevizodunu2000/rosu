# SPDX-License-Identifier: GPL-3.0-or-later
"""Same song, different sets (v1.10): fingerprint the Library's audio, list the
sets whose songs match, and recycle the ones the user picks.

Read-only until the user ticks sets and confirms through a countdown; the
recycle runs as a queued job (Recycle Bin, like the Library dedup). Different
sets of one song are often different maps worth keeping — so nothing is ticked
for the user except by an explicit "select extras" click.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QProgressBar, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from ..workers import Worker
from .countdown_dialog import CountdownConfirmDialog
from .links import plain_tip


def _fmt_size(n) -> str:
    n = int(n or 0)
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:,.2f} GB"
    return f"{n / 1024 ** 2:,.1f} MB"


def extras(group: list[dict]) -> list[str]:
    """In one same-song group, every set except the one to keep: most
    difficulties, then the larger file (Pure; tested)."""
    keep = max(group, key=lambda s: (s.get("diff_count") or 0, s.get("size") or 0,
                                     -len(s.get("filename") or "")))
    return [s["filename"] for s in group if s is not keep]


class SameSongDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.plan: list[str] | None = None
        self._groups: list[list[dict]] = []
        self._worker: Worker | None = None
        self._stop = False
        t = ctx.t
        self.setWindowTitle(t("ss_title"))
        self.setMinimumSize(820, 520)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        intro = QLabel(t("ss_intro"), objectName="status")
        intro.setWordWrap(True)
        root.addWidget(intro)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        root.addWidget(self.bar)
        self.lbl_status = QLabel(objectName="status")
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels([t("col_name"), t("col_mapper"), t("ss_col_diffs"),
                                   t("col_size"), t("col_id")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.itemChanged.connect(lambda *_: self._update_button())
        root.addWidget(self.tree, 1)

        bottom = QHBoxLayout()
        self.btn_scan = QPushButton(t("ss_scan"), objectName="secondary")
        self.btn_scan.clicked.connect(self.scan)
        self.btn_extras = QPushButton(t("ss_select_extras"), objectName="secondary")
        self.btn_extras.setToolTip(t("tip_ss_select_extras"))
        self.btn_extras.clicked.connect(self._select_extras)
        self.btn_extras.setEnabled(False)
        bottom.addWidget(self.btn_scan)
        bottom.addWidget(self.btn_extras)
        bottom.addStretch(1)
        close = QPushButton(t("btn_close"), objectName="secondary")
        close.clicked.connect(self.reject)
        self.btn_recycle = QPushButton(t("ss_recycle"))
        self.btn_recycle.setEnabled(False)
        self.btn_recycle.clicked.connect(self._confirm)
        bottom.addWidget(close)
        bottom.addWidget(self.btn_recycle)
        root.addLayout(bottom)
        self.scan()

    # -- scan (off the UI thread) -----------------------------------------------------
    def scan(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.btn_scan.setEnabled(False)
        self.bar.setRange(0, 0)
        self.bar.setVisible(True)
        self.lbl_status.setText(self.ctx.t("ss_scanning"))
        services = self.ctx.services

        def run(progress=None):
            res = services.fingerprint_library(progress, cancel=lambda: self._stop)
            if res.get("error") or res.get("cancelled"):
                return res
            return {**res, **services.same_song_report()}
        w = Worker(run)
        self._worker = w
        w.progressed.connect(self._on_progress)
        w.succeeded.connect(self._on_scanned)
        w.failed.connect(self._on_failed)
        w.start()

    def _on_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("total"):
            self.bar.setRange(0, msg["total"])
            self.bar.setValue(msg.get("done") or 0)
            self.lbl_status.setText(self.ctx.t("ss_scanning_n", done=msg.get("done") or 0,
                                               total=msg["total"]))

    def _on_failed(self, msg: str) -> None:
        self.bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.lbl_status.setText(msg)

    def _on_scanned(self, res: dict) -> None:
        t = self.ctx.t
        self.bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        if res.get("error") == "no_fpcalc":
            self.lbl_status.setText(t("ss_no_fpcalc"))
            return
        if res.get("cancelled"):
            return
        self._groups = res.get("groups") or []
        text = t("ss_summary", groups=len(self._groups),
                 sets=sum(len(g) for g in self._groups), checked=res.get("fingerprinted", 0))
        if res.get("failed"):
            text += " " + t("ss_unreadable", n=res["failed"])
        self.lbl_status.setText(text)
        self._fill()

    # -- list ----------------------------------------------------------------------
    def _fill(self) -> None:
        t = self.ctx.t
        self.tree.blockSignals(True)
        self.tree.clear()
        for g in self._groups:
            head = g[0]
            top = QTreeWidgetItem([t("ss_group", name=f"{head['artist']} - {head['title']}", n=len(g)),
                                   "", "", _fmt_size(sum(s["size"] for s in g)), ""])
            top.setFirstColumnSpanned(False)
            for s in g:
                child = QTreeWidgetItem([
                    f"{s['artist']} - {s['title']}", s.get("creator") or "",
                    str(s.get("diff_count") or ""), _fmt_size(s["size"]),
                    str(s.get("beatmapset_id") or "")])
                child.setToolTip(0, plain_tip(s["filename"]))
                child.setData(0, Qt.UserRole, s["filename"])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                top.addChild(child)
            self.tree.addTopLevelItem(top)
            top.setExpanded(True)
        self.tree.blockSignals(False)
        self.btn_extras.setEnabled(bool(self._groups))
        self._update_button()

    def _checked(self) -> list[str]:
        out = []
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                c = top.child(j)
                if c.checkState(0) == Qt.Checked:
                    out.append(c.data(0, Qt.UserRole))
        return out

    def _select_extras(self) -> None:
        wanted = {fn for g in self._groups for fn in extras(g)}
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                c = top.child(j)
                c.setCheckState(0, Qt.Checked if c.data(0, Qt.UserRole) in wanted else Qt.Unchecked)
        self.tree.blockSignals(False)
        self._update_button()

    def _update_button(self) -> None:
        n = len(self._checked())
        self.btn_recycle.setEnabled(n > 0)
        self.btn_recycle.setText(self.ctx.t("ss_recycle_n", n=n) if n else self.ctx.t("ss_recycle"))

    # -- confirm --------------------------------------------------------------------
    def _confirm(self) -> None:
        chosen = self._checked()
        if not chosen:
            return
        t = self.ctx.t
        sizes = {s["filename"]: s["size"] for g in self._groups for s in g}
        # Never take every copy of a song: one set per group always stays.
        for g in self._groups:
            if all(s["filename"] in chosen for s in g):
                self.lbl_status.setText(t("ss_keep_one"))
                return
        body = t("ss_confirm", n=len(chosen), size=_fmt_size(sum(sizes.get(f, 0) for f in chosen)))
        dlg = CountdownConfirmDialog(self, t("ss_title"), body, t("ss_recycle"), t("btn_cancel"))
        if dlg.exec() != QDialog.Accepted:
            return
        self.plan = chosen
        self.accept()

    def reject(self) -> None:
        self._stop = True   # the scan stops at its next set; the Worker keeps itself alive
        super().reject()
