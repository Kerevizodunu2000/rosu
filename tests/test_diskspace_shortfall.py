# SPDX-License-Identifier: GPL-3.0-or-later
"""``diskspace.shortfall`` checks several places at once, adding up the needs
of places on the same drive (issue #46)."""
import shutil
from collections import namedtuple
from pathlib import Path

from rosu import diskspace

MiB = 1024 * 1024
_Usage = namedtuple("_Usage", "total used free")


def _free(monkeypatch, n):
    monkeypatch.setattr(shutil, "disk_usage", lambda p: _Usage(10_000 * MiB, 0, n))


def _two_drives(monkeypatch, short, free_short, free_other=10_000 * MiB):
    """Paths under ``short`` are on drive E: with ``free_short`` free; the rest on C:."""
    short = Path(short).resolve()

    def fake(path, need, margin=diskspace.MARGIN):
        p = Path(path).resolve()
        on_e = p == short or short in p.parents
        free = free_short if on_e else free_other
        return diskspace.Space(free, 10_000 * MiB, free >= need + margin,
                               "E:\\" if on_e else "C:\\")
    monkeypatch.setattr(diskspace, "space", fake)


def test_same_drive_needs_add_up(tmp_path, monkeypatch):
    _free(monkeypatch, 150 + diskspace.MARGIN)
    a, b = tmp_path / "a", tmp_path / "b"
    assert diskspace.shortfall([(a, 100)]) is None          # each alone fits
    assert diskspace.shortfall([(b, 100)]) is None
    assert diskspace.shortfall([(a, 100), (b, 100)]) == {
        "drive": tmp_path.resolve().anchor, "need": 200 + diskspace.MARGIN,
        "free": 150 + diskspace.MARGIN}


def test_different_drives_are_checked_separately(tmp_path, monkeypatch):
    _two_drives(monkeypatch, tmp_path / "e", 150 + diskspace.MARGIN)
    assert diskspace.shortfall([(tmp_path / "e", 100), (tmp_path / "c", 100)]) is None
    assert diskspace.shortfall([(tmp_path / "c", 10), (tmp_path / "e" / "x", 100),
                                (tmp_path / "e", 100)]) == {
        "drive": "E:\\", "need": 200 + diskspace.MARGIN, "free": 150 + diskspace.MARGIN}


def test_zero_need_is_ignored(tmp_path, monkeypatch):
    _free(monkeypatch, 0)
    assert diskspace.shortfall([(tmp_path, 0), (tmp_path / "x", -5)]) is None
    assert diskspace.shortfall([]) is None


def test_unreadable_drive_never_refuses(tmp_path, monkeypatch):
    def boom(p):
        raise OSError("unreadable")
    monkeypatch.setattr(shutil, "disk_usage", boom)
    assert diskspace.shortfall([(tmp_path, 10**15)]) is None
