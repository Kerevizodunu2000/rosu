# SPDX-License-Identifier: GPL-3.0-or-later
"""Copy Output -> Library with deduplication, and refresh/disappearance tracking.

Deduplication key is the beatmapset id (falling back to filename when a .osz has
no numeric prefix). A duplicate is never stored as ``name 01.osz`` / ``02`` —
instead the track's ``copy_attempts`` counter is incremented and the file is
left untouched.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Callable

from . import msd, ratings
from .beatmap import read_osz_full
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
                    source_label: str | None = None,
                    auto_prune: bool = False,
                    prune_mode: str = "video_only") -> dict:
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
    from_osu = bool(source_label and source_label.startswith("local_osu"))
    osu_client = ("stable" if source_label == "local_osu_stable"
                  else "lazer" if source_label == "local_osu_lazer" else None)
    if source_label:
        # Use the stable code itself as the label (language-neutral; shown verbatim in
        # the Sources column). No English pretty-name to leak into other locales.
        local_pack_id = db.get_or_create_local_pack(source_label)

    new = 0
    duplicates = 0
    dup_ids: list = []

    for src_path, t in _scan_osz(output_dir):
        # Ensure the track is in memory (adds the name even if physical copy off).
        track_id = _upsert_with_meta(db, src_path, t, when)
        row = db.find_track_row(t.beatmapset_id, t.filename)
        already = bool(row and row["in_library"] == 1)  # library membership per the DB

        db.bump_copy_attempt(track_id)
        if local_pack_id is not None:
            db.add_track_source(track_id, local_pack_id, None, when)
        if from_osu and t.beatmapset_id is not None:
            # imported straight out of an osu! client -> it IS in that client
            db.set_in_osu(t.beatmapset_id, client=osu_client)

        if physical_copy:
            target = library_dir / t.filename
            
            is_pruned = False
            original_size = None
            if row:
                # use try-except in case column is missing before migrations
                try:
                    is_pruned = bool(row["is_pruned"])
                    original_size = row["original_size"]
                except IndexError:
                    pass
            
            
            same_file = False
            if target.exists():
                st_size = target.stat().st_size
                if st_size == src_path.stat().st_size:
                    same_file = True
                elif is_pruned and original_size == src_path.stat().st_size:
                    same_file = True
            
            if not same_file:
                if is_pruned and target.exists():
                    # Do not overwrite an already pruned target with an unpruned version
                    pass
                else:
                    shutil.copy2(src_path, target)   # new file, or refreshed on size change
                    if auto_prune:
                        from .prune import prune_osz
                        original_size_before = target.stat().st_size
                        freed = prune_osz(target, mode=prune_mode)
                        if freed > 0:
                            db.set_pruned_state(track_id, True, original_size_before,
                                                when=when, mode=prune_mode)
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


def _upsert_with_meta(db, src_path: Path, t, when: str) -> int:
    """Record ``t`` and, if its difficulties were never parsed, parse them now.

    Sets unpacked from Output were parsed at extraction, but a set imported
    straight out of osu!(stable)/osu!lazer arrived here as a bare name: its Mode,
    Keys, Star, BPM and length stayed blank in Search until a "Refresh Library",
    and forever when physical copies are off (Refresh only reads the Library
    folder). The source ``.osz`` is still in hand, so read it once.
    """
    row = db.find_track_row(t.beatmapset_id, t.filename)
    if row is not None and row["diffs_scanned_at"]:
        return db.upsert_track(t, when)[0]
    meta, diffs, raw = read_osz_full(src_path)
    track_id, _ = db.upsert_track(t, when, meta)
    if diffs:   # an unreadable archive stays unscanned so Refresh can retry it
        db.upsert_difficulties(track_id, diffs, ratings.stars_for_diffs(diffs, raw), when)
        db.apply_msd(track_id, msd.msd_for_diffs(diffs, raw), when)
    return track_id


def refresh_library(library_dir: Path, db, when: str,
                    progress: Callable[[str], None] | None = None) -> dict:
    """Reconcile memory with the actual .osz files in the Library folder.

    * files present but unknown  -> added to memory (manual additions),
    * files that had a physical copy and are now gone -> marked "disappeared",
    * files that reappeared -> marked "present" again.

    A set that fails is skipped (the rest still refresh); a database error stops
    the refresh.

    Returns ``{"added", "disappeared", "enriched", "present": int, "skipped":
    [{"file", "error"}]}``.
    """
    added = 0
    enriched = 0
    skipped: list[dict] = []
    present_keys: set = set()

    for path, t in _scan_osz(library_dir):
        key = t.beatmapset_id if t.beatmapset_id is not None else t.filename
        present_keys.add(key)   # before the guarded work: a skipped set is still on disk
        try:
            row = db.find_track_row(t.beatmapset_id, t.filename)
            if row is None:
                # manually-added file: read its metadata + per-difficulty data
                meta, diffs, raw = read_osz_full(path)
                track_id, _ = db.upsert_track(t, when, meta)
                db.upsert_difficulties(
                    track_id, diffs, ratings.stars_for_diffs(diffs, raw), when)
                db.apply_msd(track_id, msd.msd_for_diffs(diffs, raw), when)
                db.set_library_state(track_id, True, "present", when)
                added += 1
            else:
                # backfill metadata (imported before it existed) and/or difficulties
                # (imported before v1.5). A single full read covers both.
                needs_meta = row["bpm"] is None and row["mode"] is None
                needs_diffs = not row["diffs_scanned_at"]
                if needs_meta or needs_diffs:
                    meta, diffs, raw = read_osz_full(path)
                    if needs_meta:
                        db.upsert_track(t, when, meta)
                        enriched += 1
                    db.upsert_difficulties(
                        row["id"], diffs, ratings.stars_for_diffs(diffs, raw), when)
                    db.apply_msd(row["id"], msd.msd_for_diffs(diffs, raw), when)
                if row["library_status"] != "present" or row["in_library"] != 1:
                    db.set_library_state(row["id"], True, "present", when)
        except sqlite3.DatabaseError:
            raise   # a database failure stops the refresh; only a bad set is skipped
        except Exception as exc:
            skipped.append({"file": t.filename, "error": type(exc).__name__})
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
            "present": len(present_keys), "skipped": skipped}


def plan_library_dedup(entries: list[dict]) -> list[str]:
    """Decide which redundant duplicate ``.osz`` to remove from the Library.

    Entries sharing a ``beatmapset_id`` are duplicates (e.g. ``"123 A - B.osz"``
    plus a manual copy ``"123 A - B (1).osz"``). We keep the one whose name matches
    the DB-canonical ``canonical`` filename and remove the rest. A group with NO
    canonical file present is left untouched — removing one would orphan the DB row
    (those surface in Library Health instead). ``beatmapset_id`` ``None`` is never a
    duplicate (filename-keyed, inherently unique). Returns the names to remove.
    """
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for e in entries:
        bid = e.get("beatmapset_id")
        if bid is None:
            continue
        groups[bid].append(e)
    remove: list[str] = []
    for items in groups.values():
        if len(items) < 2:
            continue
        keeper = next((it for it in items
                       if it.get("canonical") and it["name"] == it["canonical"]),
                      None)
        if keeper is None:
            continue   # no canonical file to keep → leave the whole group alone
        remove.extend(it["name"] for it in items if it is not keeper)
    return remove
