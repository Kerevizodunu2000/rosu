# SPDX-License-Identifier: GPL-3.0-or-later
"""The About dialog reads the bundled legal notices (item B, v1.0)."""
from rosu.ui.about_dialog import _bundled_text


def test_bundled_third_party_notices_readable():
    text = _bundled_text("THIRD-PARTY-LICENSES.md")
    assert "Third-Party Licenses" in text
    assert "PySide6" in text


def test_bundled_missing_file_returns_empty():
    assert _bundled_text("does-not-exist-xyz.md") == ""
