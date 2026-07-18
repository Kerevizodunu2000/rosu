# SPDX-License-Identifier: GPL-3.0-or-later
"""Bug-report / feedback dialog. Collects a title + description (+ an optional
screenshot and contact e-mail) and submits them off-thread to Rosu's hosted
endpoint (see :mod:`rosu.report` and ``rosu-web/``). On any failure it shows the
contact e-mail so the user can still reach us."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from .. import report
from ..workers import Worker


class ReportDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        t = ctx.t
        self._image = None          # (bytes, name, mime) or None
        self._threads: list = []
        self.setWindowTitle(t("report_title"))
        self.setMinimumWidth(480)
        root = QVBoxLayout(self)

        root.addWidget(QLabel(t("report_field_title")))
        self.title = QLineEdit()
        root.addWidget(self.title)

        root.addWidget(QLabel(t("report_field_desc")))
        self.desc = QPlainTextEdit()
        self.desc.setMinimumHeight(120)
        root.addWidget(self.desc)

        root.addWidget(QLabel(t("report_contact")))
        self.contact = QLineEdit()
        self.contact.setPlaceholderText("you@example.com")
        root.addWidget(self.contact)

        arow = QHBoxLayout()
        self.btn_attach = QPushButton(t("report_attach"), objectName="secondary")
        self.btn_attach.clicked.connect(self._pick_image)
        self.lbl_attach = QLabel("", objectName="status")
        self.btn_remove = QPushButton("×", objectName="secondary")
        self.btn_remove.setFixedWidth(30)
        self.btn_remove.setVisible(False)
        self.btn_remove.clicked.connect(self._remove_image)
        arow.addWidget(self.btn_attach)
        arow.addWidget(self.lbl_attach, 1)
        arow.addWidget(self.btn_remove)
        root.addLayout(arow)

        # Honeypot: hidden and always empty for a human. A bot that fills every
        # field trips it and the server silently drops the submission.
        self.hp = QLineEdit()
        self.hp.setVisible(False)
        root.addWidget(self.hp)

        self.disclosure = QLabel(t("report_disclosure"), objectName="status")
        self.disclosure.setWordWrap(True)
        root.addWidget(self.disclosure)

        # Privacy/Terms notice at the point of submission (https links are safe as
        # clickable RichText — they open in the browser; only mailto: crashes).
        self.agree = QLabel(t("report_agree"), objectName="status")
        self.agree.setWordWrap(True)
        self.agree.setTextFormat(Qt.RichText)
        self.agree.setOpenExternalLinks(True)
        root.addWidget(self.agree)

        self.status = QLabel("", objectName="status")
        self.status.setWordWrap(True)
        # RichText with MANUAL link handling (openExternalLinks stays False):
        # the e-mail "link" is a fake 'copy-mail' href that copies the address to
        # the clipboard — never a mailto: (launching mailto: on a machine with no
        # mail client crashes; same bug fixed in About). https:// hrefs (the web
        # form) open in the browser explicitly.
        self.status.setTextFormat(Qt.RichText)
        self.status.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.status.setOpenExternalLinks(False)
        self.status.linkActivated.connect(self._on_status_link)
        root.addWidget(self.status)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.btn_send = self.buttons.addButton(t("report_submit"),
                                               QDialogButtonBox.AcceptRole)
        self.btn_send.clicked.connect(self._submit)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    # -- status links (fallback actions) -------------------------------------
    def _on_status_link(self, href: str) -> None:
        t = self.ctx.t
        if href == "copy-mail":
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText("rosu.app@gmail.com")
            self.status.setText(t("report_email_copied"))
        elif href.startswith("https://"):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(href))

    # -- attachment ----------------------------------------------------------
    def _pick_image(self) -> None:
        t = self.ctx.t
        path, _ = QFileDialog.getOpenFileName(
            self, t("report_attach"), "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp)")
        if not path:
            return
        try:
            data, name, mime = report.read_image_for_report(path)
        except report.ReportError as exc:
            reason = exc.args[0] if exc.args else ""
            key = "report_image_too_big" if reason == "image_too_big" else "report_image_bad"
            QMessageBox.warning(self, t("app_title"), t(key))
            return
        self._image = (data, name, mime)
        self.lbl_attach.setText(name)
        self.btn_remove.setVisible(True)

    def _remove_image(self) -> None:
        self._image = None
        self.lbl_attach.setText("")
        self.btn_remove.setVisible(False)

    # -- submit --------------------------------------------------------------
    def _submit(self) -> None:
        t = self.ctx.t
        title = self.title.text().strip()
        desc = self.desc.toPlainText().strip()
        if not title or not desc:
            QMessageBox.information(self, t("app_title"), t("report_need_fields"))
            return
        if self.hp.text().strip():        # honeypot tripped — look successful, send nothing
            self.accept()
            return
        self.buttons.setEnabled(False)    # block close/cancel while a send is in flight
        self.status.setText(t("report_sending"))
        img = self._image
        try:
            endpoint = self.ctx.cfg._extra.get("report_endpoint")
        except Exception:
            endpoint = None
        lang = getattr(self.ctx.cfg, "language", "")
        contact = self.contact.text().strip()

        def work(progress=None):
            return report.submit_report(
                title, desc,
                image_bytes=img[0] if img else None,
                image_name=img[1] if img else None,
                image_mime=img[2] if img else None,
                contact=contact, lang=lang, endpoint=endpoint, progress=progress)

        w = Worker(work)
        self._threads.append(w)
        w.succeeded.connect(self._done)
        w.failed.connect(self._failed)
        w.finished.connect(
            lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _done(self, res) -> None:
        t = self.ctx.t
        if res.get("ok"):
            QMessageBox.information(self, t("app_title"), t("report_sent"))
            self.accept()
            return
        self.buttons.setEnabled(True)
        err = res.get("error", "")
        if err in ("rate_minute", "rate_day", "rate_global"):
            self.status.setText(t("report_rate_limited"))
        elif err == "too_large":
            self.status.setText(t("report_image_too_big"))
        else:
            # not_configured / offline / http / unauthorized / server → e-mail fallback
            self.status.setText(t("report_failed_fallback"))

    def _failed(self, msg: str) -> None:
        self.buttons.setEnabled(True)
        self.status.setText(self.ctx.t("report_failed_fallback"))

    def closeEvent(self, event) -> None:
        # Don't tear the dialog down while a Worker is still emitting to it.
        if self._threads:
            event.ignore()
        else:
            super().closeEvent(event)

    def reject(self) -> None:
        # Escape (and Cancel) call reject() directly — which bypasses closeEvent —
        # so guard here too: a mid-send close would orphan the Worker (it would
        # outlive the widget its signals target, and the app quit-guard can't see
        # a dialog-owned thread).
        if self._threads:
            return
        super().reject()
