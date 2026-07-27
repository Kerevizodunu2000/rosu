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


class HealthMixin:
        def library_health(self, progress=None) -> dict:
            """Read-only Library report: disk usage, biggest sets, and a DB↔disk
            scrub (orphans / dead links / memory-only). Never modifies anything."""
            from .. import health
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
            from .. import health
            from ..drive import bundle
            self._verify_cancel.clear()   # own token: never collides with import/Drive
            lib = self.cfg.library_path
            rows = [r for r in self.db.library_tracks()
                    if r.get("in_library") and r.get("filename")]
            total = len(rows) if max_files is None else min(len(rows), max_files)
            checked = ok = mismatch = unhashed = missing = pruned = 0
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
                if r.get("is_pruned"):
                    # Pruning intentionally changes the file's bytes, so a hash
                    # taken at backup time is expected to no longer match — that
                    # is not corruption. Count it separately instead of raising
                    # a false "mismatch" alarm.
                    pruned += 1
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
                          unhashed=unhashed, missing=missing, pruned=pruned,
                          cancelled=cancelled)
            return {"checked": checked, "ok": ok, "mismatch": mismatch,
                    "unhashed": unhashed, "missing": missing, "pruned": pruned,
                    "mismatches": mismatches[:50], "cancelled": cancelled}

        def repair_maps(self, filenames: list[str], progress=None, cancel=None) -> dict:
            """Re-download missing or pruned maps from a third-party osu! mirror
            (Mino/Catboy — see ``rosu/api_mirror.py``) and clear their pruned flag
            on success. Returns ``{"repaired", "failed"}``; the UI layer owns
            presenting the result (this stays Qt-free like the rest of services/)."""
            from ..api_mirror import download_osz
            _eff = cancel if cancel is not None else (lambda: False)
            repaired = 0
            failed: list[str] = []
            lib = self.cfg.library_path
            total = len(filenames)

            for i, filename in enumerate(filenames, 1):
                if _eff():
                    break
                if progress:
                    progress({"kind": "repair", "done": i, "total": total, "name": filename})

                found = self.db.track_beatmapset_id(filename)
                if not found or not found[0]:
                    failed.append(filename)
                    continue
                beatmapset_id, track_id = found
                dest = lib / filename

                if download_osz(beatmapset_id, dest):
                    repaired += 1
                    self.db.set_pruned_state(track_id, False, None)
                    self.log.info("RESTORED", file=filename,
                                  beatmapset_id=beatmapset_id)
                    # A repaired-from-missing map is physically back in the
                    # Library — without this, "missing" rows stayed missing in
                    # Search until an unrelated Refresh reconciled them.
                    self.db.set_library_state(track_id, True, "present", now_iso())
                else:
                    failed.append(filename)

            if repaired > 0:
                self.db._bump()
            self.log.info("MAP_REPAIR", repaired=repaired, failed=len(failed))
            return {"repaired": repaired, "failed": failed}

