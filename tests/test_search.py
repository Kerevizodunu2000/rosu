"""Unit tests for the relevance ranker in rosu.search."""
from rosu.search import rank


def _row(id_, name):
    artist, _, title = name.partition(" - ")
    return {"beatmapset_id": id_, "display_name": name, "artist": artist,
            "title": title, "creator": None, "tags": None, "source": None,
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
