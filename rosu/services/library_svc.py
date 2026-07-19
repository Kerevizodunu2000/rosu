# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
import datetime as _dt
import threading
import time
from pathlib import Path

from .. import (
    archives, config, excel_report, extractor, gaps, jobs, library, osu_api,
    osu_import, parsing, search, db, msd, ratings
)
from ..models import ExtractPlan, ParsedPack

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
            when = now_iso()
            res = library.copy_to_library(
                self.cfg.output_path, self.cfg.library_path, self.db, when,
                self.cfg.library_physical_copy, progress,
                auto_prune=self.cfg.auto_prune, prune_mode=self.cfg.prune_mode)
            self.log.info("LIBRARY_COPY", new=res["new"], duplicates=res["duplicates"],
                          dup_ids=res["dup_ids"][:50])
            return res

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
            self.log.info("REFRESH", added=res["added"],
                          disappeared=res["disappeared"], present=res["present"])
            return res

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
                source_label=source_label, auto_prune=self.cfg.auto_prune,
                prune_mode=self.cfg.prune_mode)
            self.rebuild()
            self.log.info("LIBRARY_COPY", new=res["new"], duplicates=res["duplicates"],
                          dup_ids=res["dup_ids"][:50])
            return res

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

        def prune_library(self, names=None, progress=None, cancel=None) -> dict:
            """Recycle heavy assets from .osz in the Library. 
            Returns ``{"pruned","freed_bytes"}``."""
            from ..prune import prune_osz
            _eff = cancel if cancel is not None else (lambda: False)
            lib = self.cfg.library_path
            
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
                        freed_this = prune_osz(p, mode=self.cfg.prune_mode)
                        if freed_this > 0:
                            pruned_count += 1
                            freed += freed_this
                            # update db
                            row = self.db.find_track_row(None, name)
                            if row:
                                self.db.set_pruned_state(row["id"], True, original_size)
                    except Exception as e:
                        self.log.error("PRUNE_ERROR", file=name, error=str(e))
                if progress:
                    progress({"done": i + 1, "total": len(names), "file": name})
                    
            if pruned_count:
                self.log.info("LIBRARY_PRUNED", pruned=pruned_count, freed_bytes=freed)
            return {"pruned": pruned_count, "freed_bytes": freed}

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

