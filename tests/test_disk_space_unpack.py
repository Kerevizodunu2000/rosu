# SPDX-License-Identifier: GPL-3.0-or-later
"""Unpack and Copy to Library check the free space first and stop cleanly on
a full disk (issue #43)."""
import errno
import shutil
import sqlite3
import tempfile
import zipfile
from collections import namedtuple
from pathlib import Path

import py7zr
import pytest

from rosu import client_remove, config, diskspace, library, parsing
from rosu.db import Database
from rosu.services import Services

MiB = 1024 * 1024
_Usage = namedtuple("_Usage", "total used free")
THREE = (("1 A - B.osz", 10), ("2 C - D.osz", 1000), ("3 E - F.osz", 20))


class Log:
    def __init__(self):
        self.warns = []

    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass

    def log(self, action, level="INFO", message="", **k):
        if level == "WARN":
            self.warns.append(k.get("detail", ""))


@pytest.fixture
def trashed(monkeypatch):
    calls = []
    monkeypatch.setattr("send2trash.send2trash", lambda p: calls.append(str(p)))
    monkeypatch.setattr(client_remove, "recycle_bin_available", lambda p: True)
    return calls


@pytest.fixture
def svc(tmp_path, trashed, monkeypatch):
    # a temp folder of its own, so a fake can tell it apart from Output
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "temp"))
    (tmp_path / "temp").mkdir()
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    s = Services(cfg, db, Log())
    yield s
    db.close()


@pytest.fixture
def free(monkeypatch):
    """``free(n)`` fakes ``shutil.disk_usage``; ``free(n, temp=m)`` gives the temp
    folder its own figure."""
    def set_free(n, temp=None):
        tmp = Path(tempfile.gettempdir()).resolve()

        def fake(path):
            in_temp = temp is not None and Path(path).resolve() == tmp
            return _Usage(10_000 * MiB, 0, temp if in_temp else n)

        monkeypatch.setattr(shutil, "disk_usage", fake)
    return set_free


def _pack(svc, name="S1 - Pack.zip", entries=THREE):
    path = svc.cfg.packs_path / name
    with zipfile.ZipFile(path, "w") as z:
        for n, size in entries:
            z.writestr(n, b"x" * size)
    return path, parsing.parse_pack_name(name)


def _pack7z(svc, name="S2 - Pack.7z", entries=THREE):
    path = svc.cfg.packs_path / name
    with py7zr.SevenZipFile(path, "w") as z:
        for n, size in entries:
            z.writestr(b"y" * size, n)
    return path, parsing.parse_pack_name(name)


def _counts(svc):
    con = sqlite3.connect(svc.cfg.db_path)
    try:
        return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("packs", "tracks", "track_sources")}
    finally:
        con.close()


def _names(folder):
    return sorted(p.name for p in Path(folder).iterdir()) if Path(folder).exists() else []


def _enospc():
    return OSError(errno.ENOSPC, "No space left on device")


# -- Unpack -------------------------------------------------------------------
def test_unpack_refused_up_front_writes_nothing(svc, trashed, free):
    svc.cfg.clear_output_before_extract = True
    old = svc.cfg.output_path / "9 Old - Map.osz"
    old.write_bytes(b"o" * 10)
    path, parsed = _pack(svc)
    before = _counts(svc)
    free(1 * MiB)
    res = svc.extract([(path, parsed)])
    assert res["no_space"] == {"drive": svc.cfg.output_path.resolve().anchor,
                               "need": 1030 + diskspace.MARGIN, "free": 1 * MiB}
    assert res["packs"] == 0 and res["tracks"] == 0 and res["kept"] == 1
    assert _names(svc.cfg.output_path) == ["9 Old - Map.osz"]
    assert _counts(svc) == before
    assert path.exists()
    assert trashed == []
    assert any("Unpack refused" in w for w in svc.log.warns)


def test_7z_refused_when_temp_folder_is_short(svc, trashed, free):
    path, parsed = _pack7z(svc)
    free(5_000 * MiB, temp=1 * MiB)
    res = svc.extract([(path, parsed)])
    assert res["no_space"]["free"] == 1 * MiB
    assert res["no_space"]["need"] == 1030 + diskspace.MARGIN
    assert _names(svc.cfg.output_path) == []
    assert _names(tempfile.gettempdir()) == []
    assert _counts(svc) == {"packs": 0, "tracks": 0, "track_sources": 0}
    assert path.exists() and trashed == []


