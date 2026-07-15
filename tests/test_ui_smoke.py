# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless construction smoke test for the whole UI (offscreen Qt).

`run.py --selftest` boots config/theme/db but does NOT build the main window, so
this is the only automated check that every tab constructs and retranslates
without error — covering the v1.0 UI changes (dual import buttons, About dialog,
lost-map button, Output view, update banner). No network is used: the startup
update check is disabled for the test.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu import config


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)  # no repo write
    from rosu.app import AppContext
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.check_updates = False    # keep the network worker out of the test
    return AppContext(cfg)


def test_main_window_builds_and_retranslates(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    ctx.i18n.set_language("tr")
    win.retranslate()
    ctx.i18n.set_language("en")
    win.retranslate()
    win.close()
    ctx.db.close()


def test_update_banner_renders_when_newer(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    # isHidden() reflects the explicit hidden flag without needing a shown window.
    assert win.update_banner.isHidden()          # hidden by default
    win._on_update_checked({"newer": True, "tag": "v9.9.9", "url": "https://x/rel"})
    assert not win.update_banner.isHidden()      # revealed on a newer release
    assert "9.9.9" in win.update_banner.text()
    win.close()
    ctx.db.close()


def test_update_banner_stays_hidden_when_not_newer(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    win._on_update_checked({"newer": False, "tag": "v0.0.1", "url": "u"})
    assert win.update_banner.isHidden()
    win.close()
    ctx.db.close()


def test_health_dialog_builds_and_renders_report(qapp, tmp_path, monkeypatch):
    """The v1.1 Library Health dialog constructs and populates from a report."""
    from rosu.ui.health_dialog import HealthDialog
    ctx = _ctx(tmp_path, monkeypatch)
    report = {
        "usage": {"files": 2, "total_bytes": 3_500_000},
        "scrub": {"present": 1, "orphans": ["x.osz"],
                  "dead_links": [{"filename": "y.osz"}], "memory": 0},
        "biggest": [{"filename": "big.osz", "size_bytes": 3_000_000,
                     "display_name": "Artist - Big"}],
    }
    dlg = HealthDialog(ctx, report, None)
    assert dlg.table.rowCount() == 1
    assert "big" in dlg.table.item(0, 0).text().lower()
    ctx.i18n.set_language("tr")
    dlg.retranslate()
    ctx.i18n.set_language("en")
    dlg.close()
    ctx.db.close()
