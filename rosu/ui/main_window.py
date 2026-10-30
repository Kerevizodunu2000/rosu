# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: a tabbed shell hosting the five feature tabs."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from .. import __version__, theming, updater
from ..workers import Worker
from .artists_tab import ArtistsTab
from .dashboard_tab import DashboardTab
from .logs_tab import LogsTab
from .packs_tab import PacksTab
from .search_tab import SearchTab
from .settings_tab import SettingsTab
from .shortcuts_tab import ShortcutsTab


def load_stylesheet(theme: str) -> str:
    return theming.stylesheet_for(theme)


class MainWindow(QMainWindow):
    def __init__(self, ctx, app):
        super().__init__()
        self.ctx = ctx
        self.app = app
        self.resize(1280, 760)   # wider default so wide tables (Search) fit better

        # central column: a thin update banner (hidden until relevant) + tabs
        central = QWidget()
        col = QVBoxLayout(central)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self.update_banner = QLabel(objectName="banner")
        self.update_banner.setWordWrap(True)
        self.update_banner.setOpenExternalLinks(True)
        from .links import wire_link_hover
        wire_link_hover(self.update_banner)
        self.update_banner.setContentsMargins(12, 6, 12, 6)
        # long text wraps, but an unbroken token is clipped rather than widening the window
        self.update_banner.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.update_banner.setVisible(False)
        # banner row: the text plus "Restart now" once an update is staged
        self._banner_row = QHBoxLayout()
        self._banner_row.setContentsMargins(0, 0, 0, 0)
        self._banner_row.setSpacing(12)   # the banner's own 12 px inset
        self._banner_row.addWidget(self.update_banner, 1)
        self.update_restart = QPushButton()
        # as tall as the banner beside it, not a smaller centred button
        self.update_restart.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.update_restart.setVisible(False)
        self.update_restart.clicked.connect(self._on_restart_now)
        self._banner_row.addWidget(self.update_restart)
        self.update_dismiss = QPushButton()
        self.update_dismiss.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.update_dismiss.setVisible(False)
        self.update_dismiss.clicked.connect(self._on_dismiss_notice)
        self._banner_row.addWidget(self.update_dismiss)
        col.addLayout(self._banner_row)
        self.tabs = QTabWidget()
        col.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self._threads: list[Worker] = []
        self._update_info: dict | None = None
        self._update_phase = ""          # "", "downloading" or "ready"
        self._update_percent = 0
        self._update_cancel = None       # threading.Event of the running download
        self._update_check: dict | None = None   # last valid check result, newer or not
        self._installed_version: str | None = None   # the "was installed" notice, until dismissed
        self._restart_armed = False      # "Restart now" pressed while busy
        self._restart_timer = QTimer(self)
        self._restart_timer.setInterval(1000)
        self._restart_timer.timeout.connect(self._restart_if_idle)
        self.restart_for_update = False  # read by app.run() after the DB is closed

        self.dashboard = DashboardTab(self)
        self.shortcuts = ShortcutsTab(self)
        self.search = SearchTab(self)
        self.artists = ArtistsTab(self)
        self.packs = PacksTab(self)
        self.logs = LogsTab(self)
        self.settings = SettingsTab(self)

        self._ordered_tabs = [self.dashboard, self.shortcuts, self.search,
                              self.artists, self.packs, self.logs, self.settings]
        for tab in self._ordered_tabs:
            self.tabs.addTab(tab, "")

        # live-log mirror into the Logs tab
        self.ctx.log.ui_sink = self.logs.append_line
        from .folder_watch import FolderWatcher
        self.folder_watch = FolderWatcher(self)   # v1.9, opt-in (Settings)
        self.folder_watch.reconfigure()

        self._prev_index = self.tabs.currentIndex()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.retranslate()
        self._maybe_check_updates()

    # -- update check (item E) ----------------------------------------------
    def _maybe_check_updates(self) -> None:
        """Best-effort startup check for a newer GitHub release (off-thread)."""
        if not getattr(self.ctx.cfg, "check_updates", True):
            return
        from .. import update_check
        w = Worker(lambda progress=None: update_check.check(__version__))
        self._threads.append(w)
        w.succeeded.connect(self._on_update_checked)
        w.failed.connect(lambda _msg: None)   # offline / rate-limited: stay silent
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_update_checked(self, res) -> None:
        if not res:
            return
        self._update_check = res   # kept even when not newer: the notice uses its notes
        if not res.get("newer"):
            self._render_update_banner()
            return
        self._update_info = res
        if updater.can_auto_update(self.ctx.cfg):
            self._start_update_download(res["tag"])
        self._render_update_banner()

    def _start_update_download(self, tag: str) -> None:
        import threading
        self._update_cancel = threading.Event()
        self._update_phase, self._update_percent = "downloading", 0
        w = Worker(updater.download, self.ctx.cfg, tag, cancel=self._update_cancel)
        self._threads.append(w)
        w.progressed.connect(self._on_update_progress)
        w.succeeded.connect(self._on_update_downloaded)
        w.failed.connect(lambda _msg: self._on_update_downloaded(None))
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_update_progress(self, p) -> None:
        if isinstance(p, dict) and isinstance(p.get("percent"), int):
            self._update_percent = p["percent"]
            self._render_update_banner()

    def _on_update_downloaded(self, res) -> None:
        ready = isinstance(res, dict) and res.get("status") == updater.READY
        self._update_phase = "ready" if ready else ""   # else: today's banner
        self._render_update_banner()

    def show_updated_notice(self, version: str | None) -> None:
        """One-time "Rosu vX was installed" line; ``version`` is mark_healthy()'s result."""
        if version is None:
            return
        self._installed_version = version
        self._render_update_banner()

    def _on_dismiss_notice(self) -> None:
        self._installed_version = None
        self._render_update_banner()
        self.tabs.setFocus()   # the focused button just hid

    def _installed_text(self) -> str:
        """The notice, plus the first 6 note lines as literal text when the kept
        check result is for the installed tag (same escaping as links.plain_tip)."""
        from html import escape
        version = self._installed_version
        text = escape(self.ctx.t("update_installed", version=version))
        chk = self._update_check
        if chk and str(chk.get("tag", "")).lstrip("v") == version.lstrip("v") \
                and chk.get("notes"):
            text += "<br>" + "<br>".join(
                escape(line) for line in str(chk["notes"]).splitlines()[:6])
        return text

    def _idle_for_restart(self) -> bool:
        """No worker, no unfinished queue job (gates included), no open dialog."""
        if self._operation_running() or QApplication.activeModalWidget() is not None:
            return False
        return not any(q.has_unfinished() for q in
                       (getattr(tab, "queue", None) for tab in self._ordered_tabs) if q)

    def _on_restart_now(self) -> None:
        if self._restart_armed:
            self._set_restart_armed(False)
        elif self._idle_for_restart():
            self._restart()
        else:
            self._set_restart_armed(True)

    def _set_restart_armed(self, armed: bool) -> None:
        self._restart_armed = armed
        if armed:
            self._restart_timer.start()
        else:
            self._restart_timer.stop()
        self._render_update_banner()

    def _restart_if_idle(self) -> None:
        if self._restart_armed and self._idle_for_restart():
            self._restart_timer.stop()
            self._restart()

    def _restart(self) -> None:
        self.restart_for_update = True
        if not self.close():
            self.restart_for_update = False   # close refused: don't relaunch later
            self._set_restart_armed(False)

    def _render_update_banner(self) -> None:
        info = self._update_info
        ready = bool(info) and self._update_phase == "ready"
        notice = not info and self._installed_version is not None   # an update takes its place
        self.update_restart.setVisible(ready)
        self.update_dismiss.setVisible(notice)
        self._banner_row.setContentsMargins(0, 0, 12 if ready or notice else 0, 0)   # off the edge
        from html import escape
        t = self.ctx.t
        if notice:
            self.update_dismiss.setText(t("update_dismiss"))
            self.update_banner.setText(self._installed_text())
            self.update_banner.setVisible(True)
            return
        if not info:
            self.update_banner.setVisible(False)
            return
        if self._update_phase:
            armed = ready and self._restart_armed
            key = ("update_restart_armed" if armed else
                   "update_ready" if ready else "update_downloading")
            self.update_banner.setText(escape(t(key, tag=info["tag"],
                                                percent=self._update_percent)))
            self.update_restart.setText(t("update_cancel_restart" if armed
                                          else "update_restart"))
            self.update_banner.setVisible(True)
            return
        # The direct .exe when the site supplied one, else the release page. Both
        # were validated as links into this project's GitHub releases.
        dl = info.get("download_url") or info["url"]
        links = f"  <a href='{escape(dl, quote=True)}'>{escape(t('update_open'))}</a>"
        if info.get("download_url"):
            links += (f"  ·  <a href='{escape(info['url'], quote=True)}'>"
                      f"{escape(t('update_whats_new'))}</a>")
        self.update_banner.setText(
            escape(t("update_available", tag=info["tag"])) + links)
        if info.get("notes"):
            from .links import plain_tip
            self.update_banner.setToolTip(plain_tip(info["notes"]))
        self.update_banner.setVisible(True)

    # -- shared operations ---------------------------------------------------
    def show_missing_packs(self) -> None:
        """Dashboard 'possibly missing' link -> Packs tab, only-missing view (item 12)."""
        self.tabs.setCurrentWidget(self.packs)   # fires on_shown -> reload
        self.packs.focus_missing()

    def apply_theme(self, theme: str) -> None:
        self.app.setStyleSheet(load_stylesheet(theme))

    def apply_language(self, lang: str) -> None:
        self.ctx.i18n.set_language(lang)
        self.retranslate()

    def retranslate(self) -> None:
        t = self.ctx.t
        self.setWindowTitle(f"{t('app_title')}  ·  v{__version__}")
        keys = ["tab_dashboard", "tab_shortcuts", "tab_search", "tab_artists",
                "tab_packs", "tab_logs", "tab_settings"]
        for i, key in enumerate(keys):
            self.tabs.setTabText(i, t(key))
        for tab in self._ordered_tabs:
            tab.retranslate()
        self._render_update_banner()   # banner text follows the language

    def _operation_running(self) -> bool:
        """True if a tab has a live background worker (import / Drive backup /
        client export / scan) — used to confirm before quitting mid-operation.
        The main window's own (trivial, quick) update-check worker is excluded."""
        for tab in self._ordered_tabs:
            for w in list(getattr(tab, "_threads", [])):
                try:
                    if w.isRunning():
                        return True
                except RuntimeError:
                    pass
        return False

    def _on_tab_changed(self, index: int) -> None:
        # Guard leaving the Settings tab with unsaved path/API edits (item 11).
        prev = (self.tabs.widget(self._prev_index)
                if 0 <= self._prev_index < self.tabs.count() else None)
        if prev is self.settings and index != self._prev_index \
                and not self.settings.confirm_leave():
            self.tabs.blockSignals(True)          # veto: bounce back, don't re-enter
            self.tabs.setCurrentIndex(self._prev_index)
            self.tabs.blockSignals(False)
            return
        self._prev_index = index
        widget = self.tabs.widget(index)
        if widget is self.settings:
            self.settings.refresh_drive_storage()   # "when the panel opens"
        if self.ctx.cfg.auto_refresh_on_tab and hasattr(widget, "on_shown"):
            widget.on_shown()

    def closeEvent(self, event) -> None:
        """Stop and join background workers before the app tears down the DB.

        Without this, closing the window returns from ``app.exec()`` and
        ``ctx.db.close()`` runs while a worker thread may still be using the DB
        (``Cannot operate on a closed database``) or delivering a signal to an
        already-deleted widget.
        """
        if hasattr(self.settings, "confirm_leave") and not self.settings.confirm_leave():
            event.ignore()      # unsaved Settings edits, user chose Cancel (item 11)
            return
        if self._operation_running():
            t = self.ctx.t
            reply = QMessageBox.question(
                self, t("app_title"), t("op_running_quit"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                event.ignore()   # a Drive upload / import is still running
                return
        try:
            self.ctx.services.request_cancel()
            # Job-queue steps poll their OWN per-job token (so one job's cancel
            # can't disturb another's Drive upload), which request_cancel doesn't
            # reach — trip each queued job's token too so running steps stop.
            for tab in self._ordered_tabs:
                q = getattr(tab, "queue", None)
                if q is not None:
                    q.cancel_all()
        except Exception:
            pass
        if self._update_cancel is not None:
            self._update_cancel.set()   # the download stops at its next chunk
        self.search.gallery.stop()   # thumbnails: stop at the next cover
        from .. import workers
        holders = [getattr(h, "_threads", []) for h in self._ordered_tabs + [self]]
        # Plus every Worker still alive anywhere (a closed dialog's scan, the
        # gallery loader) — a QThread destroyed while running aborts the app.
        for w in {id(x): x for group in holders + [list(workers._live)] for x in group}.values():
            try:
                if w.isRunning():
                    w.wait(5000)  # give each worker up to 5s to finish
            except RuntimeError:
                pass  # C++ object already gone
        for tab in self._ordered_tabs:   # remove any queued job's temp stage dir
            q = getattr(tab, "queue", None)
            if q is not None:
                q.cleanup_all()
        super().closeEvent(event)
