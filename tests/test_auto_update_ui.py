# SPDX-License-Identifier: GPL-3.0-or-later
"""Auto-update in the main window and Settings (offscreen Qt, no network)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu import config, updater

NEWER = {"newer": True, "tag": "v9.9.9", "url": "https://x/rel"}


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)  # no repo write
    from rosu.app import AppContext
    from rosu.ui.main_window import MainWindow
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.check_updates = False    # keep the startup check worker out of the test
    ctx = AppContext(cfg)
    w = MainWindow(ctx, qapp)
    yield w
    w.close()
    ctx.db.close()


def _wait(qapp, w):
    for t in list(w._threads):
        t.wait(5000)
    qapp.processEvents()
    qapp.processEvents()


def test_newer_release_starts_a_download(qapp, win, monkeypatch):
    monkeypatch.setattr(updater, "can_auto_update", lambda cfg: True)
    calls = []

    def fake_download(cfg, tag, cancel=None, progress=None):
        calls.append((tag, cancel))
        progress({"percent": 42})
        return {"status": updater.READY, "tag": tag}

    monkeypatch.setattr(updater, "download", fake_download)
    win._on_update_checked(NEWER)
    assert win._threads and "Downloading" in win.update_banner.text()
    _wait(qapp, win)
    assert calls and calls[0][0] == "v9.9.9" and calls[0][1] is win._update_cancel
    assert win.update_banner.text() == "Rosu v9.9.9 is ready."
    assert not win.update_restart.isHidden()


def test_progress_shows_the_percentage(win):
    win._update_info = NEWER
    win._update_phase = "downloading"
    win._on_update_progress({"percent": 37})
    assert "37%" in win.update_banner.text() and "v9.9.9" in win.update_banner.text()
    assert win.update_restart.isHidden()


def test_ready_shows_a_focusable_restart_button(win):
    from PySide6.QtCore import Qt
    win._update_info = NEWER
    win._on_update_downloaded({"status": updater.READY, "tag": "v9.9.9"})
    assert win.update_banner.text() == "Rosu v9.9.9 is ready."
    btn = win.update_restart
    assert not btn.isHidden() and btn.isEnabled()
    assert btn.text() == "Restart now"
    assert btn.focusPolicy() & Qt.TabFocus


def test_restart_with_a_task_running_arms_and_cancels(win, monkeypatch):
    from rosu.ui import main_window
    shown = []
    monkeypatch.setattr(main_window.QMessageBox, "information",
                        lambda *a, **k: shown.append(a))
    monkeypatch.setattr(win, "_operation_running", lambda: True)
    closed = []
    monkeypatch.setattr(win, "close", lambda: closed.append(1) or True)
    win._update_info = NEWER
    win._on_update_downloaded({"status": updater.READY, "tag": "v9.9.9"})
    win.update_restart.click()
    assert shown == [] and closed == [] and win.restart_for_update is False
    assert "will restart when the current task finishes" in win.update_banner.text()
    assert win.update_restart.text() == "Cancel restart"
    assert win._restart_timer.isActive()
    win.update_restart.click()
    assert win.update_restart.text() == "Restart now"
    assert not win._restart_timer.isActive()


def test_restart_closes_the_window(win, monkeypatch):
    monkeypatch.setattr(win, "_operation_running", lambda: False)
    closed = []
    monkeypatch.setattr(win, "close", lambda: closed.append(1) or True)
    win._update_info = NEWER
    win._on_update_downloaded({"status": updater.READY, "tag": "v9.9.9"})
    win.update_restart.click()
    assert win.restart_for_update is True and closed == [1]


def test_refused_close_resets_the_restart_flag(win, monkeypatch):
    monkeypatch.setattr(win, "_operation_running", lambda: False)
    monkeypatch.setattr(win, "close", lambda: False)
    win._on_restart_now()
    assert win.restart_for_update is False


def test_close_sets_the_download_cancel_event(win):
    import threading
    win._update_cancel = threading.Event()
    win.close()
    assert win._update_cancel.is_set()


def test_not_eligible_renders_todays_banner(win, monkeypatch):
    monkeypatch.setattr(updater, "can_auto_update", lambda cfg: False)
    started = []
    monkeypatch.setattr(win, "_start_update_download", lambda tag: started.append(tag))
    win._on_update_checked(NEWER)
    assert started == [] and win._threads == []
    assert "Rosu v9.9.9 is available." in win.update_banner.text()
    assert win.update_restart.isHidden()


@pytest.mark.parametrize("res", [{"status": updater.BANNER}, None])
def test_banner_result_or_failure_renders_todays_banner(qapp, win, monkeypatch, res):
    monkeypatch.setattr(updater, "can_auto_update", lambda cfg: True)

    def fake_download(cfg, tag, cancel=None, progress=None):
        if res is None:
            raise OSError("network down")
        return res

    monkeypatch.setattr(updater, "download", fake_download)
    win._on_update_checked(NEWER)
    _wait(qapp, win)
    assert "Rosu v9.9.9 is available." in win.update_banner.text()
    assert win.update_restart.isHidden()


def test_auto_update_setting(win):
    assert config.Config().auto_update is True
    tab = win.settings
    assert tab.cb_auto_update.isChecked()
    assert "auto_update" in tab._TOGGLE_KEYS
    win.ctx.cfg.settings_autosave = True
    tab.cb_auto_update.setChecked(False)
    assert win.ctx.cfg.auto_update is False
    tab.cb_auto_update.setChecked(True)
    assert win.ctx.cfg.auto_update is True


def test_restart_button_matches_the_banner_and_keeps_off_the_edge(qapp, win):
    from rosu.app import load_stylesheet
    qapp.setStyleSheet(load_stylesheet(win.ctx.cfg.theme))   # real banner padding
    try:
        win.resize(1280, 600)
        win.show()
        win._update_info = NEWER
        win._on_update_downloaded({"status": updater.READY, "tag": "v9.9.9"})
        qapp.processEvents()
        banner, btn = win.update_banner.geometry(), win.update_restart.geometry()
        assert btn.height() == banner.height() and btn.top() == banner.top()
        assert btn.left() - banner.right() - 1 == 12                # the 12 px inset
        assert win.centralWidget().width() - btn.right() - 1 == 12  # off the edge
        win._on_update_downloaded(None)                            # today's banner
        qapp.processEvents()
        assert win.update_restart.isHidden()
        assert win.update_banner.geometry().right() == win.centralWidget().width() - 1
    finally:
        qapp.setStyleSheet("")


def test_auto_update_follows_the_check_updates_toggle(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    from rosu.app import AppContext
    from rosu.ui.main_window import MainWindow
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.check_updates = False
    ctx = AppContext(cfg)
    w = MainWindow(ctx, qapp)
    try:
        tab = w.settings
        assert not tab.cb_auto_update.isEnabled()        # off at build time
        tab.cb_check_updates.setChecked(True)
        assert tab.cb_auto_update.isEnabled()
        tab.cb_check_updates.setChecked(False)
        assert not tab.cb_auto_update.isEnabled()
        tab._restore({**tab._snapshot(), "check_updates": True})   # Discard path
        assert tab.cb_auto_update.isEnabled()
    finally:
        w.close()
        ctx.db.close()
