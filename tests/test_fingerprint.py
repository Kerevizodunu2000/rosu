# SPDX-License-Identifier: GPL-3.0-or-later
"""Audio fingerprints (v1.10): parsing, storage, alignment and grouping."""
import random

from rosu import fingerprint as fpm


def _song(seed: int, n: int = 900) -> list[int]:
    rnd = random.Random(seed)
    return [rnd.getrandbits(32) for _ in range(n)]


def _noisy(values: list[int], flips: int, seed: int = 1) -> list[int]:
    """The same recording re-encoded: a few bits differ in each value."""
    rnd = random.Random(seed)
    out = []
    for v in values:
        for _ in range(flips):
            v ^= 1 << rnd.randrange(12)       # low bits: the prefix mostly survives
        out.append(v)
    return out


def test_parse_and_pack_round_trip():
    parsed = fpm.parse_fpcalc('{"duration": 95.4, "fingerprint": [1, -1, 4294967295, 7]}')
    assert parsed == (95.4, [1, 0xFFFFFFFF, 0xFFFFFFFF, 7])
    assert fpm.parse_fpcalc("not json") is None
    assert fpm.parse_fpcalc('{"duration": 1, "fingerprint": []}') is None
    values = _song(3, 50)
    assert fpm.unpack(fpm.pack(values)) == values


def test_match_scores_same_song_high_and_aligns_offsets():
    a = _song(1)
    re_encoded = _noisy(a, 2)
    score, off = fpm.match(a, re_encoded)
    assert score > 0.9 and off == 0
    tv_cut = re_encoded[100:500]                  # starts 100 items (~12 s) later
    score, off = fpm.match(a, tv_cut)
    assert score > 0.9 and off == 100
    other, _ = fpm.match(a, _song(2))
    assert other < 0.7
    assert fpm.match(a, a[:20]) == (0.0, 0)        # too short to judge


def test_same_song_groups_find_versions_and_keep_strangers_apart():
    base = _song(10)
    fps = {
        1: base,
        2: _noisy(base, 2, seed=5),                # re-encode
        3: _noisy(base[50:800], 1, seed=6),        # cut from 6 s in
        4: _song(11),                              # another song
        5: _song(12),
        6: _noisy(_song(12), 2, seed=9),           # 5's twin
    }
    assert fpm.same_song_groups(fps) == [[1, 2, 3], [5, 6]]
    assert fpm.same_song_groups({1: base, 4: _song(11)}) == []
