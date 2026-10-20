# SPDX-License-Identifier: GPL-3.0-or-later
"""Remove beatmap sets from an osu! client (v1.8, HANDOFF 4.1).

Two Shortcuts actions share this code: **Save and Remove** (copy each set into
the Library first, and remove only the ones that provably made it) and **Remove
only** (the dialog says up front how many have no Library copy). See
:mod:`rosu.client_remove` for why stable and lazer are handled so differently.
"""
from __future__ import annotations

import datetime as _dt
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .. import client_remove, jobs
from ..columns import has_library_copy

_SOURCES = ("stable", "lazer")


def now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()


class RemovalMixin:
        # -- what can be removed from ---------------------------------------
        def removal_sources(self) -> list[dict]:
            """``[{"key","available","reason"}]`` for stable and lazer.

            lazer needs a helper built with the ``delete`` command. The bundled
            helper predates it until the owner rebuilds it and verifies the
            soft-delete against a real lazer install, so until then lazer is
            listed but unavailable (``reason="lazer_helper"``), with the reason
            shown in the dialog rather than the option silently missing.
            """
            from .. import client_import
            out = []
            if not self.client_enabled("stable"):
                out.append({"key": "stable", "available": False, "reason": "disabled"})
            elif client_import.stable_songs_dir() is None:
                out.append({"key": "stable", "available": False, "reason": "no_stable"})
            else:
                out.append({"key": "stable", "available": True, "reason": ""})
            if not self.client_enabled("lazer"):
                out.append({"key": "lazer", "available": False, "reason": "disabled"})
            elif client_import.lazer_data_dir() is None:
                out.append({"key": "lazer", "available": False, "reason": "no_lazer"})
            elif "delete" not in self.lazer_helper_capabilities():
                out.append({"key": "lazer", "available": False, "reason": "lazer_helper"})
            else:
                out.append({"key": "lazer", "available": True, "reason": ""})
            return out

        def lazer_helper_capabilities(self) -> set[str]:
            """Commands the bundled lazer helper understands (cached per helper
            file). An older helper answers ``--capabilities`` with its usage text,
            which parses to an empty set — never an error."""
            helper = self._lazer_helper()
            if helper is None:
                return set()
            try:
                stamp = (str(helper), helper.stat().st_mtime)
            except OSError:
                return set()
            cache = getattr(self, "_lazer_caps_cache", None)
            if cache and cache[0] == stamp:
                return cache[1]
            rc, out, _err = self._lazer_helper_run(["--capabilities"], timeout=30)
            caps = client_remove.parse_helper_capabilities(out) if rc == 0 else set()
            self._lazer_caps_cache = (stamp, caps)
            return caps

        def _lazer_helper_run(self, args, cancel=None, timeout: float = 3600):
            """Run the lazer helper with ``args``; ``(returncode, stdout, stderr)``.
            Output goes to temp files (no pipe-buffer deadlock on a big ``list``);
            ``cancel`` terminates it. ``returncode`` is None when it could not run
            or was cancelled."""
            helper = self._lazer_helper()
            if helper is None:
                return None, "", "helper_missing"
            out_f = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
            err_f = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
            try:
                try:
                    proc = subprocess.Popen(
                        [str(helper), *[str(a) for a in args]],
                        stdout=out_f, stderr=err_f, text=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except OSError as exc:
                    return None, "", str(exc)[:300]
                started = time.monotonic()
                while proc.poll() is None:
                    if (cancel is not None and cancel()) or \
                            time.monotonic() - started > timeout:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        return None, "", "cancelled"
                    time.sleep(0.1)
                out_f.seek(0)
                err_f.seek(0)
                return proc.returncode, out_f.read(), err_f.read()[:2000]
            finally:
                out_f.close()
                err_f.close()

        # -- preview -------------------------------------------------------
        def _library_backed_ids(self) -> set[int]:
            """Set ids with a real ``.osz`` in the Library right now — the only
            thing that counts as "backed up" before a set leaves a client."""
            lib = self.cfg.library_path
            ids: set[int] = set()
            for r in self.db.library_tracks():
                bid, fn = r.get("beatmapset_id"), r.get("filename")
                if bid is None or not fn or not has_library_copy(r):
                    continue
                if (lib / fn).is_file():
                    ids.add(int(bid))
            return ids

        def removal_scan(self, source: str, progress=None, cancel=None) -> dict:
            """Read-only: every set in ``source`` with its size and whether the
            Library already holds it. ``{"source","sets","cancelled","error"?}``."""
            from .. import client_import
            self._removal_cancel.clear()
            _eff = cancel if cancel is not None else self._removal_cancel.is_set
            backed = self._library_backed_ids()
            if source == "stable":
                songs = client_import.stable_songs_dir()
                if songs is None or not self.client_enabled("stable"):
                    return {"source": source, "sets": [], "error": "no_stable"}
                sets = client_remove.stable_candidates(songs, backed, _eff, progress)
                return {"source": source, "sets": sets, "cancelled": _eff()}
            if source == "lazer":
                data = client_import.lazer_data_dir()
                if data is None or not self.client_enabled("lazer"):
                    return {"source": source, "sets": [], "error": "no_lazer"}
                if progress:
                    progress({"kind": "phase", "key": "rm_listing_lazer"})
                rc, out, err = self._lazer_helper_run(["list", data], cancel=_eff, timeout=900)
                if rc != 0:
                    if err != "cancelled":
                        self.log.error("remove:lazer_list", err[:300])
                    return {"source": source, "sets": [], "cancelled": err == "cancelled",
                            "error": None if err == "cancelled" else "helper_failed"}
                sets = client_remove.parse_helper_list(out)
                for s in sets:
                    s["backed_up"] = s["beatmapset_id"] in backed
                return {"source": source, "sets": sets, "cancelled": False}
            return {"source": source, "sets": [], "error": "bad_source"}

        def cancel_removal_scan(self) -> None:
            self._removal_cancel.set()

        # -- the removal ---------------------------------------------------
        def remove_from_client(self, source: str, keys, save_first: bool = True,
                               progress=None, cancel=None) -> dict:
            """Remove the chosen sets (scan ``key`` values) from ``source``.

            With ``save_first`` each set is copied into the Library first and only
            the sets that are then PROVABLY in the Library (a real ``.osz`` on
            disk) are removed; the rest are reported as ``kept``. Without it,
            every chosen set is removed. Refuses while the client is running.
            Returns ``{"source","removed","kept","failed","saved","backup"?,
            "cancelled","error"?}``.
            """
            from .. import client_import
            _eff = cancel if cancel is not None else (lambda: False)
            keys = [str(k) for k in (keys or [])]
            res = {"source": source, "removed": 0, "kept": [], "failed": [],
                   "saved": 0, "cancelled": False}
            if source not in _SOURCES or not self.client_enabled(source):
                return {**res, "error": "unavailable"}
            if client_remove.client_running(source, client_remove.osu_process_paths()):
                return {**res, "error": "client_running"}

            if source == "stable":
                songs = client_import.stable_songs_dir()
                if songs is None:
                    return {**res, "error": "no_stable"}
                targets = {}
                for k in keys:
                    folder = client_remove.resolve_stable_folder(songs, k)
                    if folder is None:
                        res["failed"].append(k)
                        self.log.error("remove:refused", f"not a Songs set folder: {k[:120]}")
                    else:
                        targets[k] = (folder, client_import.beatmapset_id_for_folder(folder))
                if save_first:
                    res["saved"] = self._save_stable_folders(
                        [f for f, _ in targets.values()], progress, _eff)
                return self._remove_stable(targets, save_first, res, progress, _eff)

            # lazer
            data = client_import.lazer_data_dir()
            if data is None:
                return {**res, "error": "no_lazer"}
            if "delete" not in self.lazer_helper_capabilities():
                return {**res, "error": "lazer_helper"}
            ids = []
            for k in keys:
                if k.isdigit() and int(k) > 0:
                    ids.append(int(k))
                else:
                    res["failed"].append(k)
            if save_first and ids:
                res["saved"] = self._save_lazer_ids(data, ids, progress, _eff)
                backed = self._library_backed_ids()
                res["kept"] = [str(i) for i in ids if i not in backed]
                ids = [i for i in ids if i in backed]
            if _eff():
                return {**res, "cancelled": True}
            if not ids:
                return res
            return self._remove_lazer(data, ids, res, progress, _eff)

        def _save_stable_folders(self, folders, progress, cancel) -> int:
            """Zip the folders whose set is not in the Library yet into a temp
            stage and import that into the Library. Returns how many were added."""
            from .. import client_import
            backed = self._library_backed_ids()
            stage = Path(tempfile.mkdtemp(prefix="rosu_rm_save_"))
            try:
                made = 0
                for i, folder in enumerate(folders, 1):
                    if cancel():
                        break
                    bid = client_import.beatmapset_id_for_folder(folder)
                    if bid is not None and bid in backed:
                        continue
                    name = (client_import._osz_name_for(folder, bid) if bid is not None
                            else f"{folder.name}.osz")
                    try:
                        client_import.zip_folder_to_osz(folder, stage / name)
                        made += 1
                    except OSError as exc:
                        self.log.error("remove:save", f"{folder.name}: {str(exc)[:150]}")
                    if progress:
                        progress({"kind": "export", "done": i, "total": len(folders)})
                if not made or cancel():
                    return 0
                res = self.import_osz_folder(stage, progress, source_label="local_osu_stable")
                return int(res.get("new", 0))
            finally:
                shutil.rmtree(stage, ignore_errors=True)

        def _save_lazer_ids(self, data, ids, progress, cancel) -> int:
            """Export just these lazer sets through the helper, then import them."""
            stage = Path(tempfile.mkdtemp(prefix="rosu_rm_save_"))
            ids_file = stage / "ids.txt"
            out = stage / "osz"
            try:
                ids_file.write_text("\n".join(str(i) for i in ids), encoding="utf-8")
                if progress:
                    progress({"kind": "phase", "key": "sc_exporting_lazer"})
                rc, _o, err = self._lazer_helper_run(
                    ["export", data, out, "--ids", ids_file], cancel=cancel)
                if rc != 0:
                    if err != "cancelled":
                        self.log.error("remove:lazer_export", err[:300])
                    return 0
                res = self.import_osz_folder(out, progress, source_label="local_osu_lazer")
                return int(res.get("new", 0))
            finally:
                shutil.rmtree(stage, ignore_errors=True)

        def _remove_stable(self, targets: dict, save_first: bool, res: dict,
                           progress, cancel) -> dict:
            from send2trash import send2trash
            backed = self._library_backed_ids() if save_first else set()
            total = len(targets)
            for i, (key, (folder, bid)) in enumerate(targets.items(), 1):
                if cancel():
                    res["cancelled"] = True
                    break
                if save_first and (bid is None or bid not in backed):
                    res["kept"].append(key)   # not provably in the Library: leave it
                else:
                    try:
                        send2trash(str(folder))
                        res["removed"] += 1
                        if bid is not None:
                            self.db.set_in_osu(bid, False, client="stable")
                        self.log.info("CLIENT_REMOVE", client="stable", folder=key,
                                      beatmapset_id=bid, saved_first=save_first)
                    except OSError as exc:
                        res["failed"].append(key)
                        self.log.error("remove:stable", f"{key}: {str(exc)[:150]}")
                if progress:
                    progress({"kind": "remove", "done": i, "total": total, "name": key})
            if res["removed"]:
                self.db._bump()
            self.log.info("CLIENT_REMOVE_DONE", client="stable", removed=res["removed"],
                          kept=len(res["kept"]), failed=len(res["failed"]))
            return res

        def _remove_lazer(self, data, ids, res: dict, progress, cancel) -> dict:
            stage = Path(tempfile.mkdtemp(prefix="rosu_rm_"))
            try:
                ids_file = stage / "ids.txt"
                ids_file.write_text("\n".join(str(i) for i in ids), encoding="utf-8")
                if progress:
                    progress({"kind": "phase", "key": "rm_deleting_lazer"})
                rc, out, err = self._lazer_helper_run(["delete", data, ids_file],
                                                      cancel=cancel, timeout=900)
            finally:
                shutil.rmtree(stage, ignore_errors=True)
            if rc != 0:
                res["cancelled"] = err == "cancelled"
                if not res["cancelled"]:
                    self.log.error("remove:lazer", err[:300])
                    res["error"] = "helper_failed"
                    res["detail"] = err[:300]
                return res
            for line in out.splitlines():
                if line.startswith("BACKUP "):
                    res["backup"] = line[len("BACKUP "):].strip()
            deleted = client_remove.parse_helper_deleted(out)
            for bid in deleted:
                self.db.set_in_osu(bid, False, client="lazer")
                self.log.info("CLIENT_REMOVE", client="lazer", beatmapset_id=bid)
            res["removed"] = len(deleted)
            if deleted:
                self.db._bump()
            self.log.info("CLIENT_REMOVE_DONE", client="lazer", removed=len(deleted),
                          kept=len(res["kept"]), backup=res.get("backup", ""))
            return res

        def build_remove_job(self, source: str, keys, save_first: bool = True) -> jobs.Job:
            """Queue an ALREADY-PREVIEWED removal (the Remove dialog showed the
            sets and took a countdown confirmation, so there is no second gate)."""
            keys = [str(k) for k in (keys or [])]
            job = jobs.Job(jobs.new_id(), "job_remove", kind="remove",
                           title_kwargs={})
            job.ctx["options"] = {"remove_source": source, "sets": len(keys),
                                  "save_first": bool(save_first)}

            def s_remove(ctx, progress, cancel):
                ctx["result"] = self.remove_from_client(
                    source, keys, save_first=save_first, progress=progress, cancel=cancel)

            job.steps = [jobs.Step("job_step_remove_save" if save_first
                                   else "job_step_remove", jobs.Lane.DISK, s_remove)]
            job.finalize = lambda ctx: ctx.get("result", {"removed": 0})
            return job
