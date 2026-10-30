# SPDX-License-Identifier: GPL-3.0-or-later
"""Dashboard and Shortcuts tell the user when staging failed and nothing was sent."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu import config, theming


@pytest.fixture
def win(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from rosu.app import AppContext
    from rosu.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.check_updates = False
    ctx = AppContext(cfg)
    app.setStyleSheet(theming.stylesheet_for("dark"))
    w = MainWindow(ctx, app)
    w.calls = {"warning": [], "information": []}
    for kind in w.calls:
        monkeypatch.setattr(
            QMessageBox, kind,
            staticmethod(lambda parent, title, text, _k=kind, **kw: w.calls[_k].append(text)))
    w.t = ctx.t
    yield w
    app.setStyleSheet("")
    w.close()
    ctx.db.close()


def test_dashboard_nothing_staged(win):
    win.dashboard._after_import({"files": 0, "batches": 0, "sent": 0, "cancelled": False,
                                 "stage_failed": 3, "disk_full": True})
    want = win.t("import_stage_disk_full", n=3)
    assert win.dashboard.status.text() == want
    assert win.calls["warning"] == [want]
    assert win.calls["information"] == []


def test_dashboard_partly_staged(win):
    win.dashboard._after_import({"files": 2, "batches": 1, "sent": 2, "cancelled": False,
                                 "stage_failed": 1, "disk_full": False})
    warn = win.t("import_stage_failed", n=1)
    text = win.dashboard.status.text()
    assert win.t("import_done", files=2, batches=1) in text and warn in text
    assert len(win.calls["warning"]) == 1 and warn in win.calls["warning"][0]
    assert win.t("osu_keep_open") in win.calls["warning"][0]
    assert win.calls["information"] == []


def test_dashboard_unchanged_without_stage_failed(win):
    win.dashboard._after_import({"files": 2, "batches": 1, "sent": 2, "cancelled": False})
    assert win.calls["information"] == [win.t("osu_keep_open")]
    assert win.calls["warning"] == []


def test_dashboard_status_wraps(win):
    assert win.dashboard.status.wordWrap()


def test_unpack_warning_sums_targets(win):
    win.shortcuts._present_unpack({"extract": {"tracks": 0}, "imports": {
        "lazer": {"stage_failed": 2}, "stable": {"stage_failed": 1, "disk_full": True}}})
    assert len(win.calls["warning"]) == 1
    assert win.t("import_stage_disk_full", n=3) in win.calls["warning"][0]
