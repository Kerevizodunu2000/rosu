# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the full .osu / .osz parser (rosu.beatmap, v1.5)."""
import zipfile

from rosu import beatmap

_MANIA_7K = """osu file format v14

[General]
Mode: 3

[Metadata]
Title:Test Song
Artist:Tester
Creator:Mapper
Version:7K Insane
Tags:foo bar

[Difficulty]
HPDrainRate:8
CircleSize:7
OverallDifficulty:8.5
ApproachRate:5
SliderMultiplier:1.4
SliderTickRate:1

[TimingPoints]
0,300,4,2,0,100,1,0

[HitObjects]
64,192,1000,1,0,0:0:0:0:
128,192,3000,1,0,0:0:0:0:
"""

_STD = """osu file format v14

[General]
Mode: 0

[Metadata]
Title:Std Song
Artist:Someone
Version:Hard

[Difficulty]
HPDrainRate:5
CircleSize:4
OverallDifficulty:7
ApproachRate:9
"""


def test_read_osu_diff_mania_keycount_and_fields():
    d = beatmap.read_osu_diff(_MANIA_7K.encode("utf-8"), "song [7K Insane].osu")
    assert d.mode_int == 3
    assert d.mode == "osu!mania"
    assert d.version == "7K Insane"
    assert d.keycount == 7          # round(CircleSize) for mania
    assert d.cs == 7.0
    assert d.od == 8.5
    assert d.hp == 8.0
    assert d.ar == 5.0
    assert d.bpm == 200.0           # 60000 / 300
    assert d.length_seconds == 3    # last hit-object time 3000ms
    assert d.checksum == __import__("hashlib").md5(
        _MANIA_7K.encode("utf-8")).hexdigest()


def test_read_osu_diff_standard_has_no_keycount():
    d = beatmap.read_osu_diff(_STD.encode("utf-8"), "std.osu")
    assert d.mode_int == 0
    assert d.mode == "osu!"
    assert d.keycount is None       # only mania has a key count
    assert d.cs == 4.0


def test_read_osu_diff_missing_difficulty_section_never_raises():
    d = beatmap.read_osu_diff(b"osu file format v14\n\n[General]\nMode: 3\n", "x.osu")
    assert d.mode_int == 3
    assert d.cs is None and d.keycount is None and d.od is None


def test_read_osu_diff_parser_explosion_falls_back_to_basic_meta(monkeypatch):
    # The "never raises" contract survives even a parser bug: filename + checksum
    # are still recorded so the diff row exists and can be re-parsed later.
    def boom(text):
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(beatmap, "parse_osu_sections", boom)
    d = beatmap.read_osu_diff(b"whatever", "x.osu")
    assert d.filename == "x.osu"
    assert d.checksum == __import__("hashlib").md5(b"whatever").hexdigest()
    assert d.mode_int is None and d.cs is None


def test_read_osz_full_skips_oversized_osu(tmp_path, monkeypatch):
    # Decompression-bomb guard: a member whose reported size exceeds the cap is
    # skipped (no read), while normal siblings still parse.
    monkeypatch.setattr(beatmap, "_MAX_OSU_BYTES", 500)
    p = tmp_path / "1 A - B.osz"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("small [Easy].osu", _STD)          # ~230 bytes — under the cap
        z.writestr("big [Hard].osu", "x" * 1000)      # over the cap — skipped
    meta, diffs, raw = beatmap.read_osz_full(p)
    assert set(raw) == {"small [Easy].osu"}
    assert [d.filename for d in diffs] == ["small [Easy].osu"]
    assert meta.diff_count == 2     # counted from names even when one is skipped


def test_read_osu_diff_garbage_never_raises():
    d = beatmap.read_osu_diff(b"\x00\x01 not a beatmap \xff", "bad.osu")
    assert d.checksum  # always computed from the raw bytes
    assert d.mode_int is None


def test_read_osz_full_reads_every_osu(tmp_path):
    """The regression test for the old 'only the alphabetically-first .osu'
    behaviour — every difficulty must now be parsed."""
    osz = tmp_path / "set.osz"
    with zipfile.ZipFile(osz, "w") as zf:
        zf.writestr("song [7K Insane].osu", _MANIA_7K)
        zf.writestr("song [Hard].osu", _STD)
        zf.writestr("audio.mp3", b"not really audio")
    meta, diffs, raw = beatmap.read_osz_full(osz)
    assert meta.diff_count == 2
    assert len(diffs) == 2
    assert len(raw) == 2
    versions = {d.version for d in diffs}
    assert versions == {"7K Insane", "Hard"}
    # bytes are keyed by filename so a rating engine can consume them directly
    assert set(raw) == {"song [7K Insane].osu", "song [Hard].osu"}


def test_read_osz_full_bad_zip_returns_empties(tmp_path):
    bad = tmp_path / "bad.osz"
    bad.write_bytes(b"this is not a zip file")
    meta, diffs, raw = beatmap.read_osz_full(bad)
    assert meta.diff_count == 0 and diffs == [] and raw == {}


def test_osz_meta_wrapper_matches_representative(tmp_path):
    """The thin osz_meta.read_osz_meta wrapper still returns the representative
    TrackMeta (backward compatibility)."""
    from rosu.osz_meta import read_osz_meta
    osz = tmp_path / "set.osz"
    with zipfile.ZipFile(osz, "w") as zf:
        zf.writestr("song [7K Insane].osu", _MANIA_7K)
    meta = read_osz_meta(osz)
    assert meta.artist == "Tester"
    assert meta.mode == "osu!mania"
    assert meta.bpm == 200.0
