"""QThread wrapper that runs a Services method off the UI thread.

Signals are named to avoid clashing with QThread's own ``finished`` signal.
The wrapped callable must accept a ``progress`` keyword (a callable taking a
single string) which is forwarded as the :attr:`progressed` signal.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    progressed = Signal(object)   # str status or a structured dict
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, progress=self.progressed.emit,
                             **self._kwargs)
            self.succeeded.emit(result)
        except Exception as exc:  # surface to the UI rather than crashing
            self.failed.emit(f"{type(exc).__name__}: {exc}")
