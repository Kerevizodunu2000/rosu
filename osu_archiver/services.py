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
    n = 0
    for p in Path(folder).glob("*.osz"):
        try:
            p.unlink()
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

    def request_cancel(self) -> None:
        self._cancel.set()

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
        info = excel_report.build_report(self.db, self.cfg.excel_path,
                                         self._reference())
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
        if not res.get("cancelled") and self.cfg.clear_output_after_import:
            _clear_osz(self.cfg.output_path)
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
    def search(self, query: str) -> list[dict]:
        rows = search.search(self.db, query)
        self.log.info("SEARCH", query=query, results=len(rows))
        return rows

    def artists(self, descending: bool = True) -> list[dict]:
        return self.db.artists_by_count(descending)

    def tracks_by_artist(self, artist: str) -> list[dict]:
        return self.db.tracks_by_artist(artist)
