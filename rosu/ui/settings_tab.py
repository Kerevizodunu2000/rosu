# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings tab: language, theme, folders, osu! path, toggles and API reference."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from .. import config
from ..workers import Worker
from . import wheel_guard
from .countdown_dialog import CountdownConfirmDialog

_ZIP_ORDER = ["recycle", "move", "delete"]


class SettingsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.ctx = main_window.ctx
        cfg = self.ctx.cfg
        self._threads: list[Worker] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        page = QWidget()
        scroll.setWidget(page)
        root = QVBoxLayout(page)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)
        form = QFormLayout()
        form.setSpacing(10)
        # Fields fill the column so combos and path pickers share the same width (item 22).
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        root.addLayout(form)

        self.lang = QComboBox()
        self.lang.addItem("English", "en")
        self.lang.addItem("Türkçe", "tr")
        self.lang.setCurrentIndex(0 if cfg.language == "en" else 1)
        self.lang.currentIndexChanged.connect(self._apply_language)
        self.lbl_lang = QLabel()
        form.addRow(self.lbl_lang, self._combo_holder(self.lang, "lang"))

        self.theme = QComboBox()
        for name in config.THEMES:
            self.theme.addItem(name, name)
        self._select_theme(cfg.theme)
        self.theme.currentIndexChanged.connect(self._apply_theme)
        self.lbl_theme = QLabel()
        form.addRow(self.lbl_theme, self._combo_holder(self.theme, "theme"))

        self.packs = self._path_row(form, cfg.packs_dir, is_dir=True)
        self.output = self._path_row(form, cfg.output_dir, is_dir=True)
        self.library = self._path_row(form, cfg.library_dir, is_dir=True)
        self.osu = self._path_row(form, cfg.osu_lazer_exe, is_dir=False)
        self.osu_stable = self._path_row(form, cfg.osu_stable_exe, is_dir=False)

        self.cb_physical = QCheckBox(); self.cb_physical.setChecked(cfg.library_physical_copy)
        self.cb_clear_before = QCheckBox(); self.cb_clear_before.setChecked(cfg.clear_output_before_extract)
        self.cb_auto_backup = QCheckBox(); self.cb_auto_backup.setChecked(cfg.auto_backup_after_extract)
        self.cb_check_updates = QCheckBox(); self.cb_check_updates.setChecked(cfg.check_updates)
        self.cb_auto_refresh = QCheckBox(); self.cb_auto_refresh.setChecked(cfg.auto_refresh_on_tab)
        for cb in (self.cb_physical, self.cb_auto_backup, self.cb_clear_before,
                   self.cb_check_updates, self.cb_auto_refresh):
            root.addWidget(cb)

        zip_row = QHBoxLayout()
        self.lbl_zip = QLabel()
        self.zip = QComboBox()
        self._reload_zip_options()   # recycle/move/delete (+ drive when connected)
        zip_row.addWidget(self.lbl_zip); zip_row.addWidget(self.zip); zip_row.addStretch(1)
        root.addLayout(zip_row)

        # Toggles apply immediately (like Language/Theme) so a checked box takes
        # effect without also pressing Save — fixes "I enabled Auto-copy but it
        # didn't run" (item 6). Paths still commit via the Save button.
        for cb in (self.cb_auto_backup, self.cb_clear_before, self.cb_check_updates,
                   self.cb_auto_refresh):
            cb.toggled.connect(self._apply_toggles)
        # Turning OFF physical copies deletes files, so it gets a guarded confirm
        # (item 17) instead of the plain live-apply.
        self.cb_physical.toggled.connect(self._on_physical_toggled)
        self.zip.currentIndexChanged.connect(self._apply_toggles)
        # Combos must not change on an accidental wheel scroll (item 16).
        wheel_guard.guard(self.lang, self.theme, self.zip)

        # osu! API reference
        self.lbl_api = QLabel(objectName="h1")
        root.addWidget(self.lbl_api)
        self.lbl_api_help = QLabel(objectName="status")
        self.lbl_api_help.setWordWrap(True)
        self.lbl_api_help.setTextFormat(Qt.RichText)
        self.lbl_api_help.setOpenExternalLinks(True)   # the osu! link is clickable
        root.addWidget(self.lbl_api_help)
        api_form = QFormLayout()
        self.client_id = QLineEdit(cfg.osu_client_id)
        self.client_secret = QLineEdit(cfg.osu_client_secret)
        self.client_secret.setEchoMode(QLineEdit.Password)
        self.lbl_cid = QLabel(); self.lbl_cs = QLabel()
        api_form.addRow(self.lbl_cid, self.client_id)
        api_form.addRow(self.lbl_cs, self.client_secret)
        root.addLayout(api_form)
        ref_row = QHBoxLayout()
        self.btn_reference = QPushButton(objectName="secondary")
        self.btn_reference.clicked.connect(self._update_reference)
        self.lbl_ref_status = QLabel(objectName="status")
        ref_row.addWidget(self.btn_reference)
        ref_row.addWidget(self.lbl_ref_status, 1)
        root.addLayout(ref_row)

        # Lost-map detection (item F) — needs the API creds above
        lost_row = QHBoxLayout()
        self.btn_lost = QPushButton(objectName="secondary")
        self.btn_lost.clicked.connect(self._scan_lost_maps)
        self.lbl_lost_status = QLabel(objectName="status")
        lost_row.addWidget(self.btn_lost)
        lost_row.addWidget(self.lbl_lost_status, 1)
        root.addLayout(lost_row)

        # Auto-import from installed osu! clients (item 15)
        self.lbl_import = QLabel(objectName="h1")
        root.addWidget(self.lbl_import)
        self.lbl_import_help = QLabel(objectName="status")
        self.lbl_import_help.setWordWrap(True)
        root.addWidget(self.lbl_import_help)
        imp_row = QHBoxLayout()
        self.btn_import_stable = QPushButton(objectName="secondary")
        self.btn_import_lazer = QPushButton(objectName="secondary")
        self.btn_import_stable.clicked.connect(lambda: self._run_import("stable"))
        self.btn_import_lazer.clicked.connect(lambda: self._run_import("lazer"))
        self.lbl_import_status = QLabel(objectName="status")
        imp_row.addWidget(self.btn_import_stable)
        imp_row.addWidget(self.btn_import_lazer)
        imp_row.addWidget(self.lbl_import_status, 1)
        root.addLayout(imp_row)
        # Busy bar: the osu!lazer export runs a long .NET subprocess with no
        # incremental progress, so show an indeterminate bar so it's clearly alive.
        self.import_bar = QProgressBar()
        self.import_bar.setRange(0, 0)     # marquee / indeterminate
        self.import_bar.setVisible(False)
        root.addWidget(self.import_bar)

        # Google Drive backup (item 11)
        self.lbl_drive = QLabel(objectName="h1")
        root.addWidget(self.lbl_drive)
        self.lbl_drive_help = QLabel(objectName="status")
        self.lbl_drive_help.setWordWrap(True)
        root.addWidget(self.lbl_drive_help)
        drive_row = QHBoxLayout()
        self.btn_drive = QPushButton(objectName="secondary")
        self.btn_drive.clicked.connect(self._toggle_drive)
        self.lbl_drive_status = QLabel(objectName="status")
        drive_row.addWidget(self.btn_drive)
        drive_row.addWidget(self.lbl_drive_status, 1)
        root.addLayout(drive_row)

        # About / licenses
        about_row = QHBoxLayout()
        self.btn_about = QPushButton(objectName="secondary")
        self.btn_about.clicked.connect(self._show_about)
        about_row.addWidget(self.btn_about)
        about_row.addStretch(1)
        root.addLayout(about_row)

        root.addStretch(1)
        bottom = QHBoxLayout()
        self.saved_label = QLabel(objectName="status")
        self.btn_save = QPushButton()
        self.btn_save.clicked.connect(self._save)
        bottom.addWidget(self.saved_label, 1)
        bottom.addWidget(self.btn_save)
        root.addLayout(bottom)

        # Ctrl+S saves (item 18); snapshot the deferred fields (paths + API creds) so
        # leaving with unsaved edits can warn (item 11). Live-applied fields
        # (language/theme/toggles) already persist, so they're excluded.
        save_sc = QShortcut(QKeySequence.Save, self, activated=self._save)
        save_sc.setContext(Qt.WidgetWithChildrenShortcut)  # only when Settings is focused
        self._baseline = self._snapshot()

    def _select_theme(self, theme: str) -> None:
        idx = self.theme.findData(theme)
        self.theme.setCurrentIndex(idx if idx >= 0 else 0)

    def _path_row(self, form: QFormLayout, value: str, is_dir: bool) -> QLineEdit:
        field = QLineEdit(value)
        browse = QPushButton(objectName="secondary")
        label = QLabel()

        def pick():
            if is_dir:
                chosen = QFileDialog.getExistingDirectory(self, "", field.text())
            else:
                chosen, _ = QFileDialog.getOpenFileName(self, "", field.text())
            if chosen:
                field.setText(chosen)

        browse.clicked.connect(pick)
        field._browse = browse
        field._label = label
        holder = QHBoxLayout()
        holder.addWidget(field, 1)
        holder.addWidget(browse)
        container = QWidget()
        container.setLayout(holder)
        form.addRow(label, container)
        return field

    def _combo_holder(self, combo, key: str) -> QWidget:
        """Wrap a settings combo like a path row (field + trailing widget) so its
        right edge lines up with the path fields above the Browse buttons (item 22).
        The trailing spacer is sized to the Browse button in retranslate()."""
        holder = QHBoxLayout()
        holder.addWidget(combo, 1)
        spacer = QWidget()
        holder.addWidget(spacer)
        container = QWidget()
        container.setLayout(holder)
        setattr(self, f"_{key}_spacer", spacer)
        return container

    # -- unsaved-changes guard (items 11 & 18) -------------------------------
    def _snapshot(self) -> dict:
        return {"packs": self.packs.text(), "output": self.output.text(),
                "library": self.library.text(), "osu": self.osu.text(),
                "osu_stable": self.osu_stable.text(),
                "client_id": self.client_id.text(),
                "client_secret": self.client_secret.text()}

    def _is_dirty(self) -> bool:
        return self._snapshot() != self._baseline

    def _restore(self, snap: dict) -> None:
        self.packs.setText(snap["packs"]); self.output.setText(snap["output"])
        self.library.setText(snap["library"]); self.osu.setText(snap["osu"])
        self.osu_stable.setText(snap["osu_stable"])
        self.client_id.setText(snap["client_id"])
        self.client_secret.setText(snap["client_secret"])

    def confirm_leave(self) -> bool:
        """Called before leaving Settings / on quit. Returns True when it's OK to
        proceed (saved, discarded, or nothing unsaved); False vetoes the switch."""
        if not self._is_dirty():
            return True
        t = self.ctx.t
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(t("unsaved_title"))
        box.setText(t("unsaved_body"))
        save = box.addButton(t("btn_save_now"), QMessageBox.AcceptRole)
        discard = box.addButton(t("btn_discard"), QMessageBox.DestructiveRole)
        box.addButton(t("btn_cancel"), QMessageBox.RejectRole)
        box.setDefaultButton(save)   # Enter = Save (Ctrl+S muscle memory, item 18)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return self._save()   # False if save failed (bad path) -> stay on Settings
        if clicked is discard:
            self._restore(self._baseline)
            return True
        return False   # Cancel

    # -- i18n ----------------------------------------------------------------
    def retranslate(self) -> None:
        t = self.ctx.t
        self.lbl_lang.setText(t("set_language"))
        self.lbl_theme.setText(t("set_theme"))
        for i in range(self.theme.count()):
            name = self.theme.itemData(i)
            self.theme.setItemText(i, t(f"theme_{name}"))
        self.packs._label.setText(t("set_packs_dir"))
        self.output._label.setText(t("set_output_dir"))
        self.library._label.setText(t("set_library_dir"))
        self.osu._label.setText(t("set_osu_lazer_exe"))
        self.osu_stable._label.setText(t("set_osu_stable_exe"))
        for f in (self.packs, self.output, self.library, self.osu, self.osu_stable):
            f._browse.setText(t("btn_browse"))
        # Match the combo spacers to the (localized) Browse button width (item 22).
        bw = self.packs._browse.sizeHint().width()
        self._lang_spacer.setFixedWidth(bw)
        self._theme_spacer.setFixedWidth(bw)
        self.cb_physical.setText(t("set_physical_copy"))
        self.cb_auto_backup.setText(t("set_auto_backup"))
        self.cb_clear_before.setText(t("set_clear_output_before"))
        self.cb_check_updates.setText(t("set_check_updates"))
        self.cb_check_updates.setToolTip(t("tip_check_updates"))
        self.cb_auto_refresh.setText(t("set_auto_refresh"))
        self.cb_auto_refresh.setToolTip(t("tip_auto_refresh"))
        self.lbl_zip.setText(t("set_zip_disposal"))
        self._reload_zip_options()
        self.lbl_api.setText(t("set_osu_api"))
        self.lbl_api_help.setText(t("reference_help"))
        self.lbl_cid.setText(t("set_client_id"))
        self.lbl_cs.setText(t("set_client_secret"))
        self.btn_reference.setText(t("btn_update_reference"))
        self.btn_lost.setText(t("btn_scan_lost"))
        self.btn_lost.setToolTip(t("tip_scan_lost"))
        self.lbl_import.setText(t("set_import"))
        self.lbl_import_help.setText(t("set_import_help"))
        self.btn_import_stable.setText(t("btn_import_stable"))
        self.btn_import_lazer.setText(t("btn_import_lazer"))
        self.lbl_drive.setText(t("set_drive"))
        self.lbl_drive_help.setText(t("set_drive_help"))
        self.btn_about.setText(t("btn_about"))
        self.btn_save.setText(t("btn_save"))
        self.lang.setToolTip(t("tip_language"))
        self.theme.setToolTip(t("tip_theme"))
        self.packs.setToolTip(t("tip_packs_dir"))
        self.output.setToolTip(t("tip_output_dir"))
        self.library.setToolTip(t("tip_library_dir"))
        self.osu.setToolTip(t("tip_osu_lazer_exe"))
        self.osu_stable.setToolTip(t("tip_osu_stable_exe"))
        self.cb_physical.setToolTip(t("tip_physical_copy"))
        self.cb_auto_backup.setToolTip(t("tip_auto_backup"))
        self.cb_clear_before.setToolTip(t("tip_clear_before"))
        self.btn_reference.setToolTip(t("tip_update_reference"))
        self.btn_import_stable.setToolTip(t("tip_import_stable"))
        self.btn_import_lazer.setToolTip(t("tip_import_lazer"))
        self.btn_drive.setToolTip(t("tip_drive"))
        self.btn_about.setToolTip(t("tip_about"))
        self.btn_save.setToolTip(t("tip_save"))
        self._refresh_reference_status()
        self._refresh_lost_status()
        self._refresh_drive_status()

    def _refresh_reference_status(self) -> None:
        from .. import osu_api
        ref = osu_api.load_reference(self.ctx.cfg.reference_path)
        if ref:
            self.lbl_ref_status.setText(self.ctx.t(
                "reference_status", n=ref.get("count", 0), when=ref.get("fetched_at", "")))
        else:
            self.lbl_ref_status.setText(self.ctx.t("reference_none"))

    # -- Google Drive (item 11) ---------------------------------------------
    def _reload_zip_options(self) -> None:
        """Rebuild the Processed-.zip-action combo. The 'Upload to Drive & remove'
        option is offered only while Drive is connected; rebuilt on retranslate and
        whenever the Drive connection changes."""
        t = self.ctx.t
        cur = self.zip.currentData() or self.ctx.cfg.zip_disposal
        try:
            connected = self.ctx.services.drive_status().get("connected")
        except Exception:
            connected = False
        order = ["recycle", "move", "delete"] + (["drive"] if connected else [])
        self.zip.blockSignals(True)
        self.zip.clear()
        for v in order:
            self.zip.addItem(t(f"zip_{v}"), v)
        idx = self.zip.findData(cur if cur in order else "recycle")
        self.zip.setCurrentIndex(idx if idx >= 0 else 0)
        self.zip.blockSignals(False)

    def _refresh_drive_status(self) -> None:
        t = self.ctx.t
        self._reload_zip_options()   # offer/remove the Drive disposal option
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

    # -- About / licenses ----------------------------------------------------
    def _show_about(self) -> None:
        from .about_dialog import AboutDialog
        AboutDialog(self.ctx, self).exec()

    # -- live apply ----------------------------------------------------------
    def _apply_language(self) -> None:
        lang = self.lang.currentData()
        self.ctx.cfg.language = lang
        self.ctx.save_config()
        self.mw.apply_language(lang)

    def _apply_theme(self) -> None:
        theme = self.theme.currentData()
        if not theme:
            return
        self.ctx.cfg.theme = theme
        self.ctx.save_config()
        self.mw.apply_theme(theme)

    # -- reference sync ------------------------------------------------------
    def _update_reference(self) -> None:
        cfg = self.ctx.cfg
        cfg.osu_client_id = self.client_id.text().strip()
        cfg.osu_client_secret = self.client_secret.text().strip()
        self.ctx.save_config()
        if not cfg.osu_client_id or not cfg.osu_client_secret:
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("reference_help"))
            return
        self.btn_reference.setEnabled(False)
        self.lbl_ref_status.setText(self.ctx.t("working"))
        w = Worker(lambda progress=None: self.ctx.services.update_reference(progress))
        self._threads.append(w)
        w.progressed.connect(lambda m: self.lbl_ref_status.setText(str(m)))
        w.succeeded.connect(self._reference_done)
        w.failed.connect(self._reference_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _reference_done(self, ref) -> None:
        self.btn_reference.setEnabled(True)
        self.lbl_ref_status.setText(self.ctx.t("reference_done", n=ref.get("count", 0)))
        self.mw.dashboard._update_banner()
        self.mw.packs.reload()

    def _reference_failed(self, msg) -> None:
        self.btn_reference.setEnabled(True)
        self._refresh_reference_status()
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    # -- lost-map detection (item F) -----------------------------------------
    def _refresh_lost_status(self) -> None:
        n = self.ctx.services.lost_map_count()
        self.lbl_lost_status.setText(self.ctx.t("lost_maps_count", n=n) if n else "")

    def _scan_lost_maps(self) -> None:
        cfg = self.ctx.cfg
        cfg.osu_client_id = self.client_id.text().strip()
        cfg.osu_client_secret = self.client_secret.text().strip()
        self.ctx.save_config()
        if not (cfg.osu_client_id and cfg.osu_client_secret):
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("lost_maps_needs_api"))
            return
        self.btn_lost.setEnabled(False)
        self.lbl_lost_status.setText(self.ctx.t("working"))
        w = Worker(lambda progress=None: self.ctx.services.scan_lost_maps(progress))
        self._threads.append(w)
        w.progressed.connect(self._on_lost_progress)
        w.succeeded.connect(self._lost_done)
        w.failed.connect(self._lost_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_lost_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("kind") == "lostmap":
            self.lbl_lost_status.setText(f"{msg['done']}/{msg['total']}")

    def _lost_done(self, res) -> None:
        self.btn_lost.setEnabled(True)
        if res.get("error") == "no_api":
            self.lbl_lost_status.setText(self.ctx.t("lost_maps_needs_api"))
            return
        self.lbl_lost_status.setText(self.ctx.t(
            "lost_maps_result", checked=res["checked"], gone=res["gone"]))
        self.mw.search.reload()

    def _lost_failed(self, msg) -> None:
        self.btn_lost.setEnabled(True)
        self._refresh_lost_status()
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    # -- auto-import from installed osu! clients (item 15) -------------------
    def _run_import(self, client: str) -> None:
        self.btn_import_stable.setEnabled(False)
        self.btn_import_lazer.setEnabled(False)
        self.import_bar.setVisible(True)
        self.lbl_import_status.setText(self.ctx.t("working"))
        fn = (self.ctx.services.import_from_lazer if client == "lazer"
              else self.ctx.services.import_from_stable)
        w = Worker(fn)
        self._threads.append(w)
        w.progressed.connect(self._on_import_progress)
        w.succeeded.connect(self._on_import_done)
        w.failed.connect(self._on_import_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_import_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("kind") == "import" and "done" in msg:
            self.lbl_import_status.setText(f"{msg['done']}/{msg['total']}")
        elif isinstance(msg, str):
            self.lbl_import_status.setText(msg)

    def _on_import_done(self, res) -> None:
        self.btn_import_stable.setEnabled(True)
        self.btn_import_lazer.setEnabled(True)
        self.import_bar.setVisible(False)
        t = self.ctx.t
        client = "osu!lazer" if res.get("source") == "lazer" else "osu!(stable)"
        if not res.get("found"):
            self.lbl_import_status.setText(t("import_client_none", client=client))
            return
        if res.get("error"):
            self.lbl_import_status.setText(t("import_lazer_error"))
            return
        self.lbl_import_status.setText(t("import_client_result", client=client,
                                       new=res.get("new", 0), dup=res.get("duplicates", 0)))
        self.mw.dashboard.refresh_scan()
        self.mw.packs.reload()
        self.mw.search.reload()          # reflect the new library rows live (item 7)

    def _on_import_failed(self, msg) -> None:
        self.btn_import_stable.setEnabled(True)
        self.btn_import_lazer.setEnabled(True)
        self.import_bar.setVisible(False)
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    # -- physical-copy toggle (guarded delete) -------------------------------
    def _on_physical_toggled(self, checked: bool) -> None:
        cfg = self.ctx.cfg
        if checked:  # turning ON just keeps future copies — nothing to delete
            cfg.library_physical_copy = True
            self.ctx.save_config()
            self.saved_label.setText(self.ctx.t("saved"))
            return
        t = self.ctx.t
        dlg = CountdownConfirmDialog(
            self, t("physical_off_title"), t("physical_off_body"),
            t("physical_off_confirm"), t("btn_cancel"))
        if dlg.exec() != QDialog.Accepted:
            self.cb_physical.blockSignals(True)   # cancelled -> revert the box
            self.cb_physical.setChecked(True)
            self.cb_physical.blockSignals(False)
            return
        cfg.library_physical_copy = False
        self.ctx.save_config()
        self.saved_label.setText(t("working"))
        w = Worker(self.ctx.services.purge_library_files)
        self._threads.append(w)
        w.succeeded.connect(lambda res: self.saved_label.setText(
            self.ctx.t("physical_off_done", n=res["deleted"])))
        w.failed.connect(lambda m: QMessageBox.critical(self, t("app_title"), m))
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    # -- live toggle apply ---------------------------------------------------
    def _apply_toggles(self, *_) -> None:
        cfg = self.ctx.cfg
        cfg.library_physical_copy = self.cb_physical.isChecked()
        cfg.auto_backup_after_extract = self.cb_auto_backup.isChecked()
        cfg.clear_output_before_extract = self.cb_clear_before.isChecked()
        cfg.check_updates = self.cb_check_updates.isChecked()
        cfg.auto_refresh_on_tab = self.cb_auto_refresh.isChecked()
        cfg.zip_disposal = self.zip.currentData()
        self.ctx.save_config()
        self.saved_label.setText(self.ctx.t("saved"))
        # auto-copy toggle changes whether the Dashboard shows its Copy button
        self.mw.dashboard._sync_auto_copy()

    # -- save (paths + API) --------------------------------------------------
    def _save(self) -> bool:
        cfg = self.ctx.cfg
        cfg.packs_dir = self.packs.text().strip()
        cfg.output_dir = self.output.text().strip()
        cfg.library_dir = self.library.text().strip()
        cfg.osu_lazer_exe = self.osu.text().strip()
        cfg.osu_stable_exe = self.osu_stable.text().strip()
        cfg.osu_exe = cfg.osu_lazer_exe   # keep the legacy field mirrored
        cfg.osu_client_id = self.client_id.text().strip()
        cfg.osu_client_secret = self.client_secret.text().strip()
        try:
            cfg.ensure_dirs()   # can raise on an invalid/unreachable path the user typed
        except OSError as exc:
            QMessageBox.critical(self, self.ctx.t("app_title"),
                                 self.ctx.t("settings_save_failed", err=str(exc)))
            return False
        self._apply_toggles()   # persists cfg (now-validated paths + toggles + API)
        self.ctx.log.info("SETTINGS_SAVE", changed="paths,toggles,api")
        self.saved_label.setText(self.ctx.t("saved"))
        self._baseline = self._snapshot()   # edits are now saved — clear dirty (item 11)
        self.mw.dashboard.refresh_scan()
        return True
