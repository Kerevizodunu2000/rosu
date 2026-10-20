# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings tab — the Google Drive section (connect / disconnect, status, the
backup folder link, and the Drive option of the processed-.zip action). Split
out of ``settings_tab.py`` (v2.0)."""
from __future__ import annotations

import html

from PySide6.QtWidgets import QMessageBox

from ..workers import Worker


class SettingsDriveMixin:
    # -- Google Drive (item 11) ---------------------------------------------
    def _reload_zip_options(self) -> None:
        """Rebuild the Processed-.zip-action combo. The 'Upload to Drive & remove'
        option is offered only while Drive is connected; rebuilt on retranslate and
        whenever the Drive connection changes. If the current pick is dropped
        (Drive disconnected while 'drive' was selected), don't lose it silently:
        commit the fallback in Auto mode, mark the tab dirty in manual mode."""
        t = self.ctx.t
        cur = self.zip.currentData() or self.ctx.cfg.zip_disposal
        try:
            connected = self.ctx.services.drive_status().get("connected")
        except Exception:
            connected = False
        order = ["recycle", "move", "delete"] + (["drive"] if connected else [])
        dropped = cur not in order
        self.zip.blockSignals(True)
        self.zip.clear()
        for v in order:
            self.zip.addItem(t(f"zip_{v}"), v)
        idx = self.zip.findData(cur if cur in order else "recycle")
        self.zip.setCurrentIndex(idx if idx >= 0 else 0)
        self.zip.blockSignals(False)
        if dropped and getattr(self, "_ui_ready", False):
            self._on_setting_changed()   # commit (auto) or flag unsaved (manual)

    def _refresh_drive_folder(self) -> None:
        """Show the Drive folder Rosu backs up into, as a link, plus why a folder
        it did not create is invisible to it."""
        t = self.ctx.t
        fid = (self.ctx.cfg.drive_folder_id or "").strip()
        # Only while connected: after Disconnect there is nothing backing up, so
        # "Backing up into this Drive folder" would be describing something that
        # is not happening. The id itself is kept, so reconnecting reuses it.
        connected = bool(self.ctx.services.drive_status().get("connected"))
        if not fid or not connected:
            self.lbl_drive_folder.setVisible(False)
            return
        url = f"https://drive.google.com/drive/folders/{fid}"
        self.lbl_drive_folder.setText(
            f'{html.escape(t("drive_folder_line"))} '
            f'<a href="{html.escape(url, quote=True)}">{html.escape(fid)}</a>'
            f'<br>{html.escape(t("drive_folder_scope_note"))}')
        self.lbl_drive_folder.setVisible(True)

    def _refresh_drive_status(self) -> None:
        t = self.ctx.t
        self._reload_zip_options()   # offer/remove the Drive disposal option
        self._refresh_drive_folder()
        st = self.ctx.services.drive_status()
        if not st["configured"]:
            self.btn_drive.setEnabled(False)
            self.btn_drive.setText(t("btn_drive_connect"))
            self.lbl_drive_status.setText(t("drive_not_configured"))
            return
        if st["connected"]:
            self.btn_drive.setEnabled(True)
            self.btn_drive.setText(t("btn_drive_disconnect"))
            self.lbl_drive_status.setText(t("drive_connected"))
        elif not st.get("can_store", True):
            # Configured, but no keyring backend to store the token — guard the whole
            # OAuth flow up front instead of failing after consent (item 1b).
            self.btn_drive.setEnabled(False)
            self.btn_drive.setText(t("btn_drive_connect"))
            self.lbl_drive_status.setText(t("drive_no_keyring"))
        else:
            self.btn_drive.setEnabled(True)
            self.btn_drive.setText(t("btn_drive_connect"))
            self.lbl_drive_status.setText(t("drive_disconnected"))

    def _toggle_drive(self) -> None:
        t = self.ctx.t
        if self.ctx.services.drive_status()["connected"]:
            if self.mw._operation_running():
                reply = QMessageBox.question(self, self.ctx.t("app_title"),
                    self.ctx.t("drive_disconnect_busy_body"),
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return
            self.ctx.services.disconnect_drive()
            self._refresh_drive_status()
            self.lbl_drive_status.setText(t("drive_disconnected_done"))
            return
        self.btn_drive.setEnabled(False)
        self.lbl_drive_status.setText(t("drive_connecting"))
        w = Worker(lambda progress=None: self.ctx.services.connect_drive(progress))
        self._threads.append(w)
        w.succeeded.connect(self._drive_connected)
        w.failed.connect(self._drive_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _drive_connected(self, res) -> None:
        self._refresh_drive_status()
        if res.get("error"):
            if res["error"] == "not_configured":
                self.lbl_drive_status.setText(self.ctx.t("drive_not_configured"))
            elif res.get("detail"):
                self.lbl_drive_status.setText(res["detail"])
            else:
                self.lbl_drive_status.setText(self.ctx.t("drive_login_failed"))
            return
        # Success: the browser had focus — bring Rosu back to the front so the user
        # "returns to the app" automatically. (The OAuth tab can't be reliably
        # script-closed — browsers only let a script close tabs it opened — so we
        # rely on this raise; the result page just says the tab can be closed.)
        self.mw.raise_()
        self.mw.activateWindow()

    def _drive_failed(self, msg) -> None:
        self._refresh_drive_status()
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)
