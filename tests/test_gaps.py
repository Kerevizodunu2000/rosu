"""Unit tests for rosu.gaps (confidence-aware)."""
from rosu.gaps import (
    missing_numbers, build_numbered_rows, build_spotlight_rows, build_rows,
    build_reference_rows,
)


def test_missing_numbers_basic():
    assert missing_numbers([1819, 1820, 1822, 1823]) == [1821]
    assert missing_numbers([361, 362, 364, 365, 366]) == [363]
    assert missing_numbers([]) == []
    assert missing_numbers([5]) == []
    assert missing_numbers([100, 103]) == [101, 102]


def _numbered(nums):
    return [{"number": n, "code": f"S{n}", "title": "t", "track_count": 1} for n in nums]


def test_numbered_rows_with_gaps():
    rows = build_numbered_rows("S", _numbered([1819, 1820, 1822]), show_gaps=True)
    assert [r.number for r in rows] == [1819, 1820, 1821, 1822]
    assert [r.present for r in rows] == [True, True, False, True]


def test_numbered_missing_row_has_code_and_mode():
    # A red gap row must not be blank in Code/Mode (item 8): code = series+number,
    # mode derived from the series prefix.
    rows = build_numbered_rows("SM", _numbered([361, 363]), show_gaps=True)
    missing = [r for r in rows if not r.present]
    assert len(missing) == 1
    assert missing[0].number == 362
    assert missing[0].code == "SM362"
    assert missing[0].mode == "osu!mania"


def test_numbered_rows_without_gaps():
    rows = build_numbered_rows("FQ", _numbered([92, 94, 97]), show_gaps=False)
    assert [r.number for r in rows] == [92, 94, 97]
    assert all(r.present for r in rows)


def test_build_rows_standard_is_confident_red():
    rows = build_rows("S", "Standard", _numbered([100, 102]))
    missing = [r.number for r in rows if not r.present]
    assert missing == [101]


def test_build_rows_featured_no_red_offline():
    present = [{"number": 92, "code": "FQ92", "title": "a", "track_count": 1},
               {"number": 97, "code": "FQ97", "title": "b", "track_count": 1}]
    rows = build_rows("FQ", "Featured", present)
    assert all(r.present for r in rows)  # never guessed red without a reference


def test_build_rows_spotlights_list_only():
    present = [
        {"number": 287, "year": 2020, "season": "Winter", "mode": "osu!", "code": "R287"},
        {"number": 291, "year": 2020, "season": "Summer", "mode": "osu!", "code": "R291"},
    ]
    rows = build_rows("R", "Spotlights", present)
    assert all(r.present for r in rows)


def test_reference_rows_confirm_missing():
    present = [{"number": 92, "code": "FQ92", "title": "a", "mode": "osu!", "track_count": 1},
               {"number": 95, "code": "FQ95", "title": "d", "mode": "osu!", "track_count": 1}]
    reference = [
        {"number": 92, "code": "FQ92", "title": "a", "mode": "osu!"},
        {"number": 93, "code": "FQ93", "title": "b", "mode": "osu!"},
        {"number": 94, "code": "FQ94", "title": "c", "mode": "osu!"},
        {"number": 95, "code": "FQ95", "title": "d", "mode": "osu!"},
    ]
    rows = build_reference_rows("FQ", present, reference)
    missing = sorted(r.number for r in rows if not r.present)
    assert missing == [93, 94]


def test_reference_rows_skip_uncollected_mode():
    # user only collects osu!; a missing osu!taiko reference pack must NOT be red
    present = [{"number": 287, "code": "R287", "mode": "osu!", "title": "a", "track_count": 1},
               {"number": 291, "code": "R291", "mode": "osu!", "title": "c", "track_count": 1}]
    reference = [
        {"number": 287, "code": "R287", "mode": "osu!", "title": "a"},
        {"number": 289, "code": "R289", "mode": "osu!taiko", "title": "b"},
        {"number": 291, "code": "R291", "mode": "osu!", "title": "c"},
    ]
    rows = build_reference_rows("R", present, reference)
    assert all(r.present for r in rows)  # R289 taiko is skipped, not flagged
