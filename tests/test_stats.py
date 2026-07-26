# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the pure histogram binning (rosu.stats, v1.5)."""
from rosu import stats


def test_empty_list_yields_no_bins():
    assert stats.histogram_bins([]) == []
    assert stats.histogram_bins([None, None]) == []


def test_single_value_yields_one_bin():
    bins = stats.histogram_bins([5.0])
    assert len(bins) == 1
    lo, hi, count = bins[0]
    assert count == 1 and hi > lo   # no divide-by-zero, a drawable bar


def test_identical_values_one_bin():
    bins = stats.histogram_bins([3.3, 3.3, 3.3])
    assert len(bins) == 1
    assert bins[0][2] == 3


def test_spread_counts_sum_to_input():
    values = [1, 2, 2, 3, 4, 5, 5, 5, 6, 7, 8, 9, 10]
    bins = stats.histogram_bins(values, bins=5)
    assert len(bins) == 5
    assert sum(c for _, _, c in bins) == len(values)   # nothing lost
    # bin edges span the data range
    assert bins[0][0] == 1.0
    assert abs(bins[-1][1] - 10.0) < 1e-9


def test_max_lands_in_last_bin():
    bins = stats.histogram_bins([0.0, 10.0], bins=10)
    assert sum(c for _, _, c in bins) == 2
    assert bins[-1][2] >= 1   # the maximum is not dropped off the top edge


def test_none_values_ignored():
    bins = stats.histogram_bins([1.0, None, 2.0, None, 3.0], bins=3)
    assert sum(c for _, _, c in bins) == 3


# -- integer ("whole stars") mode, v1.7.1 ------------------------------------
def test_integer_mode_uses_whole_star_edges():
    """The data-driven split produced edges like 3.94–4.55; the owner wants plain
    0–1, 1–2, 2–3 buckets as an option."""
    bins = stats.histogram_bins([0.4, 1.2, 1.9, 4.7], mode="integer")
    assert [(lo, hi) for lo, hi, _c in bins] == [
        (0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, 5.0)]
    assert [c for _lo, _hi, c in bins] == [1, 2, 0, 0, 1]
    assert sum(c for _, _, c in bins) == 4          # nothing lost


def test_integer_mode_keeps_empty_buckets_inside_the_range():
    bins = stats.histogram_bins([0.5, 8.5], mode="integer")
    assert len(bins) == 9                            # 0–1 … 8–9, gaps included
    assert bins[0][2] == 1 and bins[-1][2] == 1
    assert sum(c for _, _, c in bins) == 2


def test_integer_mode_max_on_a_whole_number_lands_in_the_last_bin():
    bins = stats.histogram_bins([1.0, 5.0], mode="integer")
    assert sum(c for _, _, c in bins) == 2
    assert bins[-1] == (4.0, 5.0, 1)                 # 5.0 is not dropped

def test_integer_mode_identical_whole_values_still_draw_one_bar():
    bins = stats.histogram_bins([3.0, 3.0], mode="integer")
    assert bins == [(3.0, 4.0, 2)]


def test_integer_mode_empty_input_is_safe():
    assert stats.histogram_bins([], mode="integer") == []
    assert stats.histogram_bins([None], mode="integer") == []
