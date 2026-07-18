# SPDX-License-Identifier: GPL-3.0-or-later
"""Scan, pre-check and extract pack .zip archives into the flat Output folder.

Extraction is *flat*: every ``.osz`` inside a pack lands directly in Output,
even when the pack nested it under a mode folder (``osu!/``, ``osu!mania/``).
The originating subfolder is still recorded in the database so we remember where
each beatmap came from.
"""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Callable

from . import archives, ratings
from .beatmap import read_osz_full
from .models import ExtractPlan, ParsedPack, ParsedTrack
from .parsing import parse_osz_entry, parse_pack_name

_CHUNK = 1 << 20  # 1 MiB streaming buffer
_MAX_OSZ_BYTES = 500 * 1024 * 1024  # per-.osz cap (zip-bomb / disk-exhaustion guard)


def archive_dialog_filter() -> str:
    """A Qt file-dialog filter string covering the supported archive formats."""
    return archives.dialog_filter()


def scan_packs(packs_dir: Path) -> list[tuple[Path, ParsedPack]]:
    """Return ``(path, ParsedPack)`` for every parseable archive in Packs/
    (zip / 7z / tar.* — item 24)."""
    out: list[tuple[Path, ParsedPack]] = []
    for entry in archives.iter_archives(packs_dir):
        parsed = parse_pack_name(entry.name)
        if parsed is not None:
            out.append((entry, parsed))
    return out


def read_osz_entries(archive_path: Path) -> list[ParsedTrack]:
    """List the .osz entries of a pack without extracting them."""
    tracks: list[ParsedTrack] = []
    with archives.open_reader(archive_path) as r:
        for m in r.members():
            t = parse_osz_entry(m.name, m.size)
            if t is not None:
                tracks.append(t)
    return tracks


def prescan_pack(zip_path: Path, parsed: ParsedPack,
                 known_ids: set[int], known_before: bool) -> ExtractPlan:
    """Decide whether the pack is new / already fully known / partly missing.

    Drives the re-add confirmation dialog. ``known_ids`` is the set of
    beatmapset ids already in memory; ``known_before`` is whether the pack code
    was processed before.
    """
    tracks = read_osz_entries(zip_path)
    ids = [t.beatmapset_id for t in tracks if t.beatmapset_id is not None]
    new_ids = [i for i in ids if i not in known_ids]
    known = [i for i in ids if i in known_ids]

    if not known_before:
        kind = "new"
    elif not new_ids:
        kind = "all_present"
    else:
        kind = "some_missing"

    return ExtractPlan(
        parsed=parsed, zip_path=str(zip_path), track_ids=ids,
        known_before=known_before, new_ids=new_ids, known_ids=known, kind=kind,
    )


def extract_pack(archive_path: Path, parsed: ParsedPack, output_dir: Path, db,
                 when: str,
                 progress: Callable[[str, str], None] | None = None,
                 read_meta: bool = True, log=None, cancel=None) -> dict:
    """Extract one pack flat into Output and record it in the database.

    ``progress`` is called as ``progress(pack_name, osz_name)`` for each file.
    Each .osz is best-effort: a broken entry is logged and skipped, never
    stopping the extraction. Non-``.osz`` members are noted as ``extra_files``
    so a pack that also carried readmes/images can be flagged (item 25).
    Returns ``{"tracks": int, "subfolders": [..], "extra_files": [..]}``.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_resolved = output_dir.resolve()

    subfolders: set[str] = set()
    extra_files: list[str] = []
    with archives.open_reader(archive_path) as r:
        members = r.members()
        # Reject zip-bombs / path-traversal up front, before any DB write or
        # disk output, for every format (raises archives.UnsafeArchive).
        archives.security_scan(r, members=members)
        osz = [m for m in members if m.name.lower().endswith(".osz")]
        extra_files = [m.name for m in members if not m.name.lower().endswith(".osz")]
        pack_id = db.upsert_pack(parsed, len(osz), when)

        for m in osz:
            if cancel is not None and cancel():
                break
            t = parse_osz_entry(m.name, m.size)
            if t is None:
                continue
            try:
                if m.size and m.size > _MAX_OSZ_BYTES:
                    raise ValueError(f"oversize entry ({m.size} bytes)")
                if t.subfolder:
                    subfolders.add(t.subfolder)
                target = output_dir / t.filename
                # Security: never let a crafted entry name escape the Output dir.
                if target.resolve().parent != out_resolved:
                    raise ValueError(f"unsafe entry path: {t.filename!r}")
                if not (target.exists() and target.stat().st_size == m.size):
                    with r.open(m.name) as src:
                        _stream_copy(src, target, _MAX_OSZ_BYTES)
                if read_meta:
                    meta, diffs, raw = read_osz_full(target)
                    track_id, _is_new = db.upsert_track(t, when, meta)
                    db.upsert_difficulties(
                        track_id, diffs, ratings.stars_for_diffs(diffs, raw), when)
                else:
                    track_id, _is_new = db.upsert_track(t, when, None)
                db.add_track_source(track_id, pack_id, t.subfolder, when)
            except Exception as exc:  # keep going on a single bad beatmap
                if log is not None:
                    log.log("ERROR", "WARN", "", where=f"extract:{parsed.code}",
                            detail=f"{t.filename}: {exc}")
            if progress:
                progress(parsed.full_name, t.filename)

    return {"tracks": len(osz), "subfolders": sorted(subfolders),
            "extra_files": extra_files}


def _stream_copy(src: BinaryIO, target: Path, max_bytes: int | None = None) -> None:
    tmp = target.with_suffix(target.suffix + ".part")
    written = 0
    try:
        with tmp.open("wb") as dst:
            while True:
                chunk = src.read(_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if max_bytes is not None and written > max_bytes:
                    raise ValueError(f"entry exceeds size cap ({max_bytes} bytes)")
                dst.write(chunk)
        tmp.replace(target)
    except BaseException:
        tmp.unlink(missing_ok=True)  # never leave a half-written .part behind
        raise


def dispose_zip(zip_path: Path, mode: str, processed_dir: Path) -> str:
    """Recycle / move / delete a processed .zip. Returns the action code."""
    zip_path = Path(zip_path)
    if mode == "delete":
        zip_path.unlink(missing_ok=True)
        return "ZIP_DELETED"
    if mode == "move":
        processed_dir = Path(processed_dir)
        processed_dir.mkdir(parents=True, exist_ok=True)
        dest = processed_dir / zip_path.name
        n = 1
        while dest.exists():   # never clobber a different archive already here
            dest = processed_dir / f"{zip_path.stem}.{n}{zip_path.suffix}"
            n += 1
        zip_path.replace(dest)
        return "ZIP_MOVED"
    # default: Recycle Bin
    from send2trash import send2trash
    send2trash(str(zip_path))
    return "ZIP_TRASHED"
