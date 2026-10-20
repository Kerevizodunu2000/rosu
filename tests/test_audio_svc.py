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
            return None
        rnd = random.Random(data[0])
        return 90.0, [rnd.getrandbits(32) for _ in range(600)]
    monkeypatch.setattr(fingerprint, "compute", compute)
    monkeypatch.setattr(fingerprint, "fpcalc_path", lambda: fingerprint.Path("fpcalc"))


def test_fingerprints_are_cached_and_groups_found(env, monkeypatch):
    cfg, db, svc = env
    calls = []
    _fake_compute(monkeypatch, calls)
    a, _ = _set(cfg, db, 1, b"A-song", title="One")
    b, _ = _set(cfg, db, 2, b"A-song re-encoded", title="Two")      # same first byte
    _set(cfg, db, 3, b"B-song", title="Three")
    _set(cfg, db, 4, b"!unreadable", title="Four")
    res = svc.fingerprint_library()
    assert res == {"computed": 3, "cached": 0, "failed": 1, "cancelled": False}
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


def test_no_fpcalc_and_recycle_job_only_takes_library_files(env, monkeypatch, tmp_path):
    cfg, db, svc = env
    monkeypatch.setattr(fingerprint, "fpcalc_path", lambda: None)
    assert svc.fingerprint_library() == {"error": "no_fpcalc"}
    _set(cfg, db, 5, b"x")
    trash = []
    monkeypatch.setattr("send2trash.send2trash", lambda p: trash.append(p))
    from rosu import jobs
    job = svc.build_recycle_sets_job(["5 A - T.osz", "../evil.osz", "missing.osz", "5 A - T.osz"])
    assert job.ctx["options"] == {"sets": 1}
    assert jobs.run_job_sync(job)["removed"] == 1
    assert trash == [str(cfg.library_path / "5 A - T.osz")]


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
