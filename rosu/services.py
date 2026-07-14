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
    config, excel_report, extractor, gaps, library, osu_api, osu_import, search,
)
from .models import ExtractPlan, ParsedPack


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


class Services:
    def __init__(self, cfg: config.Config, db, log):
        self.cfg = cfg
        self.db = db
        self.log = log
        self._cancel = threading.Event()  # cooperative cancel for osu! import
        self._drive_cancel = threading.Event()  # separate cancel for Drive ops
        self._rebuild_lock = threading.Lock()  # serialize tracking.xlsx writes

    def request_cancel(self) -> None:
        # Set both so the shared Dashboard/close-window cancel reaches whichever
        # operation is running; each op clears only its OWN token at start, so a
        # Drive login can never wipe an in-flight osu!-import cancel (or vice versa).
        self._cancel.set()
        self._drive_cancel.set()

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
    def extract(self, approved: list[tuple[Path, ParsedPack]], progress=None) -> dict:
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
        for zip_path, parsed in approved:
            res = extractor.extract_pack(zip_path, parsed, self.cfg.output_path,
                                         self.db, when, _cb, log=self.log)
            total_tracks += res["tracks"]
            if res.get("extra_files"):
                self.db.set_pack_extra(parsed.code, len(res["extra_files"]))
            self.log.info("EXTRACT_PACK", code=parsed.code, tracks=res["tracks"],
                          subfolders=res["subfolders"])
            action = extractor.dispose_zip(zip_path, self.cfg.zip_disposal, processed_dir)
            fields = {"file": zip_path.name}
            if action == "ZIP_MOVED":
                fields["dest"] = str(processed_dir)
            self.log.info(action, **fields)

        info = self.rebuild()
        duration = int(time.time() - start)
        self.log.info("EXTRACT_DONE", packs=len(approved), tracks=total_tracks,
                      duration_s=duration)
        result = {"packs": len(approved), "tracks": total_tracks, **info}

        if self.cfg.auto_backup_after_extract:
            backup = self.copy_library(progress)
            result["backup"] = backup
        return result

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
    def import_osz_folder(self, folder, progress=None) -> dict:
        """Dedup every .osz/.olz in ``folder`` into the Library (shared by the
        stable, lazer and manual import paths)."""
        cb = (lambda name: progress({"kind": "import", "name": name})) if progress else None
        res = library.copy_to_library(folder, self.cfg.library_path, self.db,
                                      now_iso(), self.cfg.library_physical_copy, cb)
        self.rebuild()
        self.log.info("LIBRARY_COPY", new=res["new"], duplicates=res["duplicates"],
                      dup_ids=res["dup_ids"][:50])
        return res

    def import_from_stable(self, progress=None) -> dict:
        """Zip osu!(stable) Songs/ folders we don't already have into Output, then
        dedup them into the Library."""
        from . import client_import
        songs = client_import.stable_songs_dir()
        if not songs:
            return {"source": "stable", "found": False}
        known = self.db.known_track_ids()
        folders = list(client_import.iter_stable_folders(songs))
        made = 0
        for i, folder in enumerate(folders, 1):
            bid = client_import.beatmapset_id_for_folder(folder)
            if bid is None or bid in known:
                continue  # unresolved id, or we already have this set
            osz = self.cfg.output_path / client_import._osz_name_for(folder, bid)
            if not osz.exists():
                client_import.zip_folder_to_osz(folder, osz)
            made += 1
            if progress:
                progress({"kind": "import", "done": i, "total": len(folders)})
        res = self.import_osz_folder(self.cfg.output_path, progress)
        self.log.info("CLIENT_IMPORT", client="stable", added=res["new"], made=made)
        return {"source": "stable", "found": True, "made": made, **res}

    def import_from_lazer(self, progress=None) -> dict:
        """Run the bundled .NET helper to re-export osu!lazer beatmapsets from its
        Realm + files store, then dedup the exported .osz into the Library."""
        import shutil
        import subprocess
        import tempfile
        from . import client_import
        data = client_import.lazer_data_dir()
        if not data:
            return {"source": "lazer", "found": False}
        helper = self._lazer_helper()
        if not helper:
            return {"source": "lazer", "found": True, "error": "helper_missing"}
        out = Path(tempfile.mkdtemp(prefix="rosu_lazer_"))
        try:
            if progress:
                progress("Exporting from osu!lazer…")
            proc = subprocess.run([str(helper), str(data), str(out)],
                                  capture_output=True, text=True, timeout=3600)
            if proc.returncode != 0:
                self.log.error("import:lazer", (proc.stderr or "helper failed")[:300])
                return {"source": "lazer", "found": True, "error": "helper_failed",
                        "detail": (proc.stderr or "")[:300]}
            res = self.import_osz_folder(out, progress)
            self.log.info("CLIENT_IMPORT", client="lazer", added=res["new"], made=0)
            return {"source": "lazer", "found": True, **res}
        finally:
            shutil.rmtree(out, ignore_errors=True)

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

    def refresh(self, progress=None) -> dict:
        when = now_iso()
        res = library.refresh_library(self.cfg.library_path, self.db, when, progress)
        self.rebuild()
        self.log.info("REFRESH", added=res["added"],
                      disappeared=res["disappeared"], present=res["present"])
        return res

    def import_plan(self) -> dict:
        """Info for the pre-import confirmation dialog (no side effects)."""
        files = osu_import.output_osz_files(self.cfg.output_path)
        batches = len(list(osu_import.batches(files)))
        return {"files": len(files), "batches": batches,
                "eta_s": osu_import.estimate_seconds(len(files), batches)}

    # -- osu! import ---------------------------------------------------------
    def import_osu(self, progress=None) -> dict:
        self._cancel.clear()
        files = osu_import.output_osz_files(self.cfg.output_path)
        exe = self.cfg.osu_exe or config.detect_osu_exe()

        def _prog(i, total, n):
            self.log.info("OSU_IMPORT", batch=f"{i}/{total}", files=n)
            if progress:
                progress({"kind": "import", "batch": i, "total": total, "files": n})

        res = osu_import.import_files(exe, files, progress=_prog,
                                      cancel=self._cancel.is_set)
        self.log.info("OSU_IMPORT_DONE", files=res["files"], batches=res["batches"])
        # (Removed the "clear Output after import" option — item 7. osu! consumes the
        # .osz on import, so Output empties itself; an explicit clear was redundant.)
        return res

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
    def search(self, query: str, progress=None) -> list[dict]:
        """Ranked search, or the full name-sorted listing when the box is empty
        (item 11). ``progress`` is accepted so it can run in a Worker thread."""
        if query.strip():
            rows = search.search(self.db, query)
        else:
            rows = self.db.all_tracks()
            self.db.attach_sources_bulk(rows)
        self.log.info("SEARCH", query=query or "(all)", results=len(rows))
        return rows

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
                "connected": auth.is_connected()}

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

    def backup_to_drive(self, progress=None) -> dict:
        """Back up new Library .osz to Google Drive as append-only chunk
        archives, updating this device's manifest shard.

        Returns ``{"uploaded", "chunks", "skipped"}`` or ``{"error": ...}``.
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
        if not to_upload:
            self.log.info("DRIVE_BACKUP", uploaded=0, skipped=len(local), chunks=0)
            return {"uploaded": 0, "skipped": len(local), "chunks": 0}

        try:
            client = self._make_drive_client()
            folder = self.cfg.drive_folder_id or client.ensure_folder("Rosu")
            if folder != self.cfg.drive_folder_id:
                self.cfg.drive_folder_id = folder
                config.save_config(self.cfg)

            start = self._drive_next_chunk_index(client, folder, entries)
            items = [{"track": t, "path": t["_path"], "size": t["size"]}
                     for t in to_upload]
            chunks = bundle.plan_chunks(items, self.cfg.drive_chunk_bytes, start,
                                        self.cfg.device_id)

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
