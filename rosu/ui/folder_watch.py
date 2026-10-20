# SPDX-License-Identifier: GPL-3.0-or-later
"""The watch-folder watcher (v1.9): Qt's file-system watcher plus a settle
timer around the pure rules in :mod:`rosu.watch`. Ready files are queued as a
disk-lane import job on the Shortcuts tab's queue."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer

from .. import watch

SETTLE_MS = 3000   # how long a new file must stay unchanged before it is taken


class FolderWatcher(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.ctx = main_window.ctx
        self.folder: Path | None = None
        self._seen: set[str] = set()
        self._prev: dict = {}
        self._fs = QFileSystemWatcher(self)
        self._fs.directoryChanged.connect(lambda _p: self._timer.start())
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SETTLE_MS)
        self._timer.timeout.connect(self.scan)

    @property
    def _state_path(self) -> Path:
        return self.ctx.cfg.data_path / "watch_state.json"

    def reconfigure(self) -> None:
        """Start, stop or re-point watching from the current settings."""
        cfg = self.ctx.cfg
        for p in self._fs.directories():
            self._fs.removePath(p)
        self._timer.stop()
        self._prev = {}
        folder = Path(cfg.watch_folder) if cfg.watch_enabled and cfg.watch_folder else None
        if folder is None or not folder.is_dir():
            self.folder = None
            return
        seen = watch.load_state(self._state_path, folder)
        if seen is None:   # a new folder: what is there already is not "new"
            seen = watch.baseline(folder)
            watch.save_state(self._state_path, folder, seen)
        self._seen = seen
        self.folder = folder
        self._fs.addPath(str(folder))
        self._prev = watch.list_osz(folder)

    def scan(self) -> None:
        if self.folder is None:
            return
        take, self._prev, pending = watch.ready(self.folder, self._seen, self._prev)
        if take:
            for p in take:
                size, mtime = self._prev[p.name]
                self._seen.add(watch.key(p.name, size, mtime))
            watch.save_state(self._state_path, self.folder, self._seen)
            self.mw.shortcuts.queue_watch_import(take)
        if pending:
            self._timer.start()   # something is still being written: look again
