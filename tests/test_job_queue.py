# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for JobQueueController state transitions that don't need real worker
threads (v1.3.1 regression guards: a cancelled/failed job must not be
resurrected to DONE by the new per-step remove button)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu.jobs import Job, Lane, State, Step, new_id
from rosu.ui.job_queue import JobQueueController


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeTab:
    def __init__(self):
        self._threads = []


def _noop(ctx, progress, cancel):
    return None


def test_cancel_at_gate_marks_pending_and_cannot_be_resurrected(qapp):
    tab = _FakeTab()
    ctrl = JobQueueController(tab)
    job = Job(new_id(), "job_dedup", kind="dedup")
    job.steps = [Step("job_step_scan", Lane.DISK, _noop, state=State.DONE),
                 Step("job_step_remove", Lane.DISK, _noop, gated=True)]
    job.finalize = lambda ctx: {"removed": 0}
    ctrl.jobs.append(job)
    finished = []
    ctrl.job_finished.connect(finished.append)

    ctrl.cancel_job(job)                            # user declines at the dedup gate
    assert job.state == State.CANCELLED
    assert job.steps[1].state == State.CANCELLED    # no dangling PENDING step left

    ctrl.skip_step(job, job.steps[1])               # clicking a now-dead step's ×
    assert job.state == State.CANCELLED             # must NOT flip back to DONE
    assert finished == []                           # job_finished never fired


def test_finalize_done_guard_ignores_a_terminal_job(qapp):
    tab = _FakeTab()
    ctrl = JobQueueController(tab)
    job = Job(new_id(), "t")
    job.steps = [Step("a", Lane.DISK, _noop, state=State.CANCELLED)]
    job.state = State.CANCELLED
    job.finalize = lambda ctx: {"x": 1}
    finished = []
    ctrl.job_finished.connect(finished.append)
    ctrl._finalize_done(job)
    assert job.state == State.CANCELLED and finished == []


def test_skip_last_pending_step_completes_the_job(qapp):
    tab = _FakeTab()
    ctrl = JobQueueController(tab)
    job = Job(new_id(), "t", kind="x")
    job.steps = [Step("a", Lane.DISK, _noop, state=State.DONE),
                 Step("b", Lane.DISK, _noop)]        # pending + last
    job.finalize = lambda ctx: {"ok": True}
    finished = []
    ctrl.job_finished.connect(finished.append)
    ctrl.skip_step(job, job.steps[1])               # remove the only remaining step
    assert job.steps[1].state == State.SKIPPED
    assert job.state == State.DONE and finished == [job]
