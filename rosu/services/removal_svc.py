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
            if rc is not None:   # a timeout is not an answer: ask again next time
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
            # The helper writes UTF-8 (Console.OutputEncoding); "replace" keeps an
            # older helper's code-page output from failing the whole read.
            out_f = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
            err_f = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
            try:
                try:
                    proc = subprocess.Popen(
                        [str(helper), *[str(a) for a in args]],
                        stdout=out_f, stderr=err_f,
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

        # -- preview / proof -----------------------------------------------
        def _library_files_by_id(self) -> dict[int, list[Path]]:
            """Set id → the Library ``.osz`` files on disk recorded for it."""
            lib = self.cfg.library_path
            out: dict[int, list[Path]] = {}
            for r in self.db.library_tracks():
                bid, fn = r.get("beatmapset_id"), r.get("filename")
                if bid is None or not fn or not has_library_copy(r):
                    continue
                if (lib / fn).is_file():
                    out.setdefault(int(bid), []).append(lib / fn)
            return out

        def _library_backed_ids(self) -> set[int]:
            """Set ids with a real ``.osz`` in the Library — the preview's "In
            Library" hint. The removal itself proves each set file by file
            (:meth:`_proven`), so a matching id alone never removes anything."""
            return set(self._library_files_by_id())

        @staticmethod
        def _proven(want, candidates) -> bool:
            """Does one of the ``candidates`` Library files hold every file of
            ``want`` (a :func:`client_remove.folder_fingerprint`) byte for byte?"""
            if not want:
                return False
            seen: set = set()
            for p in candidates:
                if p in seen or not p.is_file():
                    continue
                seen.add(p)
                if client_remove.covers(client_remove.osz_fingerprint(p, every_file=True), want):
                    return True
            return False

        def _stable_save_name(self, folder: Path, bid) -> str:
            from .. import client_import
            return (client_import._osz_name_for(folder, bid) if bid is not None
                    else f"{folder.name}.osz")

        def _drop_existing(self, stage: Path) -> list[str]:
            """Remove from ``stage`` every ``.osz`` whose name the Library already
            uses: the import would replace that Library file when the sizes
            differ, and a save before removal must never overwrite anything.
            Returns the names dropped."""
            lib = self.cfg.library_path
            dropped = []
            for f in sorted(Path(stage).glob("*.osz")):
                if (lib / f.name).exists():
                    f.unlink(missing_ok=True)
                    dropped.append(f.name)
            return dropped

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
            the sets that are then PROVABLY in the Library (a Library ``.osz``
            holding every one of its files byte for byte) are removed;
            the rest are reported as ``kept``. Without it (stable only) every
            chosen set is removed. osu!stable removal, in either mode, needs a
            Recycle Bin on the Songs drive and on every target folder; without
            one nothing is saved or removed. osu!lazer is always saved first.
            Refuses while the client is running — or when that cannot be
            checked.
            Returns ``{"source","removed","kept","failed","saved","backup"?,
            "cancelled","error"?}``.
            """
            from .. import client_import
            _eff = cancel if cancel is not None else (lambda: False)
            keys = list(dict.fromkeys(str(k) for k in (keys or [])))   # lazer lists an id per copy
            res = {"source": source, "removed": 0, "kept": [], "failed": [],
                   "saved": 0, "cancelled": False}
            if source not in _SOURCES or not self.client_enabled(source):
                return {**res, "error": "unavailable"}
            paths = client_remove.osu_process_paths()
            if paths is None:
                return {**res, "error": "client_check_failed"}
            if client_remove.client_running(source, paths):
                return {**res, "error": "client_running"}

            if source == "stable":
                songs = client_import.stable_songs_dir()
                if songs is None:
                    return {**res, "error": "no_stable"}
                if not client_remove.recycle_bin_available(songs):
                    return {**res, "error": "no_recycle_bin"}
                targets = {}
                for k in keys:
                    folder = client_remove.resolve_stable_folder(songs, k)
                    if folder is None:
                        res["failed"].append(k)
                        self.log.error("remove:refused", f"not a Songs set folder: {k[:120]}")
                    elif not client_remove.recycle_bin_available(folder):
                        return {**res, "error": "no_recycle_bin"}   # all or nothing
                    else:
                        targets[k] = client_import.beatmapset_id_for_folder(folder)
                if save_first:
                    res["saved"] = self._save_stable_folders(
                        songs, list(targets), progress, _eff)
                return self._remove_stable(songs, targets, save_first, res, progress, _eff)

            # lazer: always saved first — once lazer restarts it purges what was
            # removed, so the Library copy is the only lasting way back.
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
            if ids:
                saved, wants = self._save_lazer_ids(data, ids, progress, _eff)
                res["saved"] = saved
                files = self._library_files_by_id()
                lib = self.cfg.library_path
                proven = []
                for i in ids:
                    exported = wants.get(i) or []
                    ok = bool(exported) and all(
                        self._proven(fp, files.get(i, []) + [lib / name])
                        for name, fp in exported)
                    if ok:
                        proven.append(i)
                    else:
                        res["kept"].append(str(i))
                ids = proven
            if _eff():
                return {**res, "cancelled": True}
            if not ids:
                return res
            return self._remove_lazer(data, ids, res, progress, _eff)

        def _save_stable_folders(self, songs: Path, keys, progress, cancel) -> int:
            """Zip each folder the Library cannot prove yet into a temp stage and
            import that (always as a real file). A name the Library already uses
            is left alone — that set is then kept, never overwritten. Returns how
            many were added."""
            from .. import client_import
            files = self._library_files_by_id()
            lib = self.cfg.library_path
            stage = Path(tempfile.mkdtemp(prefix="rosu_rm_save_"))
            try:
                made = 0
                for i, key in enumerate(keys, 1):
                    if cancel():
                        break
                    folder = client_remove.resolve_stable_folder(songs, key)
                    if folder is None:
                        continue
                    bid = client_import.beatmapset_id_for_folder(folder)
                    name = self._stable_save_name(folder, bid)
                    want = client_remove.folder_fingerprint(folder, every_file=True)
                    if self._proven(want, files.get(bid, []) + [lib / name]):
                        continue
                    if (lib / name).exists():
                        self.log.error("remove:save", f"{name}: a different file with "
                                       "this name is already in the Library; kept")
                        continue
                    try:
                        client_import.zip_folder_to_osz(folder, stage / name)
                        made += 1
                    except (OSError, ValueError) as exc:
                        self.log.error("remove:save", f"{folder.name}: {str(exc)[:150]}")
                    if progress:
                        progress({"kind": "export", "done": i, "total": len(keys)})
                if not made or cancel():
                    return 0
                res = self.import_osz_folder(stage, progress, source_label="local_osu_stable",
                                             physical_copy=True, auto_prune=False)
                return int(res.get("new", 0))
            finally:
                shutil.rmtree(stage, ignore_errors=True)

        def _save_lazer_ids(self, data, ids, progress, cancel) -> tuple[int, dict]:
            """Export just these lazer sets through the helper, then import them
            (always as real files, never over an existing Library file). Returns
            ``(added, {id: [(file name, fingerprint), …]})`` — what lazer holds
            for each id, which the removal then proves against the Library."""
            stage = Path(tempfile.mkdtemp(prefix="rosu_rm_save_"))
            ids_file = stage / "ids.txt"
            out = stage / "osz"
            wants: dict[int, list] = {}
            try:
                ids_file.write_text("\n".join(str(i) for i in ids), encoding="utf-8")
                if progress:
                    progress({"kind": "phase", "key": "sc_exporting_lazer"})
                rc, stdout, err = self._lazer_helper_run(
                    ["export", data, out, "--ids", ids_file], cancel=cancel)
                if rc != 0:
                    if err != "cancelled":
                        self.log.error("remove:lazer_export", err[:300])
                    return 0, {}
                for name, bid in client_remove.parse_helper_exported(stdout).items():
                    fp = client_remove.osz_fingerprint(out / name, every_file=True)
                    wants.setdefault(bid, []).append((name, fp))
                for name in self._drop_existing(out):
                    self.log.error("remove:save", f"{name}: a file with this name is "
                                   "already in the Library; not overwritten")
                res = self.import_osz_folder(out, progress, source_label="local_osu_lazer",
                                             physical_copy=True, auto_prune=False)
                return int(res.get("new", 0)), wants
            finally:
                shutil.rmtree(stage, ignore_errors=True)

        def _remove_stable(self, songs: Path, targets: dict, save_first: bool, res: dict,
                           progress, cancel) -> dict:
            from send2trash import send2trash
            files = self._library_files_by_id() if save_first else {}
            lib = self.cfg.library_path
            total = len(targets)
            for i, (key, bid) in enumerate(targets.items(), 1):
                if cancel():
                    res["cancelled"] = True
                    break
                # Resolved again right before the delete: saving can take minutes.
                folder = client_remove.resolve_stable_folder(songs, key)
                if folder is None:
                    res["failed"].append(key)
                    self.log.error("remove:refused", f"not a Songs set folder: {key[:120]}")
                elif save_first and not self._proven(
                        client_remove.folder_fingerprint(folder, every_file=True),
                        files.get(bid, []) + [lib / self._stable_save_name(folder, bid)]):
                    res["kept"].append(key)   # not provably in the Library: leave it
                elif not client_remove.recycle_bin_available(folder):
                    res["failed"].append(key)   # send2trash would delete it for good
                    self.log.error("remove:stable",
                                   f"{key}: no Recycle Bin on this drive; left in place")
                elif not client_remove.recycle_bin_fits(folder):
                    res["failed"].append(key)   # Windows would delete it for good
                    self.log.error("remove:stable",
                                   f"{key}: too large for the Recycle Bin; left in place")
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
            save_first = bool(save_first) or source == "lazer"   # lazer always saves first
            job = jobs.Job(jobs.new_id(), "job_remove", kind="remove",
                           title_kwargs={})
            job.ctx["options"] = {"remove_source": source, "sets": len(keys),
                                  "save_first": bool(save_first)}

            def s_remove(ctx, progress, cancel):
                ctx["result"] = self.remove_from_client(
                    source, keys, save_first=save_first, progress=progress, cancel=cancel)

            job.steps = [jobs.Step("job_step_remove_save" if save_first
                                   else "job_step_remove_only", jobs.Lane.DISK, s_remove)]
            job.finalize = lambda ctx: ctx.get("result", {"removed": 0})
            return job
