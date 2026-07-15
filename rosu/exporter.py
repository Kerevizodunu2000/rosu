# SPDX-License-Identifier: GPL-3.0-or-later
"""Export a set of Library files into one or more portable archive volumes.

Bulk-exporting many ``.osz`` for sharing or backup needs the mirror image of
:mod:`rosu.drive.bundle`: instead of packing tracks into fixed-size chunks for
upload, this groups arbitrary files into a single archive, or splits them
across several ``.partNN`` volumes capped at ``split_bytes`` (so the export
fits removable media, an email attachment limit, etc.). Members are stored
flat by basename; a basename collision (two source files sharing a name from
different folders) is disambiguated by appending `` (2)``, `` (3)``, ... so
nothing is silently overwritten.

Filesystem-touching but dependency-free for zip (stdlib zipfile); py7zr is
imported lazily, only when ``fmt="7z"`` is requested. Unit-tested by building
real files under tmp_path.
"""
from __future__ import annotations

import zipfile
from pathlib import Path


def plan_volumes(sizes: list[int], split_bytes: int | None) -> list[list[int]]:
    """Group item indices (0..len(sizes)-1) into volumes whose summed size
    stays under ``split_bytes``, preserving input order.

    A single item larger than ``split_bytes`` gets its own volume (a file is
    never split across volumes). ``split_bytes`` of ``None`` or <= 0 means "no
    splitting": every index goes into one volume. Empty ``sizes`` -> ``[]``.
    """
    if not sizes:
        return []
    if split_bytes is None or split_bytes <= 0:
        return [list(range(len(sizes)))]
    volumes: list[list[int]] = []
    cur: list[int] = []
    cur_size = 0
    for i, size in enumerate(sizes):
        if cur and cur_size + size > split_bytes:
            volumes.append(cur)
            cur, cur_size = [], 0
        cur.append(i)
        cur_size += size
    if cur:
        volumes.append(cur)
    return volumes


def _dedupe_basenames(paths: list[Path]) -> list[str]:
    """Resolve basename collisions across ``paths`` (order preserved): the
    first file with a given basename keeps it; later ones get `` (2)``,
    `` (3)``, ... appended before the suffix so nothing is overwritten."""
    used: set[str] = set()
    names: list[str] = []
    for p in paths:
        candidate = p.name
        if candidate in used:
            n = 2
            candidate = f"{p.stem} ({n}){p.suffix}"
            while candidate in used:
                n += 1
                candidate = f"{p.stem} ({n}){p.suffix}"
        used.add(candidate)
        names.append(candidate)
    return names


def _write_zip(members: list[tuple[str, Path]], out_path: Path) -> None:
    """Zip ``members`` (arcname, source path) into ``out_path`` atomically.

    ZIP_STORED (inputs are .osz, already compressed); writes to a ``.part``
    file first, replacing the target only on full success.
    """
    tmp = out_path.with_name(out_path.name + ".part")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            for name, path in members:
                z.write(path, arcname=name)
        tmp.replace(out_path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _write_7z(members: list[tuple[str, Path]], out_path: Path) -> None:
    """py7zr equivalent of :func:`_write_zip` (py7zr imported lazily)."""
    import py7zr

    tmp = out_path.with_name(out_path.name + ".part")
    try:
        with py7zr.SevenZipFile(tmp, "w") as z:
            for name, path in members:
                z.write(path, arcname=name)
        tmp.replace(out_path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def write_export(files: list[Path], dest_base: Path, fmt: str = "zip",
                 split_bytes: int | None = None, progress=None,
                 cancel=None) -> list[Path]:
    """Archive ``files`` into a single archive, or several ``.partNN`` volumes
    when ``split_bytes`` forces a split. Returns the written archive Paths in
    order.

    Files that don't exist are skipped silently; an empty (or all-missing)
    ``files`` writes nothing and returns ``[]``. Members are stored flat by
    basename (collisions disambiguated, see :func:`_dedupe_basenames`). Each
    archive is written to a ``.part`` temp file then swapped into place, so a
    crash mid-write never leaves a half-written export. If ``progress`` is
    given, it is called after every member with
    ``{"kind": "export", "done", "total", "name"}``. ``cancel`` (a no-arg
    predicate) is polled before each volume; when it returns True writing stops
    and the volumes finished so far are returned.
    """
    if fmt not in ("zip", "7z"):
        raise ValueError(f"unsupported export format: {fmt!r}")
    dest_base = Path(dest_base)
    existing = [Path(f) for f in files if Path(f).exists()]
    if not existing:
        return []

    sizes = [p.stat().st_size for p in existing]
    volumes = plan_volumes(sizes, split_bytes)
    names = _dedupe_basenames(existing)
    write_one = _write_zip if fmt == "zip" else _write_7z
    suffix = ".zip" if fmt == "zip" else ".7z"

    dest_base.parent.mkdir(parents=True, exist_ok=True)
    single = len(volumes) == 1
    # Zero-padded so "part2" never sorts after "part10"; at least 2 digits.
    width = max(2, len(str(len(volumes))))

    written: list[Path] = []
    total = len(existing)
    done = 0
    for vol_num, vol in enumerate(volumes, start=1):
        if cancel is not None and cancel():
            break
        if single:
            out_path = dest_base.with_suffix(suffix)
        else:
            out_path = dest_base.parent / (
                f"{dest_base.stem}.part{vol_num:0{width}d}{suffix}")
        members = [(names[i], existing[i]) for i in vol]
        write_one(members, out_path)
        written.append(out_path)
        for name, _ in members:
            done += 1
            if progress:
                progress({"kind": "export", "done": done, "total": total,
                          "name": name})
    return written
