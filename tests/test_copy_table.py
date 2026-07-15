# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression tests for SortItem.__lt__ (rosu/ui/copy_table.py).

Guards against a RecursionError: the old implementation fell back to
``super().__lt__(other)`` on a TypeError/AttributeError, but PySide6's virtual
trampoline re-enters the same Python override for QTableWidgetItem::__lt__, so
any row with a None/mismatched sort key recursed until RecursionError when
sorting a large table (reproduced with 14000 rows).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QTableWidgetItem

from rosu.ui.copy_table import SortItem


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_numeric_sort_not_lexical(qapp):
    assert SortItem("2", 2) < SortItem("10", 10)


def test_none_sort_key_does_not_raise(qapp):
    # This is the regression: comparing a None sort key used to RecursionError.
    result = SortItem("", None) < SortItem("x", 5)
    assert isinstance(result, bool)


def test_compare_against_plain_qtablewidgetitem_does_not_raise(qapp):
    result = SortItem("a", 1) < QTableWidgetItem("b")
    assert isinstance(result, bool)


def test_mixed_types_does_not_raise(qapp):
    result = SortItem("a", "a") < SortItem("5", 5)
    assert isinstance(result, bool)
