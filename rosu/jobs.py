# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure job-queue model for the Shortcuts tab (v1.3) — no Qt, unit-tested.

A :class:`Job` is an ordered list of :class:`Step`s; each step declares a
:class:`Lane` (DISK or DRIVE). The live scheduler (``rosu/ui/job_queue.py``)
runs at most one step per lane at a time, so lanes overlap — a disk operation
runs *while* a Drive upload runs. This module owns only the data model, the
synchronous runner (used by tests + any non-UI caller), and the pure
lane-scheduling decision ``select_next`` — none of which touch Qt or threads
beyond a cooperative ``cancel_event``.

Each step is ``run(ctx, progress, cancel)``:
  * ``ctx``      a per-job dict the steps read/write to pass data along,
  * ``progress`` the usual ``progress`` callback (structured dicts / strings),
  * ``cancel``   a zero-arg callable returning ``True`` when the job is cancelled.
The step mutates ``ctx``; a job's ``finalize(ctx)`` assembles the result dict.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class Lane(str, Enum):
    DISK = "disk"    # local disk / osu! import — serial (osu!.exe, Library writes)
    DRIVE = "drive"  # Google Drive upload/share — overlaps the disk lane


class State(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


TERMINAL = (State.DONE, State.FAILED, State.CANCELLED, State.SKIPPED)

# Step callable: run(ctx, progress, cancel) -> Any (may mutate ctx).
StepFn = Callable[[dict, Optional[Callable], Callable[[], bool]], Any]


@dataclass
class Step:
    key: str            # i18n key for the step's label
    lane: Lane
    run: StepFn
    gated: bool = False  # True → the scheduler waits for a UI confirm before running
    label_kwargs: dict = field(default_factory=dict)  # kwargs for the i18n label
    skip_event: threading.Event = field(default_factory=threading.Event)  # per-step cancel
    state: State = State.PENDING
    done: int = 0        # progress counters for the active step (from progress dicts)
    total: int = 0


@dataclass
class Job:
    id: int
    title_key: str
    title_kwargs: dict = field(default_factory=dict)
    kind: str = ""                       # routes the result to a UI presenter
    tooltip: str = ""                    # extra detail shown on the queue row (e.g. dest path)
    steps: list = field(default_factory=list)
    ctx: dict = field(default_factory=dict)
    finalize: Optional[Callable[[dict], dict]] = None
    on_cleanup: list = field(default_factory=list)   # e.g. remove a temp dir
    cancel_event: threading.Event = field(default_factory=threading.Event)
    state: State = State.PENDING
    result: Optional[dict] = None
    error: Optional[str] = None

    @property
    def cancel_cb(self) -> Callable[[], bool]:
        return self.cancel_event.is_set

    def cancel(self) -> None:
        self.cancel_event.set()

    def current_step(self) -> Optional[Step]:
        """The first step that has not reached a terminal state (the one that is
        running or up next)."""
        for s in self.steps:
            if s.state not in TERMINAL:
                return s
        return None

    def cleanup(self) -> None:
        """Run (once) any registered cleanup callbacks — safe to call repeatedly."""
        fns, self.on_cleanup = self.on_cleanup, []
        for fn in fns:
            try:
                fn()
            except Exception:   # cleanup is best-effort (temp dirs, etc.)
                pass


_counter = [0]


def new_id() -> int:
    """Monotonic job id. (Not thread-safe by design — jobs are created on the UI
    thread; ``Math.random``/time-based ids are avoided so behaviour is
    deterministic in tests.)"""
    _counter[0] += 1
    return _counter[0]


def run_job_sync(job: Job, progress=None, cancel=None) -> dict:
    """Run every step in order on the CALLING thread — used by tests and any
    synchronous (non-UI) caller. Stops early if ``cancel`` (or the job's own
    token) trips; a raising step is marked FAILED and the exception re-raises.
    ``gated`` is ignored here (gating is purely a UI-scheduler concern). Returns
    ``job.finalize(ctx)`` (or a copy of ``ctx``). Cleanup always runs."""
    check = cancel if cancel is not None else job.cancel_cb
    try:
        for step in job.steps:
            if check():
                step.state = State.CANCELLED
                continue
            step.state = State.RUNNING
            try:
                step.run(job.ctx, progress, check)
            except Exception:
                step.state = State.FAILED
                job.state = State.FAILED
                raise
            step.state = State.DONE
        job.state = State.CANCELLED if check() else State.DONE
        job.result = job.finalize(job.ctx) if job.finalize else dict(job.ctx)
        return job.result
    finally:
        job.cleanup()


def select_next(jobs, busy_lanes) -> list:
    """Pure scheduler decision: given the current jobs and the lanes already
    busy, return a list of ``(lane, job, step)`` tuples to start now — at most
    one per free lane, earliest job first, skipping gated/awaiting-confirm steps.

    A job whose current step is on the OTHER lane leaves this lane free for a
    later job (that's what lets a queued disk job run while an export's upload
    step holds the DRIVE lane). No side effects."""
    picks: list = []
    claimed = set(busy_lanes)
    for lane in (Lane.DISK, Lane.DRIVE):
        if lane in claimed:
            continue
        for job in jobs:
            if job.state in (State.DONE, State.FAILED, State.CANCELLED):
                continue
            step = job.current_step()
            if step is None or step.state == State.RUNNING or step.gated:
                continue
            if step.lane != lane:
                continue
            picks.append((lane, job, step))
            claimed.add(lane)
            break
    return picks
