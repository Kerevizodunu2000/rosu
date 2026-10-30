# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
import datetime as _dt
import time
from pathlib import Path

from .. import archives, client_remove, config, extractor, osu_import, parsing
from ..models import ExtractPlan, ParsedPack

_CLIENT_LABEL = {"lazer": "osu!lazer", "stable": "osu!(stable)"}

def now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()

def _sample_export(files, limit):
    if limit is None or limit <= 0 or len(files) <= limit:
        return files
    import random
    return random.sample(files, limit)


def _clear_osz(folder: Path) -> int:
    """Recycle every .osz in ``folder``; 0 (nothing touched) when its drive has
    no Recycle Bin, so a file is never deleted for good."""
    if not client_remove.recycle_bin_available(folder):
        return 0
    from send2trash import send2trash
    count = 0
    for f in folder.glob("*.osz"):
        try:
            send2trash(str(f))
            count += 1
        except Exception:
            pass
    return count

class ExtractMixin:
        def _warn(self, where: str, detail: str) -> None:
            self.log.log("ERROR", "WARN", "", where=where, detail=detail)

        def _clear_output_osz(self) -> int:
            """``_clear_osz`` on Output, with a WARN when files were left behind."""
            n = _clear_osz(self.cfg.output_path)
            if n == 0 and any(self.cfg.output_path.glob("*.osz")):
                self._warn("output:clear", "Output kept: no Recycle Bin on this drive")
            return n

        def scan(self):
            packs = extractor.scan_packs(self.cfg.packs_path)
            self.log.info("SCAN_PACKS", count=len(packs), source="Packs/")
            return packs

        def prescan_all(self, progress=None) -> list[ExtractPlan]:
            packs = extractor.scan_packs(self.cfg.packs_path)
            known = self.db.known_track_ids()
            plans: list[ExtractPlan] = []
            for zip_path, parsed in packs:
                known_before = self.db.get_pack_by_code(parsed.code) is not None
                try:
                    plan = extractor.prescan_pack(zip_path, parsed, known, known_before)
                except extractor.ARCHIVE_READ_ERRORS as exc:
                    self._warn(f"prescan:{parsed.code}",
                               f"{zip_path.name}: unreadable archive, skipped: {exc}")
                    continue
                plans.append(plan)
                if plan.kind != "new":
                    self.log.info("READD_PROMPT", code=parsed.code, kind=plan.kind,
                                  missing=len(plan.new_ids))
                if progress:
                    progress(parsed.code)
            return plans

        def extract(self, approved: list[tuple[Path, ParsedPack]], progress=None,
                    cancel=None) -> dict:
            # ``cancel`` (a zero-arg bool callable) lets a queued job carry its OWN
            # cancel token; when None we fall back to the shared ``_cancel`` Event
            # (Dashboard / close-window path) and clear it as before.
            _eff = cancel if cancel is not None else self._cancel.is_set
            if cancel is None:
                self._cancel.clear()   # fresh extract; makes unpacking cancellable
            when = now_iso()
            start = time.time()
            if self.cfg.clear_output_before_extract:
                self._clear_output_osz()
            self.log.info("EXTRACT_START", pack_count=len(approved), source="Packs/")
    
            def _count(zp) -> int:
                try:
                    return len(extractor.read_osz_entries(zp))
                except extractor.ARCHIVE_READ_ERRORS:
                    return 0   # unreadable: extract() below keeps and reports it

            total = sum(_count(zp) for zp, _ in approved)
            done = [0]
    
            def _cb(pack_name: str, osz_name: str) -> None:
                done[0] += 1
                if progress:
                    progress({"kind": "extract", "pack": pack_name, "osz": osz_name,
                              "done": done[0], "total": total})
    
            total_tracks = 0
            processed_dir = self.cfg.root_path / "Processed"
            rejected: list[dict] = []
            kept = 0
            for zip_path, parsed in approved:
                if _eff():
                    break
                try:
                    res = extractor.extract_pack(zip_path, parsed, self.cfg.output_path,
                                                 self.db, when, _cb, log=self.log,
                                                 cancel=_eff)
                except archives.UnsafeArchive as exc:
                    # A zip-bomb / path-traversal pack: quarantine it (don't delete —
                    # the owner may want to inspect it) and keep processing the rest.
                    reason = getattr(exc, "reason", "unsafe")
                    moved = self._quarantine(zip_path)
                    self.log.info("EXTRACT_REJECT", code=parsed.code, reason=reason,
                                  quarantined=bool(moved), detail=str(exc)[:200])
                    rejected.append({"code": parsed.code, "reason": reason,
                                     "quarantined": bool(moved)})
                    continue
                except extractor.ARCHIVE_READ_ERRORS as exc:
                    kept += 1
                    self._warn(f"extract:{parsed.code}",
                               f"{zip_path.name} kept: unreadable archive: {exc}")
                    continue
                total_tracks += res["tracks"]
                if res.get("extra_files"):
                    self.db.set_pack_extra(parsed.code, len(res["extra_files"]))
                self.log.info("EXTRACT_PACK", code=parsed.code, tracks=res["tracks"],
                              subfolders=res["subfolders"])
                if res["cancelled"] or res["failed"]:
                    kept += 1
                    why = ("cancelled" if res["cancelled"]
                           else f"{res['failed']} beatmap(s) not extracted")
                    self._warn(f"extract:{parsed.code}",
                               f"{zip_path.name} kept: incomplete extract ({why})")
                    continue
                if self.cfg.zip_disposal == "drive":
                    action = self._dispose_archive_to_drive(zip_path)
                else:
                    action = extractor.dispose_zip(zip_path, self.cfg.zip_disposal,
                                                   processed_dir)
                if action == "ZIP_KEPT":
                    kept += 1
                    self._warn("dispose", f"{zip_path.name} kept: no Recycle Bin on this drive")
                    continue
                fields = {"file": zip_path.name}
                if action == "ZIP_MOVED":
                    fields["dest"] = str(processed_dir)
                self.log.info(action, **fields)
    
            # loose .osz dropped straight into Packs need no unpacking — move them to
            # Output and record with a "Direct" source (fixes "no archive found").
            loose = self.process_loose_osz()
            total_tracks += loose
    
            info = self.rebuild()
            duration = int(time.time() - start)
            self.log.info("EXTRACT_DONE", packs=len(approved) - len(rejected),
                          tracks=total_tracks, rejected=len(rejected), loose=loose,
                          duration_s=duration)
            result = {"packs": len(approved) - len(rejected), "tracks": total_tracks,
                      "rejected": rejected, "loose": loose, "kept": kept, **info}
    
            if self.cfg.auto_backup_after_extract:
                backup = self.copy_library(progress)
                result["backup"] = backup
            return result

        def has_loose_osz(self) -> bool:
            """Whether the Packs folder holds loose .osz dropped in directly (no
            archive to unpack)."""
            return any(self.cfg.packs_path.glob("*.osz"))

        def process_loose_osz(self, progress=None) -> int:
            """Move loose .osz dropped straight into Packs into Output and record them
            with a 'Direct' source (they need no unpacking). Returns the count."""
            import shutil
            from .. import msd, ratings
            from ..beatmap import read_osz_full
            out = self.cfg.output_path
            out.mkdir(parents=True, exist_ok=True)
            when = now_iso()
            pack_id = None
            moved = 0
            for p in sorted(self.cfg.packs_path.glob("*.osz")):
                t = parsing.parse_osz_entry(p.name, p.stat().st_size)
                if t is None:
                    continue
                target = out / t.filename
                try:
                    if target.exists():
                        if not client_remove.recycle_bin_available(out):
                            self._warn("loose", f"{p.name} kept in Packs: Output already "
                                                "has it and there is no Recycle Bin")
                            continue
                        from send2trash import send2trash
                        send2trash(str(target))
                    shutil.move(str(p), str(target))   # Packs -> Output (already final)
                except OSError as exc:
                    self.log.error("loose", str(exc)[:200])
                    continue
                if pack_id is None:
                    pack_id = self.db.get_or_create_local_pack("Direct")   # Source label
                meta, diffs, raw = read_osz_full(target)
                track_id, _ = self.db.upsert_track(t, when, meta)
                self.db.upsert_difficulties(
                    track_id, diffs, ratings.stars_for_diffs(diffs, raw), when)
                self.db.apply_msd(track_id, msd.msd_for_diffs(diffs, raw), when)
                self.db.add_track_source(track_id, pack_id, None, when)
                moved += 1
                if progress:
                    progress({"kind": "loose", "name": t.filename})
            if moved:
                self.log.info("LOOSE_OSZ", moved=moved)
            return moved

        def _dispose_archive_to_drive(self, zip_path) -> str:
            """'Processed .zip action = Upload to Drive & remove': back the original
            pack archive up to a Packs/ subfolder in Drive and delete it locally to
            free disk. Falls back to moving it to Processed/ (never deleted) if Drive
            can't be reached, so an archive is never lost."""
            from ..drive.auth import DriveError
            processed = self.cfg.root_path / "Processed"
            zip_path = Path(zip_path)
            if not self._drive_auth().is_connected():
                return extractor.dispose_zip(zip_path, "move", processed)
            try:
                client = self._make_drive_client()
                folder = self.cfg.drive_folder_id or client.ensure_folder("Rosu")
                if folder != self.cfg.drive_folder_id:
                    self.cfg.drive_folder_id = folder
                    config.save_config(self.cfg)
                packs_folder = client.ensure_folder("Packs", folder)
                client.upload_file(zip_path, zip_path.name, packs_folder,
                                   cancel=self._drive_cancel.is_set)
                zip_path.unlink(missing_ok=True)   # uploaded -> reclaim local disk
                self.log.info("ZIP_TO_DRIVE", file=zip_path.name)
                return "ZIP_TO_DRIVE"
            except (DriveError, OSError) as exc:
                self.log.error("zip:drive", str(exc)[:200])
                return extractor.dispose_zip(zip_path, "move", processed)

        def _quarantine(self, zip_path: Path) -> Path | None:
            """Move a rejected (unsafe) pack aside so it is never re-scanned or
            extracted, WITHOUT deleting anything already there (the owner may want to
            inspect it). Uses ``shutil.move`` so it works even when Packs is on a
            different drive than the app root, and picks a collision-free name so a
            previously quarantined file of the same name is never overwritten.
            Returns the new path, or ``None`` if it could not be moved."""
            import shutil
            qdir = self.cfg.root_path / "Quarantine"
            src = Path(zip_path)
            try:
                qdir.mkdir(parents=True, exist_ok=True)
                dest = qdir / src.name
                n = 1
                while dest.exists():   # never clobber an earlier quarantined file
                    dest = qdir / f"{src.stem}.{n}{src.suffix}"
                    n += 1
                shutil.move(str(src), str(dest))
                return dest
            except OSError as exc:
                self.log.error("extract:quarantine", str(exc)[:200])
                return None

        def dispose_archives(self, paths) -> int:
            """Recycle / move a set of Packs archives per the user's zip_disposal
            setting (used by ``remove_added_archives``). Returns how many were
            disposed; an archive kept for want of a Recycle Bin is not counted."""
            processed = self.cfg.root_path / "Processed"
            n = 0
            for p in paths:
                try:
                    # "drive" needs the upload-then-remove path (with its safe
                    # move-to-Processed fallback); dispose_zip has no "drive" branch
                    # and would silently Recycle-Bin the archive the user asked to
                    # back up to the cloud first.
                    if self.cfg.zip_disposal == "drive":
                        action = self._dispose_archive_to_drive(Path(p))
                    else:
                        action = extractor.dispose_zip(Path(p), self.cfg.zip_disposal, processed)
                    if action == "ZIP_KEPT":
                        self._warn("dispose", f"{Path(p).name} kept: no Recycle Bin "
                                              "on this drive")
                        continue
                    self.log.info(action, file=Path(p).name)
                    n += 1
                except OSError as exc:
                    self.log.error("dispose", str(exc)[:200])
            return n

        def remove_added_archives(self, paths) -> dict:
            """'Remove already-added': dispose only the archives whose every .osz
            is in the database; any other archive stays in Packs with a WARN.
            Returns ``{"removed": int, "kept": int}``."""
            added = []
            for p in map(Path, paths):
                try:
                    with archives.open_reader(p) as r:
                        names = [m for m in r.members() if m.name.lower().endswith(".osz")]
                except extractor.ARCHIVE_READ_ERRORS as exc:
                    self._warn("dispose", f"{p.name} kept: unreadable archive: {exc}")
                    continue
                tracks = [parsing.parse_osz_entry(m.name, m.size) for m in names]
                if not tracks or None in tracks or not all(
                        self.db.find_track_row(t.beatmapset_id, t.filename)
                        for t in tracks):
                    self._warn("dispose", f"{p.name} kept: not every beatmap in it "
                                          "is in the library")
                    continue
                added.append(p)
            removed = self.dispose_archives(added)
            return {"removed": removed, "kept": len(paths) - removed}

        def clear_output(self) -> int:
            """Recycle every .osz still in Output/ — a manual "empty the staging
            folder" action for after a batch has been copied to the Library and/or
            imported into osu!. Uses the Recycle Bin (recoverable), like every other
            guarded delete. Returns how many were removed."""
            n = self._clear_output_osz()
            self.log.info("OUTPUT_CLEARED", count=n)
            return n

        def output_listing(self) -> list[dict]:
            """Every .osz currently in Output (name + size). Lets the Dashboard show
            the unpacked result instead of a blank table once Packs is consumed."""
            out = []
            for p in osu_import.output_osz_files(self.cfg.output_path):
                try:
                    size = p.stat().st_size
                except OSError:
                    size = 0
                out.append({"name": p.name, "size_bytes": size})
            return out

