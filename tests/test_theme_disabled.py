# SPDX-License-Identifier: GPL-3.0-or-later
"""Disabled controls get their own look in every theme (issue #63)."""
from __future__ import annotations

import re

import pytest

from rosu import theming
from tests.test_theme_contrast import ratio

THEMES = list(theming.PALETTES)
DISABLED = ("QCheckBox::indicator:disabled", "QCheckBox::indicator:checked:disabled",
            "QRadioButton::indicator:disabled", "QRadioButton::indicator:checked:disabled",
            "QPushButton:disabled", "QPushButton#secondary:disabled",
            "QCheckBox:disabled", "QRadioButton:disabled")


def rule(css: str, selector: str) -> dict[str, str]:
    m = re.search(r"^" + re.escape(selector) + r" \{([^}]*)\}", css, re.M)
    assert m, f"no rule for {selector}"
    return {k.strip(): v.strip() for k, v in
            (d.split(":", 1) for d in m.group(1).split(";") if d.strip())}


def test_template_has_no_hex_literals():
    assert not re.search(r"#[0-9a-fA-F]{6}", theming._TEMPLATE)


def test_there_are_12_themes():
    assert len(THEMES) == 12


@pytest.mark.parametrize("theme", THEMES)
def test_disabled_rules_use_palette_colours(theme):
    css, pal = theming.stylesheet_for(theme), theming.PALETTES[theme]
    for sel in DISABLED:
        props = rule(css, sel)
        colours = re.findall(r"#[0-9a-fA-F]{6}", " ".join(props.values()))
        assert colours, sel
        assert set(colours) <= set(pal.values()), sel


@pytest.mark.parametrize("theme", THEMES)
def test_disabled_text_is_readable(theme):
    css, pal = theming.stylesheet_for(theme), theming.PALETTES[theme]
    for sel in ("QPushButton:disabled", "QPushButton#secondary:disabled"):
        props = rule(css, sel)
        assert ratio(props["color"], props["background-color"]) >= 3, sel
    for sel in ("QCheckBox:disabled", "QRadioButton:disabled"):
        for surface in ("bg", "surface", "alt"):
            assert ratio(rule(css, sel)["color"], pal[surface]) >= 3, (sel, surface)


@pytest.mark.parametrize("theme", THEMES)
def test_disabled_differs_from_enabled(theme):
    css = theming.stylesheet_for(theme)
    for kind in ("QCheckBox", "QRadioButton"):
        on, off = rule(css, f"{kind}::indicator"), rule(css, f"{kind}::indicator:disabled")
        assert off["background"] != on["background"] and "dashed" in off["border"]
        assert "solid" in on["border"]
        checked = rule(css, f"{kind}::indicator:checked:disabled")
        assert checked["background"] != off["background"]
    base = rule(css, "QPushButton")["background-color"]
    sec = rule(css, "QPushButton#secondary")["background-color"]
    for sel in ("QPushButton:disabled", "QPushButton#secondary:disabled"):
        assert rule(css, sel)["background-color"] not in (base, sec), sel
