# SPDX-License-Identifier: GPL-3.0-or-later
"""Theme stylesheets generated from palettes.

Generating QSS from a palette (instead of hand-writing one file per theme)
keeps every theme consistent — in particular the header row and the selected-row
highlight, which were the reported pain points. Selected rows always use the
accent colour with a contrasting text colour, so selection is obvious in every
theme (including the pink ones).
"""
from __future__ import annotations

# Each palette: window/surfaces/text/border + accent (buttons) + header + selection.
PALETTES: dict[str, dict[str, str]] = {
    "dark": dict(
        bg="#181825", surface="#262638", table="#202032", alt="#262638",
        text="#e6e6f0", muted="#a8a8c0", border="#313244",
        accent="#ff6aa2", accent_text="#1a1a26", accent_hover="#ff85b5",
        secondary="#313244", secondary_text="#e6e6f0",
        header_bg="#2f2f47", header_text="#c8c8e0",
        sel_bg="#ff6aa2", sel_text="#1a1a26",
        banner_bg="#402633", banner_text="#ffb3cd", banner_border="#ff6aa2"),
    "white": dict(
        bg="#f7f7fb", surface="#ffffff", table="#ffffff", alt="#f4f4fa",
        text="#1e1e2e", muted="#77778c", border="#e0e0ea",
        accent="#ff5a97", accent_text="#ffffff", accent_hover="#ff74a9",
        secondary="#e6e6ef", secondary_text="#1e1e2e",
        header_bg="#f0f0f6", header_text="#55556a",
        sel_bg="#ff5a97", sel_text="#ffffff",
        banner_bg="#ffe6ee", banner_text="#b02864", banner_border="#ff8ab5"),
    "pink": dict(
        bg="#ffe3ef", surface="#fff7fb", table="#fff7fb", alt="#ffeef5",
        text="#3d1f2e", muted="#94577a", border="#ffbdd6",
        accent="#ff4f92", accent_text="#ffffff", accent_hover="#ff69a3",
        secondary="#ffd0e2", secondary_text="#7a2f4f",
        header_bg="#ffe0ec", header_text="#a5326a",
        sel_bg="#ff4f92", sel_text="#ffffff",
        banner_bg="#ffd0e0", banner_text="#a51f57", banner_border="#ff4f92"),
    # Pink · Light — clearly pink (surfaces are pink-tinted, not the white theme's
    # pure #ffffff), so it no longer reads like the White theme (item 2).
    "pink-white": dict(
        bg="#ffe7f1", surface="#fff4f9", table="#fff4f9", alt="#ffdcec",
        text="#3d1f2e", muted="#9a5b7a", border="#ffbcd6",
        accent="#ff3d86", accent_text="#ffffff", accent_hover="#ff5f9c",
        secondary="#ffd0e2", secondary_text="#7a2f4f",
        header_bg="#ffd2e5", header_text="#a5326a",
        sel_bg="#ff3d86", sel_text="#ffffff",
        banner_bg="#ffd0e0", banner_text="#a51f57", banner_border="#ff5f9c"),
    "pink-dark": dict(
        bg="#201019", surface="#2c1826", table="#281624", alt="#331b2c",
        text="#ffe3ef", muted="#c893ad", border="#452638",
        accent="#ff4f92", accent_text="#201019", accent_hover="#ff69a3",
        secondary="#3a2030", secondary_text="#ffd0e2",
        header_bg="#3a2030", header_text="#ffb3d1",
        sel_bg="#ff4f92", sel_text="#201019",
        banner_bg="#3a2030", banner_text="#ffb3d1", banner_border="#ff4f92"),
    # Pink · Darker — deeper than pink-dark: near-black with a rose undertone (item 23).
    "pink-darker": dict(
        bg="#140a10", surface="#1f0e18", table="#1a0c14", alt="#250f1b",
        text="#ffd9e8", muted="#b87f9a", border="#3a1c2c",
        accent="#ff3d86", accent_text="#140a10", accent_hover="#ff5f9c",
        secondary="#2a1420", secondary_text="#ffc2da",
        header_bg="#2a1420", header_text="#ff9dc2",
        sel_bg="#ff3d86", sel_text="#140a10",
        banner_bg="#2a1420", banner_text="#ff9dc2", banner_border="#ff3d86"),
    "nord": dict(
        bg="#2e3440", surface="#3b4252", table="#2e3440", alt="#3b4252",
        text="#eceff4", muted="#aab1c2", border="#434c5e",
        accent="#88c0d0", accent_text="#2e3440", accent_hover="#8fbcbb",
        secondary="#434c5e", secondary_text="#eceff4",
        header_bg="#434c5e", header_text="#d8dee9",
        sel_bg="#5e81ac", sel_text="#eceff4",
        banner_bg="#4c566a", banner_text="#e5e9f0", banner_border="#bf616a"),
    "dracula": dict(
        bg="#282a36", surface="#343746", table="#282a36", alt="#2f3240",
        text="#f8f8f2", muted="#9aa0c0", border="#44475a",
        accent="#bd93f9", accent_text="#282a36", accent_hover="#ff79c6",
        secondary="#44475a", secondary_text="#f8f8f2",
        header_bg="#44475a", header_text="#f8f8f2",
        sel_bg="#6272a4", sel_text="#f8f8f2",
        banner_bg="#44475a", banner_text="#ff79c6", banner_border="#ff5555"),
    "catppuccin-mocha": dict(
        bg="#1e1e2e", surface="#313244", table="#1e1e2e", alt="#232336",
        text="#cdd6f4", muted="#a6adc8", border="#45475a",
        accent="#f5c2e7", accent_text="#1e1e2e", accent_hover="#cba6f7",
        secondary="#313244", secondary_text="#cdd6f4",
        header_bg="#313244", header_text="#bac2de",
        sel_bg="#585b70", sel_text="#cdd6f4",
        banner_bg="#45475a", banner_text="#f5c2e7", banner_border="#f38ba8"),
    "catppuccin-latte": dict(
        bg="#eff1f5", surface="#ffffff", table="#ffffff", alt="#e6e9ef",
        text="#4c4f69", muted="#6c6f85", border="#ccd0da",
        accent="#ea76cb", accent_text="#ffffff", accent_hover="#8839ef",
        secondary="#e6e9ef", secondary_text="#4c4f69",
        header_bg="#e6e9ef", header_text="#5c5f77",
        sel_bg="#ea76cb", sel_text="#ffffff",
        banner_bg="#f7dff0", banner_text="#d20f39", banner_border="#ea76cb"),
    "solarized-dark": dict(
        bg="#002b36", surface="#073642", table="#002b36", alt="#073642",
        text="#93a1a1", muted="#839496", border="#586e75",
        accent="#268bd2", accent_text="#fdf6e3", accent_hover="#2aa198",
        secondary="#073642", secondary_text="#93a1a1",
        header_bg="#073642", header_text="#93a1a1",
        sel_bg="#586e75", sel_text="#fdf6e3",
        banner_bg="#073642", banner_text="#b58900", banner_border="#dc322f"),
    "solarized-light": dict(
        bg="#fdf6e3", surface="#ffffff", table="#fdf6e3", alt="#eee8d5",
        text="#586e75", muted="#657b83", border="#ded8c0",
        accent="#268bd2", accent_text="#fdf6e3", accent_hover="#2aa198",
        secondary="#eee8d5", secondary_text="#586e75",
        header_bg="#eee8d5", header_text="#586e75",
        sel_bg="#268bd2", sel_text="#fdf6e3",
        banner_bg="#eee8d5", banner_text="#b58900", banner_border="#cb4b16"),
}

