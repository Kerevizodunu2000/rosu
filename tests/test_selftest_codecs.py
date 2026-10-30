# SPDX-License-Identifier: GPL-3.0-or-later
"""--selftest checks the 7z codecs (BCJ + LZMA2 roundtrip) of a packaged build."""
import sys

from rosu import selftest_codecs


def test_codecs_work_on_source_tree():
    assert selftest_codecs.check_codecs() is None


def test_missing_module_reports_one_line_reason():
    reason = selftest_codecs.check_codecs(("os", "bcj_not_installed"))
    assert reason and "\n" not in reason
    assert "bcj" in reason and "ModuleNotFoundError" in reason


def test_selftest_fails_when_codec_check_fails(tmp_path, monkeypatch, capsys):
    from PySide6.QtWidgets import QApplication
    from rosu import app as app_mod, config, updater
    qapp = QApplication.instance() or QApplication([])
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    monkeypatch.setattr(config, "load_config", lambda: cfg)
    monkeypatch.setattr(config, "save_config", lambda c: None)
    monkeypatch.setattr(updater, "on_startup", lambda *a, **k: "keep")
    monkeypatch.setattr(app_mod, "_heal_paths", lambda c, headless: None)
    monkeypatch.setattr(app_mod, "QApplication", lambda argv: qapp)
    monkeypatch.setattr(sys, "argv", ["rosu", "--selftest"])
    monkeypatch.setattr(selftest_codecs, "check_codecs", lambda: "ImportError: bcj")
    assert app_mod.run() == 1
    assert "selftest FAIL (ImportError: bcj)" in capsys.readouterr().out
