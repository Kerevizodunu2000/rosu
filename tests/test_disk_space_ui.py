# SPDX-License-Identifier: GPL-3.0-or-later
"""The Dashboard and Shortcuts tab show the free-space refusals and disk-full
stops of Export, Import to osu!, Transfer and Unpack, in both languages (issue #46)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu import config, jobs, theming
from rosu.jobs import State

MiB = 1024 * 1024
NS = {"drive": "E:\\", "need": 300 * MiB, "free": 10 * MiB}


@pytest.fixture(params=["en", "tr"])
def win(request, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from rosu.app import AppContext
    from rosu.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.check_updates = False
    ctx = AppContext(cfg)
    app.setStyleSheet(theming.stylesheet_for("dark"))
    w = MainWindow(ctx, app)
    ctx.i18n.set_language(request.param)
    w.retranslate()
    w.calls = {"warning": [], "information": []}
    for kind in w.calls:
        monkeypatch.setattr(
            QMessageBox, kind,
            staticmethod(lambda parent, title, text, _k=kind, **kw: w.calls[_k].append(text)))
    w.dialogs = []
    monkeypatch.setattr(w.shortcuts, "_export_result_dialog",
                        lambda body, links: w.dialogs.append(body))
    w.reloads, w.shown = [], []
    monkeypatch.setattr(w.shortcuts, "on_shown", lambda: w.shown.append(1))   # no worker
    monkeypatch.setattr(w.search, "reload", lambda *a, **k: w.reloads.append(1))
    w.t = ctx.t
    w.lang = request.param
    yield w
    app.setStyleSheet("")
    w.close()
    ctx.db.close()


def _no_space(win):
    text = win.t("disk_no_space", drive="E:\\", need="300.0 MB", free="10.0 MB")
    assert "E:\\" in text
    return text


def _failed_unpack(extract):
    job = jobs.Job(jobs.new_id(), "job_unpack_lazer", kind="unpack")
    job.ctx["extract"] = extract
    job.state = State.FAILED
    job.error = "OSError: [Errno 28] E:\\ is full"
    return job


def test_language_is_switched(win):
    assert win.t("export_disk_full", drive="E:\\").startswith(
        "E:\\ is full" if win.lang == "en" else "E:\\ sürücüsü dolu")


def test_failed_unpack_no_space(win):
    win.shortcuts._on_job_failed(_failed_unpack({"packs": 0, "no_space": NS}))
    want = _no_space(win)
    assert win.shortcuts.status.text() == want and win.calls["warning"] == [want]
    assert win.reloads == [] and win.shown == [1]


def test_failed_unpack_disk_full(win):
    win.shortcuts._on_job_failed(_failed_unpack({"disk_full": True, "full_drive": "E:\\"}))
    want = win.t("extract_disk_full", drive="E:\\")
    assert win.shortcuts.status.text() == want and win.calls["warning"] == [want]
    assert win.reloads == [1] and win.shown == [1]


def test_other_failures_keep_their_handling(win):
    job = _failed_unpack({"packs": 1})
    win.shortcuts._on_job_failed(job)
    assert win.shortcuts.status.text() == job.error and win.calls["warning"] == []


def test_export_no_space(win):
    win.shortcuts._present_export({"source": "library", "count": 0, "archives": [],
                                   "cancelled": False, "no_space": NS})
    want = _no_space(win)
    assert win.shortcuts.status.text() == want and win.calls["warning"] == [want]
    assert win.dialogs == []


def test_export_disk_full_with_archives(win, tmp_path):
    a = str(tmp_path / "exp.part01.zip")
    win.shortcuts._present_export({"source": "library", "count": 3, "archives": [a],
                                   "cancelled": False, "disk_full": True,
                                   "full_drive": "E:\\"})
    want = win.t("export_disk_full", drive="E:\\")
    assert want in win.shortcuts.status.text()
    assert win.calls["warning"] == [want]
    assert len(win.dialogs) == 1 and "exp.part01.zip" in win.dialogs[0]
    assert "E:\\" in win.dialogs[0]


def test_export_disk_full_without_archives(win):
    win.shortcuts._present_export({"source": "library", "count": 0, "archives": [],
                                   "cancelled": False, "disk_full": True,
                                   "full_drive": "E:\\"})
    want = win.t("export_disk_full", drive="E:\\")
    assert win.shortcuts.status.text() == want and win.calls["warning"] == [want]
    assert win.dialogs == []


def test_transfer_no_space(win):
    win.shortcuts._present_transfer({"found": 2, "transferred": 0, "skipped": 0,
                                     "no_space": NS, "disk_full": False})
    want = _no_space(win)
    assert win.shortcuts.status.text() == want and win.calls["warning"] == [want]


def test_transfer_disk_full(win):
    win.shortcuts._present_transfer({"found": 2, "transferred": 1, "skipped": 0,
                                     "disk_full": True})
    done = win.t("sc_transfer_done", found=2, transferred=1, skipped=0)
    full = win.t("sc_transfer_disk_full")
    assert win.shortcuts.status.text() == done + "  " + full
    assert win.calls["warning"] == [full]


def test_unpack_import_no_space(win):
    win.shortcuts._present_unpack({"extract": {"tracks": 2}, "imports": {
        "lazer": {"no_space": NS, "sent": 0, "files": 0, "stage_failed": 0,
                  "disk_full": False, "skipped": 0}}})
    want = _no_space(win)
    assert want in win.shortcuts.status.text() and win.calls["warning"] == [want]


def test_dashboard_import_no_space(win):
    win.dashboard._after_import({"no_space": NS, "sent": 0, "files": 0, "batches": 0,
                                 "stage_failed": 0, "disk_full": False})
    want = _no_space(win)
    assert win.dashboard.status.text() == want and win.calls["warning"] == [want]
    assert win.calls["information"] == []


def test_long_messages_wrap_in_the_window(win):
    from PySide6.QtWidgets import QApplication
    win.show()
    win.tabs.setCurrentWidget(win.shortcuts)
    QApplication.processEvents()
    width = win.width()
    tab = win.shortcuts
    for show in (lambda: tab._present_transfer({"found": 2, "transferred": 1,
                                                "skipped": 0, "disk_full": True}),
                 lambda: tab._present_export({"count": 0, "archives": [], "no_space": NS}),
                 lambda: tab._present_export({"count": 0, "archives": [],
                                              "disk_full": True, "full_drive": "E:\\"})):
        show()
        QApplication.processEvents()
        assert tab.status.wordWrap()
        assert win.width() == width and tab.status.width() <= tab.width()
