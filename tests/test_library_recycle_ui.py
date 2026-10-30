# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings and Shortcuts show a refused Library delete (issue #42)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu import config, theming


@pytest.fixture
def ui(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from rosu.app import AppContext
    from rosu.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a))
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.check_updates = False
    ctx = AppContext(cfg)
    saves = []
    real_save = ctx.save_config
    monkeypatch.setattr(ctx, "save_config", lambda: (saves.append(1), real_save()))
    app.setStyleSheet(theming.stylesheet_for("dark"))
    win = MainWindow(ctx, app)
    yield ctx, win, warnings, saves
    app.setStyleSheet("")
    win.close()
    ctx.db.close()


def test_purge_refusal_turns_the_physical_copy_back_on(ui):
    ctx, win, warnings, saves = ui
    ctx.cfg.library_physical_copy = False
    win.settings.cb_physical.blockSignals(True)
    win.settings.cb_physical.setChecked(False)
    win.settings.cb_physical.blockSignals(False)
    win.settings._on_purge_done({"deleted": 0, "error": "no_recycle_bin"})
    assert ctx.cfg.library_physical_copy is True
    assert win.settings.cb_physical.isChecked() is True
    assert saves and len(warnings) == 1
    assert win.settings.saved_label.text() == ctx.t("lib_err_no_recycle_bin")


def test_purge_done_names_files_kept_as_too_large(ui):
    ctx, win, _, _ = ui
    win.settings._on_purge_done({"deleted": 3, "too_large": 2})
    text = win.settings.saved_label.text()
    assert ctx.t("physical_off_done", n=3) in text and ctx.t("lib_kept_too_large", n=2) in text
    win.settings._on_purge_done({"deleted": 3, "too_large": 0})
    assert win.settings.saved_label.text() == ctx.t("physical_off_done", n=3)


def test_dedup_refusal_and_too_large_on_the_shortcuts_status(ui):
    ctx, win, _, _ = ui
    win.shortcuts._present_dedup({"removed": 0, "freed_bytes": 0, "groups": 0,
                                  "error": "no_recycle_bin"})
    assert win.shortcuts.status.text() == ctx.t("lib_err_no_recycle_bin")
    win.shortcuts._present_dedup({"removed": 1, "freed_bytes": 10, "groups": 1, "too_large": 2})
    assert ctx.t("lib_kept_too_large", n=2) in win.shortcuts.status.text()


def test_turkish_refusal_wraps_on_the_settings_label(ui):
    ctx, win, _, _ = ui
    ctx.i18n.set_language("tr")
    win.retranslate()
    label = win.settings.saved_label
    label.setText(ctx.t("lib_err_no_recycle_bin"))
    label.ensurePolished()
    assert label.wordWrap() is True
    assert label.minimumSizeHint().width() < 1280
