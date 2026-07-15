# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the v1.3 reveal-in-file-manager helper (rosu/ui/reveal.py)."""
from rosu.ui import reveal


class FakeCtx:
    def t(self, key, **kw):
        return key


def test_reveal_missing_file_warns_and_launches_nothing(tmp_path, monkeypatch):
    warned = []
    launched = []
    monkeypatch.setattr(reveal.QMessageBox, "information",
                        lambda *a, **k: warned.append(a))
    monkeypatch.setattr(reveal.subprocess, "Popen",
                        lambda *a, **k: launched.append(a))
    reveal.reveal_in_explorer(None, FakeCtx(), tmp_path / "gone.osz")
    assert warned and not launched


def test_reveal_windows_selects_with_single_combined_arg(tmp_path, monkeypatch):
    f = tmp_path / "123 Artist - Title.osz"    # a real filename (has spaces)
    f.write_bytes(b"x")
    launched = []
    monkeypatch.setattr(reveal.sys, "platform", "win32")
    monkeypatch.setattr(reveal.subprocess, "Popen",
                        lambda args, **k: launched.append(args))
    reveal.reveal_in_explorer(None, FakeCtx(), f)
    # flag + path MUST be one token, or Explorer ignores /select
    assert launched == [["explorer", f"/select,{f}"]]


def test_reveal_non_windows_opens_containing_folder(tmp_path, monkeypatch):
    f = tmp_path / "x.osz"
    f.write_bytes(b"x")
    monkeypatch.setattr(reveal.sys, "platform", "linux")
    opened = []
    monkeypatch.setattr(reveal.QDesktopServices, "openUrl",
                        lambda url: opened.append(url))

    def _no_popen(*a, **k):
        raise AssertionError("must not launch explorer off Windows")

    monkeypatch.setattr(reveal.subprocess, "Popen", _no_popen)
    reveal.reveal_in_explorer(None, FakeCtx(), f)
    assert len(opened) == 1
