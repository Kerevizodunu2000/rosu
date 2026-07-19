# SPDX-License-Identifier: GPL-3.0-or-later
"""Uniform read access to pack archives — zip, tar(.gz/.bz2/.xz) and 7z (item 24).

Extraction elsewhere only needs to (a) list the members and (b) stream a chosen
member out. This module hides the per-format differences behind one small reader
interface, so `extractor` stays format-agnostic:

    with open_reader(path) as r:
        for m in r.members():          # Member(name, size)
            with r.open(m.name) as fh:  # binary stream
                ...

zip and tar are stdlib. 7z uses py7zr (pure-Python); because 7z is a solid format
where per-member random access is slow, the 7z reader extracts once to a temp dir
on first access and serves members from there.
"""
from __future__ import annotations

import shutil
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

# Refuse to unpack a .7z whose declared uncompressed total is absurd (zip-bomb).
# Public name is reused by rosu.drive.bundle as an overall backup sanity ceiling.
MAX_STAGE_BYTES = 30 * 1024 ** 3
_MAX_STAGE_BYTES = MAX_STAGE_BYTES  # backwards-compatible private alias

# Aggregate anti-zip-bomb limits, enforced up-front for EVERY format by
# ``security_scan`` before a single byte is written to disk. 7z already had a
# total-uncompressed ceiling; zip and tar had only a per-entry stream cap, so a
# many-entry or high-ratio archive slipped through unchecked until extraction.
MAX_TOTAL_BYTES = MAX_STAGE_BYTES        # combined uncompressed ceiling (30 GiB)
MAX_ENTRIES = 50_000                     # refuse absurd member counts
MAX_RATIO = 200                          # uncompressed:compressed blow-up cap


class UnsafeArchive(Exception):
    """An archive was refused by the security scan (distinct from a read error).

    ``reason`` is a short machine tag (``entries`` / ``total`` / ``ratio`` /
    ``path``) so a caller can quarantine the pack and show a translated message.
    """
    reason = "unsafe"

    def __init__(self, message: str, *, reason: str | None = None):
        super().__init__(message)
        if reason:
            self.reason = reason


class ArchiveTooLarge(UnsafeArchive):
    """Total uncompressed size, entry count, or decompression ratio too high."""


class ArchiveUnsafePath(UnsafeArchive):
    """A member name tried to escape the extraction dir (traversal / absolute)."""
    reason = "path"


def _unsafe_member_name(name: str) -> bool:
    """True if a member path would escape the target dir (``..`` / absolute /
    drive-relative). Shared by ``security_scan`` and the 7z staging guard."""
    norm = (name or "").replace("\\", "/")
    return norm.startswith("/") or ".." in norm.split("/") or ":" in (name or "")

# suffix -> family. Longest suffixes are matched first (see archive_kind).
_SUFFIXES = {
    ".zip": "zip",
    ".7z": "7z",
    ".tar": "tar", ".tar.gz": "tar", ".tgz": "tar",
    ".tar.bz2": "tar", ".tbz2": "tar", ".tar.xz": "tar", ".txz": "tar",
}


@dataclass
class Member:
    name: str      # path inside the archive (may include subfolders)
    size: int


def archive_kind(name: str) -> str | None:
    low = str(name).lower()
    for suf in sorted(_SUFFIXES, key=len, reverse=True):
        if low.endswith(suf):
            return _SUFFIXES[suf]
    return None


def is_supported(name: str) -> bool:
    return archive_kind(name) is not None


def dialog_filter() -> str:
    """Qt file-dialog filter string covering every supported archive format."""
    pats = " ".join("*" + s for s in _SUFFIXES)
    return f"Archives ({pats})"


def iter_archives(folder: Path):
    """Yield every supported archive file directly under ``folder`` (sorted)."""
    folder = Path(folder)
    if not folder.exists():
        return
    for p in sorted(folder.iterdir()):
        if p.is_file() and is_supported(p.name):
            yield p


# --- readers ---------------------------------------------------------------
class _ZipReader:
    def __init__(self, path: Path):
        self._z = zipfile.ZipFile(path)

    def members(self) -> list[Member]:
        return [Member(i.filename, i.file_size)
                for i in self._z.infolist() if not i.is_dir()]

    def compressed_size(self) -> int:
        # zip stores per-entry compressed sizes — the tightest ratio signal.
        return sum(i.compress_size for i in self._z.infolist())

    def open(self, name: str) -> BinaryIO:
        return self._z.open(name)

    def close(self) -> None:
        self._z.close()


class _TarReader:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._t = tarfile.open(path)  # mode "r:*" auto-detects compression

    def members(self) -> list[Member]:
        return [Member(m.name, m.size) for m in self._t.getmembers() if m.isfile()]

    def compressed_size(self) -> int:
        # tar has no per-entry compressed size; use the on-disk archive size
        # (covers .tar.gz/.bz2/.xz stream compression) as the ratio denominator.
        return self._path.stat().st_size

    def open(self, name: str) -> BinaryIO:
        fh = self._t.extractfile(name)
        if fh is None:
            raise KeyError(name)
        return fh

    def close(self) -> None:
        self._t.close()


