# SPDX-License-Identifier: GPL-3.0-or-later
"""diskspace.usage (per-drive used/total/free/low) and diskspace.tree_size."""
import os
import shutil
from collections import namedtuple

import pytest

from rosu import diskspace

GiB = 1024 ** 3
_Usage = namedtuple("_Usage", "total used free")


def _fake(monkeypatch, total, free):
    monkeypatch.setattr(shutil, "disk_usage", lambda p: _Usage(total, total - free, free))


def test_two_places_on_one_drive_give_one_entry(tmp_path, monkeypatch):
    _fake(monkeypatch, 100 * GiB, 50 * GiB)
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    out = diskspace.usage([("packs", a), ("output", b), ("lazer", None),
                           ("library", tmp_path / "missing")])
    assert len(out) == 1
    d = out[0]
    assert d["labels"] == ["packs", "output"] and d["drive"] == tmp_path.resolve().anchor
    assert (d["used"], d["total"], d["free"]) == (50 * GiB, 100 * GiB, 50 * GiB)
    assert d["readable"] is True and d["low"] is False


@pytest.mark.parametrize("total,free,low", [
    (30 * GiB, 4 * GiB, True),        # 13% but under 5 GiB
    (100 * GiB, 9 * GiB, True),       # over 5 GiB but under 10%
    (100 * GiB, 20 * GiB, False),
    (30 * GiB, 5 * GiB, False),       # exactly 5 GiB: strict
    (100 * GiB, 10 * GiB, False),     # exactly 10%: strict
])
def test_low_rule(tmp_path, monkeypatch, total, free, low):
    _fake(monkeypatch, total, free)
    assert diskspace.usage([("packs", tmp_path)])[0]["low"] is low


def test_unreadable_drive_never_raises(tmp_path, monkeypatch):
    def boom(p):
        raise OSError("gone")
    monkeypatch.setattr(shutil, "disk_usage", boom)
    d = diskspace.usage([("packs", tmp_path)])[0]
    assert d["readable"] is False and d["low"] is False
    assert d["used"] is None and d["total"] is None and d["free"] is None


def test_distinct_drives_get_their_own_entry(tmp_path, monkeypatch):
    def fake(path, need, margin=diskspace.MARGIN):
        e = "lazer" in str(path)
        return diskspace.Space(1 * GiB if e else 80 * GiB, 100 * GiB, True, "E:\\" if e else "C:\\")
    monkeypatch.setattr(diskspace, "space", fake)
    (tmp_path / "lazer").mkdir()
    out = diskspace.usage([("packs", tmp_path), ("lazer", tmp_path / "lazer"),
                           ("output", tmp_path)])
    assert [(d["drive"], d["labels"], d["low"]) for d in out] == [
        ("C:\\", ["packs", "output"], False), ("E:\\", ["lazer"], True)]


def test_tree_size_sums_nested_files(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "x.bin").write_bytes(b"1" * 10)
    (tmp_path / "a" / "y.bin").write_bytes(b"1" * 20)
    (tmp_path / "a" / "b" / "z.bin").write_bytes(b"1" * 30)
    assert diskspace.tree_size(tmp_path) == 60


def test_tree_size_ignores_symlinks(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "f").write_bytes(b"1" * 10)
    root = tmp_path / "root"
    root.mkdir()
    (root / "g").write_bytes(b"1" * 5)
    try:
        os.symlink(real / "f", root / "link_file")
        os.symlink(real, root / "link_dir", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not available")
    assert diskspace.tree_size(root) == 5


def test_tree_size_missing_path_is_zero(tmp_path):
    assert diskspace.tree_size(tmp_path / "nope") == 0


def test_tree_size_stops_when_cancelled(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "f").write_bytes(b"1" * 10)
    assert diskspace.tree_size(tmp_path, cancel=lambda: True) == 0
