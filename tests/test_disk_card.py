# SPDX-License-Identifier: GPL-3.0-or-later
"""The Dashboard "Disks" card: one row per drive, a warning word, an unreadable row,
a Worker load, a language switch without a reload, and no width growth."""
import os
import shutil
from collections import namedtuple
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu import client_import, config, diskspace, theming
from rosu.ui import dashboard_tab
from rosu.ui.dashboard_tab import _fmt_drive_size

GiB = 1024 ** 3
_Usage = namedtuple("_Usage", "total used free")


def _drive_of(path) -> str:
    s = str(path)
    if "lazer" in s:
        return "E:\\"
    for name in ("Packs", "Output", "Library"):
        if name in Path(s).parts:
            return {"Packs": "P:\\", "Output": "O:\\", "Library": "L:\\"}[name]
    return "C:\\"


def _fake_space(table):
    """``table``: drive -> (total, free)."""
    def fake(path, need, margin=diskspace.MARGIN):
        drive = _drive_of(path)
        total, free = table[drive]
        return diskspace.Space(free, total, free >= need + margin, drive)
    return fake


@pytest.fixture
def make_win(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from rosu.app import AppContext
    from rosu.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    made = []

    def make(lang, table=None):
        lazer = tmp_path / "lazer"
        lazer.mkdir(exist_ok=True)
        monkeypatch.setattr(client_import, "lazer_data_dir", lambda: lazer)
        monkeypatch.setattr(client_import, "stable_songs_dir", lambda: None)
        if table is not None:
            monkeypatch.setattr(diskspace, "space",
                                table if callable(table) else _fake_space(table))
        monkeypatch.setattr(config, "save_config", lambda cfg: None)
        cfg = config._fill_defaults(config.Config(root=str(tmp_path / "app")))
        cfg.check_updates = False
        cfg.ensure_dirs()
        ctx = AppContext(cfg)
        app.setStyleSheet(theming.stylesheet_for("dark"))
        w = MainWindow(ctx, app)
        ctx.i18n.set_language(lang)
        w.retranslate()
        made.append((w, ctx))
        return w

    yield make
    app.setStyleSheet("")
    for w, ctx in made:
        _settle(w.dashboard)
        w.close()
        ctx.db.close()


def _settle(tab):
    from PySide6.QtWidgets import QApplication
    while tab._threads:
        for w in list(tab._threads):
            w.wait()
        QApplication.processEvents()
    QApplication.processEvents()


def _load(w):
    w.dashboard.on_shown()
    _settle(w.dashboard)
    return w.dashboard


NORMAL = {"P:\\": (100 * GiB, 60 * GiB), "O:\\": (100 * GiB, 60 * GiB),
          "L:\\": (100 * GiB, 60 * GiB), "E:\\": (500 * GiB, 250 * GiB)}


def _one_drive(table):
    return {**table, "O:\\": table["P:\\"], "L:\\": table["P:\\"]}


@pytest.mark.parametrize("lang", ["en", "tr"])
def test_two_drives_give_two_rows_with_matching_bar_text(make_win, lang):
    # Packs/Output/Library all answer as one drive P:\ , the lazer folder as E:\
    def same(path, need, margin=diskspace.MARGIN):
        drive = "E:\\" if "lazer" in str(path) else "P:\\"
        total, free = {"P:\\": (100 * GiB, 60 * GiB), "E:\\": (500 * GiB, 250 * GiB)}[drive]
        return diskspace.Space(free, total, True, drive)
    tab = _load(make_win(lang, same))
    win = tab.mw
    assert len(tab.disk_rows) == 2
    t = win.ctx.t
    assert tab.disk_title.text() == t("disk_card_title") != "disk_card_title"
    for (lbl, bar), (used, total, free) in zip(
            tab.disk_rows, [(40, 100, 60), (250, 500, 250)]):
        figs = [_fmt_drive_size(n * GiB) for n in (used, total, free)]
        assert all(f in lbl.text() for f in figs)
        assert all(f in bar.accessibleDescription() for f in figs)
        assert bar.accessibleName() and not bar.isTextVisible()
        assert "disk_" not in lbl.text()
    assert "Packs" in tab.disk_rows[0][0].text() and "Library" in tab.disk_rows[0][0].text()


def test_row_text_differs_between_languages(make_win):
    en = make_win("en", NORMAL)
    en_rows = [lbl.text() for lbl, _ in _load(en).disk_rows]
    tr = make_win("tr", NORMAL)
    tr_rows = [lbl.text() for lbl, _ in _load(tr).disk_rows]
    assert en_rows and len(en_rows) == len(tr_rows)
    assert all(a != b for a, b in zip(en_rows, tr_rows))
    assert en.dashboard.disk_title.text() != tr.dashboard.disk_title.text()


@pytest.mark.parametrize("lang", ["en", "tr"])
def test_low_drives_show_the_warning_word(make_win, lang):
    table = {"P:\\": (30 * GiB, 4 * GiB),                  # 13% but under 5 GiB
             "O:\\": (10_000 * GiB, 500 * GiB),            # 5% of a huge drive
             "L:\\": (100 * GiB, 50 * GiB),                # 50%
             "E:\\": (100 * GiB, 50 * GiB)}
    win = make_win(lang, table)
    tab = _load(win)
    warn = win.ctx.t("disk_card_low")
    by_drive = {lbl.text().split(warn)[-1].split()[0]: lbl.text() for lbl, _ in tab.disk_rows}
    assert warn.strip() and warn != "disk_card_low"
    assert warn in by_drive["P:\\"] and warn in by_drive["O:\\"]
    assert warn not in by_drive["L:\\"] and warn not in by_drive["E:\\"]


@pytest.mark.parametrize("lang", ["en", "tr"])
def test_unreadable_drive_row_blocks_nothing(make_win, lang, monkeypatch):
    def boom(p):
        raise OSError("gone")
    monkeypatch.setattr(shutil, "disk_usage", boom)
    win = make_win(lang)
    tab = _load(win)
    assert tab.disk_rows
    for lbl, bar in tab.disk_rows:
        assert bar is None
        assert lbl.text() == win.ctx.t("disk_card_unreadable", drive=lbl.text().split()[0],
                                       places=lbl.text().split(": ")[0].split(" ", 1)[1])
        assert "disk_card" not in lbl.text()
    assert tab.btn_extract.isEnabled() and tab.btn_rescan.isEnabled()


def test_loads_through_a_worker_on_build_and_on_every_show(make_win, monkeypatch):
    starts = []

    class Spy(dashboard_tab.Worker):
        def __init__(self, fn, *a, **k):
            starts.append(fn)
            super().__init__(fn, *a, **k)

    monkeypatch.setattr(dashboard_tab, "Worker", Spy)
    win = make_win("en", NORMAL)
    _settle(win.dashboard)
    n = starts.count(dashboard_tab._disk_usage)
    assert n >= 1
    win.dashboard.on_shown()
    _settle(win.dashboard)
    assert starts.count(dashboard_tab._disk_usage) == n + 1
    assert "QTimer" not in Path(dashboard_tab.__file__).read_text(encoding="utf-8")


def test_a_failed_load_leaves_an_empty_card(make_win, monkeypatch):
    win = make_win("en", NORMAL)
    tab = _load(win)
    assert tab.disk_rows
    monkeypatch.setattr(dashboard_tab, "_disk_usage",
                        lambda cfg, progress=None: 1 / 0)
    tab.on_shown()
    _settle(tab)
    assert tab.disk_rows == []


def test_language_switch_rerenders_without_another_load(make_win, monkeypatch):
    win = make_win("en", NORMAL)
    tab = _load(win)
    en_rows = [lbl.text() for lbl, _ in tab.disk_rows]
    starts = []
    monkeypatch.setattr(dashboard_tab, "Worker", lambda *a, **k: starts.append(a))
    win.ctx.i18n.set_language("tr")
    win.retranslate()
    tr_rows = [lbl.text() for lbl, _ in tab.disk_rows]
    assert starts == [] and len(tr_rows) == len(en_rows) and tr_rows != en_rows
    assert tab.disk_title.text() == win.ctx.t("disk_card_title")


def test_long_turkish_rows_wrap_and_add_no_width(make_win):
    from PySide6.QtWidgets import QApplication
    win = make_win("tr", NORMAL)
    tab = _load(win)
    win.show()
    QApplication.processEvents()
    tab.disk_card.setVisible(False)
    QApplication.processEvents()
    before = tab.minimumSizeHint().width()
    tab.disk_card.setVisible(True)
    long_drive = "Z:\\" + "çok-uzun-klasör-adı\\" * 40
    tab._on_disks([{"drive": long_drive, "labels": ["packs", "output", "library", "stable",
                                                    "lazer"],
                    "used": 90 * GiB, "total": 100 * GiB, "free": 10 * GiB,
                    "readable": True, "low": True}])
    QApplication.processEvents()
    lbl, bar = tab.disk_rows[0]
    assert lbl.fontMetrics().horizontalAdvance(lbl.text()) > 1280   # one line would not fit
    for w in [tab.disk_title, lbl]:
        assert w.wordWrap() and w.minimumSizeHint().width() < 1280
    assert bar.minimumSizeHint().width() < 1280
    assert tab.minimumSizeHint().width() <= before
