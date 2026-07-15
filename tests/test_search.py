# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the relevance ranker in rosu.search."""
from rosu.search import rank, tokenize


def _row(id_, name, *, creator=None, tags=None, source=None):
    artist, _, title = name.partition(" - ")
    return {"beatmapset_id": id_, "display_name": name, "artist": artist,
            "title": title, "creator": creator, "tags": tags, "source": source,
            "copy_attempts": 0}


def test_word_prefix_beats_infix_substring():
    rows = [
        _row(1, "Camellia - WHAT THE CAT"),   # 'hat' only inside 'what'
        _row(2, "Supire - Forgotten Hate"),   # word 'Hate' starts with 'hat'
        _row(3, "Hatsune Miku - Something"),   # word 'Hatsune' starts with 'hat'
    ]
    out = rank(rows, "hat")
    names = [r["display_name"] for r in out]
    # the infix-only match must not be first
    assert names[0] != "Camellia - WHAT THE CAT"
    assert "Camellia - WHAT THE CAT" == names[-1]


def test_exact_id_ranks_top():
    rows = [_row(111, "A - B"), _row(222, "C - D")]
    out = rank(rows, "222")
    assert out[0]["beatmapset_id"] == 222


def test_prefix_beats_substring():
    rows = [_row(1, "xxx miku"), _row(2, "Miku - Song")]
    out = rank(rows, "miku")
    assert out[0]["display_name"] == "Miku - Song"


def test_tokenize_splits_and_lowercases():
    assert tokenize("Hatsune Miku") == ["hatsune", "miku"]
    assert tokenize("  ") == []


def test_multiword_requires_every_token_in_strong_fields():
    """The reported bug: 'Hatsune Miku' surfaced maps only *tagged* miku."""
    rows = [
        _row(1, "Hatsune Miku - World is Mine"),        # both tokens in artist
        _row(2, "DECO*27 - Ghost", tags="hatsune miku vocaloid"),  # tags only
        _row(3, "Hatsune Something - X"),               # 'miku' token missing
    ]
    out = rank(rows, "Hatsune Miku")
    names = [r["display_name"] for r in out]
    assert names == ["Hatsune Miku - World is Mine"]   # 2 (tag-only) & 3 excluded


def test_tag_match_is_opt_in_and_cannot_outrank_a_real_hit():
    rows = [
        _row(1, "Hatsune Miku - World is Mine"),        # real artist hit
        _row(2, "DECO*27 - Ghost", tags="hatsune miku"),  # tag-only
    ]
    default = rank(rows, "Hatsune Miku")
    assert [r["beatmapset_id"] for r in default] == [1]      # tag row hidden
    with_tags = rank(rows, "Hatsune Miku", search_tags=True)
    assert [r["beatmapset_id"] for r in with_tags] == [1, 2]  # real hit still first


def test_source_field_never_matches():
    """`source` was dropped from the weak fallback — it flooded results."""
    rows = [_row(1, "A - B", source="hatsune miku")]
    assert rank(rows, "hatsune miku") == []
    assert rank(rows, "hatsune miku", search_tags=True) == []  # not creator/tags either
