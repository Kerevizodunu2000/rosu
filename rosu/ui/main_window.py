# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: a tabbed shell hosting the five feature tabs."""
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from .. import __version__, theming
from .artists_tab import ArtistsTab
from .dashboard_tab import DashboardTab
from .logs_tab import LogsTab
from .packs_tab import PacksTab
from .search_tab import SearchTab
from .settings_tab import SettingsTab


def load_stylesheet(theme: str) -> str:
    return theming.stylesheet_for(theme)


class MainWindow(QMainWindow):
    def __init__(self, ctx, app):
        super().__init__()
        self.ctx = ctx
        self.app = app
        self.resize(1040, 680)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard = DashboardTab(self)
        self.search = SearchTab(self)
        self.artists = ArtistsTab(self)
        self.packs = PacksTab(self)
        self.logs = LogsTab(self)
        self.settings = SettingsTab(self)

        self._ordered_tabs = [self.dashboard, self.search, self.artists,
                              self.packs, self.logs, self.settings]
        for tab in self._ordered_tabs:
            self.tabs.addTab(tab, "")

        # live-log mirror into the Logs tab
        self.ctx.log.ui_sink = self.logs.append_line

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.retranslate()

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
        keys = ["tab_dashboard", "tab_search", "tab_artists", "tab_packs",
                "tab_logs", "tab_settings"]
        for i, key in enumerate(keys):
            self.tabs.setTabText(i, t(key))
        for tab in self._ordered_tabs:
            tab.retranslate()

    def _on_tab_changed(self, index: int) -> None:
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
        try:
            self.ctx.services.request_cancel()
        except Exception:
            pass
        for tab in self._ordered_tabs:
            for w in list(getattr(tab, "_threads", [])):
                try:
                    if w.isRunning():
                        w.wait(5000)  # give each worker up to 5s to finish
                except RuntimeError:
                    pass  # C++ object already gone
        super().closeEvent(event)
