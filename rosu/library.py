# SPDX-License-Identifier: GPL-3.0-or-later
"""Copy Output -> Library with deduplication, and refresh/disappearance tracking.

Deduplication key is the beatmapset id (falling back to filename when a .osz has
no numeric prefix). A duplicate is never stored as ``name 01.osz`` / ``02`` —
instead the track's ``copy_attempts`` counter is incremented and the file is
left untouched.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from .osz_meta import read_osz_meta
from .parsing import parse_osz_entry


def _scan_osz(folder: Path):
    """Yield ``(path, ParsedTrack)`` for every .osz directly in ``folder``."""
    folder = Path(folder)
    if not folder.exists():
        return
    for p in sorted(folder.glob("*.osz")):
        t = parse_osz_entry(p.name, p.stat().st_size)
        if t is not None:
            yield p, t


def copy_to_library(output_dir: Path, library_dir: Path, db, when: str,
                    physical_copy: bool = True,
                    progress: Callable[[str], None] | None = None,
                    source_label: str | None = None) -> dict:
    """Copy new beatmaps from Output into Library; dedup the rest.

    A set counts as a duplicate when it is already in the Library either by
    beatmapset-id membership (the ``already`` flag) OR by a byte-identical file
    already present at the target. The id check catches client re-exports (osu!lazer
    produces different bytes/filenames than the stored copy, which a size-only check
    would miscount as "new"); the byte check catches files already on disk whose DB
    row isn't flagged yet, e.g. manual/restored copies (item 7).

    When ``source_label`` is given (e.g. ``local_osu_lazer``), each imported set is
    tagged with a synthetic source pack so its provenance shows in the Sources
    column (item 9).

    Returns ``{"new": int, "duplicates": int, "dup_ids": [...]}``.
    """
    library_dir = Path(library_dir)
    library_dir.mkdir(parents=True, exist_ok=True)

    local_pack_id = None
    if source_label:
        # Use the stable code itself as the label (language-neutral; shown verbatim in
        # the Sources column). No English pretty-name to leak into other locales.
        local_pack_id = db.get_or_create_local_pack(source_label)

    new = 0
    duplicates = 0
    dup_ids: list = []

    for src_path, t in _scan_osz(output_dir):
        # Ensure the track is in memory (adds the name even if physical copy off).
        track_id, _is_new = db.upsert_track(t, when)
        row = db.find_track_row(t.beatmapset_id, t.filename)
        already = bool(row and row["in_library"] == 1)  # library membership per the DB

        db.bump_copy_attempt(track_id)
        if local_pack_id is not None:
            db.add_track_source(track_id, local_pack_id, None, when)

        if physical_copy:
            target = library_dir / t.filename
            same_file = (target.exists()
                         and target.stat().st_size == src_path.stat().st_size)
            if not same_file:
                shutil.copy2(src_path, target)   # new file, or refreshed on size change
            db.set_library_state(track_id, True, "present", when)
            # A byte-identical file already in Library is an existing copy even if the
            # DB row wasn't flagged yet (manual/restored files) — don't count it new.
            already = already or same_file
        elif not already:  # memory-only mode: only newly-tracked sets change state
            db.set_library_state(track_id, True, "memory", when)

        if already:
            duplicates += 1
            dup_ids.append(t.beatmapset_id if t.beatmapset_id is not None
                           else t.filename)
        else:
            new += 1

        if progress:
            progress(t.filename)

    return {"new": new, "duplicates": duplicates, "dup_ids": dup_ids}


def refresh_library(library_dir: Path, db, when: str,
                    progress: Callable[[str], None] | None = None) -> dict:
    """Reconcile memory with the actual .osz files in the Library folder.

    * files present but unknown  -> added to memory (manual additions),
    * files that had a physical copy and are now gone -> marked "disappeared",
    * files that reappeared -> marked "present" again.

    Returns ``{"added": int, "disappeared": int, "present": int}``.
    """
    added = 0
    enriched = 0
    present_keys: set = set()

    for path, t in _scan_osz(library_dir):
        key = t.beatmapset_id if t.beatmapset_id is not None else t.filename
        present_keys.add(key)
        row = db.find_track_row(t.beatmapset_id, t.filename)
        if row is None:
            # manually-added file: read its metadata too
            track_id, _ = db.upsert_track(t, when, read_osz_meta(path))
            db.set_library_state(track_id, True, "present", when)
            added += 1
        else:
            # backfill metadata for tracks imported before metadata existed
            if row["bpm"] is None and row["mode"] is None:
                db.upsert_track(t, when, read_osz_meta(path))
                enriched += 1
            if row["library_status"] != "present" or row["in_library"] != 1:
                db.set_library_state(row["id"], True, "present", when)
        if progress:
            progress(t.filename)

    # Detect disappearances: tracks that previously had a physical copy but whose
    # file is no longer in the Library folder.
    disappeared = 0
    for tr in db.library_tracks():
        if tr["library_status"] != "present":
            continue  # memory-only entries never "disappear"
        key = tr["beatmapset_id"] if tr["beatmapset_id"] is not None else tr["filename"]
        if key not in present_keys:
            db.set_library_state(tr["id"], False, "disappeared", when)
            disappeared += 1

    return {"added": added, "disappeared": disappeared, "enriched": enriched,
            "present": len(present_keys)}
