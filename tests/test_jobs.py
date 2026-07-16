# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the pure job-queue model (rosu/jobs.py): run_job_sync +
the lane-scheduling decision select_next."""
import pytest

from rosu.jobs import Job, Lane, State, new_id, run_job_sync, select_next


def _step(key, lane, fn, gated=False):
    from rosu.jobs import Step
    return Step(key, lane, fn, gated=gated)


# -- run_job_sync ------------------------------------------------------------
def test_run_job_sync_runs_in_order_threads_ctx_and_finalizes():
    order = []
    job = Job(new_id(), "t")
    job.steps = [
        _step("a", Lane.DISK, lambda ctx, p, c: (order.append("a"), ctx.update(x=1))),
        _step("b", Lane.DISK, lambda ctx, p, c: (order.append("b"),
                                                 ctx.update(y=ctx["x"] + 1))),
    ]
    job.finalize = lambda ctx: {"x": ctx["x"], "y": ctx["y"]}
    res = run_job_sync(job)
    assert order == ["a", "b"]
    assert res == {"x": 1, "y": 2}
    assert [s.state for s in job.steps] == [State.DONE, State.DONE]
    assert job.state == State.DONE


def test_run_job_sync_stops_after_cancel():
    ran = []
    job = Job(new_id(), "t")

    def step2(ctx, p, c):
        ran.append("2")
        job.cancel()          # user cancels mid-job

    job.steps = [
        _step("1", Lane.DISK, lambda ctx, p, c: ran.append("1")),
        _step("2", Lane.DISK, step2),
        _step("3", Lane.DISK, lambda ctx, p, c: ran.append("3")),  # must NOT run
    ]
    run_job_sync(job)
    assert ran == ["1", "2"]                       # step 3 skipped
    assert [s.state for s in job.steps] == [State.DONE, State.DONE, State.CANCELLED]
    assert job.state == State.CANCELLED


def test_run_job_sync_marks_failed_and_reraises():
    job = Job(new_id(), "t")

    def boom(ctx, p, c):
        raise ValueError("nope")

    job.steps = [_step("a", Lane.DISK, lambda ctx, p, c: None),
                 _step("b", Lane.DISK, boom),
                 _step("c", Lane.DISK, lambda ctx, p, c: None)]
    with pytest.raises(ValueError):
        run_job_sync(job)
    assert [s.state for s in job.steps] == [State.DONE, State.FAILED, State.PENDING]
    assert job.state == State.FAILED


def test_run_job_sync_runs_cleanup():
    cleaned = []
    job = Job(new_id(), "t")
    job.on_cleanup.append(lambda: cleaned.append(True))
    job.steps = [_step("a", Lane.DISK, lambda ctx, p, c: None)]
    run_job_sync(job)
    assert cleaned == [True]
    # cleanup only runs once even if called again
    job.cleanup()
    assert cleaned == [True]


# -- select_next -------------------------------------------------------------
def _pending_job(title, *lanes):
    job = Job(new_id(), title)
    job.steps = [_step(f"{title}{i}", lane, lambda ctx, p, c: None)
                 for i, lane in enumerate(lanes)]
    return job


def test_select_next_picks_earliest_disk_job():
    a = _pending_job("a", Lane.DISK)
    b = _pending_job("b", Lane.DISK)
    picks = select_next([a, b], set())
    # both lanes free, but only the DISK lane has ready work → one pick, job a
    assert [(lane, job) for lane, job, _ in picks] == [(Lane.DISK, a)]


def test_select_next_disk_busy_picks_nothing_on_disk():
    a = _pending_job("a", Lane.DISK)
    assert select_next([a], {Lane.DISK}) == []


def test_select_next_overlap_disk_and_drive():
    """The core concurrency invariant: an export job whose CURRENT step is on the
    DRIVE lane leaves the DISK lane free for the next queued disk job."""
    export = _pending_job("exp", Lane.DISK, Lane.DISK, Lane.DRIVE)
    export.steps[0].state = State.DONE      # gather done
    export.steps[1].state = State.DONE      # archive done → current step is upload (DRIVE)
    disk = _pending_job("unpack", Lane.DISK)
    picks = select_next([export, disk], set())
    got = {(lane, job.title_key) for lane, job, _ in picks}
    assert got == {(Lane.DRIVE, "exp"), (Lane.DISK, "unpack")}


def test_select_next_skips_gated_step():
    dedup = Job(new_id(), "dedup")
    dedup.steps = [_step("scan", Lane.DISK, lambda ctx, p, c: None),
                   _step("remove", Lane.DISK, lambda ctx, p, c: None, gated=True)]
    dedup.steps[0].state = State.DONE       # scan done, remove is gated
    assert select_next([dedup], set()) == []   # gated → not scheduled


def test_select_next_ignores_terminal_jobs():
    a = _pending_job("a", Lane.DISK)
    a.state = State.DONE
    b = _pending_job("b", Lane.DISK)
    picks = select_next([a, b], set())
    assert [job for _l, job, _s in picks] == [b]


def test_current_step_returns_first_non_terminal():
    j = _pending_job("j", Lane.DISK, Lane.DISK)
    j.steps[0].state = State.DONE
    assert j.current_step() is j.steps[1]
    j.steps[1].state = State.DONE
    assert j.current_step() is None


def test_skipped_step_is_passed_over():
    # v1.3.1 per-step cancel: a SKIPPED step is terminal, so current_step and the
    # scheduler move past it to the next real step.
    j = _pending_job("j", Lane.DISK, Lane.DISK, Lane.DISK)
    j.steps[1].state = State.SKIPPED           # middle step removed by the user
    assert j.current_step() is j.steps[0]
    j.steps[0].state = State.DONE
    assert j.current_step() is j.steps[2]      # skips the removed one
    picks = select_next([j], set())
    assert [(lane, step) for lane, _job, step in picks] == [(Lane.DISK, j.steps[2])]
