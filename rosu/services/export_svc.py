# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
import datetime as _dt
from pathlib import Path

from .. import config, jobs, osu_import, parsing

_CLIENT_LABEL = {"lazer": "osu!lazer", "stable": "osu!(stable)"}

def now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()

def _sample_export(files, limit):
    if limit is None or limit <= 0 or len(files) <= limit:
        return files
    import random
    return random.sample(files, limit)


class ExportMixin:
        def export_sets(self, source: str, dest_base, fmt: str = "zip",
                        split_bytes: int | None = None, upload_to_drive: bool = False,
                        share: bool = False, progress=None,
                        limit: int | None = None, star_range=None) -> dict:
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
    
            from .. import exporter
            self._cancel.clear()   # own the token for this export (gather → write)
            stage = Path(tempfile.mkdtemp(prefix="rosu_export_"))
            try:
                files = self._gather_export_sources(source, stage, progress,
                                                    star_range=star_range)
                files = _sample_export(files, limit)
                if not files or self._cancel.is_set():
                    return {"source": source, "count": 0, "archives": [],
                            "cancelled": self._cancel.is_set()}
                pm = self.cfg.prune_mode if getattr(self.cfg, "export_prune", False) else None
                written = exporter.write_export(files, Path(dest_base), fmt, split_bytes,
                                                progress, cancel=self._cancel.is_set,
                                                prune_mode=pm)
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
                                   cancel=None, star_range=None) -> list:
            """Collect the ``.osz`` file paths that make up an export ``source`` (see
            :meth:`export_sets`). Client sources are materialised into ``stage``.
            ``cancel`` (a queued job's own token) is threaded into the client re-export.
            ``star_range`` ``(lo, hi)`` keeps only Library sets whose ``star_max`` is in
            that range (v1.6) — applied to the Library-backed sources (library/drive and
            the Library portion of ``merged``); client-only maps have no stored star, so
            they are left unfiltered."""
            from ..parsing import parse_osz_entry
            lib = self.cfg.library_path
    
            def in_star_range(paths: list) -> list:
                if not star_range:
                    return paths
                lo, hi = star_range
                smax = {r["filename"]: r.get("star_max") for r in self.db.library_records()
                        if r.get("filename")}
                return [p for p in paths
                        if (s := smax.get(p.name)) is not None and lo <= s <= hi]
    
            def lib_files(only_drive: bool = False) -> list:
                if not lib.exists():
                    return []
                if not only_drive:
                    return in_star_range(sorted(lib.glob("*.osz")))
                names = {r["filename"] for r in self.db.library_records()
                         if r.get("in_drive") and r.get("filename")}
                return in_star_range(sorted(p for n in names if (p := lib / n).exists()))
    
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
            from ..drive.auth import DriveCancelled, DriveError
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

        def build_unpack_job(self, targets, skip_duplicates: bool = True) -> jobs.Job:
            """Shortcut ⑤ as a job: prescan → extract → send(target…). Mirrors
            :meth:`unpack_and_import`; the result dict shape is identical."""
            title = ("job_unpack_both" if len(targets) > 1
                     else f"job_unpack_{targets[0]}")
            job = jobs.Job(jobs.new_id(), title, kind="unpack")
            # "Only new" vs "All" is invisible in the title — surface it as data.
            job.ctx["options"] = {"skip_duplicates": bool(skip_duplicates)}

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
                if not self.client_enabled(target):
                    continue   # disabled client: never import into it (v1.4)
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
                if not self.client_enabled(s):
                    continue   # disabled client: don't read it into the Library (v1.4)
                key = ("job_step_save_stable" if s == "stable"
                       else "job_step_save_lazer")
                job.steps.append(jobs.Step(key, jobs.Lane.DISK, s_source(s)))
            job.finalize = lambda ctx: ctx.get("out", {})
            return job

        def build_export_job(self, source: str, dest_base, fmt: str = "zip",
                             split_bytes: int | None = None, upload: bool = False,
                             share: bool = False, limit: int | None = None,
                             star_range=None) -> jobs.Job:
            """Shortcut ④ as a job: gather → archive (DISK) → upload (DRIVE). The
            upload step is on the DRIVE lane, so once an export starts uploading the
            DISK lane frees for the next queued job (disk work ↔ Drive upload)."""
            import shutil
            import tempfile
            from .. import exporter
            dest_base = Path(dest_base)
            name = f"{dest_base.name}{'.7z' if fmt == '7z' else '.zip'}"
            job = jobs.Job(jobs.new_id(), "job_export", kind="export",
                           title_kwargs={"source": source, "name": name},
                           tooltip=str(dest_base.parent))
            stage = Path(tempfile.mkdtemp(prefix="rosu_export_"))
            job.ctx["stage"] = stage
            # Where this job will write. The UI reads it to refuse a second export
            # aimed at the same destination — otherwise job 2's archive overwrites
            # job 1's *while job 1 is uploading it* (the lanes overlap by design).
            job.ctx["dest_base"] = str(dest_base)
            # Every choice behind this job, as data. Two exports differing only in
            # random-N or star range used to render as identical queue rows (the
            # title carries just source + filename), so the user could not tell
            # them apart. The UI turns this into a translated detail line — the
            # service layer stays Qt- and i18n-free.
            job.ctx["options"] = {
                "source": source, "archive_name": name, "fmt": fmt,
                "split_bytes": split_bytes, "upload": upload, "share": share,
                "limit": limit, "star_range": star_range,
                "dest": str(dest_base.parent),
            }
            job.on_cleanup.append(lambda: shutil.rmtree(stage, ignore_errors=True))
    
            def s_gather(ctx, progress, cancel):
                files = self._gather_export_sources(source, ctx["stage"], progress,
                                                    cancel=cancel, star_range=star_range)
                ctx["files"] = _sample_export(files, limit)
    
            def s_archive(ctx, progress, cancel):
                files = ctx.get("files", [])
                if not files or cancel():
                    ctx["written"] = []
                    return
                pm = self.cfg.prune_mode if getattr(self.cfg, "export_prune", False) else None
                ctx["written"] = exporter.write_export(
                    files, Path(dest_base), fmt, split_bytes, progress, cancel=cancel,
                    prune_mode=pm)
    
            def s_upload(ctx, progress, cancel):
                if cancel() or not ctx.get("written"):
                    return
                res = self._upload_export_to_drive(
                    ctx["written"], share, progress, cancel=cancel)
                ctx["drive"] = res
                if res.get("error"):
                    # Raise so the queue marks THIS step (and the job) FAILED — a
                    # failed upload must never render as a ✓ tick. The archives are
                    # already on disk; the UI's failure presenter says where.
                    raise RuntimeError(
                        f"Drive upload failed: {res.get('detail') or res['error']}")
    
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

        def pruned_count(self) -> int:
            """How many Library sets are currently pruned (for the restore flow)."""
            return len(self.db.pruned_filenames())

        def build_restore_pruned_job(self, filenames=None) -> jobs.Job:
            """Undo prune in bulk: re-download every pruned set at full size.

            Prune's own Recycle-Bin copy is the *local* undo, but it only survives
            until the bin is emptied and only covers the Library. This re-fetches
            the complete set from an osu! mirror, which works however long ago the
            prune happened. Cancellable — it is a lot of downloading.
            """
            names = list(filenames) if filenames is not None else self.db.pruned_filenames()
            job = jobs.Job(jobs.new_id(), "job_restore_pruned", kind="restore")
            job.ctx["options"] = {"restore_sets": len(names)}

            def s_restore(ctx, progress, cancel):
                ctx["result"] = self.repair_maps(names, progress=progress,
                                                 cancel=cancel)

            job.steps = [jobs.Step("job_step_restore", jobs.Lane.DISK, s_restore)]
            job.finalize = lambda ctx: ctx.get("result", {"repaired": 0, "failed": []})
            return job

        def build_prune_apply_job(self, source: str, mode: str, keys,
                                  freed_estimate: int = 0) -> jobs.Job:
            """Apply an ALREADY-PREVIEWED prune (the v1.7.1 Prune dialog).

            No gate here on purpose: the dialog has shown exactly which sets would
            lose what, and taken a countdown confirmation. Re-asking inside the
            queue would be a second confirmation for a decision already made.
            """
            keys = list(keys or [])
            job = jobs.Job(jobs.new_id(), "job_prune", kind="prune",
                           title_kwargs={})
            job.ctx["options"] = {"prune_source": source, "mode": mode,
                                  "sets": len(keys),
                                  "freed_estimate": int(freed_estimate)}

            def s_remove(ctx, progress, cancel):
                ctx["result"] = self.prune_apply(source, mode, keys,
                                                 progress=progress, cancel=cancel)

            job.steps = [jobs.Step("job_step_prune_remove", jobs.Lane.DISK,
                                   s_remove)]
            job.finalize = lambda ctx: ctx.get(
                "result", {"pruned": 0, "freed_bytes": 0})
            return job

        def build_prune_job(self) -> jobs.Job:
            """Library prune as a job: scan (preview) -> GATED remove. The remove step
            waits for an explicit UI confirmation."""
            job = jobs.Job(jobs.new_id(), "job_prune", kind="prune")
            # Which prune mode this run will use — it comes from Settings, so the
            # queue row is the only place the user can see what was actually picked.
            job.ctx["options"] = {"mode": getattr(self.cfg, "prune_mode", "") or ""}

            def s_scan(ctx, progress, cancel):
                ctx["plan"] = self.prune_library_plan()
    
            def s_remove(ctx, progress, cancel):
                names = ctx.get("plan", {}).get("names", [])
                ctx["result"] = self.prune_library(names=names, progress=progress,
                                                   cancel=cancel)
    
            job.steps = [jobs.Step("job_step_prune_scan", jobs.Lane.DISK, s_scan),
                         jobs.Step("job_step_prune_remove", jobs.Lane.DISK, s_remove,
                                   gated=True)]
            job.finalize = lambda ctx: ctx.get(
                "result", {"pruned": 0, "freed_bytes": 0})
            return job

        def _drive_auth(self):
            """Lazily build+cache DriveAuth (keeps keyring/urllib off the startup
            path and out of ``--selftest``)."""
            auth = getattr(self, "_drive_auth_obj", None)
            if auth is None:
                from ..drive.auth import DriveAuth
                auth = DriveAuth()
                self._drive_auth_obj = auth
            return auth

        def _make_drive_client(self):
            from ..drive.client import DriveClient
            return DriveClient(self._drive_auth())

        def drive_status(self) -> dict:
            auth = self._drive_auth()
            return {"configured": auth.is_configured(),
                    "connected": auth.is_connected(),
                    "can_store": auth.can_store_token()}

        def connect_drive(self, progress=None) -> dict:
            """Run the Google OAuth consent flow (off-thread) and remember it."""
            from ..drive.auth import DriveError, DriveNotConfigured
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
            from ..drive import manifest
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
            from ..drive import bundle, manifest
            from ..drive.auth import DriveCancelled, DriveError
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
            from ..drive import bundle, manifest
            from ..drive.auth import DriveCancelled
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
            from ..drive.auth import DriveError
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
            from ..drive import bundle
            from ..drive.auth import DriveError
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