def test_7z_with_room_extracts(svc, trashed, free):
    path, parsed = _pack7z(svc)
    free(5_000 * MiB)
    res = svc.extract([(path, parsed)])
    assert "no_space" not in res and res["tracks"] == 3


def test_unpack_stops_on_a_full_disk(svc, trashed, free, monkeypatch):
    svc.cfg.auto_backup_after_extract = True
    path, parsed = _pack(svc)
    free(5_000 * MiB)
    written = []
    real_open = Path.open

    class FullAfterSomeBytes:
        def __init__(self, f):
            self.f = f

        def write(self, b):
            self.f.write(b[:5])
            self.f.flush()
            written.append(self.f.tell())
            raise _enospc()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.f.close()

    def fake_open(self, mode="r", *a, **k):
        f = real_open(self, mode, *a, **k)
        if self.name == "2 C - D.osz.part" and "w" in mode:
            return FullAfterSomeBytes(f)
        return f

    monkeypatch.setattr(Path, "open", fake_open)
    res = svc.extract([(path, parsed)])
    assert written == [5]                                   # bytes reached the .part
    out = svc.cfg.output_path
    assert not list(out.glob("*.part"))
    assert (out / "1 A - B.osz").exists()
    assert svc.db.find_track_row(1, "1 A - B.osz") is not None
    assert not (out / "2 C - D.osz").exists()
    assert not (out / "3 E - F.osz").exists()               # never attempted
    assert path.exists() and trashed == []
    assert res["disk_full"] is True and res["kept"] == 1
    assert "backup" not in res
    assert _names(svc.cfg.library_path) == []               # auto-copy skipped
    assert any("disk is full" in w for w in svc.log.warns)


def test_7z_staging_disk_full_stops_unpack(svc, trashed, free, monkeypatch):
    # py7zr passes the OSError(ENOSPC) from its own writes through unwrapped
    # (checked by hand on a 256 KiB tmpfs), so the staging failure is seen too.
    path, parsed = _pack7z(svc)
    free(5_000 * MiB)

    def full(self, path=None, **k):
        (Path(path) / "partial").write_bytes(b"z" * 5)
        raise _enospc()

    monkeypatch.setattr(py7zr.SevenZipFile, "extractall", full)
    res = svc.extract([(path, parsed)])
    assert res["disk_full"] is True
    assert path.exists() and trashed == []
    assert _names(svc.cfg.output_path) == []
    assert _names(tempfile.gettempdir()) == []              # staging cleaned up


# -- Copy to Library ----------------------------------------------------------
def _output(svc, files=(("1 A - B.osz", b"a" * 100), ("2 C - D.osz", b"c" * 300))):
    for name, data in files:
        (svc.cfg.output_path / name).write_bytes(data)
    return {name: data for name, data in files}


def _copy(svc, physical=True):
    return library.copy_to_library(svc.cfg.output_path, svc.cfg.library_path, svc.db,
                                   "2026-01-01", physical_copy=physical)


def _assert_output(svc, files):
    for name, data in files.items():
        assert (svc.cfg.output_path / name).read_bytes() == data


def test_copy_refused_up_front(svc, free):
    files = _output(svc)
    before = _counts(svc)
    free(1 * MiB)
    with pytest.raises(diskspace.NotEnoughSpace) as ei:
        _copy(svc)
    assert ei.value.need == 400 + diskspace.MARGIN and ei.value.free == 1 * MiB
    assert not [n for n in _names(svc.cfg.library_path) if n.endswith((".osz", ".part"))]
    assert _counts(svc) == before
    _assert_output(svc, files)
    res = svc.copy_library()
    assert res["no_space"] == {"drive": ei.value.drive, "need": ei.value.need,
                               "free": 1 * MiB}
    assert res["new"] == 0 and res["duplicates"] == 0 and res["dup_ids"] == []


def test_no_check_when_nothing_is_copied(svc, free):
    files = _output(svc)
    svc.cfg.library_path.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (svc.cfg.library_path / name).write_bytes(data)
    free(0)
    assert _copy(svc)["duplicates"] == 2
    (svc.cfg.library_path / "1 A - B.osz").unlink()
    _copy(svc, physical=False)                              # memory-only: no check


def _failing_copy2(monkeypatch, exc, when=lambda dst: True):
    real = shutil.copy2

    def fake(src, dst, *a, **k):
        if when(Path(dst)):
            Path(dst).write_bytes(b"partial")
            raise exc
        return real(src, dst, *a, **k)

    monkeypatch.setattr(library.shutil, "copy2", fake)


