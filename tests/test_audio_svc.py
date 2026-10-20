# SPDX-License-Identifier: GPL-3.0-or-later
"""Same song, different sets (v1.10): the fingerprint pipeline and its cache."""
import random
import shutil
import subprocess
import zipfile

import pytest

from rosu import config, fingerprint
from rosu.db import Database
from rosu.models import ParsedTrack
from rosu.services import Services


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    yield cfg, db, Services(cfg, db, DummyLog())
    db.close()


def _set(cfg, db, bid, audio: bytes, audio_name="audio.mp3", title="T"):
    fn = f"{bid} A - {title}.osz"
    with zipfile.ZipFile(cfg.library_path / fn, "w") as zf:
        zf.writestr(f"A - {title} [x].osu",
                    f"osu file format v14\n[General]\nAudioFilename: {audio_name}\n[Events]\n")
        zf.writestr(audio_name, audio)
    t = ParsedTrack(beatmapset_id=bid, filename=fn, artist="A", title=title, display_name=f"A - {title}")
    tid, _ = db.upsert_track(t, "when")
    db.set_library_state(tid, True, "present", "when")
    return tid, fn


def _fake_compute(monkeypatch, calls):
    """fpcalc stand-in: the "song" is the audio file's first byte, so files
    that start alike fingerprint alike."""
    def compute(audio, fpcalc, timeout=60):
        calls.append(audio.name)
        data = audio.read_bytes()
        if not data or data[:1] == b"!":
            return None                                   # fpcalc ran, audio unreadable
        if data[:1] == b"?":
            raise fingerprint.ToolError("timed out")      # says nothing about the set
        rnd = random.Random(data[0])
        return 90.0, [rnd.getrandbits(32) for _ in range(600)]
    monkeypatch.setattr(fingerprint, "compute", compute)
    monkeypatch.setattr(fingerprint, "fpcalc_path", lambda: fingerprint.Path("fpcalc"))
    monkeypatch.setattr(fingerprint, "probe", lambda fpcalc: True)


def test_fingerprints_are_cached_and_groups_found(env, monkeypatch):
    cfg, db, svc = env
    calls = []
    _fake_compute(monkeypatch, calls)
    a, _ = _set(cfg, db, 1, b"A-song", title="One")
    b, _ = _set(cfg, db, 2, b"A-song re-encoded", title="Two")      # same first byte
    _set(cfg, db, 3, b"B-song", title="Three")
    _set(cfg, db, 4, b"!unreadable", title="Four")
    res = svc.fingerprint_library()
    assert res == {"computed": 3, "cached": 0, "failed": 1, "retry": 0, "cancelled": False}
    report = svc.same_song_report()
    assert [[s["track_id"] for s in g] for g in report["groups"]] == [[a, b]]
    assert report["groups"][0][0]["filename"] == "1 A - One.osz"
    calls.clear()
    assert svc.fingerprint_library()["cached"] == 4 and calls == []   # nothing re-read
    (cfg.library_path / "3 A - Three.osz").unlink()
    _set(cfg, db, 3, b"A-song again", title="Three")                  # the file changed
    svc.fingerprint_library()
    assert len(calls) == 1
    assert [len(g) for g in svc.same_song_report()["groups"]] == [3]


def test_a_failed_attempt_is_not_remembered_but_unreadable_audio_is(env, monkeypatch):
    cfg, db, svc = env
    calls = []
    _fake_compute(monkeypatch, calls)
    _set(cfg, db, 21, b"?blocked", title="Busy")
    _set(cfg, db, 22, b"!broken", title="Broken")
    assert svc.fingerprint_library() == {"computed": 0, "cached": 0, "failed": 1, "retry": 1,
                                         "cancelled": False}
    calls.clear()
    res = svc.fingerprint_library()
    assert res["cached"] == 1 and res["retry"] == 1 and len(calls) == 1   # only the blocked one again


def test_fpcalc_that_does_not_run_is_reported_before_anything_is_cached(env, monkeypatch):
    cfg, db, svc = env
    monkeypatch.setattr(fingerprint, "fpcalc_path", lambda: fingerprint.Path("fpcalc"))
    monkeypatch.setattr(fingerprint, "probe", lambda fpcalc: False)
    _set(cfg, db, 23, b"A-song")
    assert svc.fingerprint_library() == {"error": "fpcalc_broken"}
    assert db.audio_fingerprint_stamps() == {}


