# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless construction smoke test for the whole UI (offscreen Qt).

`run.py --selftest` boots config/theme/db but does NOT build the main window, so
this is the only automated check that every tab constructs and retranslates
without error — covering the v1.0 UI changes (dual import buttons, About dialog,
lost-map button, Output view, update banner). No network is used: the startup
update check is disabled for the test.
"""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu import config


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)  # no repo write
    from rosu.app import AppContext
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.check_updates = False    # keep the network worker out of the test
    return AppContext(cfg)


def test_main_window_builds_and_retranslates(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    ctx.i18n.set_language("tr")
    win.retranslate()
    ctx.i18n.set_language("en")
    win.retranslate()
    win.close()
    ctx.db.close()


def test_update_banner_renders_when_newer(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    # isHidden() reflects the explicit hidden flag without needing a shown window.
    assert win.update_banner.isHidden()          # hidden by default
    win._on_update_checked({"newer": True, "tag": "v9.9.9", "url": "https://x/rel"})
    assert not win.update_banner.isHidden()      # revealed on a newer release
    assert "9.9.9" in win.update_banner.text()
    win.close()
    ctx.db.close()


def test_update_banner_stays_hidden_when_not_newer(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    win._on_update_checked({"newer": False, "tag": "v0.0.1", "url": "u"})
    assert win.update_banner.isHidden()
    win.close()
    ctx.db.close()


def test_filters_panel_composes_query_tokens(qapp, tmp_path, monkeypatch):
    """The v1.6 filters panel emits valid query-syntax that round-trips through
    rosu.query.parse into the intended structured filters."""
    from rosu import query
    from rosu.ui.filters_panel import FiltersPanel
    ctx = _ctx(tmp_path, monkeypatch)
    fp = FiltersPanel(ctx)
    fp.retranslate()
    fp._on_mode_clicked("osu!mania")            # mania → keys row visible
    fp.star.set_values(4.0, 6.5)
    fp.keys.setCurrentIndex(fp.keys.findData(7))
    toks = fp.filter_tokens()
    assert "mode=mania" in toks and "key=7" in toks
    assert "star>=4" in toks and "star<=6.5" in toks
    got = {(f.field, f.op, f.value) for f in query.parse(" ".join(toks)).filters}
    assert ("mode", "=", "osu!mania") in got
    assert ("key", "=", 7) in got
    assert ("star", ">=", 4.0) in got
    # a mode the Library owns none of is disabled and can't contribute a filter
    fp.set_mode_counts({"osu!mania": 3})
    assert fp.mode_btns["osu!mania"].isEnabled()
    assert not fp.mode_btns["osu!taiko"].isEnabled()
    fp.clear()
    assert fp.filter_tokens() == []
    ctx.db.close()


def test_star_range_export_prefill(qapp, tmp_path, monkeypatch):
    """v1.6: prefill_star_range (from the Search histogram's 'Export this range')
    fills the Shortcuts export star boxes and selects the Library source."""
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    win.shortcuts.prefill_star_range(3.5, 6.0)
    assert win.shortcuts.export_star_lo.value() == 3.5
    assert win.shortcuts.export_star_hi.value() == 6.0
    assert win.shortcuts.export_source.currentData() == "library"
    win.close()
    ctx.db.close()


def test_share_toggle_requires_informed_consent(qapp, tmp_path, monkeypatch):
    """v1.6.3 regression: enabling the public Drive share link must show the
    copyright warning; declining snaps the checkbox back off, accepting keeps it."""
    from PySide6.QtWidgets import QMessageBox
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    ctx.cfg.drive_connected = True
    win = MainWindow(ctx, qapp)
    tab = win.shortcuts
    tab.export_drive.setChecked(True)              # a link needs the upload
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.No)
    tab.export_share.setChecked(True)
    assert not tab.export_share.isChecked()        # declined → snapped back off
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.Yes)
    tab.export_share.setChecked(True)
    assert tab.export_share.isChecked()            # informed consent → stays on
    win.close()
    ctx.db.close()


def test_search_tab_says_when_results_were_truncated(qapp, tmp_path, monkeypatch):
    """v1.7.1: a capped page must never be presented as the whole answer — that
    is what made a 1600-set star range read as exactly 500 matches."""
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    tab = win.search
    seq = tab._search_seq

    tab._on_results({"rows": [], "total": 1600, "limit": 500, "truncated": True},
                    seq, "star>=3 star<4")
    assert "1600" in tab.result.text()

    tab._on_results({"rows": [], "total": 0, "limit": 5000, "truncated": False},
                    seq, "nothing-matches-this")
    assert tab.result.text() == ctx.t("search_none")
    win.close()
    ctx.db.close()


def test_export_dest_in_use_blocks_a_second_job(qapp, tmp_path, monkeypatch):
    """v1.7.1: two exports aimed at the same destination meant job 2's archive
    landed on the file job 1 was still uploading (the DRIVE lane overlaps DISK),
    so the uploaded bytes were not the bytes job 1 exported."""
    from rosu.jobs import Job, State, new_id
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    tab = win.shortcuts
    dest = tmp_path / "rosu-export-library"

    assert not tab._dest_in_use(dest)             # nothing queued yet
    job = Job(new_id(), "job_export", kind="export")
    job.ctx["dest_base"] = str(dest)
    tab.queue.jobs.append(job)                    # queued, still running/uploading
    assert tab._dest_in_use(dest)
    assert not tab._dest_in_use(tmp_path / "other")   # a different name is free
    job.state = State.DONE                        # finished → no longer reserved
    assert not tab._dest_in_use(dest)
    win.close()
    ctx.db.close()


def test_export_split_volume_overwrite_is_confirmed(qapp, tmp_path, monkeypatch):
    """The save dialog only vets the single name the user typed; a split export
    writes <stem>.partNN.zip volumes it never checks."""
    from PySide6.QtWidgets import QMessageBox
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    tab = win.shortcuts
    dest = tmp_path / "pack"

    assert tab._confirm_volume_overwrite(dest, ".zip")     # nothing there yet
    (tmp_path / "pack.part01.zip").write_bytes(b"old")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    assert not tab._confirm_volume_overwrite(dest, ".zip")  # declined → don't run
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    assert tab._confirm_volume_overwrite(dest, ".zip")
    # a different base name is unaffected
    assert tab._confirm_volume_overwrite(tmp_path / "other", ".zip")
    win.close()
    ctx.db.close()


def test_export_result_dialog_renders_a_live_link(qapp, tmp_path, monkeypatch):
    """v1.7.1: the share link used to be plain text inside a QMessageBox — not
    clickable, not reliably selectable, never on the clipboard."""
    from PySide6.QtCore import Qt
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    url = "https://drive.google.com/file/d/abc123/view"
    dlg = win.shortcuts.build_export_result_dialog(
        f'Done<br><a href="{url}">{url}</a>', [url])
    label = dlg.body_label
    assert f'href="{url}"' in label.text()             # a real anchor
    assert label.textFormat() == Qt.RichText
    assert label.openExternalLinks()                   # clicking opens the browser
    assert label.textInteractionFlags() & Qt.TextSelectableByMouse   # selectable
    dlg.close()
    win.close()
    ctx.db.close()


def test_job_row_detail_spells_out_every_export_choice(qapp, tmp_path, monkeypatch):
    """v1.7.1: the row title carries only source + filename, so two exports that
    differed in random-N / star range / split / upload rendered identically."""
    from rosu.jobs import Job, new_id
    from rosu.ui.shortcuts_tab import _describe_job
    ctx = _ctx(tmp_path, monkeypatch)
    job = Job(new_id(), "job_export", kind="export")
    job.ctx["options"] = {
        "source": "library", "archive_name": "rosu-export-library.zip",
        "fmt": "7z", "split_bytes": 2_000_000_000, "upload": True, "share": True,
        "limit": 10, "star_range": (3.5, 6.0), "dest": r"C:\out"}
    line = _describe_job(job, ctx.t)
    for expected in ("10", "3.50", "6.00", "7Z", "rosu-export-library.zip", r"C:\out"):
        assert expected in line, f"{expected!r} missing from {line!r}"

    # An open-ended star range must not print "inf".
    job.ctx["options"]["star_range"] = (4.0, float("inf"))
    assert "inf" not in _describe_job(job, ctx.t).lower()

    # Once finished, the produced link is shown on the row too.
    job.result = {"drive": {"files": [{"link": "https://drive.example/abc"}]}}
    assert "https://drive.example/abc" in _describe_job(job, ctx.t)

    # A job with no recorded options renders nothing rather than a stray separator.
    assert _describe_job(Job(new_id(), "job_dedup", kind="dedup"), ctx.t) == ""
    ctx.db.close()


def test_consecutive_duplicate_job_asks_but_an_interleaved_one_does_not(
        qapp, tmp_path, monkeypatch):
    """The owner's rule: ask only when the SAME action is started twice in a row.
    If something else was queued in between, repeating is deliberate — don't nag."""
    from PySide6.QtWidgets import QMessageBox
    from rosu.jobs import Job, new_id
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    tab = win.shortcuts
    queued, asked = [], []
    monkeypatch.setattr(tab.queue, "enqueue", queued.append)

    def fake_question(*a, **k):
        asked.append(1)
        return QMessageBox.Yes
    monkeypatch.setattr(QMessageBox, "question", fake_question)

    sig_a, sig_b = ("export", "library", "zip"), ("dedup",)
    assert tab._enqueue(Job(new_id(), "j", kind="export"), sig_a)
    assert not asked                      # first time: straight through
    assert tab._enqueue(Job(new_id(), "j", kind="export"), sig_a)
    assert len(asked) == 1                # immediate repeat: asked
    assert tab._enqueue(Job(new_id(), "j", kind="dedup"), sig_b)
    assert len(asked) == 1                # different job: no question
    assert tab._enqueue(Job(new_id(), "j", kind="export"), sig_a)
    assert len(asked) == 1                # no longer consecutive: no question
    assert len(queued) == 4

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    assert not tab._enqueue(Job(new_id(), "j", kind="export"), sig_a)
    assert len(queued) == 4               # declined → not queued
    win.close()
    ctx.db.close()


def test_map_details_offers_restore_only_when_needed(qapp, tmp_path, monkeypatch):
    """v1.7.1: a pruned set looked identical to a whole one, and the only way back
    was a right-click context item the owner never found."""
    from rosu.ui.map_details_dialog import MapDetailsDialog
    ctx = _ctx(tmp_path, monkeypatch)
    called = []

    whole = {"display_name": "A - B", "filename": "1 A - B.osz", "in_library": 1,
             "is_pruned": 0, "difficulties": []}
    dlg = MapDetailsDialog(ctx, whole, None, on_restore=called.append)
    assert dlg.btn_restore is None            # nothing to restore
    dlg.close()

    pruned = dict(whole, is_pruned=1)
    dlg = MapDetailsDialog(ctx, pruned, None, on_restore=called.append)
    assert dlg.btn_restore is not None
    dlg.btn_restore.click()
    assert called == ["1 A - B.osz"]          # hands the filename to the caller
    dlg.close()

    # No callback (e.g. opened from somewhere that can't repair) → no button.
    dlg = MapDetailsDialog(ctx, pruned, None)
    assert dlg.btn_restore is None
    dlg.close()
    ctx.db.close()


def test_health_dialog_shows_pruned_bucket_and_mismatched_files(qapp, tmp_path,
                                                                monkeypatch):
    """v1.7.1: `pruned` got its own bucket in v1.7 but was never displayed, so
    pruning looked like it lost sets from the totals; and "2 mismatch" was useless
    without saying WHICH two."""
    from rosu.ui.health_dialog import HealthDialog
    ctx = _ctx(tmp_path, monkeypatch)
    report = {"usage": {"files": 0, "total_bytes": 0},
              "scrub": {"present": 0, "orphans": [], "dead_links": [], "memory": 0},
              "biggest": []}
    dlg = HealthDialog(ctx, report, None)
    dlg._on_verified({"checked": 1922, "ok": 501, "mismatch": 2, "unhashed": 1419,
                      "missing": 0, "pruned": 7,
                      "mismatches": ["a.osz", "b.osz"]})
    text = dlg.verify_status.text()
    assert "7" in text and "1419" in text          # pruned + unhashed both named
    # isHidden() reflects the explicit hidden flag without needing a shown window.
    assert not dlg.mismatch_label.isHidden()
    assert "a.osz" in dlg.mismatch_label.text()

    dlg._on_verified({"checked": 3, "ok": 3, "mismatch": 0, "unhashed": 0,
                      "missing": 0, "pruned": 0, "mismatches": []})
    assert dlg.mismatch_label.isHidden()           # cleared on a clean re-run
    dlg.close()
    ctx.db.close()


def _prune_dialog(ctx, monkeypatch):
    """A PruneDialog with the background scan stubbed out, so the table/plan logic
    can be driven deterministically without a worker thread."""
    from rosu.ui.prune_dialog import PruneDialog
    monkeypatch.setattr(PruneDialog, "scan", lambda self: None)
    return PruneDialog(ctx, None)


def test_prune_dialog_routes_lazer_to_its_own_steps(qapp, tmp_path, monkeypatch):
    """lazer cannot be pruned from this dialog, but picking it must lead
    somewhere — refusing and stopping would leave the user with no way forward.
    It stays SELECTABLE and reveals the steps that do prune it."""
    from PySide6.QtCore import Qt
    ctx = _ctx(tmp_path, monkeypatch)
    dlg = _prune_dialog(ctx, monkeypatch)
    i = dlg.cbo_source.findData("lazer")
    assert i >= 0
    assert dlg.cbo_source.model().item(i).isEnabled()      # selectable…
    assert dlg.cbo_source.itemData(i, Qt.ToolTipRole) == ctx.t("prune_why_lazer_realm")
    assert dlg.cbo_source.currentData() == "library"       # …but not the default
    assert not dlg.btn_lazer_steps.isVisible() or dlg.btn_lazer_steps.isHidden()

    dlg.cbo_source.setCurrentIndex(i)
    assert not dlg.btn_lazer_steps.isHidden()              # the way forward appears
    assert ctx.t("prune_why_lazer_realm") in dlg.lbl_source_note.text()
    assert dlg.btn_prune.isEnabled() is False              # nothing to prune here
    dlg.close()
    ctx.db.close()


def test_prune_dialog_order_and_limit_reshape_the_preview(qapp, tmp_path,
                                                          monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    dlg = _prune_dialog(ctx, monkeypatch)
    dlg._on_scanned({"source": "library", "mode": "video_only", "scanned": 4,
                     "total_bytes": 1000, "freed_bytes": 360,
                     "sets": [{"key": "a", "name": "a", "size": 100, "freed": 10},
                              {"key": "b", "name": "b", "size": 400, "freed": 300},
                              {"key": "c", "name": "c", "size": 200, "freed": 50},
                              {"key": "d", "name": "d", "size": 50, "freed": 0}]})
    # "d" frees nothing, so it is never offered — the count must not overstate.
    assert [s["key"] for s in dlg._shown] == ["b", "c", "a"]
    assert dlg.table.rowCount() == 3
    dlg.spin_limit.setValue(2)
    assert [s["key"] for s in dlg._shown] == ["b", "c"]
    dlg.cbo_sort.setCurrentIndex(dlg.cbo_sort.findData("smallest"))
    assert [s["key"] for s in dlg._shown] == ["a", "c"]
    dlg.spin_limit.setValue(0)                       # 0 = all of them
    assert len(dlg._shown) == 3
    assert dlg.btn_prune.isEnabled()
    dlg.close()
    ctx.db.close()


def _scan_result(*keys):
    return {"source": "library", "mode": "video_only", "scanned": len(keys),
            "total_bytes": 100 * len(keys), "freed_bytes": 10 * len(keys),
            "sets": [{"key": k, "name": k, "size": 100, "freed": 10}
                     for k in keys]}


def test_prune_dialog_drops_a_superseded_scan_result(qapp, tmp_path, monkeypatch):
    """Changing source or mode mid-scan must not leave the previous source's
    results on screen — found by driving the real dialog: the old code refused to
    start the new scan while one was running, so the table silently kept lying."""
    ctx = _ctx(tmp_path, monkeypatch)
    dlg = _prune_dialog(ctx, monkeypatch)
    dlg._on_scanned(_scan_result("a"), dlg._scan_seq)
    assert [s["key"] for s in dlg._shown] == ["a"]

    dlg._scan_seq += 1                                  # a newer scan started
    dlg._on_scanned(_scan_result("stale"), dlg._scan_seq - 1)
    assert [s["key"] for s in dlg._shown] == ["a"]      # stale result ignored
    dlg._on_scanned(_scan_result("b"), dlg._scan_seq)
    assert [s["key"] for s in dlg._shown] == ["b"]      # the current one wins
    dlg.close()
    ctx.db.close()


def test_prune_dialog_queues_a_rescan_instead_of_dropping_it(qapp, tmp_path,
                                                             monkeypatch):
    """A scan requested while one is running must be QUEUED and the running one
    cancelled — silently dropping it is what left the old source's rows on
    screen. No real threads here: the Worker is stubbed."""
    from rosu.ui import prune_dialog as pd
    ctx = _ctx(tmp_path, monkeypatch)
    started, cancelled = [], []

    class _Sig:
        def connect(self, *a, **k):
            pass

    class FakeWorker:
        progressed = _Sig()
        succeeded = _Sig()
        failed = _Sig()
        finished = _Sig()

        def __init__(self, *a, **k):
            started.append(a)

        def isRunning(self):
            return True

        def start(self):
            pass

    monkeypatch.setattr(pd, "Worker", FakeWorker)
    monkeypatch.setattr(ctx.services, "cancel_prune_scan",
                        lambda: cancelled.append(1))

    dlg = pd.PruneDialog(ctx, None)      # __init__ starts the first (fake) scan
    assert len(started) == 1 and not cancelled

    dlg.scan()                            # asked again while the first is running
    assert len(started) == 1              # no second worker on top of the first
    assert dlg._rescan_pending and cancelled == [1]

    dlg._clear_worker()                   # the running scan's thread let go
    assert len(started) == 2              # …and the queued rescan actually ran
    assert not dlg._rescan_pending
    ctx.db.close()


def test_prune_dialog_builds_a_plan_only_after_the_countdown(qapp, tmp_path,
                                                             monkeypatch):
    from PySide6.QtWidgets import QDialog
    from rosu.ui import prune_dialog as pd
    ctx = _ctx(tmp_path, monkeypatch)
    dlg = _prune_dialog(ctx, monkeypatch)
    dlg._on_scanned({"source": "library", "mode": "video_only", "scanned": 1,
                     "total_bytes": 400, "freed_bytes": 300,
                     "sets": [{"key": "b.osz", "name": "b", "size": 400,
                               "freed": 300}]})

    monkeypatch.setattr(pd.CountdownConfirmDialog, "exec",
                        lambda self: QDialog.Rejected)
    dlg._confirm()
    assert dlg.plan is None                    # declined → nothing to run

    monkeypatch.setattr(pd.CountdownConfirmDialog, "exec",
                        lambda self: QDialog.Accepted)
    dlg._confirm()
    assert dlg.plan == {"source": "library", "mode": "video_only",
                        "keys": ["b.osz"], "freed_estimate": 300}
    ctx.db.close()


def test_small_icon_buttons_have_room_for_their_glyph(qapp, tmp_path, monkeypatch):
    """The base QPushButton rule pads 16px each side, so a 30px fixed-width
    button had negative room for its label and drew as an empty box. These must
    use #iconbtn, whose rule pads ~0."""
    from rosu.jobs import Job, new_id
    from rosu.ui.main_window import MainWindow
    from rosu.ui.shortcuts_tab import JobRowWidget
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    job = Job(new_id(), "job_prune", kind="prune")
    from rosu.jobs import Lane, Step
    job.steps = [Step("job_step_prune_remove", Lane.DISK, lambda *a: None)]
    row = JobRowWidget(job, win.shortcuts.queue, ctx)
    assert row.btn_cancel.objectName() == "iconbtn"
    assert row.btn_cancel.text() == "×"
    assert row.step_rows[0][3].objectName() == "iconbtn"
    assert win.shortcuts.btn_refresh.objectName() == "iconbtn"
    row.deleteLater()
    win.close()
    ctx.db.close()


def test_icon_button_style_exists_in_every_theme():
    """The style has to be in the sheet itself, not just the object name."""
    from rosu import theming
    for name in theming.PALETTES:
        qss = theming.stylesheet_for(name)
        assert "QPushButton#iconbtn" in qss, name
        assert "padding: 2px 0px" in qss, name      # room for the glyph


def test_lazer_slim_wizard_walks_the_steps(qapp, tmp_path, monkeypatch):
    """The lazer round-trip: save → you delete in lazer → verify → prune → send.
    Rosu must never claim lazer was emptied when its file store says otherwise."""
    from PySide6.QtWidgets import QMessageBox
    from rosu.ui.lazer_slim_dialog import LazerSlimDialog
    ctx = _ctx(tmp_path, monkeypatch)
    dlg = LazerSlimDialog(ctx, None)
    assert dlg.step == "intro"

    # Step 1 result lands us on "delete" and remembers the store size.
    dlg._before = None
    monkeypatch.setattr(ctx.services, "lazer_store_stats",
                        lambda: {"found": True, "path": "p", "files": 100,
                                 "bytes": 10_000_000})
    # A save that did not fully land must NOT unlock the delete step — that step
    # tells the user to delete their beatmaps out of lazer.
    dlg._on_saved({"found": True, "new": 11, "exported": 12,
                   "missing": ["9 X - Y.osz"]})
    assert dlg.step == "intro"
    dlg._on_saved({"found": True, "new": 12, "exported": 12, "missing": []})
    assert dlg.step == "delete" and dlg._before["bytes"] == 10_000_000

    # Still full → refuses to advance unless the user insists.
    monkeypatch.setattr(ctx.services, "lazer_store_stats",
                        lambda: {"found": True, "path": "p", "files": 99,
                                 "bytes": 9_900_000})
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    dlg._check_deleted()
    assert dlg.step == "delete"                    # not advanced

    # Emptied → advances without asking anything.
    monkeypatch.setattr(ctx.services, "lazer_store_stats",
                        lambda: {"found": True, "path": "p", "files": 3,
                                 "bytes": 40_000})
    dlg._check_deleted()
    assert dlg.step == "prune"

    dlg._skip()                                     # prune is optional
    assert dlg.step == "send"
    dlg._on_sent({"sent": 12})
    assert dlg.step == "done"
    dlg.close()
    ctx.db.close()


def test_lazer_slim_wizard_lets_the_user_override_the_check(qapp, tmp_path,
                                                            monkeypatch):
    """Only the user can see lazer's screen, so an unconfirmed check must be
    overridable — but never silently."""
    from PySide6.QtWidgets import QMessageBox
    from rosu.ui.lazer_slim_dialog import LazerSlimDialog
    ctx = _ctx(tmp_path, monkeypatch)
    dlg = LazerSlimDialog(ctx, None)
    dlg.step = "delete"
    dlg._before = {"found": True, "bytes": 10_000_000}
    monkeypatch.setattr(ctx.services, "lazer_store_stats",
                        lambda: {"found": True, "bytes": 9_000_000})
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: asked.append(1) or QMessageBox.Yes)
    dlg._check_deleted()
    assert asked == [1] and dlg.step == "prune"
    dlg.close()
    ctx.db.close()


def test_pruned_badge_names_where_it_happened(qapp, tmp_path, monkeypatch):
    """A bare "pruned" badge on a set that also lives in osu!lazer claimed the
    lazer copy had been stripped too. It has to name the places."""
    from rosu.ui.search_tab import _pruned_where
    ctx = _ctx(tmp_path, monkeypatch)
    t = ctx.t
    assert _pruned_where({}, t) == ""
    assert _pruned_where({"pruned_sources": "library"}, t) == t("prune_source_library")
    both = _pruned_where({"pruned_sources": "library,stable"}, t)
    assert t("prune_source_library") in both and t("prune_source_stable") in both
    assert t("prune_source_lazer") not in both
    # Rows written before pruned_sources existed still read correctly.
    assert _pruned_where({"is_pruned": 1}, t) == t("prune_source_library")
    ctx.db.close()


def test_restore_dialog_states_the_source_and_lets_you_pick(qapp, tmp_path,
                                                            monkeypatch):
    """"Restore" silently downloading from a third-party mirror is not good
    enough — say where the files come from, and offer the free exact copy."""
    from rosu.ui.restore_dialog import MIRROR, RECYCLE, RestoreSourceDialog
    ctx = _ctx(tmp_path, monkeypatch)
    dlg = RestoreSourceDialog(ctx, 214, None)
    assert dlg.rb_recycle.isChecked()             # free + exact is the default
    dlg._accept()
    assert dlg.choice == RECYCLE
    dlg.rb_mirror.setChecked(True)
    dlg._accept()
    assert dlg.choice == MIRROR
    # The mirror option must name the host it will actually download from.
    from rosu.api_mirror import MIRROR_URL
    host = MIRROR_URL.split("//", 1)[-1].split("/", 1)[0]
    assert host in ctx.t("restore_opt_mirror", url=host)
    dlg.close()
    ctx.db.close()


def test_health_dialog_builds_and_renders_report(qapp, tmp_path, monkeypatch):
    """The v1.1 Library Health dialog constructs and populates from a report."""
    from rosu.ui.health_dialog import HealthDialog
    ctx = _ctx(tmp_path, monkeypatch)
    report = {
        "usage": {"files": 2, "total_bytes": 3_500_000},
        "scrub": {"present": 1, "orphans": ["x.osz"],
                  "dead_links": [{"filename": "y.osz"}], "memory": 0},
        "biggest": [{"filename": "big.osz", "size_bytes": 3_000_000,
                     "display_name": "Artist - Big"}],
    }
    dlg = HealthDialog(ctx, report, None)
    assert dlg.table.rowCount() == 1
    assert "big" in dlg.table.item(0, 0).text().lower()
    ctx.i18n.set_language("tr")
    dlg.retranslate()
    ctx.i18n.set_language("en")
    dlg.close()
    ctx.db.close()


def test_search_row_columns_match_the_stored_data(qapp, tmp_path, monkeypatch):
    """HANDOFF 4.3: Mode lists every difficulty's mode (not the first .osu's),
    a memory-only set shows no 💾 and offers no "Open location", and the
    Library status is translated rather than a raw DB token."""
    from rosu.ui.main_window import MainWindow
    from rosu.ui.search_tab import SearchTab
    ctx = _ctx(tmp_path, monkeypatch)
    ctx.i18n.set_language("tr")
    win = MainWindow(ctx, qapp)
    tab = win.search
    diffs = [{"mode": "osu!", "mode_int": 0, "star_rating": 2.0},
             {"mode": "osu!mania", "mode_int": 3, "keycount": 7, "star_rating": 4.0}]
    tab._populate([{"id": 1, "beatmapset_id": 1, "filename": "1 A - B.osz",
                    "title": "B", "artist": "A", "display_name": "A - B",
                    "mode": "osu!", "difficulties": diffs,
                    "in_library": 1, "library_status": "memory",
                    "in_osu": 1, "in_osu_lazer": 1}])
    col = {k: i for i, k in enumerate(SearchTab._KEYS)}
    cell = lambda k: tab.table.item(0, col[k]).text()   # noqa: E731
    assert cell("col_mode") == "osu!, osu!mania"
    assert cell("col_keys") == "7K"
    assert "💾" not in cell("col_location")
    assert cell("col_lib_status") == ctx.t("lib_status_memory") != "memory"
    assert tab.table._row_path(0) == ""
    win.close()
    ctx.db.close()


def test_remove_dialog_builds_with_no_client_available(qapp, tmp_path, monkeypatch):
    from rosu.ui.remove_dialog import RemoveDialog
    ctx = _ctx(tmp_path, monkeypatch)
    monkeypatch.setattr(type(ctx.services), "removal_sources", lambda self: [
        {"key": "stable", "available": False, "reason": "no_stable"},
        {"key": "lazer", "available": False, "reason": "lazer_helper"}])
    dlg = RemoveDialog(ctx)
    _sources_loaded(dlg, qapp)
    assert not dlg.btn_run.isEnabled()
    assert dlg.lbl_status.text() == ctx.t("rm_no_source")
    dlg.reject()
    ctx.db.close()


def _sources_loaded(dlg, qapp):
    """The dialog asks which clients are available off the UI thread."""
    dlg._src_worker.wait(5000)
    qapp.processEvents()


def test_remove_dialog_offers_only_save_first_for_lazer(qapp, tmp_path, monkeypatch):
    from rosu.ui.remove_dialog import RemoveDialog
    ctx = _ctx(tmp_path, monkeypatch)
    monkeypatch.setattr(type(ctx.services), "removal_sources", lambda self: [
        {"key": "stable", "available": False, "reason": "no_stable"},
        {"key": "lazer", "available": True, "reason": ""}])
    monkeypatch.setattr(RemoveDialog, "scan", lambda self: None)
    dlg = RemoveDialog(ctx)
    _sources_loaded(dlg, qapp)
    assert dlg.cbo_source.currentData() == "lazer"
    assert dlg.rb_save.isChecked() and not dlg.rb_only.isEnabled()
    dlg.reject()
    ctx.db.close()


def test_remove_dialog_lists_a_scan_and_warns_about_unbacked_sets(qapp, tmp_path, monkeypatch):
    from rosu.ui.remove_dialog import RemoveDialog
    ctx = _ctx(tmp_path, monkeypatch)
    monkeypatch.setattr(type(ctx.services), "removal_sources", lambda self: [
        {"key": "stable", "available": False, "reason": "no_stable"},
        {"key": "lazer", "available": False, "reason": "lazer_helper"}])
    dlg = RemoveDialog(ctx)
    _sources_loaded(dlg, qapp)
    dlg._on_scanned({"source": "stable", "sets": [
        {"key": "1 A", "name": "1 A", "size": 10, "backed_up": True},
        {"key": "2 B", "name": "2 B", "size": 20, "backed_up": False}]}, dlg._scan_seq)
    assert dlg.btn_run.isEnabled() and dlg.table.rowCount() == 2
    dlg.rb_only.setChecked(True)
    assert "1" in dlg.lbl_warn.text()                     # 1 set has no Library copy
    dlg.cbo_which.setCurrentIndex(dlg.cbo_which.findData("backed_up"))
    assert dlg.table.rowCount() == 1 and dlg.lbl_warn.text() == ""
    dlg.reject()
    ctx.db.close()


def test_drive_browser_filters_and_offers_only_restorable_rows(qapp, tmp_path, monkeypatch):
    from rosu.ui import drive_browser_dialog as dbd
    entries = [
        {"key": "id:1", "name": "1 A - T.osz", "artist": "Alpha", "title": "Tune", "size": 5,
         "chunk": "c0", "on_drive": True, "in_library": True, "this_device": True, "device": "x"},
        {"key": "id:2", "name": "2 B - U.osz", "artist": "Beta", "title": "Song", "size": 7,
         "chunk": "c0", "on_drive": True, "in_library": False, "this_device": False, "device": "y"},
        {"key": "id:3", "name": "3 C - V.osz", "artist": "Gamma", "title": "Song", "size": 9,
         "chunk": "c1", "on_drive": False, "in_library": False, "this_device": False, "device": "y"},
    ]
    assert [e["key"] for e in dbd.filter_entries(entries)] == ["id:2", "id:3"]
    assert [e["key"] for e in dbd.filter_entries(entries, "song beta")] == ["id:2"]
    assert [e["key"] for e in dbd.filter_entries(entries, "", hide_in_library=False)] == ["id:1", "id:2", "id:3"]

    ctx = _ctx(tmp_path, monkeypatch)
    monkeypatch.setattr(dbd.DriveBrowserDialog, "load", lambda self: None)   # no worker
    dlg = dbd.DriveBrowserDialog(ctx)
    dlg._on_loaded({"entries": entries, "devices": 2, "missing": 1, "orphans": []})
    assert dlg.table.rowCount() == 2
    dlg.table.selectAll()
    chosen = dlg._selected()
    assert [e["key"] for e in chosen] == ["id:2"]            # the missing archive is not restorable
    dlg.reject()
    ctx.db.close()


def test_job_row_describes_remove_and_restore_jobs(qapp, tmp_path, monkeypatch):
    from rosu.jobs import Job, new_id
    from rosu.ui.shortcuts_tab import _describe_job
    ctx = _ctx(tmp_path, monkeypatch)
    job = Job(new_id(), "job_remove", kind="remove")
    job.ctx["options"] = {"remove_source": "stable", "sets": 3, "save_first": True}
    line = _describe_job(job, ctx.t)
    assert ctx.t("rm_mode_save") in line and "3" in line
    job2 = Job(new_id(), "job_drive_restore", kind="drive_restore")
    job2.ctx["options"] = {"restore_sets": 4}
    assert "4" in _describe_job(job2, ctx.t)
    ctx.db.close()


def test_update_banner_links_the_exe_and_escapes(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    rel = "https://github.com/Kerevizodunu2000/rosu/releases/"
    win._on_update_checked({"newer": True, "tag": "v9.9.9", "url": rel + "tag/v9.9.9",
                            "download_url": rel + "download/v9.9.9/rosu-v9.9.9-win64.exe",
                            "notes": "<b>notes</b>"})
    text = win.update_banner.text()
    from html import escape
    assert "rosu-v9.9.9-win64.exe" in text and escape(ctx.t("update_whats_new")) in text
    assert win.update_banner.toolTip() == "<qt>&lt;b&gt;notes&lt;/b&gt;</qt>"
    win.close()
    ctx.db.close()


def test_search_columns_hide_persist_and_saved_searches_apply(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    saves = []
    monkeypatch.setattr(type(ctx), "save_config", lambda self: saves.append(1))
    win = MainWindow(ctx, qapp)
    tab = win.search
    bpm = tab._KEYS.index("col_bpm")
    tab._set_column_visible("col_bpm", False)
    assert tab.table.isColumnHidden(bpm) and ctx.cfg.search_hidden_columns == ["col_bpm"]
    tab._set_hidden_columns(["col_name", "col_bpm"])          # the name column never hides
    assert not tab.table.isColumnHidden(0) and ctx.cfg.search_hidden_columns == ["col_bpm"]
    tab._set_column_visible("col_bpm", True)
    assert not tab.table.isColumnHidden(bpm) and saves
    ran = []
    monkeypatch.setattr(tab, "do_search", lambda: ran.append(tab.box.text()))
    tab.apply_saved_search({"name": "x", "query": "mode=mania star>5", "tags": True})
    assert ran == ["mode=mania star>5"] and tab.chk_tags.isChecked()
    tab._fill_saved_menu()                                     # builds without error
    tab.btn_gallery.setChecked(True)
    assert tab.views.currentWidget() is tab.gallery and ctx.cfg.search_view == "gallery"
    tab.btn_gallery.setChecked(False)
    assert tab.views.currentWidget() is tab.table and ctx.cfg.search_view == "table"
    win.close()
    ctx.db.close()


def test_logs_tab_filters_and_appends_live(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    tab = win.logs
    ctx.log.info("SEARCH", query="abc", results=1)
    ctx.log.error("unit:test", "something broke")
    tab.on_shown()
    qapp.processEvents()
    total = tab.table.rowCount()
    assert total >= 2
    tab.chk_errors.setChecked(True)
    assert all(tab.table.item(r, 1).text() == "ERROR" for r in range(tab.table.rowCount()))
    tab.chk_errors.setChecked(False)
    tab.filter.setText("abc")
    tab._refill()
    assert tab.table.rowCount() == 1 and tab.table.item(0, 2).text() == "SEARCH"
    tab.filter.setText("")
    tab._refill()
    ctx.log.info("SEARCH", query="live", results=0)
    qapp.processEvents()
    assert tab.table.rowCount() == total + 1
    tab._on_live_line("1999-01-01T00:00:01 | INFO  | OLD | <b>x</b> | yesterday")
    assert tab.table.rowCount() == total + 1          # another day's line stays out
    tab._on_live_line("Traceback line with <b>markup</b>")
    assert tab.table.rowCount() == total + 2
    tip = tab.table.item(total + 1, 4).toolTip()
    assert "&lt;b&gt;" in tip and "<b>" not in tip   # shown literally
    win.close()
    ctx.db.close()


def test_cover_gallery_makes_and_caches_thumbnails(qapp, tmp_path, monkeypatch):
    import zipfile
    from PySide6.QtGui import QImage
    from rosu.ui.cover_gallery import THUMB_H, THUMB_W, CoverGallery, cover_crop
    ctx = _ctx(tmp_path, monkeypatch)
    img = QImage(1920, 1080, QImage.Format_RGB32)
    img.fill(0x3366CC)
    img.save(str(tmp_path / "bg.png"), "PNG")
    png = (tmp_path / "bg.png").read_bytes()
    osz = ctx.cfg.library_path / "1 A - B.osz"
    with zipfile.ZipFile(osz, "w") as zf:
        zf.writestr("A - B [x].osu", '[Events]\n0,0,"bg.png",0,0\n')
        zf.writestr("bg.png", png)
    rows = [{"artist": "A", "title": "B", "filename": osz.name, "in_library": 1,
             "library_status": "present"},
            {"artist": "C", "title": "memory only", "filename": "2 C.osz", "in_library": 1,
             "library_status": "memory"}]
    g = CoverGallery(ctx)
    g.set_rows(rows)
    assert g.count() == 2
    g._loader.wait(10000)
    qapp.processEvents()
    assert len(list((ctx.cfg.data_path / "covers").glob("*.jpg"))) == 1
    assert g.item(0).icon().pixmap(THUMB_W, THUMB_H).toImage().pixelColor(5, 5).blue() > 150
    tall = cover_crop(QImage(100, 1000, QImage.Format_RGB32))
    assert (tall.width(), tall.height()) == (THUMB_W, THUMB_H)
    ctx.db.close()


def test_move_library_dialog_previews_and_the_result_updates_settings(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    from rosu.ui.move_library_dialog import MoveLibraryDialog
    ctx = _ctx(tmp_path, monkeypatch)
    (ctx.cfg.library_path / "1 A - B.osz").write_bytes(b"x" * 10)
    dlg = MoveLibraryDialog(ctx)
    dlg.dest.setText(str(ctx.cfg.library_path))
    dlg.check()
    dlg._worker.wait(5000)
    qapp.processEvents()
    assert not dlg.btn_move.isEnabled() and dlg.lbl_plan.text() == ctx.t("mv_err_same")
    dlg.dest.setText(str(tmp_path / "NewLib"))
    dlg.check()
    dlg._worker.wait(5000)
    qapp.processEvents()
    assert dlg.btn_move.isEnabled() and "1" in dlg.lbl_plan.text()
    win = MainWindow(ctx, qapp)
    shown = []
    monkeypatch.setattr("rosu.ui.shortcuts_tab._plain_message", lambda *a: shown.append(a[2]))
    new_lib = tmp_path / "NewLib"
    new_lib.mkdir()
    ctx.cfg.library_dir = str(new_lib)          # what move_library switched to
    win.shortcuts._present_library_move({"moved": 1, "same": 0, "dest": str(new_lib)})
    assert win.settings.library.text() == str(new_lib)
    assert not win.settings._is_dirty()
    win.settings._save(silent=True)             # a later Save keeps the new folder
    assert ctx.cfg.library_dir == str(new_lib)
    win.shortcuts._present_library_move({"error": "conflicts", "conflicts": ["a.osz"]})
    assert ctx.t("mv_nothing_changed") in shown[-1]
    win.close()
    ctx.db.close()


def test_autosaved_crash_report_toggle_leaves_settings_clean(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    ctx.cfg.settings_autosave = True
    win = MainWindow(ctx, qapp)
    win.settings.cb_crash_reports.setChecked(not win.settings.cb_crash_reports.isChecked())
    assert ctx.cfg.crash_reports == win.settings.cb_crash_reports.isChecked()
    assert not win.settings._is_dirty()      # v1.8: the toggle was missing from the baseline
    win.close()
    ctx.db.close()


def test_folder_watcher_queues_new_downloads_only(qapp, tmp_path, monkeypatch):
    import zipfile
    from types import SimpleNamespace
    from rosu import jobs
    from rosu.ui.main_window import MainWindow
    import rosu.ui.folder_watch as fw_mod
    ctx = _ctx(tmp_path, monkeypatch)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    with zipfile.ZipFile(downloads / "1 old.osz", "w") as zf:
        zf.writestr("a.osu", "x")
    win = MainWindow(ctx, qapp)
    queued = []

    def queue(paths):
        job = SimpleNamespace(state=jobs.State.PENDING, paths=[str(p) for p in paths])
        queued.append(job)
        return job
    monkeypatch.setattr(win.shortcuts, "queue_watch_import", queue)
    clock = [1000.0]
    monkeypatch.setattr(fw_mod.time, "monotonic", lambda: clock[0])
    fw = win.folder_watch
    ctx.cfg.watch_enabled = True
    ctx.cfg.watch_folder = str(downloads)
    fw.reconfigure()
    assert fw.folder == downloads
    with zipfile.ZipFile(downloads / "2 new.osz", "w") as zf:
        zf.writestr("b.osu", "y")
    fw.scan()                        # first look: new file seen, not settled
    fw.scan()                        # unchanged since: taken
    assert [[Path(p).name for p in j.paths] for j in queued] == [["2 new.osz"]]
    fw.scan()
    assert len(queued) == 1          # one batch at a time, never queued twice
    fw.reconfigure()                 # saving other settings leaves the watch alone
    fw.scan()
    assert len(queued) == 1 and fw._job is queued[0]
    new = queued[0].paths[0]
    queued[0].state = jobs.State.FAILED
    fw.job_failed([new])
    fw.scan()
    assert len(queued) == 1          # a failed import waits before it is retried
    assert fw._retry.isActive()
    clock[0] += fw_mod.RETRY_S + 1
    fw.scan()
    assert len(queued) == 2          # retried after the pause
    fw.job_done({"failed": [new]})   # failed again: the pause doubles
    clock[0] += fw_mod.RETRY_S + 1
    fw.scan()
    assert len(queued) == 2
    clock[0] += fw_mod.RETRY_S
    fw.scan()
    assert len(queued) == 3
    queued[-1].state = jobs.State.CANCELLED   # cancelled in the queue: like a failure
    fw.scan()
    assert fw._job is None and len(queued) == 3
    clock[0] += 4 * fw_mod.RETRY_S + 1
    fw.scan()
    assert len(queued) == 4
    fw.job_done({"imported": [new]})
    ctx.cfg.watch_folder = str(tmp_path)          # another folder, then back again
    fw.reconfigure()
    ctx.cfg.watch_folder = str(downloads)
    fw.reconfigure()                 # restart: the handled file is remembered
    fw.scan()
    fw.scan()
    assert len(queued) == 4
    with zipfile.ZipFile(downloads / "3 while closed.osz", "w") as zf:
        zf.writestr("c.osu", "z")
    ctx.cfg.watch_enabled = False
    fw.reconfigure()
    ctx.cfg.watch_enabled = True
    fw.reconfigure()                 # a download that arrived while Rosu was closed
    fw.scan()
    fw.scan()
    assert queued[-1].paths[0].endswith("3 while closed.osz")
    fw.job_done({"imported": ["somewhere/else.osz"]})   # a stale result changes nothing
    assert fw._job is queued[-1]
    ctx.cfg.watch_enabled = False
    fw.reconfigure()
    assert fw.folder is None
    win.close()
    ctx.db.close()


class _Sig:
    def __init__(self):
        self._slots = []

    def connect(self, fn):
        self._slots.append(fn)

    def emit(self, *a):
        for fn in self._slots:
            fn(*a)


class _ManualWorker:
    """A Worker stand-in whose result is delivered when the test says so."""
    started: list = []

    def __init__(self, fn, *a, **k):
        self.fn, self.a, self.k = fn, a, k
        self.succeeded, self.failed, self.finished = _Sig(), _Sig(), _Sig()

    def start(self):
        _ManualWorker.started.append(self)

    def deliver(self):
        self.succeeded.emit(self.fn(*self.a, **self.k))
        self.finished.emit()


def test_search_history_goes_back_and_forward(qapp, tmp_path, monkeypatch):
    from rosu.ui.main_window import MainWindow
    ctx = _ctx(tmp_path, monkeypatch)
    win = MainWindow(ctx, qapp)
    tab = win.search
    clock = iter(range(0, 1000, 10))
    monkeypatch.setattr("rosu.ui.search_tab.time.monotonic", lambda: next(clock))
    monkeypatch.setattr("rosu.ui.search_tab.Worker", _ManualWorker)
    _ManualWorker.started = []

    def search(q):
        tab.box.setText(q)
        tab.do_search()
        return _ManualWorker.started[-1]
    search("alpha").deliver()
    search("beta").deliver()
    assert tab.btn_back.isEnabled() and not tab.btn_fwd.isEnabled()
    tab._go_history(-1)
    _ManualWorker.started[-1].deliver()
    assert tab.box.text() == "alpha"
    assert tab.btn_fwd.isEnabled() and not tab.btn_back.isEnabled()
    tab._go_history(1)
    _ManualWorker.started[-1].deliver()
    assert tab.box.text() == "beta" and not tab.btn_fwd.isEnabled()
    # Going back, then typing before that result arrives: the stale result is
    # dropped and the typed search still lands in the history.
    tab._go_history(-1)
    stale = _ManualWorker.started[-1]
    search("gamma").deliver()
    stale.deliver()
    assert tab._history.back() == ("alpha", tab.chk_tags.isChecked())
    win.close()
    ctx.db.close()


def test_stage_to_output_copies_library_files_only(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    lib = ctx.cfg.library_path
    (lib / "1 A.osz").write_bytes(b"a")
    outside = tmp_path / "elsewhere.osz"
    outside.write_bytes(b"x")
    (ctx.cfg.output_path / "2 B.osz").write_bytes(b"different")
    (lib / "2 B.osz").write_bytes(b"b")
    res = ctx.services.stage_to_output([lib / "1 A.osz", lib / "2 B.osz", outside])
    assert res == {"copied": 1, "already": 0, "skipped": 2}
    assert (ctx.cfg.output_path / "1 A.osz").read_bytes() == b"a"
    assert (ctx.cfg.output_path / "2 B.osz").read_bytes() == b"different"   # not replaced
    import shutil

    def broken_copy(src, dst, **_k):
        with open(dst, "wb") as fh:
            fh.write(b"half")
        raise OSError("disk full")
    (lib / "3 C.osz").write_bytes(b"c")
    monkeypatch.setattr(shutil, "copyfile", broken_copy)
    res = ctx.services.stage_to_output([lib / "3 C.osz"])
    assert res["skipped"] == 1
    assert sorted(p.name for p in ctx.cfg.output_path.iterdir()) == ["1 A.osz", "2 B.osz"]
    ctx.db.close()


def test_same_song_dialog_lists_groups_and_keeps_one_per_song(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from rosu.ui.same_song_dialog import SameSongDialog, extras
    ctx = _ctx(tmp_path, monkeypatch)
    group = [
        {"track_id": 1, "filename": "1 A - S.osz", "beatmapset_id": 1, "artist": "A", "title": "S",
         "creator": "m1", "diff_count": 3, "size": 100},
        {"track_id": 2, "filename": "2 A - S (TV).osz", "beatmapset_id": 2, "artist": "A", "title": "S",
         "creator": "m2", "diff_count": 5, "size": 50},
        {"track_id": 3, "filename": "3 A - S.osz", "beatmapset_id": 3, "artist": "A", "title": "S",
         "creator": "m3", "diff_count": 5, "size": 80},
    ]
    assert extras(group) == ["1 A - S.osz", "2 A - S (TV).osz"]     # keeps 5 diffs, larger
    monkeypatch.setattr(type(ctx.services), "fingerprint_library",
                        lambda self, progress=None, cancel=None: {"computed": 3, "cached": 0,
                                                                  "failed": 0, "cancelled": False})
    monkeypatch.setattr(type(ctx.services), "same_song_report",
                        lambda self, progress=None: {"groups": [group], "fingerprinted": 3})
    dlg = SameSongDialog(ctx)
    dlg._worker.wait(5000)
    qapp.processEvents()
    assert dlg.tree.topLevelItemCount() == 1 and dlg.tree.topLevelItem(0).childCount() == 3
    assert not dlg.btn_recycle.isEnabled()                            # nothing pre-selected
    dlg._select_extras()
    assert sorted(dlg._checked()) == ["1 A - S.osz", "2 A - S (TV).osz"]
    top = dlg.tree.topLevelItem(0)
    for j in range(top.childCount()):
        top.child(j).setCheckState(0, Qt.Checked)
    dlg._confirm()                                                    # every copy: refused
    assert dlg.plan is None and dlg.lbl_status.text() == ctx.t("ss_keep_one")
    dlg.reject()
    ctx.db.close()
