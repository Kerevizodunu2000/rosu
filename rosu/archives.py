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
_MAX_STAGE_BYTES = 30 * 1024 ** 3

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

    def open(self, name: str) -> BinaryIO:
        return self._z.open(name)

    def close(self) -> None:
        self._z.close()


class _TarReader:
    def __init__(self, path: Path):
        self._t = tarfile.open(path)  # mode "r:*" auto-detects compression

    def members(self) -> list[Member]:
        return [Member(m.name, m.size) for m in self._t.getmembers() if m.isfile()]

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

    def _stage(self) -> None:
        import py7zr
        # Defense-in-depth against py7zr path-traversal CVEs (CVE-2022-44900,
        # CVE-2026-23879): validate every member name and the total size BEFORE
        # extracting, since extractall() writes the whole archive at once.
        total = 0
        with py7zr.SevenZipFile(self._path) as z:
            for f in z.list():
                if getattr(f, "is_directory", False):
                    continue
                name = f.filename or ""
                norm = name.replace("\\", "/")
                if norm.startswith("/") or ".." in norm.split("/") or ":" in name:
                    raise ValueError(f"unsafe 7z member: {name!r}")
                total += getattr(f, "uncompressed", 0) or 0
        if total > _MAX_STAGE_BYTES:
            raise ValueError(f"7z archive too large to unpack ({total} bytes)")
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
