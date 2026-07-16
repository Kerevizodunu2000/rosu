# SPDX-License-Identifier: GPL-3.0-or-later
"""High-level orchestration used by the UI — no Qt here, so it stays testable.

Each method combines the lower-level modules (extractor / library / excel / osu
import) and writes the appropriate log entries. Long methods accept an optional
``progress`` callback so a worker thread can report status to the UI.
"""
from __future__ import annotations

import datetime as _dt
import threading
import time
from pathlib import Path

from . import (
    archives, config, excel_report, extractor, gaps, jobs, library, osu_api,
    osu_import, parsing, search,
)
from .models import ExtractPlan, ParsedPack

# Language-neutral client display names for job titles.
_CLIENT_LABEL = {"lazer": "osu!lazer", "stable": "osu!(stable)"}


def now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()


def _clear_osz(folder: Path) -> int:
    from send2trash import send2trash
    n = 0
    for p in Path(folder).glob("*.osz"):
        try:
            send2trash(str(p))  # recoverable — matches the app's other guarded deletes
            n += 1
        except OSError:
            pass
    return n


def _sample_export(files, limit):
    """Return a random sample of ``limit`` files for the export "Random N" option
    (list order is preserved so the archive listing stays stable). ``limit`` that
    is falsy / <= 0 / >= len(files) returns the full list unchanged. Shared by
    ``export_sets`` and the job-queue export builder."""
    import random
    if not limit or limit <= 0 or limit >= len(files):
        return files
    chosen = set(random.sample(range(len(files)), limit))
    return [f for i, f in enumerate(files) if i in chosen]


