# SPDX-License-Identifier: GPL-3.0-or-later
"""The Shortcuts tab status line wraps, so a long message never widens the window."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from rosu import config, theming


def test_long_status_message_keeps_the_tab_under_the_default_width(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from rosu.app import AppContext
    from rosu.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.check_updates = False
    ctx = AppContext(cfg)
    app.setStyleSheet(theming.stylesheet_for("dark"))
    win = MainWindow(ctx, app)
    ctx.i18n.set_language("tr")
    win.retranslate()
    tab = win.shortcuts
    tab._set_status("rm_err_no_recycle_bin")
    tab.ensurePolished()
    tab.status.ensurePolished()
    assert tab.status.fontMetrics().horizontalAdvance(tab.status.text()) > 1280   # one line would not fit
    assert tab.minimumSizeHint().width() < 1280                                   # main window default
    app.setStyleSheet("")
    win.close()
    ctx.db.close()
