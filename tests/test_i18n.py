# SPDX-License-Identifier: GPL-3.0-or-later
"""i18n dictionary integrity + startup-failure helpers (v1.6.3)."""
import re
from pathlib import Path

from rosu.app import _error_line
from rosu.i18n import I18N, STRINGS

_SRC = Path(__file__).resolve().parent.parent / "rosu"
# t("some_key" / self.ctx.t('some_key' — literal keys only. Dynamic ones
# (t(f"sc_source_{x}"), t(job.title_key), t(k)) can't be checked statically and
# are skipped by construction.
_T_CALL = re.compile(r"""\bt\(\s*["']([A-Za-z0-9_]+)["']""")


def test_all_keys_have_en_and_tr():
    # Every UI string must ship both languages — a missing entry surfaces as a
    # raw key name in the running app, which no test used to catch.
    missing = [k for k, v in STRINGS.items()
               if not (isinstance(v, dict) and v.get("en") and v.get("tr"))]
    assert missing == []


def test_no_key_is_defined_twice():
    """A repeated key in the STRINGS literal silently keeps only the last value:
    v1.8's "Remove" step label replaced the dedup job's "Recycle duplicates"
    that way. Read the source, since the dict itself cannot show it."""
    import ast
    tree = ast.parse((_SRC / "i18n.py").read_text(encoding="utf-8"))
    dupes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and len(node.keys) > 50:   # the STRINGS table
            seen = set()
            for k in node.keys:
                if isinstance(k, ast.Constant):
                    if k.value in seen:
                        dupes.append(k.value)
                    seen.add(k.value)
    assert dupes == []


def test_every_literal_t_key_in_the_source_exists():
    """Guard against the v1.7.0 failure mode: ~15 new UI strings were written
    assuming ``t(key, default="…")`` was a supported fallback. It isn't — a
    missing key renders as the raw key name, and nothing failed until a human
    opened that screen. This checks every literal key actually exists."""
    missing: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for key in _T_CALL.findall(text):
            if key not in STRINGS:
                missing.append(f"{path.relative_to(_SRC.parent)}: {key}")
    assert missing == []


def test_missing_key_renders_as_the_raw_key_even_with_a_default():
    """Pins the trap the v1.7.0 code fell into: ``t()`` swallows an unknown
    ``default=`` (it is just another format kwarg) and returns the RAW KEY, so
    ``t("some_key", default="Some text")`` shows "some_key" on screen and nothing
    complains. There is no fallback — the key must exist."""
    i18n = I18N("en")
    assert i18n.t("definitely_not_a_key") == "definitely_not_a_key"
    assert i18n.t("definitely_not_a_key", default="fallback") == "definitely_not_a_key"


def test_db_init_error_strings_format():
    for lang in ("en", "tr"):
        i18n = I18N(lang)
        body = i18n.t("err_db_init_body", path="C:/x/rosu.db", error="boom")
        assert "C:/x/rosu.db" in body and "boom" in body
        assert i18n.t("err_db_init_title")


def test_error_line_is_one_readable_line():
    assert _error_line(ValueError("bad header")) == "ValueError: bad header"
