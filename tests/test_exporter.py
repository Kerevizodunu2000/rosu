# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the export/volume-splitting logic (real files in tmp_path)."""
import zipfile

import pytest

from rosu import exporter


def test_plan_volumes_no_split_single_volume():
    assert exporter.plan_volumes([10, 20, 30], None) == [[0, 1, 2]]
    assert exporter.plan_volumes([10, 20, 30], 0) == [[0, 1, 2]]
    assert exporter.plan_volumes([10, 20, 30], -5) == [[0, 1, 2]]


def test_plan_volumes_splits_by_size():
    sizes = [40, 40, 40]
    volumes = exporter.plan_volumes(sizes, split_bytes=100)
    # 40+40 <= 100; the third would overflow -> new volume
    assert volumes == [[0, 1], [2]]


def test_plan_volumes_oversized_item_gets_own_volume():
    sizes = [500, 10, 10]
    volumes = exporter.plan_volumes(sizes, split_bytes=100)
    assert volumes == [[0], [1, 2]]


def test_plan_volumes_preserves_order():
    sizes = [30, 10, 30, 10]
    volumes = exporter.plan_volumes(sizes, split_bytes=40)
    flat = [i for vol in volumes for i in vol]
    assert flat == [0, 1, 2, 3]


def test_plan_volumes_empty():
    assert exporter.plan_volumes([], None) == []
    assert exporter.plan_volumes([], 100) == []


def _make_files(tmp_path, names_and_contents, subdir=None):
    base = (tmp_path / subdir) if subdir else tmp_path
    base.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, content in names_and_contents:
        p = base / name
        p.write_bytes(content)
        paths.append(p)
    return paths


def test_write_export_zip_single(tmp_path):
    files = _make_files(tmp_path, [("a.osz", b"AAAA"), ("b.osz", b"BBBBBB")])
    dest = tmp_path / "out" / "export"
    written = exporter.write_export(files, dest, fmt="zip")
    assert len(written) == 1
    out = written[0]
    assert out == dest.with_suffix(".zip")
    assert out.exists()
    with zipfile.ZipFile(out) as z:
        assert sorted(z.namelist()) == ["a.osz", "b.osz"]
        assert all(i.compress_type == zipfile.ZIP_STORED for i in z.infolist())
        assert z.read("b.osz") == b"BBBBBB"


def test_write_export_zip_split(tmp_path):
    files = _make_files(tmp_path, [(f"f{i}.osz", b"X" * 50) for i in range(6)])
    dest = tmp_path / "out" / "export"
    written = exporter.write_export(files, dest, fmt="zip", split_bytes=120)
    assert len(written) > 1
    for p in written:
        assert ".part" in p.name
        assert p.exists()

    all_members: list[str] = []
    for p in written:
        with zipfile.ZipFile(p) as z:
            all_members.extend(z.namelist())

    expected = {f"f{i}.osz" for i in range(6)}
    assert set(all_members) == expected
    assert len(all_members) == len(expected)  # no member appears twice


def test_write_export_progress_callback(tmp_path):
    files = _make_files(tmp_path, [("a.osz", b"A"), ("b.osz", b"B")])
    dest = tmp_path / "export"
    events = []
    exporter.write_export(files, dest, fmt="zip", progress=events.append)
    assert [e["done"] for e in events] == [1, 2]
    assert all(e["total"] == 2 and e["kind"] == "export" for e in events)
    assert {e["name"] for e in events} == {"a.osz", "b.osz"}


def test_write_export_basename_collision(tmp_path):
    a = (tmp_path / "dir1" / "same.osz")
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_bytes(b"FIRST")
    b = (tmp_path / "dir2" / "same.osz")
    b.parent.mkdir(parents=True, exist_ok=True)
    b.write_bytes(b"SECOND")
    dest = tmp_path / "export"
    written = exporter.write_export([a, b], dest, fmt="zip")
    assert len(written) == 1
    with zipfile.ZipFile(written[0]) as z:
        names = sorted(z.namelist())
        assert names == ["same (2).osz", "same.osz"]
        first = z.read("same.osz")
        second = z.read("same (2).osz")
        assert {first, second} == {b"FIRST", b"SECOND"}


def test_write_export_missing_file_skipped(tmp_path):
    files = _make_files(tmp_path, [("a.osz", b"A")])
    missing = tmp_path / "missing.osz"
    dest = tmp_path / "export"
    written = exporter.write_export(files + [missing], dest, fmt="zip")
    assert len(written) == 1
    with zipfile.ZipFile(written[0]) as z:
        assert z.namelist() == ["a.osz"]


def test_write_export_empty_list(tmp_path):
    dest = tmp_path / "export"
    written = exporter.write_export([], dest, fmt="zip")
    assert written == []
    assert not dest.with_suffix(".zip").exists()
    assert not list(tmp_path.glob("*"))


def test_write_export_split_smaller_than_single_file(tmp_path):
    files = _make_files(tmp_path, [("big.osz", b"X" * 100), ("small.osz", b"Y" * 5)])
    dest = tmp_path / "export"
    written = exporter.write_export(files, dest, fmt="zip", split_bytes=10)
    assert len(written) == 2  # oversized file still gets its own volume
    all_members: list[str] = []
    for p in written:
        with zipfile.ZipFile(p) as z:
            all_members.extend(z.namelist())
    assert set(all_members) == {"big.osz", "small.osz"}
    assert len(all_members) == 2


def test_write_export_7z_single(tmp_path):
    py7zr = pytest.importorskip("py7zr")
    files = _make_files(tmp_path, [("a.osz", b"AAAA"), ("b.osz", b"BBBBBB")])
    dest = tmp_path / "export"
    written = exporter.write_export(files, dest, fmt="7z")
    assert len(written) == 1
    out = written[0]
    assert out == dest.with_suffix(".7z")
    with py7zr.SevenZipFile(out) as z:
        assert sorted(z.getnames()) == ["a.osz", "b.osz"]


def test_write_export_bad_format_raises(tmp_path):
    files = _make_files(tmp_path, [("a.osz", b"A")])
    with pytest.raises(ValueError):
        exporter.write_export(files, tmp_path / "export", fmt="rar")
