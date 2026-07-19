# SPDX-License-Identifier: GPL-3.0-or-later
"""i18n dictionary integrity + startup-failure helpers (v1.6.3)."""
from rosu.app import _error_line
from rosu.i18n import I18N, STRINGS


def test_all_keys_have_en_and_tr():
    # Every UI string must ship both languages — a missing entry surfaces as a
    # raw key name in the running app, which no test used to catch.
    missing = [k for k, v in STRINGS.items()
               if not (isinstance(v, dict) and v.get("en") and v.get("tr"))]
    assert missing == []


def test_db_init_error_strings_format():
    for lang in ("en", "tr"):
        i18n = I18N(lang)
        body = i18n.t("err_db_init_body", path="C:/x/rosu.db", error="boom")
        assert "C:/x/rosu.db" in body and "boom" in body
        assert i18n.t("err_db_init_title")


def test_error_line_is_one_readable_line():
    assert _error_line(ValueError("bad header")) == "ValueError: bad header"
