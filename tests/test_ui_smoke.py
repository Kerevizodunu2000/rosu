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


def test_filters_panel_composes_query_tokens(qapp, tmp_path, monkeypatch):
    """The v1.6 filters panel emits valid query-syntax that round-trips through
    rosu.query.parse into the intended structured filters."""
    from rosu import query
    from rosu.ui.filters_panel import FiltersPanel
    ctx = _ctx(tmp_path, monkeypatch)
    fp = FiltersPanel(ctx)
    fp.retranslate()
    fp._on_mode_clicked("osu!mania")            # mania → keys row visible
    fp.star.set_values(4.0, 6.5)
    fp.keys.setCurrentIndex(fp.keys.findData(7))
    toks = fp.filter_tokens()
    assert "mode=mania" in toks and "key=7" in toks
    assert "star>=4" in toks and "star<=6.5" in toks
    got = {(f.field, f.op, f.value) for f in query.parse(" ".join(toks)).filters}
    assert ("mode", "=", "osu!mania") in got
    assert ("key", "=", 7) in got
    assert ("star", ">=", 4.0) in got
    # a mode the Library owns none of is disabled and can't contribute a filter
    fp.set_mode_counts({"osu!mania": 3})
    assert fp.mode_btns["osu!mania"].isEnabled()
    assert not fp.mode_btns["osu!taiko"].isEnabled()
    fp.clear()
    assert fp.filter_tokens() == []
    ctx.db.close()


def test_star_range_export_prefill(qapp, tmp_path, monkeypatch):
    """v1.6: prefill_star_range (from the Search histogram's 'Export this range')
    fills the Shortcuts export star boxes and selects the Library source."""
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    win.shortcuts.prefill_star_range(3.5, 6.0)
    assert win.shortcuts.export_star_lo.value() == 3.5
    assert win.shortcuts.export_star_hi.value() == 6.0
    assert win.shortcuts.export_source.currentData() == "library"
    win.close()
    ctx.db.close()


def test_share_toggle_requires_informed_consent(qapp, tmp_path, monkeypatch):
    """v1.6.3 regression: enabling the public Drive share link must show the
    copyright warning; declining snaps the checkbox back off, accepting keeps it."""
    from PySide6.QtWidgets import QMessageBox
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    ctx.cfg.drive_connected = True
    win = MainWindow(ctx, qapp)
    tab = win.shortcuts
    tab.export_drive.setChecked(True)              # a link needs the upload
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.No)
    tab.export_share.setChecked(True)
    assert not tab.export_share.isChecked()        # declined → snapped back off
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.Yes)
    tab.export_share.setChecked(True)
    assert tab.export_share.isChecked()            # informed consent → stays on
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
