# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: a tabbed shell hosting the five feature tabs."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel, QMainWindow, QMessageBox, QTabWidget, QVBoxLayout, QWidget,
)

from .. import __version__, theming
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
        self.update_banner.setContentsMargins(12, 6, 12, 6)
        self.update_banner.setVisible(False)
        col.addWidget(self.update_banner)
        self.tabs = QTabWidget()
        col.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self._threads: list[Worker] = []
        self._update_info: dict | None = None

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
        if not res or not res.get("newer"):
            return
        self._update_info = res
        self._render_update_banner()

    def _render_update_banner(self) -> None:
        info = self._update_info
        if not info:
            self.update_banner.setVisible(False)
            return
        link = self.ctx.t("update_open")
        self.update_banner.setText(
            self.ctx.t("update_available", tag=info["tag"])
            + f"  <a href='{info['url']}'>{link}</a>")
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
        if hasattr(widget, "on_shown"):
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
        except Exception:
            pass
        for holder in self._ordered_tabs + [self]:   # include our own update worker
            for w in list(getattr(holder, "_threads", [])):
                try:
                    if w.isRunning():
                        w.wait(5000)  # give each worker up to 5s to finish
                except RuntimeError:
                    pass  # C++ object already gone
        super().closeEvent(event)
