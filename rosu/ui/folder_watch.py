# SPDX-License-Identifier: GPL-3.0-or-later
"""The watch-folder watcher (v1.9): Qt's file-system watcher plus a settle
timer around the pure rules in :mod:`rosu.watch`. Ready files are queued as a
disk-lane import job on the Shortcuts tab's queue, one batch at a time; a file
is marked handled only when that job reports it imported (or rejected as not
an archive). A failed, cancelled or interrupted import is tried again after a
pause that doubles each time (a full disk or an unplugged Library drive does
not turn into an import every few minutes)."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer

from .. import jobs, watch

SETTLE_MS = 3000            # how long a new file must stay unchanged before it is taken
RETRY_S = 5 * 60            # the first pause after a failed import …
MAX_RETRY_S = 2 * 60 * 60   # … doubling up to this


class FolderWatcher(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.ctx = main_window.ctx
        self.folder: Path | None = None
        self._seen: dict[str, None] = {}
        self._prev: dict = {}
        self._job = None                              # the import job in the queue, if any
        self._batch: dict[str, str] = {}              # its files: path -> key
        self._fails: dict[str, int] = {}              # key -> failed attempts in a row
        self._wait_until: dict[str, float] = {}       # key -> not before (monotonic)
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
        """Start, stop or re-point watching from the current settings. Saving
        other settings leaves a running watch (and its import) alone."""
        cfg = self.ctx.cfg
        folder = Path(cfg.watch_folder) if cfg.watch_enabled and cfg.watch_folder else None
        if folder is not None and not folder.is_dir():
            folder = None
        if folder is not None and folder == self.folder:
            if str(folder) not in self._fs.directories():
                self._fs.addPath(str(folder))
            return
        for p in self._fs.directories():
            self._fs.removePath(p)
        self._timer.stop()
        self._retry.stop()
        self._prev = {}
        self._job = None
        self._batch = {}
        self._fails = {}
        self._wait_until = {}
        self.folder = folder
        if folder is None:
            return
        seen = watch.load_state(self._state_path, folder)
        if seen is None:   # a new folder: what is there already is not "new"
            seen = watch.baseline(folder)
            watch.save_state(self._state_path, folder, seen)
        self._seen = seen
        self._fs.addPath(str(folder))
        # Look once now: downloads that arrived while Rosu was closed are taken
        # after the usual settle check (the first look only records them).
        self._timer.start()

    def scan(self) -> None:
        if self.folder is None:
            return
        if self._job is not None:
            if self._job.state not in jobs.TERMINAL:
                return               # one batch at a time; its result re-arms the timer
            # Finished without reporting back (cancelled): like a failure.
            self.job_failed(list(self._batch))
            return
        now = time.monotonic()
        self._wait_until = {k: t for k, t in self._wait_until.items() if t > now}
        take, self._prev, pending = watch.ready(self.folder, self._seen, self._prev,
                                                set(self._wait_until))
        if take:
            self._batch = {str(p): watch.key(p.name, *self._prev[p.name]) for p in take}
            self._job = self.mw.shortcuts.queue_watch_import(take)
        elif pending:
            self._timer.start()      # something is still being written
        self._arm_retry()

    def job_done(self, res: dict) -> None:
        """The import job reported back: remember what it handled; the rest
        (failed, or not reached before a cancel) waits before it is tried again."""
        reported = [str(p) for k in ("imported", "rejected", "failed") for p in (res.get(k) or [])]
        if not any(p in self._batch for p in reported):
            return                   # a job from before the folder changed
        for path in list(res.get("imported") or []) + list(res.get("rejected") or []):
            key = self._batch.pop(str(path), None)
            if key is not None:
                self._seen[key] = None
                self._fails.pop(key, None)
        self._job = None
        self._backoff(list(self._batch.values()))
        self._batch = {}
        if self.folder is not None:
            watch.save_state(self._state_path, self.folder, self._seen)
            self._timer.start()      # the next batch
        self._arm_retry()

    def job_failed(self, paths) -> None:
        """The import job failed or was cancelled: its files wait, then are
        tried again."""
        keys = [self._batch[str(p)] for p in paths if str(p) in self._batch]
        if not keys:
            return                   # a job from before the folder changed
        self._job = None
        self._batch = {}
        self._backoff(keys)
        if self.folder is not None:
            self._timer.start()      # other files may be ready meanwhile
        self._arm_retry()

    def _backoff(self, keys) -> None:
        now = time.monotonic()
        for key in keys:
            n = self._fails.get(key, 0) + 1
            self._fails[key] = n
            self._wait_until[key] = now + min(RETRY_S * 2 ** (n - 1), MAX_RETRY_S)

    def _arm_retry(self) -> None:
        if self.folder is None or not self._wait_until:
            self._retry.stop()
            return
        wait = min(self._wait_until.values()) - time.monotonic()
        self._retry.start(max(1000, int(wait * 1000) + 1000))
