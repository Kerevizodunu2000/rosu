# SPDX-License-Identifier: GPL-3.0-or-later
"""Live job-queue scheduler for the Shortcuts tab (v1.3).

The controller lives on the UI thread and owns the ordered list of jobs. It runs
at most one step per lane (DISK / DRIVE) at a time — lanes overlap, so a disk
operation runs *while* a Drive upload runs. Each step runs on its own
:class:`~rosu.workers.Worker` (a QThread); the step only computes and emits
signals, while all model mutation happens back on the UI thread via queued
signal connections. Cancellation is per-job (each :class:`~rosu.jobs.Job` has its
own ``threading.Event``), so cancelling one job never disturbs another.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..jobs import Lane, State, select_next
from ..workers import Worker

_JOB_TERMINAL = (State.DONE, State.FAILED, State.CANCELLED)


class JobQueueController(QObject):
    changed = Signal()            # the model changed → the tab re-renders the list
    job_finished = Signal(object)  # a job reached DONE → route its result to a presenter
    gate_needed = Signal(object)   # a job is waiting for a UI confirmation (dedup)

    def __init__(self, tab):
        super().__init__()
        self.tab = tab
        self.jobs: list = []
        self._workers: dict = {Lane.DISK: None, Lane.DRIVE: None}
        self._running: dict = {Lane.DISK: None, Lane.DRIVE: None}  # (job, step)

    # -- public API ------------------------------------------------------------
    def enqueue(self, job) -> None:
        self.jobs.append(job)
        self.changed.emit()
        self._pump()

    def cancel_job(self, job) -> None:
        """Cancel one job. A running step observes the token and returns
        cooperatively (then :meth:`_on_done` marks it CANCELLED); a job that is
        only queued or waiting at a gate is cancelled immediately. The rest of
        the queue keeps going."""
        job.cancel()
        if not self._is_actively_running(job):
            if job.state not in _JOB_TERMINAL:
                self._mark_pending_cancelled(job)  # no dangling steps left runnable
                job.state = State.CANCELLED
                job.cleanup()
        self.changed.emit()
        self._pump()

    @staticmethod
    def _mark_pending_cancelled(job) -> None:
        """Mark every not-yet-run step of a terminating job CANCELLED, so no live
        skip/cancel button (which keys off step state) can later resurrect it."""
        for s in job.steps:
            if s.state in (State.PENDING, State.RUNNING):
                s.state = State.CANCELLED

    def skip_step(self, job, step) -> None:
        """Remove ONE step from a job (per-step ✕) — the job keeps going with the
        rest. A pending step is marked SKIPPED so the scheduler passes it; a
        running step is stopped cooperatively (then :meth:`_on_done` marks it
        SKIPPED and advances). The job's own cancel token is untouched, so other
        steps are unaffected."""
        if job.state in _JOB_TERMINAL:            # job already finished — ignore
            return
        if step.state == State.PENDING:
            step.state = State.SKIPPED
            if job.current_step() is None:        # was the last thing left to do
                self._finalize_done(job)
        elif step.state == State.RUNNING:
            step.skip_event.set()
        self.changed.emit()
        self._pump()

    def confirm_gate(self, job) -> None:
        """User approved a gated step (dedup remove) — un-gate it and schedule."""
        step = job.current_step()
        if step is not None and step.gated:
            step.gated = False
        self.changed.emit()
        self._pump()

    def skip_gate(self, job) -> None:
        """Skip a gated step (e.g. dedup found nothing / user declined but the job
        should complete cleanly rather than read as an error)."""
        step = job.current_step()
        if step is not None and step.gated:
            step.state = State.SKIPPED
        nxt = job.current_step()
        if nxt is None:
            self._finalize_done(job)
        self.changed.emit()
        self._pump()

    def clear_finished(self) -> None:
        self.jobs = [j for j in self.jobs
                     if j.state not in (State.DONE, State.FAILED, State.CANCELLED)]
        self.changed.emit()

    def has_active(self) -> bool:
        return any(w is not None for w in self._workers.values())

    def cancel_all(self) -> None:
        """App is closing: trip every job's OWN cancel token so running steps stop
        cooperatively (they poll their own token, so ``services.request_cancel`` —
        which only sets the shared Events — does not reach them)."""
        for job in self.jobs:
            job.cancel()

    def cleanup_all(self) -> None:
        """Run every job's cleanup — including jobs that never started (their temp
        stage dir is created at build time), so nothing is left in %TEMP%."""
        for job in self.jobs:
            job.cleanup()

    # -- scheduling ------------------------------------------------------------
    def _busy_lanes(self) -> set:
        return {lane for lane, w in self._workers.items() if w is not None}

    def _is_actively_running(self, job) -> bool:
        return any(rj is job for rj in
                   (v[0] for v in self._running.values() if v is not None))

    def _pump(self) -> None:
        for lane, job, step in select_next(self.jobs, self._busy_lanes()):
            self._start(lane, job, step)

    def _start(self, lane, job, step) -> None:
        job.state = State.RUNNING
        step.state = State.RUNNING
        # The step stops on EITHER a whole-job cancel or this one step being
        # individually skipped (per-step ✕).
        def cancel():
            return job.cancel_cb() or step.skip_event.is_set()

        def work(progress=None):
            return step.run(job.ctx, progress, cancel)

        w = Worker(work)
        self._workers[lane] = w
        self._running[lane] = (job, step)
        self.tab._threads.append(w)   # keep the app-close quit-guard aware of it
        w.progressed.connect(lambda m, s=step: self._on_progress(s, m))
        w.succeeded.connect(lambda _r, l=lane, j=job, s=step: self._on_done(l, j, s))
        w.failed.connect(lambda e, l=lane, j=job, s=step: self._on_failed(l, j, s, e))
        w.finished.connect(lambda ww=w: self._drop_worker(ww))
        w.start()
        self.changed.emit()

    def _drop_worker(self, w) -> None:
        if w in self.tab._threads:
            self.tab._threads.remove(w)

    def _free_lane(self, lane) -> None:
        self._workers[lane] = None
        self._running[lane] = None

    # -- worker callbacks (UI thread) -----------------------------------------
    def _on_progress(self, step, msg) -> None:
        if isinstance(msg, dict) and "total" in msg:
            step.total = msg.get("total", 0) or 0
            step.done = msg.get("done", msg.get("batch", 0)) or 0
            self.changed.emit()

    def _on_done(self, lane, job, step) -> None:
        self._free_lane(lane)
        # (1) This one step was individually skipped (per-step ✕) — mark it and
        #     let the job carry on with its remaining steps.
        if step.skip_event.is_set() and not job.cancel_cb():
            step.state = State.SKIPPED
            nxt = job.current_step()
            self.changed.emit()
            self._pump()
            if nxt is None:
                self._finalize_done(job)
            elif nxt.gated:
                self.gate_needed.emit(job)
            return
        step.state = State.DONE
        if step.total:
            step.done = step.total
        nxt = job.current_step()
        # (2) Whole-job cancel with steps still to run → CANCELLED (skip the rest).
        #     But if this was the LAST step and it finished, the cancel came too
        #     late — the work IS done, so don't mislabel it "cancelled" (e.g. a
        #     Drive upload that completed just as Cancel was clicked).
        if job.cancel_cb() and nxt is not None:
            for s in job.steps:
                if s.state == State.PENDING:
                    s.state = State.CANCELLED
            job.state = State.CANCELLED
            job.cleanup()
            self.changed.emit()
            self._pump()
            return
        self.changed.emit()
        # Put any freed lane back to work BEFORE we (possibly) pop a modal dialog.
        self._pump()
        if nxt is None:
            self._finalize_done(job)       # DONE → result presenter (may be modal)
        elif nxt.gated:
            self.gate_needed.emit(job)     # waiting for the dedup confirm (modal)

    def _on_failed(self, lane, job, step, err) -> None:
        self._free_lane(lane)
        # A step that raises while its job was cancelled is a cancellation, not a
        # failure — keep the promise that a cancelled job reads as CANCELLED.
        if job.cancel_cb():
            step.state = State.CANCELLED
            job.state = State.CANCELLED
        else:
            step.state = State.FAILED
            job.state = State.FAILED
            job.error = err
        self._mark_pending_cancelled(job)   # no later step left runnable on a dead job
        job.cleanup()
        self.changed.emit()
        self._pump()

    def _finalize_done(self, job) -> None:
        if job.state in _JOB_TERMINAL:       # already cancelled/failed — never resurrect
            return
        job.state = State.DONE
        if job.finalize is not None:
            try:
                job.result = job.finalize(job.ctx)
            except Exception as exc:   # a bad finalize must not wedge the queue
                job.error = f"{type(exc).__name__}: {exc}"
                job.state = State.FAILED
        job.cleanup()
        self.changed.emit()
        if job.state == State.DONE:
            self.job_finished.emit(job)