class Services:
    def __init__(self, cfg: config.Config, db, log):
        self.cfg = cfg
        self.db = db
        self.log = log
        self._cancel = threading.Event()  # cooperative cancel for osu! import
        self._drive_cancel = threading.Event()  # separate cancel for Drive ops
        self._lostmap_cancel = threading.Event()  # separate cancel for lost-map scan
        self._verify_cancel = threading.Event()  # separate cancel for SHA-256 verify
        self._rebuild_lock = threading.Lock()  # serialize tracking.xlsx writes

    def request_cancel(self) -> None:
        # Set all so the shared Dashboard/close-window cancel reaches whichever
        # operation is running; each op clears only its OWN token at start, so one
        # operation can never wipe another's in-flight cancel (import vs Drive vs
        # lost-map scan can run concurrently from different tabs).
        self._cancel.set()
        self._drive_cancel.set()
        self._lostmap_cancel.set()
        self._verify_cancel.set()

    # -- scanning / pre-check ------------------------------------------------
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
            plan = extractor.prescan_pack(zip_path, parsed, known, known_before)
            plans.append(plan)
            if plan.kind != "new":
                self.log.info("READD_PROMPT", code=parsed.code, kind=plan.kind,
                              missing=len(plan.new_ids))
            if progress:
                progress(parsed.code)
        return plans

    # -- extraction ----------------------------------------------------------
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
            _clear_osz(self.cfg.output_path)
        self.log.info("EXTRACT_START", pack_count=len(approved), source="Packs/")

        total = sum(len(extractor.read_osz_entries(zp)) for zp, _ in approved)
        done = [0]

        def _cb(pack_name: str, osz_name: str) -> None:
            done[0] += 1
            if progress:
                progress({"kind": "extract", "pack": pack_name, "osz": osz_name,
                          "done": done[0], "total": total})

        total_tracks = 0
        processed_dir = self.cfg.root_path / "Processed"
        rejected: list[dict] = []
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
            total_tracks += res["tracks"]
            if res.get("extra_files"):
                self.db.set_pack_extra(parsed.code, len(res["extra_files"]))
            self.log.info("EXTRACT_PACK", code=parsed.code, tracks=res["tracks"],
                          subfolders=res["subfolders"])
            if self.cfg.zip_disposal == "drive":
                action = self._dispose_archive_to_drive(zip_path)
            else:
                action = extractor.dispose_zip(zip_path, self.cfg.zip_disposal,
                                               processed_dir)
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
                  "rejected": rejected, "loose": loose, **info}

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
        from .osz_meta import read_osz_meta
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
                    target.unlink()
                shutil.move(str(p), str(target))   # Packs -> Output (already final)
            except OSError as exc:
                self.log.error("loose", str(exc)[:200])
                continue
            if pack_id is None:
                pack_id = self.db.get_or_create_local_pack("Direct")   # Source label
            track_id, _ = self.db.upsert_track(t, when, read_osz_meta(target))
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
        from .drive.auth import DriveError
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
        """Recycle / move / delete a set of Packs archives per the user's
        zip_disposal setting (used by the Dashboard 'Remove already-added' action).
        Returns how many were disposed."""
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
                self.log.info(action, file=Path(p).name)
                n += 1
            except OSError as exc:
                self.log.error("dispose", str(exc)[:200])
        return n

    def clear_output(self) -> int:
        """Recycle every .osz still in Output/ — a manual "empty the staging
        folder" action for after a batch has been copied to the Library and/or
        imported into osu!. Uses the Recycle Bin (recoverable), like every other
        guarded delete. Returns how many were removed."""
        n = _clear_osz(self.cfg.output_path)
        self.log.info("OUTPUT_CLEARED", count=n)
        return n

    def rebuild(self) -> dict:
        # Serialize report writes so two workers (e.g. a Dashboard extract and a
        # Settings import) can't corrupt tracking.xlsx by saving it at once.
        with self._rebuild_lock:
            try:
                info = excel_report.build_report(self.db, self.cfg.excel_path,
                                                 self._reference())
            except PermissionError:
                # Report is open in Excel (Windows file lock). Don't abort the
                # pipeline — data is safe in the DB and re-renders next run.
                self.log.info("EXCEL_LOCKED", path=str(self.cfg.excel_path))
                return {"sheets": [], "numbered_missing": {}}
            summary = gaps.gap_summary(info["numbered_missing"])
            self.log.info("GAP_DETECT", summary=summary)
            self.log.info("EXCEL_WRITE", path=str(self.cfg.excel_path),
                          sheets=len(info["sheets"]))
            return info

    # -- library -------------------------------------------------------------
    def copy_library(self, progress=None) -> dict:
        when = now_iso()
        res = library.copy_to_library(
            self.cfg.output_path, self.cfg.library_path, self.db, when,
            self.cfg.library_physical_copy, progress)
        self.log.info("LIBRARY_COPY", new=res["new"], duplicates=res["duplicates"],
                      dup_ids=res["dup_ids"][:50])
        return res

    # -- auto-import from installed osu! clients (item 15) -------------------
    def import_osz_folder(self, folder, progress=None, source_label=None) -> dict:
        """Dedup every .osz in ``folder`` into the Library (shared by the stable,
        lazer and manual import paths). Emits k/n import progress (item 3) and, when
        ``source_label`` is set, tags each set with its origin (item 9)."""
        folder = Path(folder)
        total = sum(1 for _ in folder.glob("*.osz")) if folder.exists() else 0
        done = [0]

        def cb(name):
            done[0] += 1
            progress({"kind": "import", "name": name,
                      "done": done[0], "total": total})

        res = library.copy_to_library(
            folder, self.cfg.library_path, self.db, now_iso(),
            self.cfg.library_physical_copy, cb if progress else None,
            source_label=source_label)
        self.rebuild()
        self.log.info("LIBRARY_COPY", new=res["new"], duplicates=res["duplicates"],
                      dup_ids=res["dup_ids"][:50])
        return res

    def import_from_stable(self, progress=None, cancel=None) -> dict:
        """Zip osu!(stable) Songs/ folders we don't already have into Output, then
        dedup them into the Library."""
        from . import client_import
        _eff = cancel if cancel is not None else self._cancel.is_set
        if cancel is None:
            self._cancel.clear()   # fresh op; own the token so its Cancel button works
        songs = client_import.stable_songs_dir()
        if not songs:
            return {"source": "stable", "found": False}
        known = self.db.known_track_ids()
        folders = list(client_import.iter_stable_folders(songs))
        made = 0
        cancelled = False
        for i, folder in enumerate(folders, 1):
            if _eff():
                cancelled = True
                break
            bid = client_import.beatmapset_id_for_folder(folder)
            if bid is None or bid in known:
                continue  # unresolved id, or we already have this set
            osz = self.cfg.output_path / client_import._osz_name_for(folder, bid)
            if not osz.exists():
                client_import.zip_folder_to_osz(folder, osz)
            made += 1
            if progress:
                progress({"kind": "import", "done": i, "total": len(folders)})
        res = self.import_osz_folder(self.cfg.output_path, progress,
                                     source_label="local_osu_stable")
        self.log.info("CLIENT_IMPORT", client="stable", added=res["new"], made=made)
        return {"source": "stable", "found": True, "made": made,
                "cancelled": cancelled, **res}

    def import_from_lazer(self, progress=None, cancel=None) -> dict:
        """Run the bundled .NET helper to re-export osu!lazer beatmapsets from its
        Realm + files store, then dedup the exported .osz into the Library. The
        (long) export is cancellable."""
        import shutil
        import tempfile
        from . import client_import
        _eff = cancel if cancel is not None else self._cancel.is_set
        if cancel is None:
            self._cancel.clear()   # fresh op; own the token for this import
        data = client_import.lazer_data_dir()
        if not data:
            return {"source": "lazer", "found": False}
        out = Path(tempfile.mkdtemp(prefix="rosu_lazer_"))
        try:
            ok, detail = self._run_lazer_export(data, out, progress, cancel=_eff)
            if not ok:
                if detail == "helper_missing":
                    return {"source": "lazer", "found": True, "error": "helper_missing"}
                if detail == "cancelled":
                    return {"source": "lazer", "found": True, "cancelled": True}
                self.log.error("import:lazer", detail)
                return {"source": "lazer", "found": True, "error": "helper_failed",
                        "detail": detail}
            res = self.import_osz_folder(out, progress,
                                         source_label="local_osu_lazer")
            self.log.info("CLIENT_IMPORT", client="lazer", added=res["new"], made=0)
            return {"source": "lazer", "found": True, **res}
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def _run_lazer_export(self, data, out, progress=None, cancel=None):
        """Run the bundled osu!lazer export helper into ``out``, polling ``cancel``
        so a long export can be interrupted (the subprocess is terminated). stderr
        is captured to a temp file (no pipe-buffer deadlock). Returns
        ``(ok: bool, detail: str)`` — detail is ``"cancelled"`` / ``"helper_missing"``
        / the helper's stderr on failure, ``""`` on success."""
        import subprocess
        import tempfile
        import time
        helper = self._lazer_helper()
        if not helper:
            return False, "helper_missing"
        if progress:
            progress({"kind": "phase", "key": "sc_exporting_lazer"})
        errf = tempfile.TemporaryFile(mode="w+")
        try:
            proc = subprocess.Popen([str(helper), str(data), str(out)],
                                    stdout=subprocess.DEVNULL, stderr=errf, text=True)
        except OSError as exc:
            errf.close()
            return False, str(exc)[:300]
        try:
            while proc.poll() is None:
                if cancel is not None and cancel():
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    return False, "cancelled"
                time.sleep(0.2)
            errf.seek(0)
            err = errf.read()
        finally:
            errf.close()
        if proc.returncode != 0:
            return False, (err or "helper failed")[:300]
        return True, ""

    def _lazer_helper(self):
        """Locate the bundled lazer-export .exe (works in the dev tree and the
        frozen exe, where PyInstaller extracts data under _MEIPASS/rosu)."""
        import sys
        name = "RosuLazerExport.exe"
        candidates = [Path(__file__).resolve().parent / "assets" / "lazer_export" / name]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "rosu" / "assets" / "lazer_export" / name)
        for p in candidates:
            if p.exists():
                return p
        return None

    def purge_library_files(self, progress=None) -> dict:
        """Move every physical .osz in Library to the Recycle Bin but keep the
        rows as memory-only (item 17). Metadata stays; the files go."""
        from send2trash import send2trash
        deleted = 0
        files = list(self.cfg.library_path.glob("*.osz"))
        for i, p in enumerate(files, 1):
            try:
                send2trash(str(p))
                deleted += 1
            except OSError:
                pass
            if progress:
                progress({"kind": "purge", "done": i, "total": len(files)})
        self.db.mark_library_memory(now_iso())
        self.rebuild()
        self.log.info("LIBRARY_PURGE", deleted=deleted)
        return {"deleted": deleted}

    # -- library health / integrity (v1.1) ----------------------------------
    def _scan_library_files(self) -> dict:
        """``{filename: size_bytes}`` for every ``.osz`` in the Library folder.
        A stat failure records size 0 rather than dropping the file, so it still
        shows up in the scrub as present."""
        lib = self.cfg.library_path
        out: dict[str, int] = {}
        if lib.exists():
            for p in lib.glob("*.osz"):
                try:
                    out[p.name] = p.stat().st_size
                except OSError:
                    out[p.name] = 0
        return out

    def library_health(self, progress=None) -> dict:
        """Read-only Library report: disk usage, biggest sets, and a DB↔disk
        scrub (orphans / dead links / memory-only). Never modifies anything."""
        from . import health
        disk = self._scan_library_files()
        rows = self.db.library_records()   # includes memory/disappeared (not orphans)
        scrub = health.scrub(rows, disk)
        usage = health.disk_usage(disk)
        biggest = health.biggest_sets(rows, disk, n=25)
        self.log.info("LIBRARY_HEALTH", files=usage["files"],
                      total_mb=usage["total_bytes"] // (1024 * 1024),
                      orphans=len(scrub["orphans"]),
                      dead=len(scrub["dead_links"]), memory=scrub["memory"])
        return {"usage": usage, "scrub": scrub, "biggest": biggest}

    def verify_library(self, progress=None, max_files: int | None = None) -> dict:
        """Re-hash each physical Library ``.osz`` and compare to the SHA-256 that
        was recorded when it was backed up to Drive. Read-only — flags corruption
        or drift, never repairs. Sets without a stored hash count as ``unhashed``
        (nothing to check against). ``max_files`` caps the run; cancellable."""
        from . import health
        from .drive import bundle
        self._verify_cancel.clear()   # own token: never collides with import/Drive
        lib = self.cfg.library_path
        rows = [r for r in self.db.library_tracks()
                if r.get("in_library") and r.get("filename")]
        total = len(rows) if max_files is None else min(len(rows), max_files)
        checked = ok = mismatch = unhashed = missing = 0
        mismatches: list[str] = []
        cancelled = False
        for r in rows:
            if self._verify_cancel.is_set():
                cancelled = True
                break
            if max_files is not None and checked >= max_files:
                break
            p = lib / r["filename"]
            if not p.exists():
                missing += 1
                continue
            try:
                computed = bundle.sha256_file(p)
            except OSError:
                missing += 1
                continue
            status = health.verify_classify(computed, r.get("drive_hash"))
            checked += 1
            if status == "ok":
                ok += 1
            elif status == "mismatch":
                mismatch += 1
                mismatches.append(r["filename"])
            else:
                unhashed += 1
            if progress:
                progress({"kind": "verify", "done": checked, "total": total,
                          "name": r["filename"]})
        self.log.info("LIBRARY_VERIFY", checked=checked, ok=ok, mismatch=mismatch,
                      unhashed=unhashed, missing=missing, cancelled=cancelled)
        return {"checked": checked, "ok": ok, "mismatch": mismatch,
                "unhashed": unhashed, "missing": missing,
                "mismatches": mismatches[:50], "cancelled": cancelled}

    def refresh(self, progress=None) -> dict:
        when = now_iso()
        res = library.refresh_library(self.cfg.library_path, self.db, when, progress)
        self.rebuild()
        self.log.info("REFRESH", added=res["added"],
                      disappeared=res["disappeared"], present=res["present"])
        return res

    def import_plan(self, target: str = "lazer") -> dict:
        """Info for the pre-import confirmation dialog (no side effects). Batch
        count depends on the target (osu!(stable) is one file per launch)."""
        files = osu_import.output_osz_files(self.cfg.output_path)
        max_files = 1 if target == "stable" else osu_import._MAX_BATCH_FILES
        n_batches = len(osu_import.batches(files, max_files))
        return {"files": len(files), "batches": n_batches,
                "eta_s": osu_import.estimate_seconds(len(files), n_batches)}

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

    # -- osu! import ---------------------------------------------------------
    def import_osu(self, target: str = "lazer", progress=None) -> dict:
        """Send the Output .osz files to an installed osu! client. ``target`` is
        ``"lazer"`` or ``"stable"``; both import an .osz passed on the command
        line (single-instance forwarding), so the launch path is identical."""
        self._cancel.clear()   # fresh import; a stale cancel must not kill it
        files = osu_import.output_osz_files(self.cfg.output_path)
        return self._dispatch_to_client(target, files, progress)

    def _dispatch_to_client(self, target: str, files, progress=None,
                            cancel=None) -> dict:
        """Launch osu! (``target`` = ``"lazer"``/``"stable"``) to import an explicit
        list of ``.osz`` files, with the per-client staging + batching the client
        needs, and flag the sets present in that client. Shared by the Dashboard
        import (from Output) and the Shortcuts lazer↔stable transfer (from a temp
        export). Stages COPIES, so the caller's originals survive.

        Does NOT clear the cancel token — the caller owns it, so a cancel raised
        during an earlier phase of the same operation (e.g. a transfer's export
        step) still stops the dispatch. ``cancel`` (a queued job's own token)
        overrides the shared ``_cancel`` when given."""
        _eff = cancel if cancel is not None else self._cancel.is_set
        if target == "stable":
            exe = self.cfg.osu_stable_exe or config.detect_stable_exe()
            # osu!(stable) *moves* each .osz into its Songs folder on import; a
            # cross-drive move fails with "Error moving file". Stage copies on the
            # install drive so the move is a same-drive rename, and the source is
            # left intact. It also imports one file per launch (batching makes it
            # fail), so send max_batch_files=1.
            files = self._stage_for_stable(files, exe)
            batch_kw = {"max_batch_files": 1}
        else:
            exe = self.cfg.osu_lazer_exe or config.detect_osu_exe()
            # osu!lazer consumes the source .osz on import; stage copies so the
            # source survives too, consistent with stable.
            files = self._stage_copies(files, self.cfg.data_path / "_import_stage")
            batch_kw = {}

        def _prog(i, total, n):
            self.log.info("OSU_IMPORT", target=target, batch=f"{i}/{total}", files=n)
            if progress:
                progress({"kind": "import", "batch": i, "total": total, "files": n})

        res = osu_import.import_files(exe, files, progress=_prog,
                                      cancel=_eff, **batch_kw)
        # Optimistically flag the dispatched sets as present in osu! so the Search
        # 'Where' column shows the 🎮 marker (item F2 / user feedback).
        sent = res.get("sent", len(files))
        for f in files[:sent]:
            t = parsing.parse_osz_entry(f.name, 0)
            if t is not None and t.beatmapset_id is not None:
                self.db.set_in_osu(t.beatmapset_id, client=target)
        if sent:
            self.db._bump()   # let Search/Artists see the new 🎮 flags on reload
        self.log.info("OSU_IMPORT_DONE", target=target, files=res["files"],
                      batches=res["batches"])
        return res

    def _stage_copies(self, files, stage_dir):
        """Copy ``files`` into ``stage_dir`` (clearing prior leftovers first) so the
        osu! client consumes the COPIES and the Output folder is preserved — the
        same batch can then also go to the other client. Clears the read-only bit
        so osu can move each file. Returns the staged paths, or the originals if
        staging can't be set up (or per-file, on a copy error)."""
        import os
        import shutil
        stage = Path(stage_dir)
        try:
            if stage.exists():
                for old in stage.glob("*.osz"):   # clear leftovers osu already took
                    try:
                        old.unlink()
                    except OSError:
                        pass
            stage.mkdir(parents=True, exist_ok=True)
        except OSError:
            return files
        staged = []
        for f in files:
            dst = stage / f.name
            try:
                shutil.copy2(f, dst)
                try:
                    os.chmod(dst, 0o666)   # clear read-only so osu can move it
                except OSError:
                    pass
                staged.append(dst)
            except OSError as exc:
                # Do NOT substitute the Output original: osu! would consume it and
                # break the "Output is preserved" guarantee, silently. Log and skip
                # — the set stays in Output (and the Library) to retry.
                self.log.error("import:stage", f"{f.name}: {str(exc)[:150]}")
        return staged or files

    def _stage_for_stable(self, files, exe=None):
        """Stage on the osu!(stable) install drive, so its import-move is a
        same-drive rename. Derives the install dir from the configured exe (custom
        paths work), falling back to auto-detection; returns the Output paths
        unchanged if neither can be located."""
        from . import client_import
        install = None
        if exe:
            try:
                install = Path(exe).resolve().parent
            except OSError:
                install = None
        if install is None or not install.exists():
            songs = client_import.stable_songs_dir()
            install = songs.parent if songs else None
        if install is None:
            return files
        return self._stage_copies(files, install / "_rosu_import")

    # -- shortcuts / quick-actions tab (v1.2) --------------------------------
    def installed_summary(self, progress=None) -> dict:
        """Read-only counts for the Shortcuts (Kısayollar) tab: how many beatmap
        sets live in each place — osu!lazer, osu!(stable), the Library and the
        Drive backup.

        ``lazer['count']`` is ``None`` when lazer is installed: its set list lives
        in an unreadable Realm database (only the bundled .NET helper can
        enumerate it), so we report presence without a number here and fill the
        number in after a transfer/import. ``stable`` counts ``Songs/`` subfolders
        (≈ one per set), which is cheap. ``installed`` reflects on-disk detection
        only — the per-client enable/disable toggle arrives in v1.3.
        """
        from . import client_import
        songs = client_import.stable_songs_dir()
        stable_count = (sum(1 for _ in client_import.iter_stable_folders(songs))
                        if songs is not None else 0)
        lazer_installed = client_import.lazer_data_dir() is not None
        # lazer's set list is Realm-opaque, so we can't count it directly. Fill the
        # number from the Library sets Rosu has recorded as present in lazer
        # (``in_osu_lazer``) and flag it so the UI can explain where it came from.
        lazer_count = len(self.db.osu_client_ids("lazer")) if lazer_installed else None
        return {
            "lazer": {"installed": lazer_installed, "count": lazer_count,
                      "from_library": True},
            "stable": {"installed": songs is not None, "count": stable_count},
            "library": {"count": self.db.counts().get("in_library", 0)},
            "drive": {"connected": bool(self.cfg.drive_connected),
                      "count": self.db.drive_count()},
        }

    def unpack_and_import(self, targets, skip_duplicates: bool = True,
                          progress=None) -> dict:
        """Shortcut ⑤: unpack every NEW pack in Packs/ into Output, then import the
        result into the given osu! client(s). With ``skip_duplicates`` (default) each
        target only receives Output sets it doesn't already have — so re-unpacking
        sets that came from that client doesn't pointlessly re-send them. Both the
        unpack and the send honor the cancel token. Returns ``{"extract": {...},
        "imports": {target: {sent, skipped, ...}}, "cancelled": bool}``.
        """
        self._cancel.clear()
        plans = self.prescan_all(progress)
        approved = [(Path(p.zip_path), p.parsed) for p in plans if p.kind == "new"]
        if approved or self.has_loose_osz():
            extract_res = self.extract(approved, progress)
        else:
            extract_res = {"packs": 0, "tracks": 0}
        imports: dict = {}
        if not self._cancel.is_set():
            files = osu_import.output_osz_files(self.cfg.output_path)
            for target in targets:
                if self._cancel.is_set():
                    break
                target_ids = self._client_set_ids(target) if skip_duplicates else set()
                if target_ids:
                    send = [f for f in files
                            if (pt := parsing.parse_osz_entry(f.name, 0)) is None
                            or pt.beatmapset_id not in target_ids]
                else:
                    send = list(files)
                res = self._dispatch_to_client(target, send, progress)
                imports[target] = {**res, "skipped": len(files) - len(send)}
        return {"extract": extract_res, "imports": imports,
                "cancelled": self._cancel.is_set()}

    def save_installed_to_library(self, sources, progress=None) -> dict:
        """Shortcut ③: import the beatmaps installed in the given osu! client(s)
        (``"lazer"``/``"stable"``) straight into the Library (dedup is automatic —
        reuses the existing client-import pipeline). Returns ``{source: {...}}``."""
        out: dict = {}
        for s in sources:
            if s == "stable":
                out["stable"] = self.import_from_stable(progress)
            elif s == "lazer":
                out["lazer"] = self.import_from_lazer(progress)
        return out

    def transfer_between_clients(self, source: str, target: str,
                                 progress=None) -> dict:
        """Shortcut ①/②: copy the beatmaps installed in one osu! client into the
        other, skipping sets the target already has (id dedup — cheap for a stable
        target; a lazer target relies on lazer's own import-time dedup). ``source``
        and ``target`` are ``"lazer"``/``"stable"``. Returns
        ``{"source","target","found","transferred","skipped","cancelled"}`` or
        ``{"error": ...}``.
        """
        import shutil
        import tempfile
        if source == target:
            return {"error": "same_client"}
        target_exe = (self.cfg.osu_stable_exe or config.detect_stable_exe()
                      if target == "stable"
                      else self.cfg.osu_lazer_exe or config.detect_osu_exe())
        if not target_exe or not Path(target_exe).exists():
            return {"error": "no_target_exe", "source": source, "target": target}
        self._cancel.clear()   # own the token for the whole transfer (export → send)
        skip_ids = self._client_set_ids(target)
        stage = Path(tempfile.mkdtemp(prefix="rosu_xfer_"))
        try:
            osz, skipped = self._export_client_sets(source, stage, skip_ids, progress)
            found = len(osz) + skipped   # total examined = sent + already-in-target
            if self._cancel.is_set():
                return {"source": source, "target": target, "found": found,
                        "transferred": 0, "skipped": skipped, "cancelled": True}
            if not osz:
                return {"source": source, "target": target, "found": found,
                        "transferred": 0, "skipped": skipped, "cancelled": False}
            res = self._dispatch_to_client(target, osz, progress)
            transferred = res.get("sent", 0)
            self.log.info("CLIENT_TRANSFER", source=source, target=target,
                          found=found, transferred=transferred, skipped=skipped)
            return {"source": source, "target": target, "found": found,
                    "transferred": transferred, "skipped": skipped,
                    "cancelled": res.get("cancelled", False)}
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    def _client_set_ids(self, client: str) -> set[int]:
        """Beatmapset ids already in ``client`` — used to skip re-sending them on a
        transfer. For **stable** we read the real ``Songs/`` folder ids
        (authoritative). For **lazer**, whose set list is Realm-opaque, we fall back
        to the ids Rosu has recorded as present there (``in_osu_lazer``); combined
        with lazer's own import-time dedup this stops repeated transfers re-zipping
        sets already sent. An empty set means "skip nothing"."""
        from . import client_import
        if client == "stable":
            songs = client_import.stable_songs_dir()
            if songs is None:
                return set()
            ids: set[int] = set()
            for folder in client_import.iter_stable_folders(songs):
                bid = client_import.beatmapset_id_for_folder(folder)
                if bid is not None:
                    ids.add(bid)
            return ids
        return self.db.osu_client_ids(client)

    def _export_client_sets(self, source: str, stage, skip_ids,
                            progress=None, cancel=None) -> tuple[list, int]:
        """Materialise the beatmaps installed in ``source`` as ``.osz`` files under
        ``stage``, skipping any whose id is in ``skip_ids`` (already in the target).
        Returns ``(osz_paths, skipped_count)``. ``cancel`` (a queued job's own
        token) overrides the shared ``_cancel`` when given."""
        from . import client_import
        _eff = cancel if cancel is not None else self._cancel.is_set
        stage = Path(stage)
        stage.mkdir(parents=True, exist_ok=True)
        out: list = []
        skipped = 0
        if source == "stable":
            songs = client_import.stable_songs_dir()
            if songs is None:
                return out, skipped
            folders = list(client_import.iter_stable_folders(songs))
            for i, folder in enumerate(folders, 1):
                if _eff():
                    break
                bid = client_import.beatmapset_id_for_folder(folder)
                if skip_ids and bid is not None and bid in skip_ids:
                    skipped += 1
                    continue
                # Never fabricate id 0 for a set with no resolvable id — a "0 …"
                # name re-parses to beatmapset_id 0 and would collapse every id-less
                # set onto the same merged-export dedup key (silent data loss).
                if bid is not None:
                    dest = stage / client_import._osz_name_for(folder, bid)
                else:
                    dest = stage / f"{folder.name}.osz"
                try:
                    client_import.zip_folder_to_osz(folder, dest)
                    out.append(dest)
                except OSError as exc:
                    self.log.error("xfer:zip", str(exc)[:200])
                if progress:
                    progress({"kind": "export", "done": i, "total": len(folders)})
            return out, skipped
        # source == "lazer": re-export via the bundled .NET helper, then filter.
        data = client_import.lazer_data_dir()
        if data is None or _eff():
            return out, skipped
        ok, detail = self._run_lazer_export(data, stage, progress, cancel=_eff)
        if not ok:
            if detail not in ("cancelled", "helper_missing"):
                self.log.error("xfer:lazer", detail)
            return out, skipped
        for p in client_import.iter_osz_in_folder(stage):
            if _eff():
                break
            t = parsing.parse_osz_entry(p.name, 0)
            if skip_ids and t is not None and t.beatmapset_id in skip_ids:
                skipped += 1
                try:
                    p.unlink()
                except OSError:
                    pass
                continue
            out.append(p)
        return out, skipped

    def _dedup_scan(self) -> tuple[list, dict, int]:
        """Scan the Library and plan dedup without deleting: returns
        ``(names_to_remove, sizes_by_name, groups)``. Duplicates are files sharing a
        beatmapset id; the DB-canonical file is kept and a group with no canonical
        file on disk is left alone (removing would orphan the DB row)."""
        from .parsing import parse_osz_entry
        lib = self.cfg.library_path
        if not lib.exists():
            return [], {}, 0
        canon: dict = {}
        for r in self.db.library_records():
            bid = r.get("beatmapset_id")
            if bid is not None and r.get("filename"):
                canon.setdefault(bid, r["filename"])
        entries: list = []
        sizes: dict = {}
        bid_of: dict = {}
        for p in sorted(lib.glob("*.osz")):
            try:
                sz = p.stat().st_size
            except OSError:
                sz = 0
            t = parse_osz_entry(p.name, sz)
            bid = t.beatmapset_id if t is not None else None
            sizes[p.name] = sz
            bid_of[p.name] = bid
            entries.append({"name": p.name, "size": sz, "beatmapset_id": bid,
                            "canonical": canon.get(bid)})
        to_remove = library.plan_library_dedup(entries)
        groups = len({bid_of.get(n) for n in to_remove})
        return to_remove, sizes, groups

    def dedup_library_plan(self, progress=None) -> dict:
        """Preview which duplicate files dedup WOULD recycle — feeds the
        confirmation dialog, deletes nothing. Returns
        ``{"count","freed_bytes","groups","names"}``."""
        to_remove, sizes, groups = self._dedup_scan()
        return {"count": len(to_remove),
                "freed_bytes": sum(sizes.get(n, 0) for n in to_remove),
                "groups": groups, "names": to_remove}

    def dedup_library(self, names=None, progress=None, cancel=None) -> dict:
        """Recycle redundant duplicate ``.osz`` in the Library (see
        :meth:`dedup_library_plan` for how duplicates are identified). ``names`` is
        an explicit list from a confirmed plan; when ``None`` it scans and removes in
        one shot. Recycle Bin (recoverable). ``cancel`` (a queued job's own token)
        stops the recycle loop cooperatively. Returns
        ``{"removed","freed_bytes","groups"}``."""
        from send2trash import send2trash
        # This method never owned/cleared the shared ``_cancel`` in v1.2, so for
        # the cancel=None path it must NOT read it (a leftover cancel from an
        # earlier op would silently make it a no-op). Only an explicitly passed
        # job token cancels it.
        _eff = cancel if cancel is not None else (lambda: False)
        lib = self.cfg.library_path
        if names is None:
            names, sizes, groups = self._dedup_scan()
        else:
            sizes = {}
            for n in names:
                try:
                    sizes[n] = (lib / n).stat().st_size
                except OSError:
                    sizes[n] = 0
            groups = 0
        removed = freed = 0
        for i, name in enumerate(names, 1):
            if _eff():
                break
            try:
                send2trash(str(lib / name))
                removed += 1
                freed += sizes.get(name, 0)
            except OSError as exc:
                self.log.error("dedup", str(exc)[:200])
            if progress:
                progress({"kind": "dedup", "done": i, "total": len(names)})
        self.log.info("LIBRARY_DEDUP", removed=removed,
                      freed_mb=freed // (1024 * 1024), groups=groups)
        return {"removed": removed, "freed_bytes": freed, "groups": groups}

    def export_sets(self, source: str, dest_base, fmt: str = "zip",
                    split_bytes: int | None = None, upload_to_drive: bool = False,
                    share: bool = False, progress=None,
                    limit: int | None = None) -> dict:
        """Shortcut ④: gather the beatmaps from ``source`` and write them to
        archive(s) at ``dest_base``.

        ``source`` is ``"library"`` (every physical Library .osz), ``"drive"``
        (only the Library sets already backed up to Drive), ``"lazer"`` /
        ``"stable"`` (re-export from that client), or ``"merged"`` (the union of
        Library + both clients, deduped by id). ``fmt`` is ``"zip"`` or ``"7z"``;
        ``split_bytes`` splits into volumes (None = one archive). ``limit`` (>0)
        exports a random sample of that many sets instead of all of them. With
        ``upload_to_drive`` the archive(s) are uploaded to a Drive ``Exports``
        folder, and ``share`` adds an anyone-with-link permission + returns the
        link. Returns ``{"source","count","archives":[...], ["drive": {...}]}``.
        """
        import shutil
        import tempfile

        from . import exporter
        self._cancel.clear()   # own the token for this export (gather → write)
        stage = Path(tempfile.mkdtemp(prefix="rosu_export_"))
        try:
            files = self._gather_export_sources(source, stage, progress)
            files = _sample_export(files, limit)
            if not files or self._cancel.is_set():
                return {"source": source, "count": 0, "archives": [],
                        "cancelled": self._cancel.is_set()}
            written = exporter.write_export(files, Path(dest_base), fmt, split_bytes,
                                            progress, cancel=self._cancel.is_set)
            cancelled = self._cancel.is_set()
            result = {"source": source, "count": len(files),
                      "archives": [str(a) for a in written], "cancelled": cancelled}
            if upload_to_drive and not cancelled:
                result["drive"] = self._upload_export_to_drive(written, share,
                                                               progress)
            self.log.info("EXPORT", source=source, sets=len(files),
                          archives=len(written), fmt=fmt, cancelled=cancelled)
            return result
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    def _gather_export_sources(self, source: str, stage, progress=None,
                               cancel=None) -> list:
        """Collect the ``.osz`` file paths that make up an export ``source`` (see
        :meth:`export_sets`). Client sources are materialised into ``stage``.
        ``cancel`` (a queued job's own token) is threaded into the client re-export."""
        from .parsing import parse_osz_entry
        lib = self.cfg.library_path

        def lib_files(only_drive: bool = False) -> list:
            if not lib.exists():
                return []
            if not only_drive:
                return sorted(lib.glob("*.osz"))
            names = {r["filename"] for r in self.db.library_records()
                     if r.get("in_drive") and r.get("filename")}
            return sorted(p for n in names if (p := lib / n).exists())

        if source == "library":
            return lib_files()
        if source == "drive":
            return lib_files(only_drive=True)
        if source in ("lazer", "stable"):
            osz, _ = self._export_client_sets(source, stage, None, progress, cancel)
            return osz
        if source == "merged":
            seen: set = set()
            out: list = []

            def _add(paths):
                for p in paths:
                    t = parse_osz_entry(p.name, 0)
                    bid = t.beatmapset_id if t else None
                    key = bid if bid else p.name   # id None or 0 → key by filename
                    if key not in seen:
                        seen.add(key)
                        out.append(p)

            _add(lib_files())
            for client in ("lazer", "stable"):
                osz, _ = self._export_client_sets(client, stage, None, progress, cancel)
                _add(osz)
            return out
        return []

    def _upload_export_to_drive(self, archives, share: bool,
                                progress=None, cancel=None) -> dict:
        """Upload the written export archive(s) to a Drive ``Exports`` folder and,
        when ``share``, grant an anyone-with-link permission and collect the link
        for each. Returns ``{"uploaded", "files": [{name,id,link}]}`` or
        ``{"error": ...}``. ``cancel`` (a queued job's own token) overrides the
        shared ``_drive_cancel`` when given, so cancelling THIS export never trips
        another job's Drive upload."""
        from .drive.auth import DriveCancelled, DriveError
        _eff = cancel if cancel is not None else self._drive_cancel.is_set
        if cancel is None:
            self._drive_cancel.clear()
        if not self._drive_auth().is_connected():
            return {"error": "not_connected"}
        try:
            client = self._make_drive_client()
            folder = self.cfg.drive_folder_id or client.ensure_folder("Rosu")
            if folder != self.cfg.drive_folder_id:
                self.cfg.drive_folder_id = folder
                config.save_config(self.cfg)
            exports = client.ensure_folder("Exports", folder)
            if progress:
                progress({"kind": "phase", "key": "sc_uploading_drive"})
            files: list = []
            cancelled = False
            for a in archives:
                if _eff():
                    cancelled = True
                    break
                a = Path(a)

                def _up(sent, size, _n=a.name):
                    if progress:
                        progress({"kind": "upload", "done": sent, "total": size,
                                  "name": _n})

                try:
                    fid = client.upload_file(a, a.name, exports, progress=_up,
                                             cancel=_eff)
                except DriveCancelled:
                    cancelled = True
                    break
                link = None
                shared = False
                link_error = False
                if share and fid:
                    try:
                        client.share_anyone(fid)
                        shared = True
                        # Record the grant BEFORE fetching the link: if get_link
                        # then fails the file is ALREADY public, and the user must
                        # be told so they can review/revoke it in Drive.
                        self.log.info("EXPORT_SHARE", file=a.name)
                    except DriveError as exc:
                        self.log.error("export:share", str(exc)[:200])
                    if shared:
                        try:
                            link = client.get_link(fid)
                        except DriveError as exc:
                            link_error = True
                            self.log.error("export:link", str(exc)[:200])
                files.append({"name": a.name, "id": fid, "link": link,
                              "shared": shared, "link_error": link_error})
            self.log.info("EXPORT_UPLOAD", files=len(files), shared=share,
                          cancelled=cancelled)
            return {"uploaded": len(files), "files": files, "cancelled": cancelled}
        except DriveError as exc:
            self.log.error("export:drive", str(exc)[:300])
            return {"error": "drive", "detail": str(exc)[:300]}

    # -- job-queue builders (v1.3) -------------------------------------------
    # Each returns a jobs.Job — an ordered list of lane-tagged Steps that reuse
    # the sub-methods above, carrying data through ``job.ctx`` and a per-job
    # cancel token (``cancel``), so the İş Kuyruğu can run them step-by-step with
    # live status, per-item cancel, and DISK/DRIVE concurrency. Each step calls
    # a sub-method with ``cancel=`` (the job's own token) — never the shared
    # ``_cancel`` — so cancelling one job can't disturb another.

    def build_unpack_job(self, targets, skip_duplicates: bool = True) -> jobs.Job:
        """Shortcut ⑤ as a job: prescan → extract → send(target…). Mirrors
        :meth:`unpack_and_import`; the result dict shape is identical."""
        title = ("job_unpack_both" if len(targets) > 1
                 else f"job_unpack_{targets[0]}")
        job = jobs.Job(jobs.new_id(), title, kind="unpack")

        def s_prescan(ctx, progress, cancel):
            plans = self.prescan_all(progress)
            ctx["approved"] = [(Path(p.zip_path), p.parsed)
                               for p in plans if p.kind == "new"]

        def s_extract(ctx, progress, cancel):
            approved = ctx.get("approved", [])
            if approved or self.has_loose_osz():
                ctx["extract"] = self.extract(approved, progress, cancel=cancel)
            else:
                ctx["extract"] = {"packs": 0, "tracks": 0}

        def s_send(target):
            def _run(ctx, progress, cancel):
                files = osu_import.output_osz_files(self.cfg.output_path)
                target_ids = self._client_set_ids(target) if skip_duplicates else set()
                if target_ids:
                    send = [f for f in files
                            if (pt := parsing.parse_osz_entry(f.name, 0)) is None
                            or pt.beatmapset_id not in target_ids]
                else:
                    send = list(files)
                res = self._dispatch_to_client(target, send, progress, cancel=cancel)
                ctx.setdefault("imports", {})[target] = {
                    **res, "skipped": len(files) - len(send)}
            return _run

        job.steps = [jobs.Step("job_step_prescan", jobs.Lane.DISK, s_prescan),
                     jobs.Step("job_step_extract", jobs.Lane.DISK, s_extract)]
        for target in targets:
            key = ("job_step_send_lazer" if target == "lazer"
                   else "job_step_send_stable")
            job.steps.append(jobs.Step(key, jobs.Lane.DISK, s_send(target)))
        job.finalize = lambda ctx: {
            "extract": ctx.get("extract", {"packs": 0, "tracks": 0}),
            "imports": ctx.get("imports", {}), "cancelled": job.cancel_cb()}
        return job

    def build_transfer_job(self, source: str, target: str) -> jobs.Job:
        """Shortcut ①/② as a job: enumerate target → export source → send.
        Assumes the caller already validated (same-client / target-exe)."""
        import shutil
        import tempfile
        job = jobs.Job(jobs.new_id(), "job_transfer", kind="transfer",
                       title_kwargs={"source": _CLIENT_LABEL.get(source, source),
                                     "target": _CLIENT_LABEL.get(target, target)})
        stage = Path(tempfile.mkdtemp(prefix="rosu_xfer_"))
        job.ctx["stage"] = stage
        job.on_cleanup.append(lambda: shutil.rmtree(stage, ignore_errors=True))

        def s_enumerate(ctx, progress, cancel):
            ctx["skip_ids"] = self._client_set_ids(target)

        def s_export(ctx, progress, cancel):
            osz, skipped = self._export_client_sets(
                source, ctx["stage"], ctx["skip_ids"], progress, cancel=cancel)
            ctx["osz"], ctx["skipped"] = osz, skipped
            ctx["found"] = len(osz) + skipped

        def s_send(ctx, progress, cancel):
            osz = ctx.get("osz", [])
            if cancel() or not osz:
                ctx["transferred"] = 0
                ctx["send_cancelled"] = False
                return
            res = self._dispatch_to_client(target, osz, progress, cancel=cancel)
            ctx["transferred"] = res.get("sent", 0)
            ctx["send_cancelled"] = res.get("cancelled", False)

        job.steps = [jobs.Step("job_step_enumerate", jobs.Lane.DISK, s_enumerate),
                     jobs.Step("job_step_export_client", jobs.Lane.DISK, s_export),
                     jobs.Step("job_step_send", jobs.Lane.DISK, s_send)]

        def finalize(ctx):
            res = {"source": source, "target": target, "found": ctx.get("found", 0),
                   "transferred": ctx.get("transferred", 0),
                   "skipped": ctx.get("skipped", 0),
                   "cancelled": job.cancel_cb() or ctx.get("send_cancelled", False)}
            self.log.info("CLIENT_TRANSFER", source=source, target=target,
                          found=res["found"], transferred=res["transferred"],
                          skipped=res["skipped"])
            return res
        job.finalize = finalize
        return job

    def build_save_job(self, sources) -> jobs.Job:
        """Shortcut ③ as a job: one step per source client → Library."""
        labels = ", ".join(_CLIENT_LABEL.get(s, s) for s in sources)
        job = jobs.Job(jobs.new_id(), "job_save", kind="save",
                       title_kwargs={"sources": labels})

        def s_source(src):
            def _run(ctx, progress, cancel):
                if src == "stable":
                    r = self.import_from_stable(progress, cancel=cancel)
                else:
                    r = self.import_from_lazer(progress, cancel=cancel)
                ctx.setdefault("out", {})[src] = r
            return _run

        for s in sources:
            key = ("job_step_save_stable" if s == "stable"
                   else "job_step_save_lazer")
            job.steps.append(jobs.Step(key, jobs.Lane.DISK, s_source(s)))
        job.finalize = lambda ctx: ctx.get("out", {})
        return job

    def build_export_job(self, source: str, dest_base, fmt: str = "zip",
                         split_bytes: int | None = None, upload: bool = False,
                         share: bool = False, limit: int | None = None) -> jobs.Job:
        """Shortcut ④ as a job: gather → archive (DISK) → upload (DRIVE). The
        upload step is on the DRIVE lane, so once an export starts uploading the
        DISK lane frees for the next queued job (disk work ↔ Drive upload)."""
        import shutil
        import tempfile
        from . import exporter
        dest_base = Path(dest_base)
        name = f"{dest_base.name}{'.7z' if fmt == '7z' else '.zip'}"
        job = jobs.Job(jobs.new_id(), "job_export", kind="export",
                       title_kwargs={"source": source, "name": name},
                       tooltip=str(dest_base.parent))
        stage = Path(tempfile.mkdtemp(prefix="rosu_export_"))
        job.ctx["stage"] = stage
        job.on_cleanup.append(lambda: shutil.rmtree(stage, ignore_errors=True))

        def s_gather(ctx, progress, cancel):
            files = self._gather_export_sources(source, ctx["stage"], progress,
                                                cancel=cancel)
            ctx["files"] = _sample_export(files, limit)

        def s_archive(ctx, progress, cancel):
            files = ctx.get("files", [])
            if not files or cancel():
                ctx["written"] = []
                return
            ctx["written"] = exporter.write_export(
                files, Path(dest_base), fmt, split_bytes, progress, cancel=cancel)

        def s_upload(ctx, progress, cancel):
            if cancel() or not ctx.get("written"):
                return
            ctx["drive"] = self._upload_export_to_drive(
                ctx["written"], share, progress, cancel=cancel)

        job.steps = [
            jobs.Step("job_step_gather", jobs.Lane.DISK, s_gather,
                      label_kwargs={"source": source}),
            jobs.Step("job_step_archive", jobs.Lane.DISK, s_archive,
                      label_kwargs={"name": name})]
        if upload:
            job.steps.append(jobs.Step("job_step_upload", jobs.Lane.DRIVE, s_upload))

        def finalize(ctx):
            written = ctx.get("written", [])
            # Match export_sets: count reflects sets actually archived — 0 when the
            # write never happened (cancelled between gather and archive, or empty).
            res = {"source": source,
                   "count": len(ctx.get("files", [])) if written else 0,
                   "archives": [str(a) for a in written],
                   "cancelled": job.cancel_cb() and not written}
            if "drive" in ctx:
                res["drive"] = ctx["drive"]
            self.log.info("EXPORT", source=source, sets=res["count"],
                          archives=len(written), fmt=fmt, cancelled=res["cancelled"])
            return res
        job.finalize = finalize
        return job

    def build_dedup_job(self) -> jobs.Job:
        """Library dedup as a job: scan (preview) → GATED remove. The remove step
        waits for an explicit UI confirmation (the queue shows the preview dialog
        before recycling anything)."""
        job = jobs.Job(jobs.new_id(), "job_dedup", kind="dedup")

        def s_scan(ctx, progress, cancel):
            ctx["plan"] = self.dedup_library_plan()

        def s_remove(ctx, progress, cancel):
            names = ctx.get("plan", {}).get("names", [])
            ctx["result"] = self.dedup_library(names=names, progress=progress,
                                               cancel=cancel)

        job.steps = [jobs.Step("job_step_scan", jobs.Lane.DISK, s_scan),
                     jobs.Step("job_step_remove", jobs.Lane.DISK, s_remove,
                               gated=True)]
        job.finalize = lambda ctx: ctx.get(
            "result", {"removed": 0, "freed_bytes": 0, "groups": 0})
        return job

    # -- reference (osu! API) ------------------------------------------------
    def _reference(self):
        return osu_api.load_reference(self.cfg.reference_path)

    def update_reference(self, progress=None) -> dict:
        ref = osu_api.fetch_reference(
            self.cfg.osu_client_id, self.cfg.osu_client_secret,
            progress=(lambda s: progress(s)) if progress else None)
        osu_api.save_reference(ref, self.cfg.reference_path)
        self.log.info("REFERENCE_SYNC", packs=ref.get("count", 0))
        return ref

    def scan_lost_maps(self, progress=None, max_calls: int = 500) -> dict:
        """Flag owned beatmapsets that no longer exist on osu! (item F, v1.0).

        Needs osu! API credentials (returns ``{"error": "no_api"}`` otherwise).
        Checks up to ``max_calls`` library beatmapsets, stores each result, and
        returns ``{"checked", "gone"}``.
        """
        if not (self.cfg.osu_client_id and self.cfg.osu_client_secret):
            return {"error": "no_api"}
        self._lostmap_cancel.clear()   # own token: never collides with import/Drive
        ids = [r["beatmapset_id"] for r in self.db.library_tracks()
               if r.get("beatmapset_id")]
        result = osu_api.beatmapset_availability(
            ids, self.cfg.osu_client_id, self.cfg.osu_client_secret,
            progress=progress, max_calls=max_calls,
            cancel=self._lostmap_cancel.is_set)
        gone = 0
        for bid, status in result.items():
            self.db.set_availability(bid, status)
            if status == "gone":
                gone += 1
        self.log.info("LOST_MAP_SCAN", checked=len(result), gone=gone)
        return {"checked": len(result), "gone": gone}

    def lost_map_count(self) -> int:
        return self.db.lost_map_count()

    # -- gap rows for the Packs tab / Excel ----------------------------------
    def series_rows(self, series: str):
        """Confidence-aware rows for one series (present + any real red gaps)."""
        present = self.db.packs_for_series(series)
        category = present[0]["category"] if present else "Other"
        ref = osu_api.reference_by_series(self._reference()).get(series)
        return gaps.build_rows(series, category, present, ref)

    def compute_missing(self) -> dict[str, list[int]]:
        """Confirmed-missing numbers per series (banner/log). Read-only.

        Only Standard series (or reference-validated series) contribute, so the
        banner never shows guessed reds.
        """
        numbered: dict[str, list[int]] = {}
        for s in self.db.series_list():
            for row in self.series_rows(s):
                if not row.present and row.number is not None:
                    numbered.setdefault(s, []).append(row.number)
        return numbered

    # -- search --------------------------------------------------------------
    def search(self, query: str, search_tags: bool = False,
               progress=None) -> list[dict]:
        """Ranked search, or the full name-sorted listing when the box is empty
        (item 11). ``search_tags`` opts into matching creator/tags too (off by
        default — it flooded results). ``progress`` is accepted so it can run in a
        Worker thread."""
        if query.strip():
            rows = search.search(self.db, query, search_tags=search_tags)
        else:
            rows = self.db.all_tracks()
            self.db.attach_sources_bulk(rows)
        self.log.info("SEARCH", query=query or "(all)", results=len(rows),
                      tags=search_tags)
        return rows

    def data_generation(self) -> int:
        """Monotonic counter bumped on track writes — the Artists tab uses it to
        skip a costly rebuild when nothing changed (item 10)."""
        return self.db.data_generation()

    def artists(self, metric: str = "count", descending: bool = True) -> list[dict]:
        return self.db.artists_ranked(metric, descending)

    def tracks_by_artist(self, artist: str) -> list[dict]:
        return self.db.tracks_by_artist(artist)

    # -- Google Drive backup (item 11, v0.8) --------------------------------
    def _drive_auth(self):
        """Lazily build+cache DriveAuth (keeps keyring/urllib off the startup
        path and out of ``--selftest``)."""
        auth = getattr(self, "_drive_auth_obj", None)
        if auth is None:
            from .drive.auth import DriveAuth
            auth = DriveAuth()
            self._drive_auth_obj = auth
        return auth

    def _make_drive_client(self):
        from .drive.client import DriveClient
        return DriveClient(self._drive_auth())

    def drive_status(self) -> dict:
        auth = self._drive_auth()
        return {"configured": auth.is_configured(),
                "connected": auth.is_connected(),
                "can_store": auth.can_store_token()}

    def connect_drive(self, progress=None) -> dict:
        """Run the Google OAuth consent flow (off-thread) and remember it."""
        from .drive.auth import DriveError, DriveNotConfigured
        self._drive_cancel.clear()
        auth = self._drive_auth()
        try:
            auth.login(cancel=self._drive_cancel.is_set)
        except DriveNotConfigured as exc:
            return {"error": "not_configured", "detail": str(exc)}
        except DriveError as exc:
            return {"error": "auth", "detail": str(exc)[:300]}
        self.cfg.drive_connected = True
        config.save_config(self.cfg)
        self.log.info("DRIVE_CONNECT", connected=True)
        return {"connected": True}

    def disconnect_drive(self, progress=None) -> dict:
        self._drive_auth().logout()
        self.cfg.drive_connected = False
        config.save_config(self.cfg)
        self.log.info("DRIVE_DISCONNECT")
        return {"connected": False}

    def backup_plan(self) -> dict:
        """Preview a Drive backup (read-only): how many new/changed Library sets
        are not yet in this device's shard, and their total size. Feeds the
        pre-backup options dialog. ``{"count", "total_bytes", "chunk_bytes"}`` or
        ``{"error": "not_connected"}``."""
        from .drive import manifest
        if not self._drive_auth().is_connected():
            return {"error": "not_connected"}
        lib = self.cfg.library_path
        local = []
        for t in self.db.library_tracks():
            if t.get("library_status") == "memory":
                continue
            fn = t.get("filename")
            p = (lib / fn) if fn else None
            if p and p.exists():
                local.append({"size": p.stat().st_size, **{k: t.get(k) for k in
                             ("beatmapset_id", "filename", "drive_hash")}})
        shard_dir = self.cfg.drive_cache_path
        shard_dir.mkdir(parents=True, exist_ok=True)
        shard_path = shard_dir / manifest.shard_name(self.cfg.device_id)
        entries = manifest.load_shard(shard_path)
        to_upload = manifest.diff_to_upload(local, entries)
        return {"count": len(to_upload),
                "total_bytes": sum(int(t["size"]) for t in to_upload),
                "chunk_bytes": self.cfg.drive_chunk_bytes}

    def backup_to_drive(self, progress=None, max_sets: int | None = None,
                        chunk_bytes: int | None = None) -> dict:
        """Back up new Library .osz to Google Drive as append-only chunk
        archives, updating this device's manifest shard.

        ``max_sets`` caps how many new sets to upload this run (None = all);
        ``chunk_bytes`` overrides the per-chunk size for this run. Returns
        ``{"uploaded", "chunks", "skipped"}`` or ``{"error": ...}``.
        """
        from .drive import bundle, manifest
        from .drive.auth import DriveCancelled, DriveError
        self._drive_cancel.clear()
        auth = self._drive_auth()
        if not auth.is_connected():
            return {"error": "not_connected"}

        # 1. Library tracks that actually have a physical .osz to upload.
        lib = self.cfg.library_path
        local: list[dict] = []
        for t in self.db.library_tracks():
            if t.get("library_status") == "memory":
                continue  # memory-only row: nothing on disk to back up
            fn = t.get("filename")
            p = (lib / fn) if fn else None
            if p and p.exists():
                item = dict(t)
                item["_path"] = p
                item["size"] = p.stat().st_size
                local.append(item)

        # 2. Diff against this device's shard (append-only, incremental).
        shard_dir = self.cfg.drive_cache_path
        shard_dir.mkdir(parents=True, exist_ok=True)
        shard_path = shard_dir / manifest.shard_name(self.cfg.device_id)
        entries = manifest.load_shard(shard_path)
        to_upload = manifest.diff_to_upload(local, entries)
        if max_sets is not None and max_sets >= 0:
            to_upload = to_upload[:max_sets]   # user chose a per-run cap
        if not to_upload:
            self.log.info("DRIVE_BACKUP", uploaded=0, skipped=len(local), chunks=0)
            return {"uploaded": 0, "skipped": len(local), "chunks": 0}

        try:
            client = self._make_drive_client()
            folder = self.cfg.drive_folder_id or client.ensure_folder("Rosu")
            if folder != self.cfg.drive_folder_id:
                self.cfg.drive_folder_id = folder
                config.save_config(self.cfg)

            if chunk_bytes == 0:   # "individual" mode — one Drive file per set
                return self._backup_individual(
                    client, folder, to_upload, entries, shard_path, len(local),
                    progress)

            start = self._drive_next_chunk_index(client, folder, entries)
            items = [{"track": t, "path": t["_path"], "size": t["size"]}
                     for t in to_upload]
            chunks = bundle.plan_chunks(items, chunk_bytes or self.cfg.drive_chunk_bytes,
                                        start, self.cfg.device_id)

            total = len(to_upload)
            done = 0
            uploaded = 0
            uploaded_chunks = 0
            cancelled = False
            for ch in chunks:
                if self._drive_cancel.is_set():
                    cancelled = True
                    break
                members = [it["path"] for it in ch["items"]]
                local_chunk = shard_dir / ch["name"]
                bundle.write_chunk(members, local_chunk)
                try:
                    client.upload_file(local_chunk, ch["name"], folder,
                                       cancel=self._drive_cancel.is_set)
                except DriveCancelled:
                    cancelled = True
                finally:
                    # transient staging copy — remove even if the upload failed
                    try:
                        local_chunk.unlink()
                    except OSError:
                        pass
                if cancelled:
                    break
                for it in ch["items"]:
                    t = it["track"]
                    sha = bundle.sha256_file(it["path"])
                    entries[manifest.track_key(t)] = manifest.entry_from_track(
                        t, ch["name"], it["size"], sha)
                    row = self.db.find_track_row(t.get("beatmapset_id"),
                                                 t.get("filename"))
                    if row:
                        self.db.set_drive_state(row["id"], True, ch["name"], sha)
                    uploaded += 1
                    done += 1
                    if progress:
                        progress({"kind": "backup", "name": t.get("filename"),
                                  "done": done, "total": total})
                uploaded_chunks += 1
                # persist the shard after each chunk so a crash mid-run resumes
                manifest.save_shard(shard_path, self.cfg.device_id, entries)

            if uploaded:
                self._push_shard(client, shard_path, folder)
            self.log.info("DRIVE_BACKUP", uploaded=uploaded, chunks=uploaded_chunks,
                          skipped=len(local) - len(to_upload), cancelled=cancelled)
            return {"uploaded": uploaded, "chunks": uploaded_chunks,
                    "skipped": len(local) - len(to_upload), "cancelled": cancelled}
        except DriveError as exc:
            self.log.error("drive:backup", str(exc)[:300])
            return {"error": "drive", "detail": str(exc)[:300]}

    def _backup_individual(self, client, folder, to_upload, entries, shard_path,
                           local_count, progress) -> dict:
        """Upload each .osz as its own Drive file (no chunk archive) so sets are
        browsable individually in Drive. Slower (one upload per set) but each file
        stands alone. Raises DriveError to the caller's handler on transport
        failure; DriveCancelled stops early keeping partial progress."""
        from .drive import bundle, manifest
        from .drive.auth import DriveCancelled
        total = len(to_upload)
        done = uploaded = 0
        cancelled = False
        for t in to_upload:
            if self._drive_cancel.is_set():
                cancelled = True
                break
            path = t["_path"]
            name = t.get("filename") or path.name
            try:
                client.upload_file(path, name, folder,
                                   cancel=self._drive_cancel.is_set)
            except DriveCancelled:
                cancelled = True
                break
            sha = bundle.sha256_file(path)
            entries[manifest.track_key(t)] = manifest.entry_from_track(
                t, name, t["size"], sha)
            row = self.db.find_track_row(t.get("beatmapset_id"), t.get("filename"))
            if row:
                self.db.set_drive_state(row["id"], True, name, sha)
            uploaded += 1
            done += 1
            if progress:
                progress({"kind": "backup", "name": name,
                          "done": done, "total": total})
            manifest.save_shard(shard_path, self.cfg.device_id, entries)
        if uploaded:
            self._push_shard(client, shard_path, folder)
        self.log.info("DRIVE_BACKUP", uploaded=uploaded, chunks=0, individual=True,
                      skipped=local_count - total, cancelled=cancelled)
        return {"uploaded": uploaded, "chunks": 0,
                "skipped": local_count - total, "cancelled": cancelled}

    def _push_shard(self, client, shard_path, folder) -> None:
        """Publish this device's manifest shard to Drive (replace the prior copy
        so shards don't accumulate). Non-fatal on failure."""
        from .drive.auth import DriveError
        try:
            existing = client.find_file(shard_path.name, folder)
            if existing:
                client.delete_file(existing)
            client.upload_file(shard_path, shard_path.name, folder)
        except DriveError as exc:
            self.log.error("drive:shard", str(exc)[:200])

    def _drive_next_chunk_index(self, client, folder, entries) -> int:
        """Next append-only chunk index for THIS device, reconciled with Drive.

        Seeds from the local shard AND the actual Drive folder listing, so a
        lost/cleared local cache or a reinstall never restarts numbering at 0
        and collides (by name) with a chunk already in the shared folder.
        """
        from .drive import bundle
        from .drive.auth import DriveError
        prefix = f"chunk-{self.cfg.device_id}-"
        highest = bundle.next_chunk_index(entries) - 1   # local-shard max, or -1
        try:
            for f in client.list_folder(folder):
                name = f.get("name", "")
                if name.startswith(prefix):
                    idx = bundle.parse_chunk_index(name)
                    if idx is not None and idx > highest:
                        highest = idx
        except DriveError:
            pass   # listing failed -> fall back to the local-shard index
        return highest + 1
