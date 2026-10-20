# SPDX-License-Identifier: GPL-3.0-or-later
"""QThread wrapper that runs a Services method off the UI thread.

Signals are named to avoid clashing with QThread's own ``finished`` signal.
The wrapped callable must accept a ``progress`` keyword (a callable taking a
single string) which is forwarded as the :attr:`progressed` signal.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal

# Every started Worker stays referenced here until its thread has ended. A
# dialog closed mid-scan drops its own reference; without this the QThread
# could be garbage-collected while still running, which aborts the process.
_live: set = set()


class Worker(QThread):
    progressed = Signal(object)   # str status or a structured dict
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.finished.connect(self._release)   # queued to the owning (UI) thread

    def start(self, *args) -> None:
        _live.add(self)
        super().start(*args)

    def _release(self) -> None:
        self.wait()   # finished is emitted just before the thread exits
        _live.discard(self)

    def run(self) -> None:
        try:
            result = self._fn(*self._args, progress=self.progressed.emit,
                             **self._kwargs)
            self.succeeded.emit(result)
        except Exception as exc:  # surface to the UI rather than crashing
            from . import crash_report
            crash_report.capture(exc)   # no-op unless the user opted in
            self.failed.emit(f"{type(exc).__name__}: {exc}")
