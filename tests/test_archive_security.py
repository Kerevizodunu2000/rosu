# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the shared archive-security guard (item A, v1.0).

SAFETY: these tests never create or extract a real zip-bomb. The bomb cases use
an in-memory *stub reader* that merely reports fabricated member sizes/counts as
plain integers — no oversized file is ever written and nothing is decompressed.
The only real archives built here are a few-hundred-byte happy-path zip and a
tiny zip whose member is *named* with ``../`` (a harmless string; extraction is
refused before any byte is written).
"""
import zipfile

import pytest

from rosu import archives, extractor
from rosu.archives import Member
from rosu.db import Database
from rosu.parsing import parse_pack_name


class _StubReader:
    """A fake archive reader: reports the given members + compressed size without
    touching the disk. Lets us exercise the guard's thresholds with pure data."""

    def __init__(self, members, compressed=1_000_000):
        self._members = members
        self._compressed = compressed

    def members(self):
        return self._members

    def compressed_size(self):
        return self._compressed


# -- _unsafe_member_name --------------------------------------------------------
@pytest.mark.parametrize("name", [
    "../evil.osz", "a/../../evil.osz", "/abs/evil.osz", "\\abs\\evil.osz",
    "C:/Windows/evil.osz", "C:evil.osz",
])
def test_unsafe_member_names_flagged(name):
    assert archives._unsafe_member_name(name) is True


@pytest.mark.parametrize("name", [
    "12345 Artist - Song.osz", "osu!mania/67890 A - B.osz", "readme.txt",
    "sub/folder/ok.osz",
])
def test_safe_member_names_pass(name):
    assert archives._unsafe_member_name(name) is False


# -- security_scan: pure threshold checks (no real bombs) -----------------------
def test_scan_passes_normal_archive():
    r = _StubReader([Member("111 A - B.osz", 5_000_000),
                     Member("222 C - D.osz", 6_000_000)], compressed=10_000_000)
    result = archives.security_scan(r)
    assert result.entries == 2
    assert result.total_bytes == 11_000_000


def test_scan_rejects_too_many_entries():
    members = [Member(f"{i} X - Y.osz", 10) for i in range(archives.MAX_ENTRIES + 1)]
    with pytest.raises(archives.ArchiveTooLarge) as exc:
        archives.security_scan(_StubReader(members))
    assert exc.value.reason == "entries"


def test_scan_rejects_oversize_total():
    # Two members whose *reported* sizes sum past the ceiling — no real data.
    half = archives.MAX_TOTAL_BYTES // 2 + 1
    members = [Member("a.osz", half), Member("b.osz", half)]
    with pytest.raises(archives.ArchiveTooLarge) as exc:
        archives.security_scan(_StubReader(members, compressed=archives.MAX_TOTAL_BYTES))
    assert exc.value.reason == "total"


def test_scan_rejects_high_ratio():
    # Tiny compressed size vs a large reported uncompressed total = classic bomb
    # signature — expressed purely as numbers.
    r = _StubReader([Member("a.osz", 1_000_000)], compressed=100)
    with pytest.raises(archives.ArchiveTooLarge) as exc:
        archives.security_scan(r)
    assert exc.value.reason == "ratio"


def test_scan_rejects_traversal_member():
    r = _StubReader([Member("../escape.osz", 10)])
    with pytest.raises(archives.ArchiveUnsafePath) as exc:
        archives.security_scan(r)
    assert exc.value.reason == "path"


def test_scan_ignores_ratio_when_no_compressed_info():
    # compressed_size() == 0 must not divide-by-zero or false-trigger.
    r = _StubReader([Member("a.osz", 1_000_000)], compressed=0)
    result = archives.security_scan(r)
    assert result.ratio == 0.0


def test_scan_fails_closed_when_compressed_size_unreadable():
    # An OSError from compressed_size() used to silently degrade to 0, skipping
    # the ratio check entirely — the scan must refuse the archive instead.
    class _BrokenStat(_StubReader):
        def compressed_size(self):
            raise OSError("stat failed")

    r = _BrokenStat([Member("a.osz", 1_000_000)])
    with pytest.raises(archives.UnsafeArchive) as exc:
        archives.security_scan(r)
    assert exc.value.reason == "ratio"


# -- real (harmless) archives ---------------------------------------------------
def _make_clean_zip(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("12345 Artist - Song.osz", b"fake-osz-bytes")
        z.writestr("readme.txt", b"hello")


def test_real_clean_zip_scans_ok(tmp_path):
    p = tmp_path / "S1 - Pack.zip"
    _make_clean_zip(p)
    with archives.open_reader(p) as r:
        result = archives.security_scan(r)
    assert result.entries == 2


def test_extract_pack_rejects_traversal_named_member(tmp_path):
    """A tiny zip whose member is *named* '../…' is refused, and nothing is
    written outside (or inside) the Output dir. No payload is extracted."""
    p = tmp_path / "S9 - Bad.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("../12345 Evil - Escape.osz", b"x")  # harmless bytes
    out = tmp_path / "Output"
    db = Database(tmp_path / "m.db")
    parsed = parse_pack_name(p.name)
    try:
        with pytest.raises(archives.UnsafeArchive):
            extractor.extract_pack(p, parsed, out, db, "2026-01-01T00:00:00",
                                   read_meta=False)
        # extraction refused before writing: no escaped file next to Output
        assert not (tmp_path / "12345 Evil - Escape.osz").exists()
    finally:
        db.close()