_TEMPLATE = """
QWidget {{ background-color: {bg}; color: {text};
    font-family: "Segoe UI", "Noto Sans", sans-serif; font-size: 13px; }}
QMainWindow, QDialog, QScrollArea {{ background-color: {bg}; }}
QScrollArea {{ border: none; }}

QTabWidget::pane {{ border: 1px solid {border}; border-radius: 6px; }}
QTabBar::tab {{ background: {surface}; color: {muted};
    padding: 8px 16px; margin-right: 2px;
    border-top-left-radius: 6px; border-top-right-radius: 6px; }}
QTabBar::tab:selected {{ background: {accent}; color: {accent_text}; }}
QTabBar::tab:hover:!selected {{ background: {header_bg}; }}

QPushButton {{ background-color: {accent}; color: {accent_text};
    border: none; border-radius: 6px; padding: 9px 16px; font-weight: 600; }}
QPushButton:hover {{ background-color: {accent_hover}; }}
QPushButton:disabled {{ background-color: {border}; color: {muted}; }}
QPushButton#secondary {{ background-color: {secondary}; color: {secondary_text}; }}
QPushButton#secondary:hover {{ background-color: {header_bg}; }}

QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {{
    background-color: {surface}; border: 1px solid {border};
    border-radius: 6px; padding: 6px 8px; color: {text};
    selection-background-color: {accent}; selection-color: {accent_text}; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {accent}; }}
QComboBox QAbstractItemView {{ background: {surface}; color: {text};
    selection-background-color: {accent}; selection-color: {accent_text}; }}

QTableView, QTableWidget {{ background-color: {table};
    alternate-background-color: {alt}; gridline-color: {border};
    border: 1px solid {border}; border-radius: 6px; }}
QTableView::item:selected, QTableWidget::item:selected {{
    background: {sel_bg}; color: {sel_text}; }}
QHeaderView::section {{ background-color: {header_bg}; color: {header_text};
    padding: 6px; border: none; border-right: 1px solid {border}; font-weight: 600; }}
QTableCornerButton::section {{ background: {header_bg}; border: none; }}

QProgressBar {{ border: 1px solid {border}; border-radius: 6px;
    background: {surface}; text-align: center; color: {text}; }}
QProgressBar::chunk {{ background-color: {accent}; border-radius: 5px; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid {border}; background: {surface}; }}
QCheckBox::indicator:checked {{ background: {accent}; border: 1px solid {accent}; }}

QSplitter::handle {{ background: {border}; }}
QLabel#banner {{ background-color: {banner_bg}; color: {banner_text};
    border: 1px solid {banner_border}; border-radius: 6px; padding: 8px 12px; }}
QLabel#h1 {{ font-size: 20px; font-weight: 700; color: {text}; }}
QLabel#status {{ color: {muted}; }}
QToolTip {{ background-color: {surface}; color: {text};
    border: 1px solid {accent}; border-radius: 4px; padding: 4px 8px; }}
QScrollBar:vertical {{ background: {bg}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 6px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: {bg}; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 6px; min-width: 24px; }}
"""


def stylesheet_for(theme: str) -> str:
    pal = PALETTES.get(theme) or PALETTES["dark"]
    return _TEMPLATE.format(**pal)
