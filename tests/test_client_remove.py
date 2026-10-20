# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure helpers behind "Remove from osu!" (v1.8, HANDOFF 4.1)."""
import os

import pytest

from rosu import client_remove


def _folder(root, name, files=None):
    d = root / name
    d.mkdir(parents=True)
    for fn, data in (files or {"a.osu": b"x"}).items():
        (d / fn).write_bytes(data)
    return d


def test_select_filters_orders_and_caps():
    sets = [{"name": "b", "size": 5, "backed_up": True},
            {"name": "a", "size": 9, "backed_up": False},
            {"name": "c", "size": 1, "backed_up": True}]
    assert [s["name"] for s in client_remove.select(sets)] == ["a", "b", "c"]
    assert [s["name"] for s in client_remove.select(sets, "backed_up", "smallest")] == ["c", "b"]
    assert [s["name"] for s in client_remove.select(sets, "not_backed_up")] == ["a"]
    assert [s["name"] for s in client_remove.select(sets, sort="name", limit=2)] == ["a", "b"]


def test_resolve_stable_folder_only_accepts_direct_child_dirs(tmp_path):
    songs = tmp_path / "Songs"
    _folder(songs, "123 A - B")
    (songs / "loose.osz").write_bytes(b"x")
    assert client_remove.resolve_stable_folder(songs, "123 A - B") == songs / "123 A - B"
    for bad in ("", ".", "..", "../x", "123 A - B/sub", "C:\\Windows", "loose.osz", "missing"):
        assert client_remove.resolve_stable_folder(songs, bad) is None, bad


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
def test_resolve_stable_folder_refuses_symlinks(tmp_path):
    songs = tmp_path / "Songs"
    songs.mkdir()
    outside = _folder(tmp_path, "precious")
    try:
        (songs / "evil").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not permitted")
    assert client_remove.resolve_stable_folder(songs, "evil") is None


def test_stable_candidates_sizes_ids_and_backup_flag(tmp_path):
    songs = tmp_path / "Songs"
    _folder(songs, "123 A - B", {"a.osu": b"x" * 10, "bg.jpg": b"y" * 5})
    _folder(songs, "456 C - D", {"c.osu": b"z" * 3})
    out = client_remove.stable_candidates(songs, backed_up_ids={123})
    by = {s["name"]: s for s in out}
    assert by["123 A - B"]["size"] == 15 and by["123 A - B"]["backed_up"] is True
    assert by["456 C - D"]["beatmapset_id"] == 456 and by["456 C - D"]["backed_up"] is False


def test_client_running_classifies_lazer_and_stable():
    stable = r"C:\Users\x\AppData\Local\osu!\osu!.exe"
    lazer = r"C:\Users\x\AppData\Local\osulazer\current\osu!.exe"
    assert client_remove.client_running("stable", [stable])
    assert not client_remove.client_running("lazer", [stable])
    assert client_remove.client_running("lazer", [lazer])
    assert not client_remove.client_running("stable", [lazer])
    assert client_remove.client_running("stable", ["?"])   # unknown path: assume running
    assert not client_remove.client_running("stable", [])
    assert not client_remove.client_running("stable", None)


def test_osu_process_paths_parses_runner_output():
    out = client_remove.osu_process_paths(runner=lambda cmd: "C:\\a\\osu!.exe\r\n?\r\n")
    assert out == ["C:\\a\\osu!.exe", "?"]
    def boom(cmd):
        raise OSError("no powershell")
    assert client_remove.osu_process_paths(runner=boom) is None


def test_helper_protocol_parsers():
    assert client_remove.parse_helper_capabilities("CAPS export list delete\n") == {"export", "list", "delete"}
    assert client_remove.parse_helper_capabilities("usage: RosuLazerExport ...") == set()
    listing = "SET\t123\t2048\tArtist - Title\nSET\tx\t1\tbad\nSET\t-4\t1\tneg\ngarbage\nSET\t9\t0\t\n"
    assert client_remove.parse_helper_list(listing) == [
        {"key": "123", "name": "Artist - Title", "beatmapset_id": 123, "size": 2048},
        {"key": "9", "name": "9", "beatmapset_id": 9, "size": 0},
    ]
    assert client_remove.parse_helper_deleted("BACKUP x\nDELETED 5\nDELETED x\nDELETED 7\n") == {5, 7}