class _SevenReader:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._tmp: Path | None = None

    def members(self) -> list[Member]:
        import py7zr
        with py7zr.SevenZipFile(self._path) as z:
            out = []
            for f in z.list():
                if getattr(f, "is_directory", False):
                    continue
                out.append(Member(f.filename, getattr(f, "uncompressed", 0) or 0))
            return out

    def compressed_size(self) -> int:
        return self._path.stat().st_size

    def _stage(self) -> None:
        import py7zr
        # Defense-in-depth against py7zr path-traversal CVEs (CVE-2022-44900,
        # CVE-2026-23879): validate every member name and the total size BEFORE
        # extracting, since extractall() writes the whole archive at once. Uses
        # the same shared checks as security_scan so all formats stay consistent.
        total = 0
        with py7zr.SevenZipFile(self._path) as z:
            for f in z.list():
                if getattr(f, "is_directory", False):
                    continue
                name = f.filename or ""
                if _unsafe_member_name(name):
                    raise ArchiveUnsafePath(f"unsafe 7z member: {name!r}")
                total += getattr(f, "uncompressed", 0) or 0
        if total > MAX_TOTAL_BYTES:
            raise ArchiveTooLarge(
                f"7z archive too large to unpack ({total} bytes)", reason="total")
        self._tmp = Path(tempfile.mkdtemp(prefix="rosu7z_"))
        with py7zr.SevenZipFile(self._path) as z:
            z.extractall(path=str(self._tmp))

    def open(self, name: str) -> BinaryIO:
        if self._tmp is None:
            self._stage()  # one decompression, then serve members from disk
        return open(self._tmp / name, "rb")

    def close(self) -> None:
        if self._tmp is not None:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None


class ArchiveReader:
    """Context-managed wrapper around the format-specific reader."""

    def __init__(self, path: Path):
        kind = archive_kind(Path(path).name)
        if kind == "zip":
            self._r = _ZipReader(path)
        elif kind == "tar":
            self._r = _TarReader(path)
        elif kind == "7z":
            self._r = _SevenReader(path)
        else:
            raise ValueError(f"unsupported archive: {path}")

    def members(self) -> list[Member]:
        return self._r.members()

    def compressed_size(self) -> int:
        return self._r.compressed_size()

    def open(self, name: str) -> BinaryIO:
        return self._r.open(name)

    def close(self) -> None:
        self._r.close()

    def __enter__(self) -> "ArchiveReader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def open_reader(path: Path) -> ArchiveReader:
    return ArchiveReader(path)


@dataclass
class ScanResult:
    entries: int
    total_bytes: int
    compressed_bytes: int
    ratio: float


def security_scan(reader, *, members: list[Member] | None = None,
                  max_total: int = MAX_TOTAL_BYTES,
                  max_entries: int = MAX_ENTRIES,
                  max_ratio: int = MAX_RATIO) -> ScanResult:
    """Reject an archive *before* extraction if it looks like a zip-bomb or a
    path-traversal attempt; return a ``ScanResult`` when it is safe.

    Format-agnostic — works on any reader exposing ``members()`` +
    ``compressed_size()``. Raises ``ArchiveUnsafePath`` for an escaping member
    name and ``ArchiveTooLarge`` for an excessive entry count, uncompressed
    total, or decompression ratio. Reading metadata does not extract anything,
    so this stays cheap and never materialises the (potentially huge) payload.
    """
    if members is None:
        members = reader.members()
    count = len(members)
    if count > max_entries:
        raise ArchiveTooLarge(
            f"too many entries: {count} > {max_entries}", reason="entries")
    total = 0
    for m in members:
        if _unsafe_member_name(m.name):
            raise ArchiveUnsafePath(f"unsafe member path: {m.name!r}")
        total += m.size or 0
    if total > max_total:
        raise ArchiveTooLarge(
            f"uncompressed total {total} > {max_total}", reason="total")
    try:
        compressed = reader.compressed_size()
    except OSError as exc:
        # Fail closed: silently treating the size as 0 would skip the ratio
        # check entirely, letting a bomb through on the one path where the
        # denominator couldn't be read.
        raise UnsafeArchive(
            f"could not determine compressed size for ratio check: {exc}",
            reason="ratio") from exc
    ratio = (total / compressed) if compressed > 0 else 0.0
    if compressed > 0 and ratio > max_ratio:
        raise ArchiveTooLarge(
            f"decompression ratio {ratio:.0f}:1 exceeds {max_ratio}:1",
            reason="ratio")
    return ScanResult(count, total, compressed, ratio)
