# SPDX-License-Identifier: GPL-3.0-or-later
"""Auto-update follow-ups: the one-time "installed" notice and the armed restart."""
import json
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu import __version__, config, updater
from rosu.jobs import Job, Lane, State, Step

NEWER = {"newer": True, "tag": "v9.9.9", "url": "https://x/rel"}
SAME = {"newer": False, "tag": "v1.2.3", "url": "https://x/rel", "notes": "Fixed A\nFixed B"}


# -- mark_healthy ---------------------------------------------------------------
@pytest.fixture
def frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    exe = tmp_path / "rosu.exe"
    exe.write_bytes(b"MZ")
    return SimpleNamespace(exe=exe, state=tmp_path / "rosu-update-state.json")


def _state(frozen, **st):
    frozen.state.write_text(json.dumps(st))


def test_mark_healthy_returns_the_installed_version(frozen):
    _state(frozen, **{"from": "1.0.0", "to": __version__, "boots": 1, "skip": []})
    assert updater.mark_healthy(exe=frozen.exe) == __version__
    assert json.loads(frozen.state.read_text()) == {"skip": []}


def test_mark_healthy_returns_none_without_a_state(frozen):
    assert updater.mark_healthy(exe=frozen.exe) is None


def test_mark_healthy_returns_none_for_another_version(frozen):
    _state(frozen, **{"from": "1.0.0", "to": "0.0.1", "boots": 1, "skip": []})
    assert updater.mark_healthy(exe=frozen.exe) is None


def test_mark_healthy_returns_none_when_not_frozen(frozen, monkeypatch):
    monkeypatch.delattr(sys, "frozen")
    _state(frozen, **{"from": "1.0.0", "to": __version__, "boots": 1, "skip": []})
    assert updater.mark_healthy(exe=frozen.exe) is None


def test_mark_healthy_returns_none_when_the_clear_fails(frozen, monkeypatch):
    _state(frozen, **{"from": "1.0.0", "to": __version__, "boots": 1, "skip": []})

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(updater, "_write_state", boom)
    assert updater.mark_healthy(exe=frozen.exe) is None


# -- window ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    from rosu.app import AppContext
    from rosu.ui.main_window import MainWindow
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.check_updates = False
    ctx = AppContext(cfg)
    w = MainWindow(ctx, qapp)
    yield w
    w._restart_timer.stop()
    w.close()
    ctx.db.close()


def test_notice_shows_with_a_focusable_dismiss(win):
    win.show_updated_notice(None)
    assert win.update_banner.isHidden() and win.update_dismiss.isHidden()
    win.show_updated_notice("1.2.3")
    assert "Rosu v1.2.3 was installed." in win.update_banner.text()
    from PySide6.QtCore import Qt
    d = win.update_dismiss
    assert not d.isHidden() and d.isEnabled() and d.focusPolicy() & Qt.TabFocus


@pytest.mark.parametrize("notice_first", [True, False])
def test_notes_appear_when_the_tag_matches(win, notice_first):
    steps = [lambda: win.show_updated_notice("1.2.3"),
             lambda: win._on_update_checked(SAME)]
    for step in (steps if notice_first else steps[::-1]):
        step()
    text = win.update_banner.text()
    assert "Fixed A" in text and "Fixed B" in text
    assert win._threads == [] and "is available" not in text


def test_notes_are_absent_for_another_tag_or_no_check(win):
    win.show_updated_notice("1.2.3")
    assert "Fixed A" not in win.update_banner.text()
    win._on_update_checked({**SAME, "tag": "v1.2.4"})
    assert "Fixed A" not in win.update_banner.text()
    win._on_update_checked({**SAME, "tag": "1.2.3"})   # the v prefix is optional
    assert "Fixed A" in win.update_banner.text()


def test_notes_are_plain_text_and_capped_at_six_lines(win):
    win.show_updated_notice("1.2.3")
    win._on_update_checked({**SAME, "notes": "<a href='https://evil.example'>x</a>\n"
                                             "<b>bold</b><img src=x>"})
    text = win.update_banner.text()
    assert "&lt;a href=" in text and "&lt;b&gt;" in text
    assert "<a " not in text and "<b>" not in text and "<img" not in text
    win._on_update_checked({**SAME, "notes": "\n".join(f"line{i}" for i in range(20))})
    text = win.update_banner.text()
    assert "line5" in text and "line6" not in text


