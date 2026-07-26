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


# -- v1.7.1 modes: the choice is made at the point of use ---------------------
def test_images_only_removes_images_keeps_video_and_audio(tmp_path):
    p = tmp_path / "set.osz"
    _make_osz(p, {
        "map.osu": _OSU_TEXT.encode("utf-8"),
        "audio.mp3": b"a" * 1000,
        "bg.jpg": b"b" * 4000,          # the referenced background goes too
        "sb/extra.png": b"c" * 2000,
        "video.mp4": b"v" * 9000,       # kept: this mode is images only
    })
    freed = prune.prune_osz(p, mode="images_only")
    assert freed == 6000
    with zipfile.ZipFile(p) as zf:
        assert set(zf.namelist()) == {"map.osu", "audio.mp3", "video.mp4"}


def test_video_and_images_removes_both_keeps_audio_and_maps(tmp_path):
    p = tmp_path / "set.osz"
    _make_osz(p, {
        "map.osu": _OSU_TEXT.encode("utf-8"),
        "hard.osu": _OSU_TEXT.encode("utf-8"),
        "audio.mp3": b"a" * 1000,
        "bg.jpg": b"b" * 4000,
        "video.mp4": b"v" * 9000,
    })
    freed = prune.prune_osz(p, mode="video_and_images")
    assert freed == 13000
    with zipfile.ZipFile(p) as zf:
        assert set(zf.namelist()) == {"map.osu", "hard.osu", "audio.mp3"}


def test_no_mode_ever_removes_a_dot_osu(tmp_path):
    """Losing a .osu deletes a difficulty — that is not 'saving space'."""
    for mode in prune.MODES:
        p = tmp_path / f"{mode}.osz"
        _make_osz(p, {"map.osu": _OSU_TEXT.encode("utf-8"),
                      "audio.mp3": b"a" * 1000,
                      "bg.jpg": b"b" * 1000,
                      "video.mp4": b"v" * 9000})
        prune.prune_osz(p, mode=mode)
        with zipfile.ZipFile(p) as zf:
            assert "map.osu" in zf.namelist(), mode


# -- scan_osz: the preview must equal what pruning actually reports -----------
def test_scan_matches_what_prune_then_frees(tmp_path):
    for mode in prune.MODES:
        p = tmp_path / f"scan-{mode}.osz"
        _make_osz(p, {
            "map.osu": _OSU_TEXT.encode("utf-8"),
            "audio.mp3": b"a" * 1000,
            "bg.jpg": b"b" * 1000,
            "unused.png": b"c" * (600 * 1024),
            "story.osb": b"d" * 9000,
            "video.mp4": b"v" * 5000,
        })
        size, predicted = prune.scan_osz(p, mode)
        assert size == p.stat().st_size
        assert prune.prune_osz(p, mode=mode) == predicted, mode


def test_scan_reads_nothing_from_a_bad_zip(tmp_path):
    p = tmp_path / "bad.osz"
    p.write_bytes(b"not a zip")
    size, removable = prune.scan_osz(p, "video_only")
    assert size == p.stat().st_size and removable == 0


def test_scan_missing_file_is_zero(tmp_path):
    assert prune.scan_osz(tmp_path / "nope.osz", "video_only") == (0, 0)


# -- loose folders (osu!(stable)) --------------------------------------------
def _make_folder(root, name, files):
    d = root / name
    d.mkdir(parents=True)
    for fn, data in files.items():
        p = d / fn
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return d


def _fake_trash(monkeypatch):
    trashed = []

    def fake(path):
        trashed.append(str(path))
        import os
        os.remove(path)
    monkeypatch.setattr("send2trash.send2trash", fake)
    return trashed


def test_prune_folder_removes_video_keeps_maps(tmp_path, monkeypatch):
    songs = tmp_path / "Songs"
    songs.mkdir()
    d = _make_folder(songs, "123 A - B", {
        "map.osu": _OSU_TEXT.encode("utf-8"),
        "audio.mp3": b"a" * 1000,
        "bg.jpg": b"b" * 1000,
        "video.mp4": b"v" * 7000,
    })
    trashed = _fake_trash(monkeypatch)
    assert prune.prune_folder(d, mode="video_only", root=songs) == 7000
    assert {p.name for p in d.iterdir()} == {"map.osu", "audio.mp3", "bg.jpg"}
    assert len(trashed) == 1          # Recycle Bin, not unlink — still recoverable


def test_prune_folder_refuses_a_path_outside_the_songs_root(tmp_path, monkeypatch):
    songs = tmp_path / "Songs"
    songs.mkdir()
    outside = _make_folder(tmp_path, "elsewhere", {
        "map.osu": _OSU_TEXT.encode("utf-8"), "video.mp4": b"v" * 7000})
    trashed = _fake_trash(monkeypatch)
    assert prune.prune_folder(outside, mode="video_only", root=songs) == 0
    assert (outside / "video.mp4").exists()
    assert trashed == []


def test_prune_folder_ignores_a_folder_with_no_osu(tmp_path, monkeypatch):
    songs = tmp_path / "Songs"
    songs.mkdir()
    d = _make_folder(songs, "not-a-beatmap", {"video.mp4": b"v" * 7000})
    _fake_trash(monkeypatch)
    assert prune.prune_folder(d, mode="video_only", root=songs) == 0
    assert (d / "video.mp4").exists()


def test_scan_folder_matches_prune_folder(tmp_path, monkeypatch):
    songs = tmp_path / "Songs"
    songs.mkdir()
    d = _make_folder(songs, "1 A - B", {
        "map.osu": _OSU_TEXT.encode("utf-8"),
        "audio.mp3": b"a" * 1000,
        "bg.jpg": b"b" * 2000,
        "video.mp4": b"v" * 7000,
    })
    total, removable = prune.scan_folder(d, "video_and_images")
    assert total == 10000 + len(_OSU_TEXT.encode("utf-8"))   # every file counted
    assert removable == 9000                                  # bg.jpg + video.mp4
    _fake_trash(monkeypatch)
    assert prune.prune_folder(d, mode="video_and_images", root=songs) == removable


# -- select_targets (pure) ---------------------------------------------------
def _s(name, freed):
    return {"key": name, "name": name, "size": freed * 2, "freed": freed}


def test_select_targets_orders_and_limits():
    sets = [_s("a", 10), _s("b", 300), _s("c", 50)]
    assert [s["name"] for s in prune.select_targets(sets, "largest")] == ["b", "c", "a"]
    assert [s["name"] for s in prune.select_targets(sets, "smallest")] == ["a", "c", "b"]
    assert [s["name"] for s in prune.select_targets(sets, "name")] == ["a", "b", "c"]
    assert [s["name"] for s in prune.select_targets(sets, "largest", 2)] == ["b", "c"]


def test_select_targets_drops_sets_with_nothing_to_free():
    """Offering to 'prune 200 sets' and then touching 40 would make the preview
    a lie — only sets that actually free something are eligible."""
    sets = [_s("a", 0), _s("b", 5)]
    assert [s["name"] for s in prune.select_targets(sets)] == ["b"]
    assert prune.select_targets([_s("a", 0)]) == []


def test_select_targets_limit_zero_or_none_means_all():
    sets = [_s("a", 1), _s("b", 2)]
    assert len(prune.select_targets(sets, limit=None)) == 2
    assert len(prune.select_targets(sets, limit=0)) == 2
