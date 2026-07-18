# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings tab: language, theme, folders, osu! path, toggles and API reference."""
from __future__ import annotations

from pathlib import Path

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
        self._live_connected = False   # are path/API live-commit signals wired? (v1.4)

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
        # Labels sit vertically CENTERED on their field boxes (v1.4.2) — the
        # wrapper widgets below zero their margins for the same reason: a
        # taller-than-field wrapper made every label look shifted upward.
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root.addLayout(form)
        self._form = form   # kept: per-client rows are shown/hidden live (v1.4)

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
        # osu! client executables, each with its per-client enable toggle right
        # beneath its path (v1.4): a disabled client's path row VANISHES entirely
        # (it comes back when the toggle is re-enabled) and it is never written to.
        # Each client = ONE row: the "Enable …" checkbox IS the row's label
        # (same column + centering as Language/Packs folder), with the path
        # field + Browse beside it. Disabling hides only the field side — the
        # checkbox stays so the client can be re-enabled (v1.4.2). The path
        # field carries its description as placeholder + tooltip.
        self.cb_lazer_enabled = QCheckBox(); self.cb_lazer_enabled.setChecked(cfg.lazer_enabled)
        self.osu = self._path_row(form, cfg.osu_lazer_exe, is_dir=False,
                                  label_widget=self.cb_lazer_enabled)
        self.cb_stable_enabled = QCheckBox(); self.cb_stable_enabled.setChecked(cfg.stable_enabled)
        self.osu_stable = self._path_row(form, cfg.osu_stable_exe, is_dir=False,
                                         label_widget=self.cb_stable_enabled)
        self._sync_client_rows()

        self.cb_physical = QCheckBox(); self.cb_physical.setChecked(cfg.library_physical_copy)
        self.cb_clear_before = QCheckBox(); self.cb_clear_before.setChecked(cfg.clear_output_before_extract)
        self.cb_auto_backup = QCheckBox(); self.cb_auto_backup.setChecked(cfg.auto_backup_after_extract)
        self.cb_check_updates = QCheckBox(); self.cb_check_updates.setChecked(cfg.check_updates)
        self.cb_auto_refresh = QCheckBox(); self.cb_auto_refresh.setChecked(cfg.auto_refresh_on_tab)
        # Settings-commit mode (v1.4): Auto hides the Save button (everything
        # applies immediately); Manual keeps the explicit Save + dirty-guard.
        self.cb_autosave = QCheckBox(); self.cb_autosave.setChecked(cfg.settings_autosave)
        for cb in (self.cb_physical,
                   self.cb_auto_backup, self.cb_clear_before,
                   self.cb_check_updates, self.cb_auto_refresh, self.cb_autosave):
            root.addWidget(cb)

        zip_row = QHBoxLayout()
        self.lbl_zip = QLabel()
        self.zip = QComboBox()
        self._reload_zip_options()   # recycle/move/delete (+ drive when connected)
        zip_row.addWidget(self.lbl_zip); zip_row.addWidget(self.zip); zip_row.addStretch(1)
        root.addLayout(zip_row)

        # Commit model (v1.4.1): toggles/combos apply immediately ONLY in
        # Auto-Save mode. In manual mode they just mark the tab dirty and wait
        # for Save — "Auto-Save off" must genuinely mean nothing saves itself.
        # (Language/Theme stay live in both modes: they're visual pickers whose
        # effect you need to SEE to choose. Physical-copy keeps its own guarded
        # confirm flow because turning it off deletes files.)
        for cb in (self.cb_auto_backup, self.cb_clear_before, self.cb_check_updates,
                   self.cb_auto_refresh):
            cb.toggled.connect(self._on_setting_changed)
        self.cb_physical.toggled.connect(self._on_physical_toggled)
        self.zip.currentIndexChanged.connect(self._on_setting_changed)
        # Per-client toggles: commit + reactive hide/show in Auto mode; dirty
        # in manual mode (the UI re-syncs on Save). The save-mode toggle itself
        # is always live — it's the switch that decides the commit model.
        self.cb_lazer_enabled.toggled.connect(self._on_client_toggle_changed)
        self.cb_stable_enabled.toggled.connect(self._on_client_toggle_changed)
        self.cb_autosave.toggled.connect(self._on_autosave_toggled)
        # Combos must not change on an accidental wheel scroll (item 16).
        wheel_guard.guard(self.lang, self.theme, self.zip)

        # osu! API reference
        self.lbl_api = QLabel(objectName="h1")
        root.addWidget(self.lbl_api)
        self.lbl_api_help = QLabel(objectName="status")
        self.lbl_api_help.setWordWrap(True)
        self.lbl_api_help.setTextFormat(Qt.RichText)
        self.lbl_api_help.setOpenExternalLinks(True)   # the osu! link is clickable
        from .links import wire_link_hover
        wire_link_hover(self.lbl_api_help)
        root.addWidget(self.lbl_api_help)
        api_form = QFormLayout()
        self.client_id = QLineEdit(cfg.osu_client_id)
        self.client_secret = QLineEdit(cfg.osu_client_secret)
        self.client_secret.setEchoMode(QLineEdit.Password)
        self.lbl_cid = QLabel(); self.lbl_cs = QLabel()
        api_form.addRow(self.lbl_cid, self.client_id)
        api_form.addRow(self.lbl_cs, self.client_secret)
        root.addLayout(api_form)
        # v1.5: opt in to pulling ranked status/dates/counts/genre/language (and a
        # fallback star) from the osu! API — needs the creds above.
        self.cb_enrich = QCheckBox(); self.cb_enrich.setChecked(cfg.enrich_from_api_enabled)
        self.cb_enrich.toggled.connect(self._on_setting_changed)
        root.addWidget(self.cb_enrich)
        enrich_row = QHBoxLayout()
        self.btn_enrich = QPushButton(objectName="secondary")
        self.btn_enrich.clicked.connect(self._enrich_metadata)
        self.lbl_enrich_status = QLabel(objectName="status")
        enrich_row.addWidget(self.btn_enrich)
        enrich_row.addWidget(self.lbl_enrich_status, 1)
        root.addLayout(enrich_row)
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

        # Library health (v1.1) — moved here from the Dashboard in v1.5.
        self.lbl_library = QLabel(objectName="h1")
        root.addWidget(self.lbl_library)
        health_row = QHBoxLayout()
        self.btn_health = QPushButton(objectName="secondary")
        self.btn_health.clicked.connect(self._library_health)
        self.lbl_health_status = QLabel(objectName="status")
        health_row.addWidget(self.btn_health)
        health_row.addWidget(self.lbl_health_status, 1)
        root.addLayout(health_row)

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
        self.btn_report = QPushButton(objectName="secondary")
        self.btn_report.clicked.connect(self._show_report)
        about_row.addWidget(self.btn_report)
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
        self._sync_client_import_buttons()   # hide a disabled client's import button
        self._apply_save_mode()              # set Save-button visibility + live commits
        self._ui_ready = True   # from here on, dropped combo picks may react (v1.4.1)

    def _select_theme(self, theme: str) -> None:
        idx = self.theme.findData(theme)
        self.theme.setCurrentIndex(idx if idx >= 0 else 0)

    def _path_row(self, form: QFormLayout, value: str, is_dir: bool,
                  label_widget: QWidget | None = None) -> QLineEdit:
        field = QLineEdit(value)
        browse = QPushButton(objectName="secondary")
        label = label_widget if label_widget is not None else QLabel()

        def pick():
            if is_dir:
                chosen = QFileDialog.getExistingDirectory(self, "", field.text())
            else:
                chosen, _ = QFileDialog.getOpenFileName(self, "", field.text())
            if chosen:
                field.setText(chosen)
                # Programmatic setText never fires editingFinished, so an
                # Auto-Save commit would silently miss a Browse-picked path (and
                # later surface as a bogus "unsaved changes" warning). Emit it
                # ourselves; in manual mode nothing is connected, so it's a no-op.
                field.editingFinished.emit()

        browse.clicked.connect(pick)
        field._browse = browse
        field._label = label
        holder = QHBoxLayout()
        holder.setContentsMargins(0, 0, 0, 0)   # wrapper = exactly field height
        holder.addWidget(field, 1)
        holder.addWidget(browse)
        container = QWidget()
        container.setLayout(holder)
        field._container = container
        form.addRow(label, container)
        # A non-QLabel label widget (the Enable checkbox) defaults to the TOP of
        # its cell — pin every label item to vertical center explicitly so the
        # checkbox rows line up exactly like the plain-label rows above them.
        item = form.itemAt(form.rowCount() - 1, QFormLayout.LabelRole)
        if item is not None:
            item.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return field

    def _combo_holder(self, combo, key: str) -> QWidget:
        """Wrap a settings combo like a path row (field + trailing widget) so its
        right edge lines up with the path fields above the Browse buttons (item 22).
        The trailing spacer is sized to the Browse button in retranslate()."""
        holder = QHBoxLayout()
        holder.setContentsMargins(0, 0, 0, 0)   # wrapper = exactly combo height
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
                "client_secret": self.client_secret.text(),
                # Toggles/combos are deferred in manual mode too (v1.4.1), so
                # they take part in the dirty check + Discard restore.
                "auto_backup": self.cb_auto_backup.isChecked(),
                "clear_before": self.cb_clear_before.isChecked(),
                "check_updates": self.cb_check_updates.isChecked(),
                "auto_refresh": self.cb_auto_refresh.isChecked(),
                "enrich": self.cb_enrich.isChecked(),
                "lazer_enabled": self.cb_lazer_enabled.isChecked(),
                "stable_enabled": self.cb_stable_enabled.isChecked(),
                "zip": self.zip.currentData()}

    def _is_dirty(self) -> bool:
        return self._snapshot() != self._baseline

    def _restore(self, snap: dict) -> None:
        self.packs.setText(snap["packs"]); self.output.setText(snap["output"])
        self.library.setText(snap["library"]); self.osu.setText(snap["osu"])
        self.osu_stable.setText(snap["osu_stable"])
        self.client_id.setText(snap["client_id"])
        self.client_secret.setText(snap["client_secret"])
        # Restore the deferred toggles WITHOUT re-triggering their handlers
        # (they'd re-mark the tab dirty, or re-commit in auto mode).
        boxes = ((self.cb_auto_backup, "auto_backup"),
                 (self.cb_clear_before, "clear_before"),
                 (self.cb_check_updates, "check_updates"),
                 (self.cb_auto_refresh, "auto_refresh"),
                 (self.cb_enrich, "enrich"),
                 (self.cb_lazer_enabled, "lazer_enabled"),
                 (self.cb_stable_enabled, "stable_enabled"))
        for cb, key in boxes:
            cb.blockSignals(True)
            cb.setChecked(bool(snap[key]))
            cb.blockSignals(False)
        self.zip.blockSignals(True)
        idx = self.zip.findData(snap["zip"])
        if idx >= 0:
            self.zip.setCurrentIndex(idx)
        self.zip.blockSignals(False)
        # The client boxes were restored with signals blocked — re-sync the
        # instant visuals they normally drive (path rows + import buttons).
        self._sync_client_rows()
        self._sync_client_import_buttons()

    def confirm_leave(self) -> bool:
        """Called before leaving Settings / on quit. Returns True when it's OK to
        proceed (saved, discarded, or nothing unsaved); False vetoes the switch."""
        if self.ctx.cfg.settings_autosave:
            if not self._is_dirty():
                return True
            if self._save(silent=True):   # Auto mode keeps everything saved
                return True
            # The auto-commit FAILED (e.g. an invalid/unreachable folder path).
            # Silently allowing the leave would drop the edit with no visible
            # warning — fall through to the explicit Save/Discard/Cancel dialog
            # so the user gets the same real veto Manual mode has.
        elif not self._is_dirty():
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
        # The client exe rows are labelled by their "Enable …" checkboxes
        # (translated below); the fields explain themselves via placeholder.
        self.osu.setPlaceholderText(t("set_osu_lazer_exe"))
        self.osu_stable.setPlaceholderText(t("set_osu_stable_exe"))
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
        self.cb_enrich.setText(t("set_enrich_api"))
        self.cb_enrich.setToolTip(t("tip_enrich_api"))
        self.btn_enrich.setText(t("btn_enrich_api"))
        self.btn_enrich.setToolTip(t("tip_enrich_api"))
        self.cb_lazer_enabled.setText(t("set_lazer_enabled"))
        self.cb_lazer_enabled.setToolTip(t("tip_lazer_enabled"))
        self.cb_stable_enabled.setText(t("set_stable_enabled"))
        self.cb_stable_enabled.setToolTip(t("tip_stable_enabled"))
        self.cb_autosave.setText(t("set_autosave"))
        self.cb_autosave.setToolTip(t("tip_autosave"))
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
        self.lbl_library.setText(t("set_library_section"))
        self.btn_health.setText(t("btn_library_health"))
        self.btn_health.setToolTip(t("tip_library_health"))
        self.lbl_drive.setText(t("set_drive"))
        self.lbl_drive_help.setText(t("set_drive_help"))
        self.btn_about.setText(t("btn_about"))
        self.btn_report.setText(t("btn_report"))
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
        self.btn_report.setToolTip(t("tip_report"))
        self.btn_save.setToolTip(t("tip_save"))
        self._sync_client_import_buttons()
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

    def _show_report(self) -> None:
        from .report_dialog import ReportDialog
        ReportDialog(self.ctx, self).exec()

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

    def _commit_api_creds(self) -> bool:
        """Persist the API credential fields (used by the reference/lost-map
        buttons). Empty fields are NOT written — a stray click must never wipe
        stored credentials — and the dirty baseline is synced so a later
        Discard can't roll the fields back to a stale snapshot. Returns True
        when both credentials are present."""
        cfg = self.ctx.cfg
        cid = self.client_id.text().strip()
        cs = self.client_secret.text().strip()
        if cid and cs:
            cfg.osu_client_id = cid
            cfg.osu_client_secret = cs
            self.ctx.save_config()
            self._baseline["client_id"] = cid
            self._baseline["client_secret"] = cs
            return True
        return False

    # -- reference sync ------------------------------------------------------
    def _update_reference(self) -> None:
        if not self._commit_api_creds():
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
        if not self._commit_api_creds():
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
        # Say exactly where the scan stands: how many of the library's sets were
        # checked this run, and how many have never been checked yet (the scan
        # goes in batches — run again to continue).
        if res.get("remaining"):
            self.lbl_lost_status.setText(self.ctx.t(
                "lost_maps_result_more", checked=res["checked"], gone=res["gone"],
                remaining=res["remaining"]))
        else:
            self.lbl_lost_status.setText(self.ctx.t(
                "lost_maps_result_all", checked=res["checked"], gone=res["gone"],
                total=res.get("total", res["checked"])))
        self.mw.search.reload()

    def _lost_failed(self, msg) -> None:
        self.btn_lost.setEnabled(True)
        self._refresh_lost_status()
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    # -- osu! API metadata enrichment (v1.5) ---------------------------------
    def _enrich_metadata(self) -> None:
        if getattr(self, "_enriching", False):   # button doubles as Cancel mid-run
            self.ctx.services.cancel_enrich()
            self.lbl_enrich_status.setText(self.ctx.t("cancelling"))
            return
        if not self.cb_enrich.isChecked():
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("enrich_disabled_msg"))
            return
        if not self._commit_api_creds():
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("enrich_no_api_msg"))
            return
        self.ctx.cfg.enrich_from_api_enabled = True   # an explicit click opts in
        self._enriching = True
        self.btn_enrich.setText(self.ctx.t("btn_cancel"))
        self.lbl_enrich_status.setText(self.ctx.t("working"))
        # max_calls=None → enrich the WHOLE library in one run (paced ~2-3/s); it's
        # cancellable and shows progress, so there's no need for an artificial cap.
        w = Worker(lambda progress=None:
                   self.ctx.services.enrich_metadata(progress, max_calls=None))
        self._threads.append(w)
        w.progressed.connect(self._on_enrich_progress)
        w.succeeded.connect(self._enrich_done)
        w.failed.connect(self._enrich_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_enrich_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("kind") == "enrich":
            self.lbl_enrich_status.setText(f"{msg['done']}/{msg['total']}")

    def _enrich_done(self, res) -> None:
        self._enriching = False
        self.btn_enrich.setText(self.ctx.t("btn_enrich_api"))
        err = res.get("error")
        if err == "no_api":
            self.lbl_enrich_status.setText(self.ctx.t("enrich_no_api"))
            return
        if err == "disabled":
            self.lbl_enrich_status.setText(self.ctx.t("enrich_disabled"))
            return
        self.lbl_enrich_status.setText(self.ctx.t(
            "enrich_done", checked=res["checked"], updated=res["updated"],
            remaining=res["remaining"]))
        self.mw.search.reload()

    def _enrich_failed(self, msg) -> None:
        self._enriching = False
        self.btn_enrich.setText(self.ctx.t("btn_enrich_api"))
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    # -- Library health (v1.1, moved from Dashboard in v1.5) -----------------
    def _library_health(self) -> None:
        self.btn_health.setEnabled(False)
        self.lbl_health_status.setText(self.ctx.t("working"))
        w = Worker(self.ctx.services.library_health)
        self._threads.append(w)
        w.succeeded.connect(self._health_done)
        w.failed.connect(self._health_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _health_done(self, report) -> None:
        self.btn_health.setEnabled(True)
        self.lbl_health_status.setText(self.ctx.t(
            "health_done", files=report["usage"]["files"]))
        from .health_dialog import HealthDialog
        HealthDialog(self.ctx, report, self).exec()

    def _health_failed(self, msg) -> None:
        self.btn_health.setEnabled(True)
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
        self.import_bar.setVisible(False)
        self._sync_client_import_buttons()   # re-show per-toggle, re-enable
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
        self.import_bar.setVisible(False)
        self._sync_client_import_buttons()   # re-show per-toggle, re-enable
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    # -- physical-copy toggle (guarded delete) -------------------------------
    def _set_saved_text(self, text: str) -> None:
        """Show a status on the shared saved-label WITHOUT hiding a live
        "unsaved changes" hint — the dirty warning wins while edits are pending."""
        self.saved_label.setText(
            self.ctx.t("settings_dirty") if self._is_dirty() else text)

    def _on_physical_toggled(self, checked: bool) -> None:
        cfg = self.ctx.cfg
        if checked:  # turning ON just keeps future copies — nothing to delete
            cfg.library_physical_copy = True
            self.ctx.save_config()
            self._set_saved_text(self.ctx.t("saved"))
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
        w.succeeded.connect(lambda res: self._set_saved_text(
            self.ctx.t("physical_off_done", n=res["deleted"])))
        w.failed.connect(lambda m: QMessageBox.critical(self, t("app_title"), m))
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    # -- toggle commit model (v1.4.1) ----------------------------------------
    _TOGGLE_KEYS = ("auto_backup", "clear_before", "check_updates",
                    "auto_refresh", "enrich", "lazer_enabled", "stable_enabled",
                    "zip")

    def _mark_dirty(self) -> None:
        self.saved_label.setText(self.ctx.t("settings_dirty"))

    def _sync_toggle_baseline(self) -> None:
        """Mark ONLY the toggle keys as saved in the dirty baseline. Never
        blanket-sync the whole snapshot here: a pending (not yet committed)
        path/API text edit must stay dirty or it would be silently blessed
        without ever reaching the config."""
        snap = self._snapshot()
        for k in self._TOGGLE_KEYS:
            self._baseline[k] = snap[k]

    def _on_setting_changed(self, *_) -> None:
        """A deferred toggle/combo changed: commit right away in Auto-Save mode,
        otherwise just mark the tab dirty and wait for Save."""
        if self.ctx.cfg.settings_autosave:
            self._apply_toggles()
            self._sync_toggle_baseline()
        else:
            self._mark_dirty()

    def _on_client_toggle_changed(self, *_) -> None:
        if self.ctx.cfg.settings_autosave:
            self._apply_client_toggles()
            self._sync_toggle_baseline()
        else:
            # Deferred COMMIT, instant VISUALS (v1.4.2): this tab's path row +
            # import button react to the tick right away; the config (and the
            # other tabs) only change when Save commits it. A Discard re-ticks
            # the box via _restore, which re-syncs these visuals back.
            self._sync_client_rows()
            self._sync_client_import_buttons()
            self._mark_dirty()

    # -- toggle apply (called on commit) -------------------------------------
    def _apply_toggles(self, *_) -> None:
        cfg = self.ctx.cfg
        cfg.library_physical_copy = self.cb_physical.isChecked()
        cfg.auto_backup_after_extract = self.cb_auto_backup.isChecked()
        cfg.clear_output_before_extract = self.cb_clear_before.isChecked()
        cfg.check_updates = self.cb_check_updates.isChecked()
        cfg.auto_refresh_on_tab = self.cb_auto_refresh.isChecked()
        cfg.enrich_from_api_enabled = self.cb_enrich.isChecked()
        cfg.lazer_enabled = self.cb_lazer_enabled.isChecked()
        cfg.stable_enabled = self.cb_stable_enabled.isChecked()
        cfg.settings_autosave = self.cb_autosave.isChecked()
        cfg.zip_disposal = self.zip.currentData()
        self.ctx.save_config()
        self.saved_label.setText(self.ctx.t("saved"))
        # auto-copy toggle changes whether the Dashboard shows its Copy button.
        self.mw.dashboard._sync_auto_copy()

    # -- per-client enable/disable (v1.4) ------------------------------------
    def _apply_client_toggles(self, *_) -> None:
        """Persist the client on/off flags, then reactively hide/show that
        client's controls on this tab and the Dashboard + Shortcuts tabs."""
        self._apply_toggles()
        self._sync_client_rows()
        self._sync_client_import_buttons()
        if hasattr(self.mw, "dashboard"):
            self.mw.dashboard._sync_import_buttons()
        if hasattr(self.mw, "shortcuts"):
            self.mw.shortcuts.refresh_client_visibility()

    def _sync_client_rows(self) -> None:
        """A disabled client's exe path field + Browse disappear until the
        client is re-enabled — the Enable checkbox (the row's label) stays.
        Follows the CHECKBOX (not the saved config), so unticking hides the
        field instantly even in manual mode where the commit itself waits for
        Save — a Discard re-ticks the box and the field comes straight back."""
        self.osu._container.setVisible(self.cb_lazer_enabled.isChecked())
        self.osu_stable._container.setVisible(self.cb_stable_enabled.isChecked())

    def _sync_client_import_buttons(self) -> None:
        """Hide a disabled client's 'import installed songs' button (v1.4) —
        consistent with its path row vanishing above; follows the checkbox so
        the whole tab reacts instantly even in manual mode (v1.4.2). While an
        import runs the visible buttons stay disabled (the busy bar is showing)."""
        running = self.import_bar.isVisible()
        for btn, on in ((self.btn_import_lazer, self.cb_lazer_enabled.isChecked()),
                        (self.btn_import_stable, self.cb_stable_enabled.isChecked())):
            btn.setVisible(bool(on))
            btn.setEnabled(not running)

    # -- Save / Auto-Save commit mode (v1.4) ---------------------------------
    def _on_autosave_toggled(self, *_) -> None:
        # Entering OR leaving Auto commits the current TOGGLE state, then the
        # commit wiring is switched; _apply_save_mode commits any pending
        # path/API text edits (they stay dirty until actually saved).
        self._apply_client_toggles()   # persist toggles + re-sync visibility
        self._sync_toggle_baseline()
        self._apply_save_mode()

    def _apply_save_mode(self) -> None:
        """Reflect the Save/Auto-Save setting. Auto: hide the Save button and
        commit path/API edits on focus-out. Manual: show Save + keep the
        dirty-guard (the historical behaviour)."""
        auto = bool(self.ctx.cfg.settings_autosave)
        self.btn_save.setVisible(not auto)
        fields = (self.packs, self.output, self.library, self.osu,
                  self.osu_stable, self.client_id, self.client_secret)
        if self._live_connected:                    # only disconnect what we connected
            for f in fields:
                f.editingFinished.disconnect(self._commit_live)
            self._live_connected = False
        if auto:
            for f in fields:
                f.editingFinished.connect(self._commit_live)
            self._live_connected = True
        # Commit anything pending on EITHER mode switch: edits made while Auto
        # was on were meant to be applied live, so flipping to Manual must not
        # retroactively turn them into "unsaved changes" (bogus leave warning).
        if self._is_dirty():
            self._save(silent=True)

    def _commit_live(self) -> None:
        if self.ctx.cfg.settings_autosave:
            self._save(silent=True)

    # -- save (paths + API) --------------------------------------------------
    def _save(self, silent: bool = False) -> bool:
        cfg = self.ctx.cfg
        packs = self.packs.text().strip()
        output = self.output.text().strip()
        library = self.library.text().strip()
        # Commit the TOGGLE unit first: it has no validity constraint, so a bad
        # folder path must never hold unrelated toggle/zip edits hostage (or a
        # later Discard-to-escape would throw them away with the bad path).
        self._apply_client_toggles()
        self._sync_toggle_baseline()
        # Validate the user-editable folders BEFORE mutating the path fields of
        # cfg, so a bad path (Auto-save commits on focus-out) can never corrupt
        # the live config — nothing is assigned unless the paths are creatable.
        try:
            for d in (packs, output, library):
                Path(d).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            msg = self.ctx.t("settings_save_failed", err=str(exc))
            if silent:   # Auto-save on focus-out — inline notice, keep editing
                self.saved_label.setText(msg)
            else:
                QMessageBox.critical(self, self.ctx.t("app_title"), msg)
            return False
        cfg.packs_dir = packs
        cfg.output_dir = output
        cfg.library_dir = library
        cfg.osu_lazer_exe = self.osu.text().strip()
        cfg.osu_stable_exe = self.osu_stable.text().strip()
        cfg.osu_exe = cfg.osu_lazer_exe   # keep the legacy field mirrored
        cfg.osu_client_id = self.client_id.text().strip()
        cfg.osu_client_secret = self.client_secret.text().strip()
        cfg.ensure_dirs()   # create the derived data/logs dirs (user dirs already made)
        self.ctx.save_config()   # persist the path/API unit (toggles saved above)
        self.ctx.log.info("SETTINGS_SAVE", changed="paths,toggles,api")
        self.saved_label.setText(self.ctx.t("saved"))
        self._baseline = self._snapshot()   # edits are now saved — clear dirty (item 11)
        self.mw.dashboard.refresh_scan()
        return True