def test_fingerprints_of_sets_no_longer_in_the_library_take_no_part(env, monkeypatch):
    cfg, db, svc = env
    _fake_compute(monkeypatch, [])
    a, _ = _set(cfg, db, 31, b"A-song", title="One")
    gone, _ = _set(cfg, db, 32, b"A-song too", title="Gone")
    svc.fingerprint_library()
    db.set_library_state(gone, False, "disappeared", "when")
    assert svc.same_song_report() == {"groups": [], "fingerprinted": 1}


def test_probe_and_compute_tell_tool_failures_apart(tmp_path):
    missing = tmp_path / "no-such-fpcalc"
    assert fingerprint.probe(missing) is False
    with pytest.raises(fingerprint.ToolError):
        fingerprint.compute(tmp_path / "a.mp3", missing)


def test_no_fpcalc_and_recycle_job_only_takes_library_files(env, monkeypatch, tmp_path):
    cfg, db, svc = env
    monkeypatch.setattr(fingerprint, "fpcalc_path", lambda: None)
    assert svc.fingerprint_library() == {"error": "no_fpcalc"}
    _set(cfg, db, 5, b"x")
    trash = []
    from rosu import jobs
    job = svc.build_recycle_sets_job(["5 A - T.osz", "../evil.osz", "missing.osz", "5 A - T.osz"])
    assert job.ctx["options"] == {"sets": 1}
    def recycle(p):
        trash.append(p)
        fingerprint.Path(p).unlink()
    monkeypatch.setattr("send2trash.send2trash", recycle)
    assert jobs.run_job_sync(job)["removed"] == 1
    assert trash == [str(cfg.library_path / "5 A - T.osz")]
    # The Library no longer has that set (it was its own entry, not a duplicate).
    row = db.find_track_row(5, "5 A - T.osz")
    assert row["in_library"] == 0 and row["library_status"] == "disappeared"


@pytest.mark.skipif(shutil.which("ffmpeg") is None or fingerprint.fpcalc_path() is None,
                    reason="needs ffmpeg and fpcalc (python tools/fetch_fpcalc.py)")
def test_real_fpcalc_matches_a_re_encode_and_tells_songs_apart(env, tmp_path):
    cfg, db, svc = env

    def tone(path, expr, extra=()):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"aevalsrc='{expr}':s=44100:d=40", *extra, str(path)], check=True)
        return path.read_bytes()
    song = "0.3*sin(2*PI*(220+110*floor(mod(t*2,8)))*t)+0.2*sin(2*PI*(330+55*floor(mod(t*3,5)))*t)"
    other = "0.3*sin(2*PI*(196+98*floor(mod(t*1.5,7)))*t)+0.2*sin(2*PI*(392+49*floor(mod(t*2.5,6)))*t)"
    a, _ = _set(cfg, db, 11, tone(tmp_path / "a.mp3", song, ["-b:a", "192k"]), title="Hi")
    b, _ = _set(cfg, db, 12, tone(tmp_path / "b.ogg", song, ["-c:a", "libvorbis", "-q:a", "2"]),
                audio_name="audio.ogg", title="Lo")
    _set(cfg, db, 13, tone(tmp_path / "c.mp3", other), title="Other")
    assert svc.fingerprint_library()["computed"] == 3
    assert [[s["track_id"] for s in g] for g in svc.same_song_report()["groups"]] == [[a, b]]


def test_a_cancelled_scan_stops_and_leaves_no_temp_files(env, monkeypatch, tmp_path):
    cfg, db, svc = env
    _fake_compute(monkeypatch, [])
    import tempfile
    work = tmp_path / "work"
    monkeypatch.setattr(tempfile, "mkdtemp", lambda prefix="": (work.mkdir(), str(work))[1])
    for i in range(3):
        _set(cfg, db, 40 + i, bytes([65 + i]) + b"-song", title=f"S{i}")
    res = svc.fingerprint_library(cancel=lambda: True)
    assert res["cancelled"] and res["computed"] == 0
    assert not work.exists()
