# SPDX-License-Identifier: GPL-3.0-or-later
"""Save and Remove proves every file of a set, not only the .osu (issue #16)."""
import zipfile

import pytest

from rosu import client_import, client_remove, config
from rosu.client_remove import covers, folder_fingerprint, osz_fingerprint
from rosu.db import Database
from rosu.models import ParsedTrack
from rosu.services import Services

OSU = "osu file format v14\n[General]\nAudioFilename: audio.mp3\n[Metadata]\nBeatmapSetID:{bid}\n"


class DummyLog:
    def __init__(self):
        self.lines = []

    def info(self, *a, **k):
        self.lines.append(("info", a, k))

    def error(self, *a, **k):
        self.lines.append(("error", a, k))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    cfg.stable_enabled = True
    db = Database(cfg.db_path)
    svc = Services(cfg, db, DummyLog())
    songs = tmp_path / "Songs"
    songs.mkdir()
    monkeypatch.setattr(client_import, "stable_songs_dir", lambda: songs)
    monkeypatch.setattr(client_remove, "osu_process_paths", lambda: [])
    trash = tmp_path / "trash"
    trash.mkdir()

    def fake_send2trash(path):
        import shutil
        from pathlib import Path
        shutil.move(str(path), str(trash / Path(path).name))
    monkeypatch.setattr("send2trash.send2trash", fake_send2trash)
    yield cfg, db, svc, songs, trash
    db.close()


def _folder(base, bid=1, video=True):
    d = base / f"{bid} A - B"
    d.mkdir(parents=True)
    (d / "map.osu").write_text(OSU.format(bid=bid))
    (d / "audio.mp3").write_bytes(b"a" * 1000)
    (d / "bg.jpg").write_bytes(b"b" * 500)
    if video:
        (d / "video.mp4").write_bytes(b"v" * 3000)
    return d


def _zip(path, folder, skip=(), replace=None):
    with zipfile.ZipFile(path, "w") as z:
        for p in sorted(folder.iterdir()):
            if p.name in skip:
                continue
            z.writestr(p.name, (replace or {}).get(p.name, p.read_bytes()))
    return path


def test_every_file_must_match(tmp_path):
    folder = _folder(tmp_path / "Songs")
    want = folder_fingerprint(folder, every_file=True)
    assert set(want) == {"map.osu", "audio.mp3", "bg.jpg", "video.mp4"}
    for skip in ("audio.mp3", "bg.jpg", "video.mp4"):
        x = _zip(tmp_path / f"no-{skip}.osz", folder, skip=(skip,))
        assert not covers(osz_fingerprint(x, every_file=True), want), skip
    x = _zip(tmp_path / "other-audio.osz", folder, replace={"audio.mp3": b"c" * 1000})
    assert not covers(osz_fingerprint(x, every_file=True), want)
    full = client_import.zip_folder_to_osz(folder, tmp_path / "full.osz")
    assert covers(osz_fingerprint(full, every_file=True), want)


def test_no_osu_never_covers_and_corrupt_member_proves_nothing(tmp_path):
    assert not covers({"audio.mp3": (1, 2)}, {"audio.mp3": (1, 2)})
    x = tmp_path / "bad.osz"
    with zipfile.ZipFile(x, "w") as z:      # stored, so the bytes are easy to find
        z.writestr("map.osu", "osu file format v14\n")
        z.writestr("audio.mp3", b"a" * 1000)
    data = bytearray(x.read_bytes())
    i = data.index(b"a" * 1000)
    data[i] = ord("z")                      # the stored CRC no longer matches
    x.write_bytes(bytes(data))
    assert osz_fingerprint(x) is not None   # .osu-only read never touches it
    assert osz_fingerprint(x, every_file=True) is None


def test_save_first_is_not_auto_pruned(env):
    cfg, db, svc, songs, trash = env
    cfg.auto_prune = True
    cfg.prune_mode = "video_only"
    folder = _folder(songs, bid=505)
    res = svc.remove_from_client("stable", [folder.name], save_first=True)
    assert res["removed"] == 1, res
    assert (trash / folder.name).exists()
    lib = cfg.library_path / "505 A - B.osz"
    with zipfile.ZipFile(lib) as z:
        assert "video.mp4" in z.namelist()


def test_incomplete_library_copy_keeps_the_set(env):
    cfg, db, svc, songs, trash = env
    folder = _folder(songs, bid=606, video=False)
    name = svc._stable_save_name(folder, 606)
    _zip(cfg.library_path / name, folder, skip=("audio.mp3",))
    t = ParsedTrack(beatmapset_id=606, filename=name, artist="A", title="B", display_name="A - B")
    tid, _ = db.upsert_track(t, "when")
    db.set_library_state(tid, True, "present", "when")
    res = svc.remove_from_client("stable", [folder.name], save_first=True)
    assert res["removed"] == 0 and res["kept"] == [folder.name], res
    assert folder.is_dir()
