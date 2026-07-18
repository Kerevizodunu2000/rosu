# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the v1.3 job builders on Services: they must decompose each shortcut
op into the right lane-tagged sub-steps and, when run, produce the same result
shape as the v1.2 monolithic methods (parity)."""
from pathlib import Path

from rosu import client_import, config
from rosu.db import Database
from rosu.jobs import Lane, State, run_job_sync
from rosu.services import Services


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def _svc(tmp_path):
    cfg = config.Config(root=str(tmp_path))
    cfg = config._fill_defaults(cfg)
    cfg.stable_enabled = True   # tests here exercise both clients (v1.4: stable off by default)
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    return cfg, db, Services(cfg, db, DummyLog())


class _Plan:
    def __init__(self, kind, zip_path):
        self.kind = kind
        self.zip_path = zip_path
        self.parsed = object()


def _step_keys(job):
    return [s.key for s in job.steps]


def _lanes(job):
    return [s.lane for s in job.steps]


# -- unpack ------------------------------------------------------------------
def test_build_unpack_job_steps_and_result(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    cfg.stable_enabled = True   # exercise both send steps (v1.4: stable off by default)
    monkeypatch.setattr(svc, "prescan_all", lambda progress=None: [
        _Plan("new", "a.zip"), _Plan("all_present", "b.zip"), _Plan("new", "c.zip")])
    got = {}

    def fake_extract(approved, progress=None, cancel=None):
        got["approved"] = approved
        return {"packs": len(approved), "tracks": 5}

    monkeypatch.setattr(svc, "extract", fake_extract)
    monkeypatch.setattr(svc, "has_loose_osz", lambda: False)
    dispatched = []
    monkeypatch.setattr(
        svc, "_dispatch_to_client",
        lambda target, files, progress=None, cancel=None:
        (dispatched.append(target), {"sent": 0})[1])

    job = svc.build_unpack_job(["lazer", "stable"])
    assert _step_keys(job) == ["job_step_prescan", "job_step_extract",
                               "job_step_send_lazer", "job_step_send_stable"]
    assert all(lane is Lane.DISK for lane in _lanes(job))
    res = run_job_sync(job)
    assert [Path(p).name for p, _ in got["approved"]] == ["a.zip", "c.zip"]
    assert dispatched == ["lazer", "stable"]
    assert res["extract"]["packs"] == 2
    assert "lazer" in res["imports"] and "stable" in res["imports"]
    assert job.state == State.DONE
    db.close()


def test_build_unpack_job_skips_target_duplicates(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    monkeypatch.setattr(svc, "prescan_all", lambda progress=None: [])
    monkeypatch.setattr(svc, "has_loose_osz", lambda: False)
    (cfg.output_path / "10 A - B.osz").write_bytes(b"x")
    (cfg.output_path / "20 C - D.osz").write_bytes(b"y")
    db._conn.execute(
        "INSERT INTO tracks(beatmapset_id, in_osu, in_osu_lazer) VALUES(20,1,1)")
    db._conn.commit()
    sent = {}
    monkeypatch.setattr(
        svc, "_dispatch_to_client",
        lambda target, files, progress=None, cancel=None: sent.update(
            {target: sorted(Path(f).name for f in files)}) or {"sent": len(files)})
    res = run_job_sync(svc.build_unpack_job(["lazer"], skip_duplicates=True))
    assert sent["lazer"] == ["10 A - B.osz"]              # set 20 already in lazer
    assert res["imports"]["lazer"]["skipped"] == 1
    db.close()


# -- save --------------------------------------------------------------------
def test_build_save_job(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    calls = []
    monkeypatch.setattr(
        svc, "import_from_stable",
        lambda progress=None, cancel=None: (calls.append("stable"), {"new": 1})[1])
    monkeypatch.setattr(
        svc, "import_from_lazer",
        lambda progress=None, cancel=None: (calls.append("lazer"), {"new": 2})[1])
    job = svc.build_save_job(["lazer"])
    assert _step_keys(job) == ["job_step_save_lazer"]
    out = run_job_sync(job)
    assert calls == ["lazer"] and out["lazer"] == {"new": 2}
    db.close()


# -- transfer ----------------------------------------------------------------
def test_build_transfer_job_end_to_end(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    songs = tmp_path / "Songs"
    songs.mkdir()
    for bid in (11, 22):
        d = songs / f"{bid} A - B"
        d.mkdir()
        (d / "x.osu").write_text("o")
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    dispatched = {}

    def fake_dispatch(target, files, progress=None, cancel=None):
        dispatched["target"] = target
        dispatched["files"] = sorted(Path(f).name for f in files)
        return {"sent": len(files), "cancelled": False}

    monkeypatch.setattr(svc, "_dispatch_to_client", fake_dispatch)
    job = svc.build_transfer_job("stable", "lazer")
    assert _step_keys(job) == ["job_step_enumerate", "job_step_export_client",
                               "job_step_send"]
    res = run_job_sync(job)
    assert dispatched["target"] == "lazer"
    assert dispatched["files"] == ["11 A - B.osz", "22 A - B.osz"]
    assert res["found"] == 2 and res["transferred"] == 2 and res["skipped"] == 0
    db.close()


# -- export ------------------------------------------------------------------
def test_build_export_job_library(tmp_path):
    import zipfile
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "1 A - B.osz").write_bytes(b"a" * 10)
    (cfg.library_path / "2 C - D.osz").write_bytes(b"b" * 10)
    job = svc.build_export_job("library", tmp_path / "out" / "E", fmt="zip")
    assert _step_keys(job) == ["job_step_gather", "job_step_archive"]  # no upload step
    res = run_job_sync(job)
    assert res["count"] == 2 and len(res["archives"]) == 1
    with zipfile.ZipFile(res["archives"][0]) as z:
        assert set(z.namelist()) == {"1 A - B.osz", "2 C - D.osz"}
    assert "drive" not in res
    db.close()


def test_build_export_job_upload_step_on_drive_lane(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    job = svc.build_export_job("library", tmp_path / "out" / "E", fmt="zip",
                               upload=True, share=True)
    assert _step_keys(job) == ["job_step_gather", "job_step_archive",
                               "job_step_upload"]
    assert _lanes(job) == [Lane.DISK, Lane.DISK, Lane.DRIVE]   # upload overlaps disk
    db.close()


def test_build_export_job_upload_failure_fails_the_step(tmp_path, monkeypatch):
    """A failed Drive upload must FAIL the upload step (and the job) — it used
    to swallow the error dict and render a ✓ tick while the upload had failed."""
    import pytest
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "1 A - B.osz").write_bytes(b"a" * 10)
    monkeypatch.setattr(svc, "_upload_export_to_drive",
                        lambda *a, **k: {"error": "drive", "detail": "boom"})
    job = svc.build_export_job("library", tmp_path / "out" / "E", fmt="zip",
                               upload=True)
    with pytest.raises(RuntimeError, match="boom"):
        run_job_sync(job)
    assert job.state == State.FAILED
    assert job.steps[-1].state == State.FAILED          # the upload step
    assert job.ctx["drive"]["error"] == "drive"         # detail kept for the UI
    assert job.ctx["written"]                            # archives are on disk
    db.close()


def test_build_export_job_count_zero_when_nothing_written(tmp_path):
    """Parity with export_sets: count reflects sets actually archived, so a job
    cancelled between gather and archive reports count 0 (not the gathered count)."""
    cfg, db, svc = _svc(tmp_path)
    job = svc.build_export_job("library", tmp_path / "out" / "E", fmt="zip")
    job.ctx["files"] = [Path("1 A - B.osz"), Path("2 C - D.osz")]
    assert job.finalize(job.ctx)["count"] == 0        # write never happened
    job.ctx["written"] = [Path("E.zip")]
    assert job.finalize(job.ctx)["count"] == 2        # archived → counted
    db.close()


def test_build_export_job_random_limit(tmp_path):
    import zipfile
    cfg, db, svc = _svc(tmp_path)
    for i in range(5):
        (cfg.library_path / f"{i} A - B.osz").write_bytes(b"x" * 10)
    res = run_job_sync(svc.build_export_job("library", tmp_path / "out" / "R",
                                            fmt="zip", limit=2))
    assert res["count"] == 2
    with zipfile.ZipFile(res["archives"][0]) as z:
        assert len(z.namelist()) == 2                    # exactly the sample
    db.close()


# -- dedup -------------------------------------------------------------------
def test_build_dedup_job_gated_then_removes(tmp_path, monkeypatch):
    trashed = []

    def fake_trash(p):
        trashed.append(p)
        Path(p).unlink()

    monkeypatch.setattr("send2trash.send2trash", fake_trash)
    cfg, db, svc = _svc(tmp_path)
    (cfg.library_path / "123 A - B.osz").write_bytes(b"x" * 100)
    (cfg.library_path / "123 A - B (1).osz").write_bytes(b"y" * 40)   # dup copy
    db._conn.execute(
        "INSERT INTO tracks(beatmapset_id, filename, in_library, library_status) "
        "VALUES(123,'123 A - B.osz',1,'present')")
    db._conn.commit()
    job = svc.build_dedup_job()
    assert _step_keys(job) == ["job_step_scan", "job_step_remove"]
    assert job.steps[1].gated is True                    # remove waits for confirm
    # run_job_sync ignores gating (that's a UI-scheduler concern) → scan + remove
    res = run_job_sync(job)
    assert job.ctx["plan"]["count"] == 1
    assert res["removed"] == 1 and res["freed_bytes"] == 40
    assert not (cfg.library_path / "123 A - B (1).osz").exists()
    db.close()


# -- per-client enable/disable (v1.4) ----------------------------------------
def test_dispatch_disabled_client_returns_disabled(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    cfg.stable_enabled = False
    res = svc._dispatch_to_client("stable", [Path("1 A - B.osz")])
    assert res.get("disabled") is True and res["sent"] == 0
    db.close()


def test_build_unpack_job_skips_disabled_target(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    cfg.stable_enabled = False        # lazer on (default), stable off
    job = svc.build_unpack_job(["lazer", "stable"])
    assert _step_keys(job) == ["job_step_prescan", "job_step_extract",
                               "job_step_send_lazer"]   # no stable send step
    db.close()


def test_build_save_job_skips_disabled_source(tmp_path):
    cfg, db, svc = _svc(tmp_path)
    cfg.stable_enabled = False
    job = svc.build_save_job(["lazer", "stable"])
    assert _step_keys(job) == ["job_step_save_lazer"]
    db.close()


def test_installed_summary_reports_enabled(tmp_path, monkeypatch):
    cfg, db, svc = _svc(tmp_path)
    cfg.lazer_enabled = True
    cfg.stable_enabled = False
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: None)
    monkeypatch.setattr(client_import, "lazer_data_dir", lambda: None)
    s = svc.installed_summary()
    assert s["lazer"]["enabled"] is True
    assert s["stable"]["enabled"] is False
    db.close()
