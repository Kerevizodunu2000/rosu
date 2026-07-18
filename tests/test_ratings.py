# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the rosu-pp star-rating wrapper (rosu.ratings, v1.5).

Both paths must stay green regardless of whether rosu-pp-py is installed: the
'engine present' test skips when it's absent, and the 'engine absent' test forces
the unavailable branch so it runs everywhere.
"""
import pytest

from rosu import ratings
from rosu.models import DiffMeta

_STD = b"""osu file format v14

[General]
Mode: 0

[Metadata]
Title:T
Artist:A
Version:Hard

[Difficulty]
HPDrainRate:5
CircleSize:4
OverallDifficulty:7
ApproachRate:9

[TimingPoints]
0,300,4,2,0,100,1,0

[HitObjects]
64,192,1000,1,0,0:0:0:0:
128,192,2000,1,0,0:0:0:0:
256,192,3000,1,0,0:0:0:0:
"""


def test_available_returns_bool():
    assert isinstance(ratings.available(), bool)


@pytest.mark.skipif(not ratings.available(), reason="rosu-pp-py not installed")
def test_star_rating_with_engine():
    res = ratings.star_rating(_STD)
    assert res.error is None
    assert res.stars is not None and res.stars >= 0.0


def test_star_rating_without_engine(monkeypatch):
    monkeypatch.setattr(ratings, "_AVAILABLE", False)
    res = ratings.star_rating(_STD)
    assert res.stars is None
    assert res.error and "not installed" in res.error


def test_star_rating_never_raises_on_garbage():
    # Whether or not the engine is present, garbage must not raise.
    res = ratings.star_rating(b"\x00 not a beatmap \xff")
    assert res.stars is None or isinstance(res.stars, float)


def test_stars_for_diffs_without_engine(monkeypatch):
    monkeypatch.setattr(ratings, "_AVAILABLE", False)
    diffs = [DiffMeta(filename="a.osu"), DiffMeta(filename="b.osu")]
    raw = {"a.osu": _STD, "b.osu": _STD}
    stars = ratings.stars_for_diffs(diffs, raw)
    assert stars == {"a.osu": None, "b.osu": None}


def test_stars_for_diffs_missing_raw_is_none(monkeypatch):
    monkeypatch.setattr(ratings, "_AVAILABLE", True)
    monkeypatch.setattr(ratings, "star_rating",
                        lambda b, mods=0: ratings.RatingResult(4.2))
    diffs = [DiffMeta(filename="a.osu"), DiffMeta(filename="missing.osu")]
    raw = {"a.osu": _STD}   # no bytes for missing.osu
    stars = ratings.stars_for_diffs(diffs, raw)
    assert stars == {"a.osu": 4.2, "missing.osu": None}
