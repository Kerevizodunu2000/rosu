# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the Rosu Skillset Rating heuristic (rosu.msd, v1.6).

These assert RELATIVE ordering on synthetic patterns — a pure jack scores highest
on jackspeed, a pure stream on stream, etc. — not exact magnitudes (the scale
factors are hand-tuned and expected to drift). This keeps the heuristic honestly
testable without pinning brittle numbers.
"""
from rosu import beatmap, msd

_DT = 125   # ms between rows (~120 bpm 1/4), fast enough to register


def _single_stream(n=64, key=7):
    """One note per row, cycling columns so nothing jacks."""
    return [(i * _DT, i % key, None) for i in range(n)]


def _jack(n=64, col=3):
    """One note per row, always the same column → pure jack."""
    return [(i * _DT, col, None) for i in range(n)]


def _chordjack(n=64):
    """A 2-note chord repeated on the same columns every row → chordjack."""
    out = []
    for i in range(n):
        out.append((i * _DT, 0, None))
        out.append((i * _DT, 1, None))
    return out


def _jumpstream(n=64):
    """Alternating single notes and (moving) 2-note jumps."""
    out = []
    for i in range(n):
        if i % 2 == 0:
            out.append((i * _DT, 0, None))
        else:
            out.append((i * _DT, 3, None))
            out.append((i * _DT, 4, None))
    return out


def _handstream(n=64):
    """Alternating single notes and (moving) 3-note hands."""
    out = []
    for i in range(n):
        if i % 2 == 0:
            out.append((i * _DT, 0, None))
        else:
            out.append((i * _DT, 2, None))
            out.append((i * _DT, 3, None))
            out.append((i * _DT, 4, None))
    return out


def _dominant(res):
    skills = res.skills()
    return max(skills, key=skills.get)


def test_pure_stream_scores_stream_highest():
    res = msd.skillset(_single_stream(), 7)
    assert res is not None
    assert _dominant(res) == "stream"
    assert res.jackspeed < res.stream
    assert res.chordjack < res.stream


def test_pure_jack_scores_jackspeed_highest():
    res = msd.skillset(_jack(), 7)
    assert res is not None
    assert _dominant(res) == "jackspeed"
    assert res.stream < res.jackspeed


def test_chordjack_scores_chordjack_highest():
    res = msd.skillset(_chordjack(), 7)
    assert res is not None
    assert _dominant(res) == "chordjack"
    assert res.jackspeed < res.chordjack


def test_jumpstream_beats_handstream_and_jacks():
    res = msd.skillset(_jumpstream(), 7)
    assert res is not None
    assert res.jumpstream > res.handstream
    assert res.jumpstream > res.jackspeed
    assert res.jumpstream >= res.stream


def test_handstream_beats_jumpstream():
    res = msd.skillset(_handstream(), 7)
    assert res is not None
    assert res.handstream > res.jumpstream


def test_overall_is_positive_and_source_tagged():
    res = msd.skillset(_single_stream(), 7)
    assert res.overall > 0
    assert res.source == "rosu-heuristic-v1"


def test_too_few_notes_returns_none():
    assert msd.skillset([(0, 0, None), (100, 1, None)], 7) is None
    assert msd.skillset([], 7) is None
    assert msd.skillset(_single_stream(), 0) is None


def test_zero_duration_returns_none():
    # all notes at the same time → no duration to rate
    assert msd.skillset([(0, i % 4, None) for i in range(12)], 4) is None


def test_read_mania_notes_column_mapping_and_hold():
    osu = (
        "osu file format v14\n\n[General]\nMode: 3\n\n"
        "[HitObjects]\n"
        "64,192,1000,1,0,0:0:0:0:\n"     # 4K col 0 (x=64)
        "192,192,1100,1,0,0:0:0:0:\n"    # 4K col 1 (x=192)
        "448,192,1200,128,0,1500:0:0:0:0:\n"   # 4K col 3 hold, ends 1500
    )
    notes = beatmap.read_mania_notes(osu.encode("utf-8"), 4)
    assert notes == [(1000, 0, None), (1100, 1, None), (1200, 3, 1500)]


def test_read_mania_notes_non_mania_or_zero_keys_empty():
    assert beatmap.read_mania_notes(b"[HitObjects]\n64,192,1,1,0", 0) == []
