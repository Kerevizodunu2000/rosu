# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the search query-syntax parser (rosu.query, v1.5)."""
from rosu import query


def _f(parsed):
    return [(x.field, x.op, x.value) for x in parsed.filters]


def test_single_numeric_filter_no_free_text():
    p = query.parse("star>5")
    assert _f(p) == [("star", ">", 5.0)]
    assert p.free_text == ""


def test_mixed_filters_and_free_text():
    p = query.parse("star>5 mode=mania key=7 camellia")
    assert ("star", ">", 5.0) in _f(p)
    assert ("mode", "=", "osu!mania") in _f(p)
    assert ("key", "=", 7) in _f(p)          # keys/key alias -> keycount int
    assert p.free_text == "camellia"


def test_all_operators_on_numeric():
    p = query.parse("star>=5.2 bpm<200 ar<=9 od>3")
    ops = {(x.field, x.op) for x in p.filters}
    assert ops == {("star", ">="), ("bpm", "<"), ("ar", "<="), ("od", ">")}


def test_case_insensitive_key_and_mode_alias():
    p = query.parse("STAR>5 mode=Mania")
    assert ("star", ">", 5.0) in _f(p)
    assert ("mode", "=", "osu!mania") in _f(p)


def test_mode_aliases():
    assert query.parse("mode=std").filters[0].value == "osu!"
    assert query.parse("mode=ctb").filters[0].value == "osu!catch"
    assert query.parse("mode=taiko").filters[0].value == "osu!taiko"


def test_malformed_value_left_in_free_text():
    p = query.parse("star>abc foo")
    assert p.filters == []
    assert p.free_text == "star>abc foo"   # nothing silently dropped


def test_unknown_field_is_free_text():
    p = query.parse("colour=red")
    assert p.filters == []
    assert p.free_text == "colour=red"


def test_string_field_rejects_comparison_ops():
    # mode/status only make sense with '='
    p = query.parse("mode>mania")
    assert p.filters == []
    assert p.free_text == "mode>mania"


def test_status_lowercased():
    p = query.parse("status=Ranked")
    assert _f(p) == [("status", "=", "ranked")]


def test_numeric_query_stays_free_text():
    # a bare id must not be swallowed as a filter (id search still works)
    p = query.parse("12345")
    assert p.filters == []
    assert p.free_text == "12345"


def test_text_contains_fields():
    p = query.parse("artist=camellia mapper=blocko name=ghost")
    assert _f(p) == [("artist", "contains", "camellia"),
                     ("creator", "contains", "blocko"),   # mapper -> creator
                     ("title", "contains", "ghost")]      # name -> title
    assert p.free_text == ""


def test_length_accepts_mmss_and_seconds():
    assert query.parse("length>4:03").filters[0].value == 243.0
    assert query.parse("length<243").filters[0].value == 243.0
    assert query.parse("length=1:30").filters[0].value == 90.0
    # a bad mm:ss (seconds >= 60) is rejected → stays free text
    assert query.parse("length=1:75").filters == []
