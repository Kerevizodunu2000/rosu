"""Scan, pre-check and extract pack .zip archives into the flat Output folder.

Extraction is *flat*: every ``.osz`` inside a pack lands directly in Output,
even when the pack nested it under a mode folder (``osu!/``, ``osu!mania/``).
The originating subfolder is still recorded in the database so we remember where
each beatmap came from.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Callable

from .models import ExtractPlan, ParsedPack, ParsedTrack
from .osz_meta import read_osz_meta
from .parsing import parse_osz_entry, parse_pack_name

_CHUNK = 1 << 20  # 1 MiB streaming buffer


def scan_packs(packs_dir: Path) -> list[tuple[Path, ParsedPack]]:
    """Return ``(zip_path, ParsedPack)`` for every parseable .zip in Packs/."""
    packs_dir = Path(packs_dir)
    out: list[tuple[Path, ParsedPack]] = []
    if not packs_dir.exists():
        return out
    for entry in sorted(packs_dir.glob("*.zip")):
        parsed = parse_pack_name(entry.name)
        if parsed is not None:
            out.append((entry, parsed))
    return out


def read_osz_entries(zip_path: Path) -> list[ParsedTrack]:
    """List the .osz entries of a pack without extracting them."""
    tracks: list[ParsedTrack] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            t = parse_osz_entry(info.filename, info.file_size)
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


def extract_pack(zip_path: Path, parsed: ParsedPack, output_dir: Path, db,
                 when: str,
                 progress: Callable[[str, str], None] | None = None,
                 read_meta: bool = True, log=None) -> dict:
    """Extract one pack flat into Output and record it in the database.

    ``progress`` is called as ``progress(pack_name, osz_name)`` for each file.
    Each .osz is best-effort: a broken entry is logged and skipped, never
    stopping the extraction. Returns ``{"tracks": int, "subfolders": [..]}``.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    entries = read_osz_entries(zip_path)
    pack_id = db.upsert_pack(parsed, len(entries), when)

    subfolders: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            t = parse_osz_entry(info.filename, info.file_size)
            if t is None:
                continue
            try:
                if t.subfolder:
                    subfolders.add(t.subfolder)
                target = output_dir / t.filename
                if not (target.exists() and target.stat().st_size == info.file_size):
                    _stream_extract(zf, info, target)
                meta = read_osz_meta(target) if read_meta else None
                track_id, _is_new = db.upsert_track(t, when, meta)
                db.add_track_source(track_id, pack_id, t.subfolder, when)
            except Exception as exc:  # keep going on a single bad beatmap
                if log is not None:
                    log.log("ERROR", "WARN", "", where=f"extract:{parsed.code}",
                            detail=f"{t.filename}: {exc}")
            if progress:
                progress(parsed.full_name, t.filename)

    return {"tracks": len(entries), "subfolders": sorted(subfolders)}


def _stream_extract(zf: zipfile.ZipFile, info: zipfile.ZipInfo, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".part")
    with zf.open(info) as src, tmp.open("wb") as dst:
        while True:
            chunk = src.read(_CHUNK)
            if not chunk:
                break
            dst.write(chunk)
    tmp.replace(target)


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
        if dest.exists():
            dest.unlink()
        zip_path.replace(dest)
        return "ZIP_MOVED"
    # default: Recycle Bin
    from send2trash import send2trash
    send2trash(str(zip_path))
    return "ZIP_TRASHED"
