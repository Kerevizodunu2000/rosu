# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings tab — the maintenance actions (osu! API reference sync, lost-map
scan, metadata enrichment, Library health, mania skillset scan, importing from
the installed osu! clients, collection sync). Each runs off the UI thread
through :class:`~rosu.workers.Worker`; split out of ``settings_tab.py`` (v2.0)."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from ..workers import Worker


class SettingsActionsMixin:
    def _refresh_reference_status(self) -> None:
        from .. import osu_api
        ref = osu_api.load_reference(self.ctx.cfg.reference_path)
        if ref:
            self.lbl_ref_status.setText(self.ctx.t(
                "reference_status", n=ref.get("count", 0), when=ref.get("fetched_at", "")))
        else:
            self.lbl_ref_status.setText(self.ctx.t("reference_none"))

    # -- reference sync ------------------------------------------------------
    def _update_reference(self) -> None:
        # The button doubles as Cancel while a sync runs — a network sync that
        # cannot be stopped just leaves the user staring at a disabled button.
        if getattr(self, "_ref_syncing", False):
            self.ctx.services.cancel_reference_sync()
            self.lbl_ref_status.setText(self.ctx.t("cancelling"))
            return
        if not self._commit_api_creds():
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("reference_help"))
            return
        self._ref_syncing = True
        self.btn_reference.setText(self.ctx.t("btn_cancel"))
        self.lbl_ref_status.setText(self.ctx.t("working"))
        w = Worker(lambda progress=None: self.ctx.services.update_reference(progress))
        self._threads.append(w)
        w.progressed.connect(lambda m: self.lbl_ref_status.setText(str(m)))
        w.succeeded.connect(self._reference_done)
        w.failed.connect(self._reference_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _reference_idle(self) -> None:
        self._ref_syncing = False
        self.btn_reference.setText(self.ctx.t("btn_update_reference"))

    def _reference_done(self, ref) -> None:
        self._reference_idle()
        if ref.get("cancelled"):
            # Deliberately NOT saved: a half-fetched reference would turn real
            # packs into "missing" reds. Say so instead of implying success.
            self.lbl_ref_status.setText(self.ctx.t("reference_cancelled"))
            return
        self.lbl_ref_status.setText(self.ctx.t("reference_done", n=ref.get("count", 0)))
        self.mw.dashboard._update_banner()
        self.mw.packs.reload()

    def _reference_failed(self, msg) -> None:
        self._reference_idle()
        self._refresh_reference_status()
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    # -- lost-map detection (item F) -----------------------------------------
    def _refresh_lost_status(self) -> None:
        n = self.ctx.services.lost_map_count()
        self.lbl_lost_status.setText(self.ctx.t("lost_maps_count", n=n) if n else "")

    def _scan_lost_maps(self) -> None:
        # Doubles as Cancel: the scan now walks the WHOLE library (no 500-per-run
        # cap), so being able to stop it is what makes that safe.
        if getattr(self, "_lost_scanning", False):
            self.ctx.services.cancel_lost_scan()
            self.lbl_lost_status.setText(self.ctx.t("cancelling"))
            return
        if not self._commit_api_creds():
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("lost_maps_needs_api"))
            return
        self._lost_scanning = True
        self.btn_lost.setText(self.ctx.t("btn_cancel"))
        self.lbl_lost_status.setText(self.ctx.t("working"))
        w = Worker(lambda progress=None: self.ctx.services.scan_lost_maps(progress))
        self._threads.append(w)
        w.progressed.connect(self._on_lost_progress)
        w.succeeded.connect(self._lost_done)
        w.failed.connect(self._lost_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_lost_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("kind") == "lostmap":
            self.lbl_lost_status.setText(f"{msg['done']}/{msg['total']}")

    def _lost_idle(self) -> None:
        self._lost_scanning = False
        self.btn_lost.setText(self.ctx.t("btn_scan_lost"))

    def _lost_done(self, res) -> None:
        self._lost_idle()
        if res.get("error") == "no_api":
            self.lbl_lost_status.setText(self.ctx.t("lost_maps_needs_api"))
            return
        # Say exactly where the scan stands: how many of the library's sets were
        # checked this run, and how many have never been checked yet (the scan
        # goes in batches — run again to continue).
        if res.get("remaining"):
            # Only reachable now by cancelling — the scan no longer stops on its own.
            self.lbl_lost_status.setText(self.ctx.t(
                "lost_maps_result_more", checked=res["checked"], gone=res["gone"],
                remaining=res["remaining"]))
        else:
            self.lbl_lost_status.setText(self.ctx.t(
                "lost_maps_result_all", checked=res["checked"], gone=res["gone"],
                total=res.get("total", res["checked"])))
        self.mw.search.reload()

    def _lost_failed(self, msg) -> None:
        self._lost_idle()
        self._refresh_lost_status()
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    # -- osu! API metadata enrichment (v1.5) ---------------------------------
    def _enrich_metadata(self) -> None:
        if getattr(self, "_enriching", False):   # button doubles as Cancel mid-run
            self.ctx.services.cancel_enrich()
            self.lbl_enrich_status.setText(self.ctx.t("cancelling"))
            return
        if not self.cb_enrich.isChecked():
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("enrich_disabled_msg"))
            return
        if not self._commit_api_creds():
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("enrich_no_api_msg"))
            return
        self.ctx.cfg.enrich_from_api_enabled = True   # an explicit click opts in
        self._enriching = True
        self.btn_enrich.setText(self.ctx.t("btn_cancel"))
        self.lbl_enrich_status.setText(self.ctx.t("working"))
        # max_calls=None → enrich the WHOLE library in one run (paced ~2-3/s); it's
        # cancellable and shows progress, so there's no need for an artificial cap.
        w = Worker(lambda progress=None:
                   self.ctx.services.enrich_metadata(progress, max_calls=None))
        self._threads.append(w)
        w.progressed.connect(self._on_enrich_progress)
        w.succeeded.connect(self._enrich_done)
        w.failed.connect(self._enrich_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_enrich_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("kind") == "enrich":
            self.lbl_enrich_status.setText(f"{msg['done']}/{msg['total']}")

    def _enrich_done(self, res) -> None:
        self._enriching = False
        self.btn_enrich.setText(self.ctx.t("btn_enrich_api"))
        err = res.get("error")
        if err == "no_api":
            self.lbl_enrich_status.setText(self.ctx.t("enrich_no_api"))
            return
        if err == "disabled":
            self.lbl_enrich_status.setText(self.ctx.t("enrich_disabled"))
            return
        self.lbl_enrich_status.setText(self.ctx.t(
            "enrich_done", checked=res["checked"], updated=res["updated"],
            remaining=res["remaining"]))
        self.mw.search.reload()

    def _enrich_failed(self, msg) -> None:
        self._enriching = False
        self.btn_enrich.setText(self.ctx.t("btn_enrich_api"))
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    # -- Library health (v1.1, moved from Dashboard in v1.5) -----------------
    def _library_health(self) -> None:
        self.btn_health.setEnabled(False)
        self.lbl_health_status.setText(self.ctx.t("working"))
        w = Worker(self.ctx.services.library_health)
        self._threads.append(w)
        w.succeeded.connect(self._health_done)
        w.failed.connect(self._health_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _health_done(self, report) -> None:
        self.btn_health.setEnabled(True)
        self.lbl_health_status.setText(self.ctx.t(
            "health_done", files=report["usage"]["files"]))
        from .health_dialog import HealthDialog
        HealthDialog(self.ctx, report, self).exec()

    def _health_failed(self, msg) -> None:
        self.btn_health.setEnabled(True)
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    # -- Mania skillset (Rosu Skillset Rating) whole-library scan (v1.6) ------
    def _compute_msd(self) -> None:
        if getattr(self, "_msd_running", False):   # button doubles as Cancel mid-run
            self.ctx.services.cancel_msd()
            self.lbl_msd_status.setText(self.ctx.t("cancelling"))
            return
        status = self.ctx.services.msd_status()
        if status["in_library"] == 0:
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("msd_no_library"))
            return
        self._msd_running = True
        self.btn_msd.setText(self.ctx.t("btn_cancel"))
        self.lbl_msd_status.setText(self.ctx.t("working"))
        w = Worker(self.ctx.services.compute_msd)
        self._threads.append(w)
        w.progressed.connect(self._on_msd_progress)
        w.succeeded.connect(self._msd_done)
        w.failed.connect(self._msd_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_msd_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("kind") == "msd":
            self.lbl_msd_status.setText(f"{msg['done']}/{msg['total']}")

    def _msd_done(self, res) -> None:
        self._msd_running = False
        self.btn_msd.setText(self.ctx.t("btn_compute_msd"))
        if not (res["scanned"] or res["rated"] or res["remaining"]):
            # Re-running after a completed scan legitimately reports 0/0/0 (already
            # scanned sets are skipped). "0 rated, 0 scanned, 0 remaining" read as a
            # failure, so say what actually happened instead.
            self.lbl_msd_status.setText(self.ctx.t("msd_nothing_new"))
        else:
            self.lbl_msd_status.setText(self.ctx.t(
                "msd_done", rated=res["rated"], scanned=res["scanned"],
                remaining=res["remaining"]))
        self.mw.search.reload()

    def _msd_failed(self, msg) -> None:
        self._msd_running = False
        self.btn_msd.setText(self.ctx.t("btn_compute_msd"))
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    # -- auto-import from installed osu! clients (item 15) -------------------
    def _run_import(self, client: str) -> None:
        self.btn_import_stable.setEnabled(False)
        self.btn_import_lazer.setEnabled(False)
        self.import_bar.setVisible(True)
        self.lbl_import_status.setText(self.ctx.t("working"))
        fn = (self.ctx.services.import_from_lazer if client == "lazer"
              else self.ctx.services.import_from_stable)
        w = Worker(fn)
        self._threads.append(w)
        w.progressed.connect(self._on_import_progress)
        w.succeeded.connect(self._on_import_done)
        w.failed.connect(self._on_import_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_import_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("kind") == "import" and "done" in msg:
            self.lbl_import_status.setText(f"{msg['done']}/{msg['total']}")
        elif isinstance(msg, str):
            self.lbl_import_status.setText(msg)

    def _on_import_done(self, res) -> None:
        self.import_bar.setVisible(False)
        self._sync_client_import_buttons()   # re-show per-toggle, re-enable
        t = self.ctx.t
        client = "osu!lazer" if res.get("source") == "lazer" else "osu!(stable)"
        if not res.get("found"):
            self.lbl_import_status.setText(t("import_client_none", client=client))
            return
        if res.get("error"):
            self.lbl_import_status.setText(t("import_lazer_error"))
            return
        self.lbl_import_status.setText(t("import_client_result", client=client,
                                       new=res.get("new", 0), dup=res.get("duplicates", 0)))
        self.mw.dashboard.refresh_scan()
        self.mw.packs.reload()
        self.mw.search.reload()          # reflect the new library rows live (item 7)

    def _on_import_failed(self, msg) -> None:
        self.import_bar.setVisible(False)
        self._sync_client_import_buttons()   # re-show per-toggle, re-enable
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    def _sync_collections(self) -> None:
        db_path = self.ctx.services.locate_stable_collection_db()
        if db_path is None:
            QMessageBox.warning(self, self.ctx.t("app_title"),
                                self.ctx.t("sync_coll_no_stable"))
            return
        self.btn_sync_coll.setEnabled(False)
        self.lbl_import_status.setText(self.ctx.t("working"))
        w = Worker(lambda progress=None: self.ctx.services.sync_collections(db_path))
        self._threads.append(w)
        w.succeeded.connect(self._sync_collections_done)
        w.failed.connect(self._sync_collections_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _sync_collections_done(self, res) -> None:
        self.btn_sync_coll.setEnabled(True)
        self.lbl_import_status.setText(self.ctx.t(
            "sync_coll_done", tagged=res.get("tagged", 0),
            collections=res.get("collections", 0)))
        self.mw.search.reload()

    def _sync_collections_failed(self, msg) -> None:
        self.btn_sync_coll.setEnabled(True)
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)
