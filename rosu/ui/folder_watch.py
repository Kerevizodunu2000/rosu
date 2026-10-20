# SPDX-License-Identifier: GPL-3.0-or-later
"""The watch-folder watcher (v1.9): Qt's file-system watcher plus a settle
timer around the pure rules in :mod:`rosu.watch`. Ready files are queued as a
disk-lane import job on the Shortcuts tab's queue; a file is marked handled
only when that job reports it imported (or rejected as not an archive), so a
failed, cancelled or interrupted import is tried again — after a pause, so a
full disk does not turn into an import every few seconds."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer

from .. import watch

SETTLE_MS = 3000        # how long a new file must stay unchanged before it is taken
INFLIGHT_S = 30 * 60    # a queued import not heard back from by then is retried
RETRY_S = 5 * 60        # a failed import is tried again after this long


class FolderWatcher(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.ctx = main_window.ctx
        self.folder: Path | None = None
        self._seen: dict[str, None] = {}
        self._prev: dict = {}
        self._inflight: dict[str, tuple[str, float]] = {}   # path -> (key, busy until)
        self._fs = QFileSystemWatcher(self)
        self._fs.directoryChanged.connect(lambda _p: self._timer.start())
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SETTLE_MS)
        self._timer.timeout.connect(self.scan)
        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.timeout.connect(self.scan)

    @property
    def _state_path(self) -> Path:
        return self.ctx.cfg.data_path / "watch_state.json"

    def reconfigure(self) -> None:
        """Start, stop or re-point watching from the current settings."""
        cfg = self.ctx.cfg
        for p in self._fs.directories():
            self._fs.removePath(p)
        self._timer.stop()
        self._retry.stop()
        self._prev = {}
        self._inflight = {}
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
        # Look once now: downloads that arrived while Rosu was closed are taken
        # after the usual settle check (the first look only records them).
        self._timer.start()

    def scan(self) -> None:
        if self.folder is None:
            return
        now = time.monotonic()
        self._inflight = {p: v for p, v in self._inflight.items() if v[1] > now}
        busy = {k for k, _until in self._inflight.values()}
        take, self._prev, pending = watch.ready(self.folder, self._seen, self._prev, busy)
        if take:
            for p in take:
                size, mtime = self._prev[p.name]
                self._inflight[str(p)] = (watch.key(p.name, size, mtime), now + INFLIGHT_S)
            self.mw.shortcuts.queue_watch_import(take)
        if pending:
            self._timer.start()   # something is still being written, or more to take
        self._arm_retry()

    def job_done(self, res: dict) -> None:
        """The import job reported back: remember what it handled; what failed
        is tried again after :data:`RETRY_S`."""
        for path in list(res.get("imported") or []) + list(res.get("rejected") or []):
            entry = self._inflight.pop(str(path), None)
            if entry is not None:
                self._seen[entry[0]] = None
        self.job_failed(res.get("failed") or [])
        if self.folder is not None:
            watch.save_state(self._state_path, self.folder, self._seen)
            self._timer.start()   # the next batch

    def job_failed(self, paths) -> None:
        """These files were not imported (the job failed, or reported them
        failed): keep them aside for :data:`RETRY_S`, then look again."""
        until = time.monotonic() + RETRY_S
        for path in paths:
            entry = self._inflight.get(str(path))
            if entry is not None:
                self._inflight[str(path)] = (entry[0], until)
        self._arm_retry()

    def _arm_retry(self) -> None:
        if self.folder is None or not self._inflight:
            self._retry.stop()
            return
        wait = min(until for _k, until in self._inflight.values()) - time.monotonic()
        self._retry.start(max(1000, int(wait * 1000) + 1000))
