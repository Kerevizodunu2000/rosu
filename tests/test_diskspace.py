# SPDX-License-Identifier: GPL-3.0-or-later
"""The shared free-space helper and disk-full detection (issue #43)."""
import errno
import shutil
from collections import namedtuple

import pytest

from rosu import diskspace

MiB = 1024 * 1024
_Usage = namedtuple("_Usage", "total used free")


@pytest.fixture
def usage(monkeypatch):
    """Fake ``shutil.disk_usage``; set ``state["free"]``, read ``state["calls"]``."""
    state = {"free": 0, "calls": []}

    def fake(path):
        state["calls"].append(path)
        return _Usage(10_000 * MiB, 0, state["free"])

    monkeypatch.setattr(shutil, "disk_usage", fake)
    return state


def test_fits_when_free_is_well_above(usage, tmp_path):
    usage["free"] = 5_000 * MiB
    sp = diskspace.space(tmp_path, 100 * MiB)
    assert sp.fits and sp.free == 5_000 * MiB and sp.total == 10_000 * MiB


def test_margin_is_applied(usage, tmp_path):
    need = 100 * MiB
    usage["free"] = need + diskspace.MARGIN - 1   # free alone covers need
    assert not diskspace.space(tmp_path, need).fits
    usage["free"] = need + diskspace.MARGIN
    assert diskspace.space(tmp_path, need).fits


def test_custom_margin(usage, tmp_path):
    usage["free"] = 150 * MiB
    assert diskspace.space(tmp_path, 100 * MiB, margin=50 * MiB).fits
    assert not diskspace.space(tmp_path, 100 * MiB, margin=51 * MiB).fits
    assert diskspace.space(tmp_path, 150 * MiB, margin=0).fits


def test_unreadable_drive_never_blocks(monkeypatch, tmp_path):
    def boom(path):
        raise OSError("no such drive")

    monkeypatch.setattr(shutil, "disk_usage", boom)
    sp = diskspace.space(tmp_path, 10**15)
    assert sp.free is None and sp.total is None and sp.fits is True


def test_missing_folder_checks_existing_parent(usage, tmp_path):
    usage["free"] = 5_000 * MiB
    diskspace.space(tmp_path / "a" / "b" / "c", 1)
    assert [str(p) for p in usage["calls"]] == [str(tmp_path.resolve())]


def test_drive_is_the_anchor(usage, tmp_path):
    sp = diskspace.space(tmp_path / "not" / "there", 1)
    assert sp.drive == tmp_path.resolve().anchor
    assert sp.drive != str(tmp_path)


def test_is_disk_full():
    assert diskspace.is_disk_full(OSError(errno.ENOSPC, "x"))
    for code in (112, 39):
        exc = OSError("x")
        exc.winerror = code
        assert diskspace.is_disk_full(exc)
    assert not diskspace.is_disk_full(OSError(errno.EACCES, "x"))
    assert not diskspace.is_disk_full(ValueError())


def test_not_enough_space_is_not_an_oserror():
    exc = diskspace.NotEnoughSpace("D:\\", 300 * MiB, 10 * MiB)
    assert not isinstance(exc, OSError)
    assert (exc.drive, exc.need, exc.free) == ("D:\\", 300 * MiB, 10 * MiB)
    assert "D:\\" in str(exc) and str(300 * MiB) in str(exc) and str(10 * MiB) in str(exc)
