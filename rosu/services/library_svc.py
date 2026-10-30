# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
import datetime as _dt
from pathlib import Path

from .. import client_remove, diskspace, jobs, library

_CLIENT_LABEL = {"lazer": "osu!lazer", "stable": "osu!(stable)"}

def now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()

def _sample_export(files, limit):
    if limit is None or limit <= 0 or len(files) <= limit:
        return files
    import random
    return random.sample(files, limit)


class LibraryMixin:
        def copy_library(self, progress=None) -> dict:
            """Copy to Library. A free-space refusal or a full disk comes back as
            ``no_space`` / ``disk_full`` in the result, so the Dashboard can
            translate it; any other error propagates."""
            when = now_iso()
            empty = {"new": 0, "duplicates": 0, "dup_ids": []}
            try:
                res = library.copy_to_library(
                    self.cfg.output_path, self.cfg.library_path, self.db, when,
                    self.cfg.library_physical_copy, progress,
                    auto_prune=self.cfg.auto_prune, prune_mode=self.cfg.prune_mode)
            except diskspace.NotEnoughSpace as exc:
                self._warn("library:space", f"Copy to Library refused: {exc}")
                return {**empty, "no_space": {"drive": exc.drive, "need": exc.need,
                                              "free": exc.free}}
            except OSError as exc:
                if not diskspace.is_disk_full(exc):
                    raise
                self._warn("library:copy", f"Copy to Library stopped: disk full: {exc}")
                return {**empty, "disk_full": True,
                        "full_drive": diskspace.space(self.cfg.library_path, 0).drive}
            self.log.info("LIBRARY_COPY", new=res["new"], duplicates=res["duplicates"],
                          dup_ids=res["dup_ids"][:50])
            return res

        def purge_library_files(self, progress=None) -> dict:
            """Move every physical .osz in Library to the Recycle Bin but keep the
            rows as memory-only (item 17). Metadata stays; the files go. Only
            the rows whose file actually reached the Recycle Bin are marked."""
            from send2trash import send2trash
            if not client_remove.recycle_bin_available(self.cfg.library_path):
                # send2trash would delete every file for good
                self.log.error("library:purge", "no Recycle Bin on the Library drive; nothing deleted")
                return {"deleted": 0, "error": "no_recycle_bin"}
            trashed: list[str] = []
            too_large = 0
            files = list(self.cfg.library_path.glob("*.osz"))
            for i, p in enumerate(files, 1):
                if not client_remove.recycle_bin_available(p):
                    self.log.error("library:purge", f"{p.name}: no Recycle Bin on this drive; left in place")
                elif not client_remove.recycle_bin_fits(p):
                    too_large += 1
                    self.log.error("library:purge", f"{p.name}: too large for the Recycle Bin; left in place")
                else:
                    try:
                        send2trash(str(p))
                        trashed.append(p.name)
                    except Exception:
                        pass   # still on disk: its row stays in the Library
                if progress:
                    progress({"kind": "purge", "done": i, "total": len(files)})
            deleted = len(trashed)
            self.db.mark_library_memory(now_iso(), trashed)
            self.rebuild()
            self.log.info("LIBRARY_PURGE", deleted=deleted, too_large=too_large)
            return {"deleted": deleted, "too_large": too_large}

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

        def refresh(self, progress=None) -> dict:
            when = now_iso()
            res = library.refresh_library(self.cfg.library_path, self.db, when, progress)
            self.rebuild()
            for s in res["skipped"]:
                self.log.error("refresh:skip", f"{s['file']}: {s['error']}")
            self.log.info("REFRESH", added=res["added"],
                          disappeared=res["disappeared"], present=res["present"],
                          skipped=len(res["skipped"]))
            return res

        def import_osz_folder(self, folder, progress=None, source_label=None,
                              physical_copy: bool | None = None,
                              auto_prune: bool | None = None) -> dict:
            """Dedup every .osz in ``folder`` into the Library (shared by the stable,
            lazer and manual import paths). Emits k/n import progress (item 3) and, when
            ``source_label`` is set, tags each set with its origin (item 9).
            ``physical_copy`` overrides the setting: saving a set before it leaves
            osu!, or restoring one from Drive, must leave a real file.
            ``auto_prune`` overrides the setting the same way: a set saved
            before removal must stay whole."""
            folder = Path(folder)
            total = sum(1 for _ in folder.glob("*.osz")) if folder.exists() else 0
            done = [0]
    
            def cb(name):
                done[0] += 1
                progress({"kind": "import", "name": name,
                          "done": done[0], "total": total})
    
            res = library.copy_to_library(
                folder, self.cfg.library_path, self.db, now_iso(),
                self.cfg.library_physical_copy if physical_copy is None else physical_copy,
                cb if progress else None,
                source_label=source_label,
                auto_prune=self.cfg.auto_prune if auto_prune is None else auto_prune,
                prune_mode=self.cfg.prune_mode)
            self.rebuild()
            self.log.info("LIBRARY_COPY", new=res["new"], duplicates=res["duplicates"],
                          dup_ids=res["dup_ids"][:50])
            return res

        def import_osz_files(self, paths, progress=None, cancel=None) -> dict:
            """Add these ``.osz`` files to the Library (the watch folder, v1.9).
            They are copied to a temp stage first, so the import never reads a
            file that is still changing — and never moves or deletes the user's
            own copies. ``{"new","duplicates","files","imported","rejected",
            "failed","cancelled"}``: ``imported`` / ``rejected`` (not an archive)
            are done with; ``failed`` (copy error, no space) may be retried."""
            import shutil
            import tempfile
            import zipfile
            _eff = cancel if cancel is not None else (lambda: False)
            srcs = [Path(p) for p in (paths or [])]
            res = {"new": 0, "duplicates": 0, "files": 0, "imported": [], "rejected": [],
                   "failed": [], "cancelled": False}
            need = 0
            for src in srcs:
                try:
                    need += src.stat().st_size
                except OSError:
                    pass
            if not self.cfg.library_path.is_dir():
                # The Library's drive is unplugged (or the folder is gone): do not
                # stage anything; the watcher waits and tries again later.
                res["failed"] = [str(p) for p in srcs]
                self.log.error("watch:library", f"Library folder not available: {self.cfg.library_path}")
                return res
            stage = Path(tempfile.mkdtemp(prefix="rosu_watch_"))
            try:
                margin = 256 * 1024 * 1024
                for where in (stage, self.cfg.library_path):
                    try:
                        if shutil.disk_usage(where).free < need + margin:
                            res["failed"] = [str(p) for p in srcs]
                            self.log.error("watch:space", f"not enough free space in {where}")
                            return res
                    except OSError:
                        pass
                staged: list[Path] = []
                for src in srcs:
                    if _eff():
                        res["cancelled"] = True
                        break
                    if src.suffix.lower() != ".osz" or not src.is_file():
                        res["rejected"].append(str(src))
                        continue
                    try:
                        shutil.copy2(src, stage / src.name)
                    except OSError as exc:
                        res["failed"].append(str(src))
                        self.log.error("watch:copy", f"{src.name}: {str(exc)[:150]}")
                        continue
                    if not zipfile.is_zipfile(stage / src.name):
                        (stage / src.name).unlink(missing_ok=True)
                        res["rejected"].append(str(src))
                        continue
                    staged.append(src)
                res["files"] = len(staged)
                if not staged or res["cancelled"]:
                    res["failed"] += [str(p) for p in staged]   # not imported: try again later
                    return res
                out = self.import_osz_folder(stage, progress, source_label="watch_folder")
                res["new"] = int(out.get("new", 0))
                res["duplicates"] = int(out.get("duplicates", 0))
                res["imported"] = [str(p) for p in staged]
                self.log.info("WATCH_IMPORT", files=len(staged), new=res["new"])
                return res
            finally:
                shutil.rmtree(stage, ignore_errors=True)

        def stage_to_output(self, paths, progress=None) -> dict:
            """Copy chosen Library sets into Output (v1.9), so "Import to osu!"
            sends exactly those. Only files directly in the Library are taken;
            an Output file with the same name is never replaced. ``{"copied",
            "already", "skipped"}``."""
            import os
            import shutil
            import tempfile
            from ..fsutil import place_new
            lib = self.cfg.library_path.resolve()
            out = self.cfg.output_path
            out.mkdir(parents=True, exist_ok=True)
            res = {"copied": 0, "already": 0, "skipped": 0}
            paths = list(paths or [])
            for i, p in enumerate(paths, 1):
                src = Path(p)
                try:
                    inside = src.resolve().parent == lib
                except OSError:
                    inside = False
                if not inside or src.suffix.lower() != ".osz" or not src.is_file():
                    res["skipped"] += 1
                    continue
                dest = out / src.name
                if dest.exists():
                    same = dest.is_file() and dest.stat().st_size == src.stat().st_size
                    res["already" if same else "skipped"] += 1
                    continue
                # Through a temp file next to it, so a failed copy never leaves a
                # half-written .osz in Output for "Import to osu!" to pick up.
                tmp = None
                try:
                    fd, tmp_name = tempfile.mkstemp(dir=out, prefix=".rosu-stage-", suffix=".part")
                    os.close(fd)
                    tmp = Path(tmp_name)
                    shutil.copyfile(src, tmp)
                    shutil.copystat(src, tmp)
                    place_new(tmp, dest)   # never replaces a file that appeared meanwhile
                    tmp = None
                    res["copied"] += 1
                except OSError as exc:
                    res["skipped"] += 1
                    self.log.error("stage:output", f"{src.name}: {str(exc)[:150]}")
                finally:
                    if tmp is not None:
                        tmp.unlink(missing_ok=True)
                if progress:
                    progress({"kind": "stage", "done": i, "total": len(paths)})
            self.log.info("STAGE_OUTPUT", **res)
            return res

        def build_watch_import_job(self, paths) -> jobs.Job:
            """Queue new watch-folder files for import (disk lane)."""
            paths = [str(p) for p in (paths or [])]
            job = jobs.Job(jobs.new_id(), "job_watch_import", kind="watch_import")
            job.ctx["options"] = {"files": len(paths)}
            job.ctx["paths"] = paths

            def s_import(ctx, progress, cancel):
                ctx["result"] = self.import_osz_files(paths, progress, cancel)

            job.steps = [jobs.Step("job_step_watch_import", jobs.Lane.DISK, s_import)]
            job.finalize = lambda ctx: ctx.get("result", {"new": 0})
            return job

        def _dedup_scan(self) -> tuple[list, dict, int]:
            """Scan the Library and plan dedup without deleting: returns
            ``(names_to_remove, sizes_by_name, groups)``. Duplicates are files sharing a
            beatmapset id; the DB-canonical file is kept and a group with no canonical
            file on disk is left alone (removing would orphan the DB row)."""
            from ..parsing import parse_osz_entry
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

        def _prune_scan(self) -> tuple[list[str], dict[str, int]]:
            """Finds mapsets in the Library that have not been pruned yet."""
            lib = self.cfg.library_path
            sizes = {}
            names = []
            # Only consider files that are not already pruned.
            for name in self.db.unpruned_library_filenames():
                p = lib / name
                try:
                    if p.exists():
                        sizes[name] = p.stat().st_size
                        names.append(name)
                except OSError:
                    pass
            return names, sizes

        def prune_library_plan(self, progress=None) -> dict:
            """Preview which files prune WOULD process."""
            names, sizes = self._prune_scan()
            return {"count": len(names),
                    "total_bytes": sum(sizes.get(n, 0) for n in names),
                    "names": names}

        def prune_library(self, names=None, progress=None, cancel=None,
                          mode: str | None = None) -> dict:
            """Recycle heavy assets from .osz in the Library.

            ``mode`` overrides the Settings default, so the Prune dialog can offer
            the choice at the point of use. Returns ``{"pruned","freed_bytes"}``.
            """
            from ..prune import prune_osz
            _eff = cancel if cancel is not None else (lambda: False)
            lib = self.cfg.library_path
            mode = mode or self.cfg.prune_mode

            if names is None:
                names, sizes = self._prune_scan()
            else:
                sizes = {}
                for n in names:
                    try:
                        sizes[n] = (lib / n).stat().st_size
                    except OSError:
                        sizes[n] = 0

            pruned_count = 0
            freed = 0
            
            for i, name in enumerate(names):
                if _eff():
                    break
                p = lib / name
                original_size = sizes.get(name, 0)
                if p.exists() and original_size > 0:
                    try:
                        freed_this = prune_osz(p, mode=mode)
                        if freed_this > 0:
                            pruned_count += 1
                            freed += freed_this
                            row = self.db.find_track_row(None, name)
                            if row:
                                # Tag WHEN and with WHICH mode, so "which maps lost
                                # their video?" is answerable from the data.
                                self.db.set_pruned_state(row["id"], True,
                                                         original_size,
                                                         when=now_iso(), mode=mode)
                            # One line per set: a summary total cannot tell the
                            # owner *which* of their maps was stripped.
                            self.log.info("PRUNED", source="library", file=name,
                                          mode=mode, freed_bytes=freed_this,
                                          original_size=original_size)
                    except Exception as e:
                        self.log.error("PRUNE_ERROR", f"{name}: {type(e).__name__}")
                if progress:
                    progress({"done": i + 1, "total": len(names), "file": name})
                    
            if pruned_count:
                self.log.info("LIBRARY_PRUNED", pruned=pruned_count, freed_bytes=freed)
            return {"pruned": pruned_count, "freed_bytes": freed}

        # -- prune sources (v1.7.1: choose at the point of use) ----------------
        def prune_sources(self) -> list[dict]:
            """The three prune sources and whether each can actually be used.

            ``[{"key", "available", "sets", "reason"}]``. Sizes are deliberately
            NOT computed here — that needs a full scan, which the dialog runs off
            the UI thread once a source is picked.

            ``lazer`` is always ``available: False`` with ``reason="lazer_realm"``.
            That is a technical fact, not a preference: lazer stores files
            content-addressed and **shares one copy between every set containing
            that byte-identical asset**, so deleting a set's video can break other
            sets, and ``client.realm`` would still reference the missing file.
            Pruning lazer must go through its own model (the bundled Realm
            helper) — never the filesystem.
            """
            from .. import client_import
            out = [{"key": "library", "available": True,
                    "sets": len(self.db.unpruned_library_filenames()),
                    "reason": ""}]

            songs = None
            if self.client_enabled("stable"):
                try:
                    songs = client_import.stable_songs_dir()
                except Exception:
                    songs = None
            if songs is not None:
                try:
                    sets = sum(1 for _ in client_import.iter_stable_folders(songs))
                except OSError:
                    sets = 0
                out.append({"key": "stable", "available": True, "sets": sets,
                            "reason": ""})
            else:
                out.append({"key": "stable", "available": False, "sets": 0,
                            "reason": "no_stable"})

            out.append({"key": "lazer", "available": False, "sets": 0,
                        "reason": "lazer_realm"})
            return out

        def _prune_candidates(self, source: str):
            """``(key, display_name, path)`` for every set a prune could touch."""
            from .. import client_import
            if source == "stable":
                songs = client_import.stable_songs_dir()
                if songs is None:
                    return []
                return [(f.name, f.name, f)
                        for f in client_import.iter_stable_folders(songs)]
            lib = self.cfg.library_path
            # Already-pruned sets are excluded by the query, so a second run
            # never re-offers what it already stripped.
            return [(n, n, lib / n) for n in self.db.unpruned_library_filenames()]

        def prune_scan(self, source: str = "library", mode: str | None = None,
                       progress=None, cancel=None) -> dict:
            """Read-only preview: what each set would lose under ``mode``.

            Returns ``{"source", "mode", "sets": [{"key","name","size","freed"}],
            "total_bytes", "freed_bytes", "scanned", "cancelled"}``. Nothing is
            written or deleted — the caller picks a sort/limit from this and only
            then applies.
            """
            from .. import prune as prune_mod
            mode = mode or self.cfg.prune_mode
            # Own token, so closing the dialog mid-scan stops THIS scan without
            # disturbing an import or a Drive upload running alongside it.
            self._prune_cancel.clear()
            _eff = cancel if cancel is not None else self._prune_cancel.is_set
            scan = (prune_mod.scan_folder if source == "stable"
                    else prune_mod.scan_osz)
            candidates = self._prune_candidates(source)
            rows: list[dict] = []
            total = freed = 0
            cancelled = False
            for i, (key, name, path) in enumerate(candidates):
                if _eff():
                    cancelled = True
                    break
                try:
                    size, removable = scan(path, mode)
                except Exception:
                    continue      # one unreadable set must not abort the scan
                total += size
                freed += removable
                if removable > 0:
                    rows.append({"key": key, "name": name, "size": size,
                                 "freed": removable})
                if progress:
                    progress({"kind": "prune_scan", "done": i + 1,
                              "total": len(candidates), "name": name})
            self.log.info("PRUNE_SCAN", source=source, mode=mode,
                          candidates=len(candidates), prunable=len(rows),
                          freed_bytes=freed, cancelled=cancelled)
            return {"source": source, "mode": mode, "sets": rows,
                    "total_bytes": total, "freed_bytes": freed,
                    "scanned": len(candidates), "cancelled": cancelled}

        def cancel_prune_scan(self) -> None:
            """Cancel only an in-progress prune SCAN (leaves other ops alone)."""
            self._prune_cancel.set()

        def prune_stable(self, folders, progress=None, cancel=None,
                         mode: str | None = None) -> dict:
            """Recycle the unwanted files inside the given ``Songs/<set>/`` folders.

            Every folder is resolved against the detected Songs directory before
            anything is touched, so a name that escapes it is refused rather than
            deleted.
            """
            from .. import client_import, prune as prune_mod
            mode = mode or self.cfg.prune_mode
            _eff = cancel if cancel is not None else (lambda: False)
            songs = client_import.stable_songs_dir()
            if songs is None:
                return {"pruned": 0, "freed_bytes": 0, "error": "no_stable"}
            names = list(folders or [])
            pruned = freed = 0
            for i, name in enumerate(names):
                if _eff():
                    break
                try:
                    freed_this = prune_mod.prune_folder(songs / name, mode=mode,
                                                        root=songs)
                except Exception as exc:
                    self.log.error("PRUNE_ERROR", f"{name}: {type(exc).__name__}")
                    freed_this = 0
                if freed_this > 0:
                    pruned += 1
                    freed += freed_this
                    # Note WHERE it happened, but never set `is_pruned` — that
                    # flag means "the Library copy is stripped", and this one
                    # isn't. Without the distinction a row claimed every copy of
                    # the set had been pruned when only stable's had.
                    bid = client_import.beatmapset_id_for_folder(songs / name)
                    row = self.db.find_track_row(bid, None) if bid else None
                    if row:
                        self.db.note_pruned_source(row["id"], "stable",
                                                   when=now_iso(), mode=mode)
                    self.log.info("PRUNED", source="stable", folder=name,
                                  mode=mode, freed_bytes=freed_this)
                if progress:
                    progress({"kind": "prune", "done": i + 1, "total": len(names),
                              "name": name})
            if pruned:
                self.log.info("STABLE_PRUNED", pruned=pruned, freed_bytes=freed)
            return {"pruned": pruned, "freed_bytes": freed}

        def prune_apply(self, source: str, mode: str, keys, progress=None,
                        cancel=None) -> dict:
            """Apply a prune to the chosen sets of ``source``. Qt-free."""
            if source == "stable":
                return self.prune_stable(keys, progress=progress, cancel=cancel,
                                         mode=mode)
            if source == "lazer":
                # Never reachable from the UI (the source is offered disabled),
                # but fail loudly rather than silently doing nothing if it ever is.
                return {"pruned": 0, "freed_bytes": 0, "error": "lazer_realm"}
            return self.prune_library(names=list(keys or []), progress=progress,
                                      cancel=cancel, mode=mode)

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
            if not client_remove.recycle_bin_available(lib):
                # send2trash would delete every duplicate for good
                self.log.error("dedup", "no Recycle Bin on the Library drive; nothing deleted")
                return {"removed": 0, "freed_bytes": 0, "groups": groups,
                        "error": "no_recycle_bin"}
            removed = freed = too_large = 0
            for i, name in enumerate(names, 1):
                if _eff():
                    break
                if not client_remove.recycle_bin_available(lib / name):
                    self.log.error("dedup", f"{name}: no Recycle Bin on this drive; left in place")
                elif not client_remove.recycle_bin_fits(lib / name):
                    too_large += 1
                    self.log.error("dedup", f"{name}: too large for the Recycle Bin; left in place")
                else:
                    try:
                        send2trash(str(lib / name))
                        removed += 1
                        freed += sizes.get(name, 0)
                    except OSError as exc:
                        self.log.error("dedup", str(exc)[:200])
                if progress:
                    progress({"kind": "dedup", "done": i, "total": len(names)})
            self.log.info("LIBRARY_DEDUP", removed=removed,
                          freed_mb=freed // (1024 * 1024), groups=groups, too_large=too_large)
            return {"removed": removed, "freed_bytes": freed, "groups": groups,
                    "too_large": too_large}