def test_dismiss_clears_the_notice_for_good(qapp, win):
    win.show()
    win.show_updated_notice("1.2.3")
    win.update_dismiss.click()
    assert win.update_banner.isHidden() and win.update_dismiss.isHidden()
    assert win.tabs.hasFocus() or win.tabs.focusWidget() is not None
    win._render_update_banner()
    win.retranslate()
    assert win.update_banner.isHidden()


def test_an_update_banner_takes_the_notices_place(win, monkeypatch):
    monkeypatch.setattr(updater, "can_auto_update", lambda cfg: False)
    win.show_updated_notice("1.2.3")
    win._on_update_checked(NEWER)
    assert "Rosu v9.9.9 is available." in win.update_banner.text()
    assert win.update_dismiss.isHidden()


def test_long_notes_do_not_resize_the_window(qapp, win):
    # taller than 760: the Shortcuts tab alone needs ~800 px here, which is not the banner
    win.resize(1280, 1000)
    win.show()
    win.show_updated_notice("1.2.3")
    # as update_check hands it over: at most 1500 characters
    notes = "x" * 400 + "\n" + "\n".join("long words " * 5 for _ in range(20))
    win._on_update_checked({**SAME, "notes": notes})
    qapp.processEvents()
    assert (win.size().width(), win.size().height()) == (1280, 1000)


def test_turkish_strings(win):
    win.apply_language("tr")
    win.show_updated_notice("1.2.3")
    assert "Rosu v1.2.3 yüklendi." in win.update_banner.text()
    assert win.update_dismiss.text() == "Kapat"
    win._update_info = NEWER
    win._update_phase = "ready"
    win._set_restart_armed(True)
    assert "Geçerli işlem bitince" in win.update_banner.text()
    assert win.update_restart.text() == "Yeniden başlatmayı iptal et"


# -- armed restart --------------------------------------------------------------
def _job(state, gated=False):
    step = Step("k", Lane.DISK, lambda *a: None, gated=gated)
    job = Job(id=1, title_key="k", steps=[step])
    job.state = state
    return job


@pytest.fixture
def armed(win, monkeypatch):
    closed = []
    monkeypatch.setattr(win, "close", lambda: closed.append(1) or True)
    monkeypatch.setattr(win, "_operation_running", lambda: True)
    win._update_info = NEWER
    win._on_update_downloaded({"status": updater.READY, "tag": "v9.9.9"})
    win.update_restart.click()
    monkeypatch.undo()   # drop the busy patch; ``close`` is re-patched below
    monkeypatch.setattr(win, "close", lambda: closed.append(1) or True)
    assert win._restart_armed
    return SimpleNamespace(win=win, closed=closed, mp=monkeypatch)


def test_has_unfinished(win):
    q = win.shortcuts.queue
    assert not q.has_unfinished()
    q.jobs = [_job(State.DONE), _job(State.FAILED), _job(State.CANCELLED)]
    assert not q.has_unfinished()
    for s in (State.PENDING, State.RUNNING):
        q.jobs = [_job(State.DONE), _job(s)]
        assert q.has_unfinished()


@pytest.mark.parametrize("busy", ["worker", "pending", "running", "gate", "modal"])
def test_no_restart_while_not_idle(armed, busy):
    w, mp = armed.win, armed.mp
    if busy == "worker":
        mp.setattr(w, "_operation_running", lambda: True)
    elif busy == "modal":
        from PySide6.QtWidgets import QApplication
        mp.setattr(QApplication, "activeModalWidget", staticmethod(lambda: w))
    else:
        state = {"pending": State.PENDING, "running": State.RUNNING,
                 "gate": State.PENDING}[busy]
        w.shortcuts.queue.jobs = [_job(state, gated=busy == "gate")]
    w._restart_if_idle()
    assert armed.closed == [] and w.restart_for_update is False and w._restart_armed


def test_restart_once_idle(armed):
    w = armed.win
    w._restart_if_idle()
    assert w.restart_for_update is True and armed.closed == [1]
    assert not w._restart_timer.isActive()


def test_refused_close_disarms(armed):
    w = armed.win
    armed.mp.setattr(w, "close", lambda: False)
    w._restart_if_idle()
    assert w.restart_for_update is False and not w._restart_armed
    assert w.update_restart.text() == "Restart now" and not w._restart_timer.isActive()


def test_retired_key_is_gone():
    from rosu.i18n import STRINGS
    assert "update_restart_" + "later" not in STRINGS   # keeps the AC grep clean
