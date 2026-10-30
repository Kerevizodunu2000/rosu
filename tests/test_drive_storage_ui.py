# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings shows the Drive storage quota; the Dashboard explains a full Drive.
Offscreen Qt, fake services, no network."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu import config
from rosu.ui.settings_drive import storage_permille

_GIB = 1024 ** 3
_RES = {"limit": 15 * _GIB, "usage": 6 * _GIB, "usage_in_drive": 2 * _GIB,
        "usage_in_drive_trash": 512 * 1024 * 1024, "rosu": _GIB}


@pytest.fixture
def win(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from rosu.app import AppContext
    from rosu.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.check_updates = False
    ctx = AppContext(cfg)
    w = MainWindow(ctx, app)
    w.connected = True
    ctx.services.drive_status = lambda: {"configured": True, "connected": w.connected,
                                         "can_store": True}
    yield w
    w.close()
    ctx.db.close()


# 1
def test_storage_permille():
    assert storage_permille(0, 100) == 0
    assert storage_permille(50, 100) == 500
    assert storage_permille(6 * _GIB, 15 * _GIB) == 400   # beyond 32-bit ints
    assert storage_permille(150, 100) == 1000
    assert storage_permille(-5, 100) == 0
    assert storage_permille(5, None) is None
    assert storage_permille(5, 0) is None


# 2
def test_settings_renders_storage(win):
    s = win.settings
    s._drive_storage_loaded(dict(_RES))
    assert not s.bar_drive_storage.isHidden() and not s.lbl_drive_storage.isHidden()
    assert s.bar_drive_storage.value() == 400
    assert s.bar_drive_storage.maximum() == 1000
    text = s.lbl_drive_storage.text()
    assert "6.00 GB" in text and "15.00 GB" in text and "512.0 MB" in text
    assert s.bar_drive_storage.accessibleName() == "Google Drive storage"
    assert s.bar_drive_storage.accessibleDescription() == text

    win.ctx.i18n.set_language("tr")
    win.retranslate()                        # re-rendered, no new load
    assert s.lbl_drive_storage.text() != text
    assert s.bar_drive_storage.accessibleDescription() == s.lbl_drive_storage.text()
    win.ctx.i18n.set_language("en")
    win.retranslate()

    s._drive_storage_loaded({**_RES, "limit": None})
    assert "Unlimited" in s.lbl_drive_storage.text()
    assert not s.lbl_drive_storage.isHidden()
    assert s.bar_drive_storage.isHidden()


def test_disconnect_hides_storage(win):
    s = win.settings
    s._drive_storage_loaded(dict(_RES))
    win.connected = False
    s._refresh_drive_status()
    assert s.bar_drive_storage.isHidden() and s.lbl_drive_storage.isHidden()


# 3
def test_error_result_hides_storage(win):
    s = win.settings
    s._drive_storage_loaded(dict(_RES))
    s._drive_storage_loaded({"error": "drive"})
    assert s.bar_drive_storage.isHidden() and s.lbl_drive_storage.isHidden()


def test_opening_settings_loads_storage(win):
    calls = []
    win.settings.refresh_drive_storage = lambda: calls.append(1)
    win.ctx.cfg.auto_refresh_on_tab = False
    win.tabs.setCurrentWidget(win.settings)
    assert calls == [1]


# 4
@pytest.mark.parametrize("res,phrase", [
    ({"error": "drive_full", "needed": 2 * _GIB, "free": _GIB, "trash": 0},
     "did not start"),
    ({"error": "drive_full", "uploaded": 3, "chunks": 1}, "3 tracks"),
])
def test_after_backup_drive_full_is_not_a_generic_failure(win, monkeypatch, res, phrase):
    from rosu.ui import dashboard_tab
    shown = []

    class Box:
        @staticmethod
        def warning(parent, title, text):
            shown.append(("warning", text))

        @staticmethod
        def critical(parent, title, text):
            shown.append(("critical", text))

    monkeypatch.setattr(dashboard_tab, "QMessageBox", Box)
    refreshed = []
    win.settings.refresh_drive_storage = lambda: refreshed.append(1)
    win.dashboard._after_backup(res)
    assert [kind for kind, _ in shown] == ["warning"]
    assert phrase in shown[0][1] and "trash" in shown[0][1]
    assert win.dashboard.status.text() != win.ctx.t("drive_backup_failed")
    assert refreshed == [1]