def test_copy_stops_on_a_full_disk(svc, free, monkeypatch):
    files = _output(svc)
    free(5_000 * MiB)
    _failing_copy2(monkeypatch, _enospc(), when=lambda d: d.name.startswith("2 "))
    with pytest.raises(OSError) as ei:
        _copy(svc)
    assert ei.value.errno == errno.ENOSPC
    lib = svc.cfg.library_path
    assert _names(lib) == ["1 A - B.osz"]
    assert (lib / "1 A - B.osz").read_bytes() == files["1 A - B.osz"]
    assert svc.db.find_track_row(1, "1 A - B.osz")["in_library"] == 1
    _assert_output(svc, files)
    assert svc.copy_library() == {"new": 0, "duplicates": 0, "dup_ids": [],
                                  "disk_full": True}
    assert not list(lib.glob("*.part"))


@pytest.mark.parametrize("exc", [_enospc(), PermissionError(errno.EACCES, "denied")])
def test_refresh_failure_keeps_the_old_library_file(svc, free, monkeypatch, exc):
    lib = svc.cfg.library_path
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "1 A - B.osz").write_bytes(b"X" * 50)
    files = _output(svc, files=(("1 A - B.osz", b"Y" * 80),))
    free(5_000 * MiB)
    _failing_copy2(monkeypatch, exc)
    with pytest.raises(type(exc)):
        _copy(svc)
    assert (lib / "1 A - B.osz").read_bytes() == b"X" * 50
    assert _names(lib) == ["1 A - B.osz"]
    _assert_output(svc, files)


def test_other_copy_errors_still_propagate(svc, free, monkeypatch):
    _output(svc)
    free(5_000 * MiB)
    _failing_copy2(monkeypatch, PermissionError(errno.EACCES, "denied"))
    with pytest.raises(PermissionError):
        svc.copy_library()


# -- Dashboard ----------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def test_dashboard_shows_space_messages(qapp, tmp_path, monkeypatch):
    from rosu.app import AppContext
    from rosu.ui import dashboard_tab
    from rosu.ui.main_window import MainWindow
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.check_updates = False
    ctx = AppContext(cfg)
    win = MainWindow(ctx, qapp)
    warned = []
    monkeypatch.setattr(dashboard_tab.QMessageBox, "warning",
                        lambda *a, **k: warned.append(a))
    d, t = win.dashboard, ctx.t
    ns = {"drive": "D:\\", "need": 300 * MiB, "free": 1 * MiB}
    base = {"packs": 1, "tracks": 1, "rejected": [], "loose": 0, "kept": 0}
    keys = ("disk_no_space", "extract_disk_full", "library_disk_full",
            "library_done", "extract_done")
    try:
        for lang in ("en", "tr"):
            ctx.i18n.set_language(lang)
            no_space = t("disk_no_space", drive="D:\\", need=dashboard_tab._fmt_size(300 * MiB),
                         free=dashboard_tab._fmt_size(1 * MiB))
            done = t("extract_done", packs=1, tracks=1)
            cases = [
                (d._after_extract, {**base, "packs": 0, "tracks": 0, "kept": 1,
                                    "no_space": ns}, no_space),
                (d._after_extract, {**base, "kept": 1, "disk_full": True},
                 done + "  " + t("disposal_kept", n=1) + "  " + t("extract_disk_full")),
                (d._after_extract, {**base, "backup": {"new": 0, "duplicates": 0,
                                                       "dup_ids": [], "no_space": ns}},
                 done + "  " + no_space),
                (d._after_extract, {**base, "backup": {"new": 0, "duplicates": 0,
                                                       "dup_ids": [], "disk_full": True}},
                 done + "  " + t("library_disk_full")),
                (d._after_copy, {"new": 0, "duplicates": 0, "dup_ids": [],
                                 "no_space": ns}, no_space),
                (d._after_copy, {"new": 0, "duplicates": 0, "dup_ids": [],
                                 "disk_full": True}, t("library_disk_full")),
            ]
            for handler, result, expected in cases:
                warned.clear()
                handler(result)
                text = d.status.text()
                assert text == expected
                assert not any(k in text for k in keys)
                assert len(warned) == 1
            if lang == "tr":
                assert "boş" in no_space          # really Turkish, not the en fallback
    finally:
        ctx.i18n.set_language("en")
        win.close()
        ctx.db.close()
