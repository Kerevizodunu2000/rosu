"""Settings tab: language, theme, folders, osu! path, toggles and API reference."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
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
        root.addLayout(form)

        self.lang = QComboBox()
        self.lang.addItem("English", "en")
        self.lang.addItem("Türkçe", "tr")
        self.lang.setCurrentIndex(0 if cfg.language == "en" else 1)
        self.lang.currentIndexChanged.connect(self._apply_language)
        self.lbl_lang = QLabel()
        form.addRow(self.lbl_lang, self.lang)

        self.theme = QComboBox()
        for name in config.THEMES:
            self.theme.addItem(name, name)
        self._select_theme(cfg.theme)
        self.theme.currentIndexChanged.connect(self._apply_theme)
        self.lbl_theme = QLabel()
        form.addRow(self.lbl_theme, self.theme)

        self.packs = self._path_row(form, cfg.packs_dir, is_dir=True)
        self.output = self._path_row(form, cfg.output_dir, is_dir=True)
        self.library = self._path_row(form, cfg.library_dir, is_dir=True)
        self.osu = self._path_row(form, cfg.osu_exe, is_dir=False)

        self.cb_physical = QCheckBox(); self.cb_physical.setChecked(cfg.library_physical_copy)
        self.cb_clear_before = QCheckBox(); self.cb_clear_before.setChecked(cfg.clear_output_before_extract)
        self.cb_auto_backup = QCheckBox(); self.cb_auto_backup.setChecked(cfg.auto_backup_after_extract)
        for cb in (self.cb_physical, self.cb_auto_backup, self.cb_clear_before):
            root.addWidget(cb)

        zip_row = QHBoxLayout()
        self.lbl_zip = QLabel()
        self.zip = QComboBox()
        for v in _ZIP_ORDER:
            self.zip.addItem("", v)
        self.zip.setCurrentIndex(_ZIP_ORDER.index(cfg.zip_disposal)
                                 if cfg.zip_disposal in _ZIP_ORDER else 0)
        zip_row.addWidget(self.lbl_zip); zip_row.addWidget(self.zip); zip_row.addStretch(1)
        root.addLayout(zip_row)

        # Toggles apply immediately (like Language/Theme) so a checked box takes
        # effect without also pressing Save — fixes "I enabled Auto-copy but it
        # didn't run" (item 6). Paths still commit via the Save button.
        for cb in (self.cb_auto_backup, self.cb_clear_before):
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

        root.addStretch(1)
        bottom = QHBoxLayout()
        self.saved_label = QLabel(objectName="status")
        self.btn_save = QPushButton()
        self.btn_save.clicked.connect(self._save)
        bottom.addWidget(self.saved_label, 1)
        bottom.addWidget(self.btn_save)
        root.addLayout(bottom)

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
        self.osu._label.setText(t("set_osu_exe"))
        for f in (self.packs, self.output, self.library, self.osu):
            f._browse.setText(t("btn_browse"))
        self.cb_physical.setText(t("set_physical_copy"))
        self.cb_auto_backup.setText(t("set_auto_backup"))
        self.cb_clear_before.setText(t("set_clear_output_before"))
        self.lbl_zip.setText(t("set_zip_disposal"))
        self.zip.setItemText(0, t("zip_recycle"))
        self.zip.setItemText(1, t("zip_move"))
        self.zip.setItemText(2, t("zip_delete"))
        self.lbl_api.setText(t("set_osu_api"))
        self.lbl_api_help.setText(t("reference_help"))
        self.lbl_cid.setText(t("set_client_id"))
        self.lbl_cs.setText(t("set_client_secret"))
        self.btn_reference.setText(t("btn_update_reference"))
        self.btn_save.setText(t("btn_save"))
        self._refresh_reference_status()

    def _refresh_reference_status(self) -> None:
        from .. import osu_api
        ref = osu_api.load_reference(self.ctx.cfg.reference_path)
        if ref:
            self.lbl_ref_status.setText(self.ctx.t(
                "reference_status", n=ref.get("count", 0), when=ref.get("fetched_at", "")))
        else:
            self.lbl_ref_status.setText(self.ctx.t("reference_none"))

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
        cfg.zip_disposal = self.zip.currentData()
        self.ctx.save_config()
        self.saved_label.setText(self.ctx.t("saved"))

    # -- save (paths + API) --------------------------------------------------
    def _save(self) -> None:
        cfg = self.ctx.cfg
        cfg.packs_dir = self.packs.text().strip()
        cfg.output_dir = self.output.text().strip()
        cfg.library_dir = self.library.text().strip()
        cfg.osu_exe = self.osu.text().strip()
        self._apply_toggles()
        cfg.osu_client_id = self.client_id.text().strip()
        cfg.osu_client_secret = self.client_secret.text().strip()
        cfg.ensure_dirs()
        self.ctx.save_config()
        self.ctx.log.info("SETTINGS_SAVE", changed="paths,toggles,api")
        self.saved_label.setText(self.ctx.t("saved"))
        self.mw.dashboard.refresh_scan()
