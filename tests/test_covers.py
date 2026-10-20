# SPDX-License-Identifier: GPL-3.0-or-later
"""Cover art lookup for the Search gallery (v1.9)."""
import os
import zipfile

from rosu import covers

OSU = """osu file format v14

[General]
AudioFilename: audio.mp3

[Events]
//Background and Video events
0,0,"sub\\bg one.jpg",0,0
Video,0,"video.mp4"
"""


def _osz(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_background_name_reads_events():
    assert covers.background_name(OSU) == "sub/bg one.jpg"
    assert covers.background_name("[Events]\n0,0,\"clip.mp4\",0,0\n") is None
    assert covers.background_name("[General]\n0,0,\"x.jpg\"\n") is None   # not in Events


def test_cover_bytes_prefers_the_named_background(tmp_path):
    p = _osz(tmp_path / "a.osz", {"A [x].osu": OSU, "sub/BG one.jpg": b"named",
                                  "huge.png": b"p" * 100})
    assert covers.cover_bytes(p) == b"named"                 # case-insensitive match
    q = _osz(tmp_path / "b.osz", {"A [x].osu": "[Events]\n", "small.jpg": b"s",
                                  "big.png": b"b" * 10})
    assert covers.cover_bytes(q) == b"b" * 10               # largest image fallback
    r = _osz(tmp_path / "c.osz", {"A [x].osu": "[Events]\n"})
    assert covers.cover_bytes(r) is None
    (tmp_path / "bad.osz").write_bytes(b"not a zip")
    assert covers.cover_bytes(tmp_path / "bad.osz") is None


def test_cache_name_tracks_changes_and_prune_keeps_the_newest(tmp_path):
    p = _osz(tmp_path / "a.osz", {"x.osu": "x"})
    first = covers.cache_name(p)
    _osz(p, {"x.osu": "changed contents"})
    assert covers.cache_name(p) != first
    assert covers.cache_name(tmp_path / "missing.osz") is None
    cache = tmp_path / "covers"
    cache.mkdir()
    for i in range(5):
        f = cache / f"{i}.jpg"
        f.write_bytes(b"x")
        os.utime(f, (1000 + i, 1000 + i))
    assert covers.prune_cache(cache, keep=2) == 3
    assert sorted(f.name for f in cache.glob("*.jpg")) == ["3.jpg", "4.jpg"]
