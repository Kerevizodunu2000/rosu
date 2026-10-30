# SPDX-License-Identifier: GPL-3.0-or-later
"""Recycle Bin settings (issue #42): a turned-off or too-small bin counts as none."""
import os
import sys
from pathlib import Path

import pytest

from rosu import client_remove


def _reader(fixed=True, nuke=None, max_mb=None, total=10 ** 12):
    return lambda path: {"fixed": fixed, "nuke": nuke, "max_mb": max_mb, "total": total}


def _raises(exc):
    def reader(path):
        raise exc
    return reader


@pytest.mark.parametrize("reader, expected", [
    (_reader(nuke=None), True),
    (_reader(nuke=0), True),
    (_reader(nuke=1), False),
    (_reader(fixed=False), False),
    (_raises(OSError("unmappable volume")), False),
    (_raises(PermissionError("registry access denied")), False),
    (_raises(AttributeError("no windll")), False),
])
def test_available_follows_drive_type_and_nuke_on_delete(tmp_path, reader, expected):
    assert client_remove.recycle_bin_available(tmp_path, reader=reader) is expected


def _file(path, size):
    path.write_bytes(b"x" * size)
    return path


def test_fits_uses_max_capacity(tmp_path):
    mib = 1024 * 1024
    r = _reader(max_mb=1)
    assert client_remove.recycle_bin_fits(_file(tmp_path / "a", mib), reader=r) is True
    assert client_remove.recycle_bin_fits(_file(tmp_path / "b", mib + 1), reader=r) is False


def test_fits_falls_back_to_five_percent_of_the_volume(tmp_path):
    r = _reader(max_mb=None, total=2000)
    assert client_remove.recycle_bin_fits(_file(tmp_path / "a", 100), reader=r) is True
    assert client_remove.recycle_bin_fits(_file(tmp_path / "b", 101), reader=r) is False


def test_fits_counts_a_whole_folder(tmp_path):
    d = tmp_path / "set"
    d.mkdir()
    _file(d / "a", 60)
    (d / "sub").mkdir()
    _file(d / "sub" / "b", 60)
    assert client_remove.recycle_bin_fits(d, reader=_reader(total=2000)) is False
    assert client_remove.recycle_bin_fits(d, reader=_reader(total=2400)) is True


def test_fits_fails_closed(tmp_path):
    f = _file(tmp_path / "a", 1)
    assert client_remove.recycle_bin_fits(f, reader=_raises(OSError("x"))) is False
    assert client_remove.recycle_bin_fits(tmp_path / "missing", reader=_reader()) is False


def test_without_a_reader_off_windows_both_say_yes(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert client_remove.recycle_bin_available(tmp_path) is True
    assert client_remove.recycle_bin_fits(tmp_path) is True


def test_reader_never_writes_the_registry():
    src = Path(client_remove.__file__).read_text(encoding="utf-8")
    for call in ("SetValue", "CreateKey", "DeleteKey", "DeleteValue", "KEY_WRITE",
                 "KEY_ALL_ACCESS"):
        assert call not in src


@pytest.mark.skipif(sys.platform != "win32", reason="real Recycle Bin lookup is Windows only")
def test_real_lookup_on_the_system_drive(tmp_path):
    # Default user settings (as on CI): the system drive has a bin and 1 KB fits.
    assert client_remove.recycle_bin_available(Path(os.environ["SystemDrive"] + "\\")) is True
    assert client_remove.recycle_bin_fits(_file(tmp_path / "small", 1024)) is True
