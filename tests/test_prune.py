# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the space-saving prune engine (v1.7).

Destructive-operation safety is the priority here: the swap-in must never
leave the Library file missing, and a suspiciously large zip member must be
refused rather than read into memory.
"""
import zipfile

from rosu import prune


_OSU_TEXT = (
    "osu file format v14\n\n"
    "[General]\n"
    "AudioFilename: audio.mp3\n\n"
    "[Events]\n"
    '0,0,"bg.jpg",0,0\n'
)


def _make_osz(path, entries: dict[str, bytes]):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)


# -- get_osu_assets ----------------------------------------------------------
def test_get_osu_assets_parses_audio_and_background():
    assets = prune.get_osu_assets(_OSU_TEXT)
    assert assets == {"audio.mp3", "bg.jpg"}


def test_get_osu_assets_empty_text():
    assert prune.get_osu_assets("") == set()


# -- prune_osz: basic contract -------------------------------------------------
def test_prune_nonexistent_path_returns_zero(tmp_path):
    assert prune.prune_osz(tmp_path / "missing.osz") == 0


def test_prune_bad_zip_returns_zero(tmp_path):
    p = tmp_path / "not-a-zip.osz"
    p.write_bytes(b"this is not a zip file")
    assert prune.prune_osz(p) == 0
    assert p.exists()
    assert p.read_bytes() == b"this is not a zip file"


# -- prune_osz: video_only mode ------------------------------------------------
def test_video_only_removes_video_keeps_rest(tmp_path):
    p = tmp_path / "set.osz"
    _make_osz(p, {
        "map.osu": _OSU_TEXT.encode("utf-8"),
        "audio.mp3": b"x" * 1000,
        "bg.jpg": b"y" * 1000,
        "video.mp4": b"z" * 5000,
    })
    freed = prune.prune_osz(p, mode="video_only")
    assert freed == 5000
    with zipfile.ZipFile(p) as zf:
        names = set(zf.namelist())
    assert names == {"map.osu", "audio.mp3", "bg.jpg"}


def test_video_only_no_video_frees_nothing(tmp_path):
    p = tmp_path / "set.osz"
    original = {"map.osu": _OSU_TEXT.encode("utf-8"), "audio.mp3": b"x" * 1000}
    _make_osz(p, original)
    before = p.read_bytes()
    freed = prune.prune_osz(p, mode="video_only")
    assert freed == 0
    assert p.read_bytes() == before   # untouched, not just "same size"


# -- prune_osz: heavy_assets mode ---------------------------------------------
def test_heavy_assets_keeps_referenced_and_small_files(tmp_path):
    p = tmp_path / "set.osz"
    _make_osz(p, {
        "map.osu": _OSU_TEXT.encode("utf-8"),
        "audio.mp3": b"a" * 1000,          # referenced -> kept regardless of size rule
        "bg.jpg": b"b" * 1000,             # referenced -> kept
        "unused_small.png": b"c" * 1000,   # unreferenced but small -> kept
        "storyboard.osb": b"d" * 9000,     # unreferenced, not audio/image -> removed
    })
    freed = prune.prune_osz(p, mode="heavy_assets")
    assert freed == 9000
    with zipfile.ZipFile(p) as zf:
        names = set(zf.namelist())
    assert names == {"map.osu", "audio.mp3", "bg.jpg", "unused_small.png"}


def test_heavy_assets_removes_oversized_unreferenced_image(tmp_path):
    p = tmp_path / "set.osz"
    big_image = b"e" * (600 * 1024)   # over the 500 KiB unreferenced-image cap
    _make_osz(p, {
        "map.osu": _OSU_TEXT.encode("utf-8"),
        "audio.mp3": b"a" * 1000,
        "bg.jpg": b"b" * 1000,
        "extra.png": big_image,
    })
    freed = prune.prune_osz(p, mode="heavy_assets")
    assert freed == len(big_image)
    with zipfile.ZipFile(p) as zf:
        assert "extra.png" not in zf.namelist()


def test_heavy_assets_no_osu_file_frees_nothing(tmp_path):
    p = tmp_path / "set.osz"
    _make_osz(p, {"audio.mp3": b"a" * 1000})
    assert prune.prune_osz(p, mode="heavy_assets") == 0


# -- zip-bomb guard: refuse an oversized declared entry ------------------------
def test_refuses_oversized_essential_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(prune, "_MAX_ENTRY_BYTES", 10)
    p = tmp_path / "set.osz"
    _make_osz(p, {
        "map.osu": _OSU_TEXT.encode("utf-8"),   # > 10 bytes -> "too large" under the test cap
        "video.mp4": b"z" * 5000,
    })
    before = p.read_bytes()
    freed = prune.prune_osz(p, mode="video_only")
    assert freed == 0
    assert p.exists()
    assert p.read_bytes() == before   # refused, original untouched


def test_heavy_assets_scan_refuses_oversized_osu(tmp_path, monkeypatch):
    monkeypatch.setattr(prune, "_MAX_ENTRY_BYTES", 10)
    p = tmp_path / "set.osz"
    _make_osz(p, {"map.osu": _OSU_TEXT.encode("utf-8")})
    assert prune.prune_osz(p, mode="heavy_assets") == 0


# -- data-loss window: a failed swap must never leave `p` missing ------------
def test_swap_failure_leaves_original_untouched(tmp_path, monkeypatch):
    # The swap-in is a single atomic os.replace(temp, p); if it fails, p was
    # never touched (no rename-aside-then-swap-back dance to fail mid-way).
    p = tmp_path / "set.osz"
    _make_osz(p, {
        "map.osu": _OSU_TEXT.encode("utf-8"),
        "audio.mp3": b"a" * 1000,
        "video.mp4": b"z" * 5000,
    })
    original_bytes = p.read_bytes()

    def flaky_replace(src, dst):
        raise OSError("simulated failure mid-swap")

    monkeypatch.setattr(prune.os, "replace", flaky_replace)
    freed = prune.prune_osz(p, mode="video_only")

    assert freed == 0   # failure surfaces as "nothing changed"
    assert p.exists()   # never left missing
    assert p.read_bytes() == original_bytes   # original content preserved
    # no stray temp/trash-copy files left behind
    assert list(tmp_path.iterdir()) == [p]


def test_readonly_file_leaves_no_stray_orig_copy(tmp_path):
    # shutil.copy2 also copies the read-only bit, so the aside-copy of a
    # read-only Library file is itself read-only and a plain os.remove raises
    # PermissionError on Windows — which used to litter the Library folder with
    # a stray *.osz.orig on every prune attempt against such a file.
    import os
    import stat

    p = tmp_path / "set.osz"
    _make_osz(p, {
        "map.osu": _OSU_TEXT.encode("utf-8"),
        "video.mp4": b"z" * 5000,
    })
    original_bytes = p.read_bytes()
    os.chmod(p, stat.S_IREAD)
    try:
        prune.prune_osz(p, mode="video_only")
        assert p.exists()
        assert p.read_bytes() == original_bytes
        assert [f.name for f in tmp_path.iterdir()] == ["set.osz"]
    finally:
        os.chmod(p, stat.S_IWRITE | stat.S_IREAD)


def test_trash_copy_failure_leaves_original_untouched(tmp_path, monkeypatch):
    # If even making the recoverable copy fails, the original must still be
    # untouched (the swap-in never runs).
    p = tmp_path / "set.osz"
    _make_osz(p, {
        "map.osu": _OSU_TEXT.encode("utf-8"),
        "video.mp4": b"z" * 5000,
    })
    original_bytes = p.read_bytes()

    def flaky_copy2(src, dst):
        raise OSError("simulated copy failure")

    monkeypatch.setattr(prune.shutil, "copy2", flaky_copy2)
    freed = prune.prune_osz(p, mode="video_only")

    assert freed == 0
    assert p.exists()
    assert p.read_bytes() == original_bytes
    assert list(tmp_path.iterdir()) == [p]
