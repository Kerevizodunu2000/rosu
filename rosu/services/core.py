# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
import datetime as _dt
import threading

from .. import config, excel_report, gaps

_CLIENT_LABEL = {"lazer": "osu!lazer", "stable": "osu!(stable)"}

def now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()

def _sample_export(files, limit):
    if limit is None or limit <= 0 or len(files) <= limit:
        return files
    import random
    return random.sample(files, limit)


class BaseServices:
        def __init__(self, cfg: config.Config, db, log):
            self.cfg = cfg
            self.db = db
            self.log = log
            self._cancel = threading.Event()  # cooperative cancel for osu! import
            self._drive_cancel = threading.Event()  # separate cancel for Drive ops
            self._lostmap_cancel = threading.Event()  # separate cancel for lost-map scan
            self._verify_cancel = threading.Event()  # separate cancel for SHA-256 verify
            self._ratings_cancel = threading.Event()  # separate cancel for star-rating scan
            self._enrich_cancel = threading.Event()  # separate cancel for API enrichment
            self._msd_cancel = threading.Event()  # separate cancel for skillset (MSD) scan
            self._prune_cancel = threading.Event()  # separate cancel for the prune scan
            self._reference_cancel = threading.Event()  # separate cancel for the pack-reference sync
            self._removal_cancel = threading.Event()  # separate cancel for the remove-from-client scan
            self._collections_cancel = threading.Event()  # separate cancel for collection sync
            self._rebuild_lock = threading.Lock()  # serialize tracking.xlsx writes
            self._reference_cache = None           # lazy osu! reference (invalidated on sync)

        def request_cancel(self) -> None:
            # Set all so the shared Dashboard/close-window cancel reaches whichever
            # operation is running; each op clears only its OWN token at start, so one
            # operation can never wipe another's in-flight cancel (import vs Drive vs
            # lost-map scan can run concurrently from different tabs).
            self._cancel.set()
            self._drive_cancel.set()
            self._lostmap_cancel.set()
            self._verify_cancel.set()
            self._ratings_cancel.set()
            self._enrich_cancel.set()
            self._msd_cancel.set()
            self._prune_cancel.set()
            self._reference_cancel.set()
            self._removal_cancel.set()
            self._collections_cancel.set()

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

        def data_generation(self) -> int:
            """Monotonic counter bumped on track writes — the Artists tab uses it to
            skip a costly rebuild when nothing changed (item 10)."""
            return self.db.data_generation()

