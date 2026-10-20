# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
import datetime as _dt
import threading
import time
from pathlib import Path

from .. import config, osu_import, parsing

_CLIENT_LABEL = {"lazer": "osu!lazer", "stable": "osu!(stable)"}

def now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()

def _sample_export(files, limit):
    if limit is None or limit <= 0 or len(files) <= limit:
        return files
    import random
    return random.sample(files, limit)



def _export_line(line: str) -> tuple[int, int | None]:
    """One line of the lazer helper's stdout → ``(exported, total)``: an
    ``EXPORT`` line counts one set; ``TOTAL <n>`` (newer helpers) says how many
    to expect. Anything else → ``(0, None)``."""
    parts = line.split()
    if parts[:1] == ["EXPORT"]:
        return 1, None
    if len(parts) == 2 and parts[0] == "TOTAL" and parts[1].isdigit():
        return 0, int(parts[1])
    return 0, None

class ImportMixin:
        def import_plan(self, target: str = "lazer") -> dict:
            """Info for the pre-import confirmation dialog (no side effects). Batch
            count depends on the target (osu!(stable) is one file per launch)."""
            files = osu_import.output_osz_files(self.cfg.output_path)
            max_files = 1 if target == "stable" else osu_import._MAX_BATCH_FILES
            n_batches = len(osu_import.batches(files, max_files))
            return {"files": len(files), "batches": n_batches,
                    "eta_s": osu_import.estimate_seconds(len(files), n_batches)}

        def import_osu(self, target: str = "lazer", progress=None) -> dict:
            """Send the Output .osz files to an installed osu! client. ``target`` is
            ``"lazer"`` or ``"stable"``; both import an .osz passed on the command
            line (single-instance forwarding), so the launch path is identical."""
            self._cancel.clear()   # fresh import; a stale cancel must not kill it
            files = osu_import.output_osz_files(self.cfg.output_path)
            return self._dispatch_to_client(target, files, progress)

        def import_from_stable(self, progress=None, cancel=None) -> dict:
            """Zip osu!(stable) Songs/ folders we don't already have into Output, then
            dedup them into the Library."""
            if not self.client_enabled("stable"):   # disabled in Settings — never read it
                return {"source": "stable", "found": False, "disabled": True}
            from .. import client_import
            _eff = cancel if cancel is not None else self._cancel.is_set
            if cancel is None:
                self._cancel.clear()   # fresh op; own the token so its Cancel button works
            songs = client_import.stable_songs_dir()
            if not songs:
                return {"source": "stable", "found": False}
            known = self.db.known_track_ids()
            folders = list(client_import.iter_stable_folders(songs))
            made = 0
            cancelled = False
            for i, folder in enumerate(folders, 1):
                if _eff():
                    cancelled = True
                    break
                bid = client_import.beatmapset_id_for_folder(folder)
                if bid is None or bid in known:
                    continue  # unresolved id, or we already have this set
                osz = self.cfg.output_path / client_import._osz_name_for(folder, bid)
                if not osz.exists():
                    client_import.zip_folder_to_osz(folder, osz)
                made += 1
                if progress:
                    progress({"kind": "import", "done": i, "total": len(folders)})
            res = self.import_osz_folder(self.cfg.output_path, progress,
                                         source_label="local_osu_stable")
            self.log.info("CLIENT_IMPORT", client="stable", added=res["new"], made=made)
            return {"source": "stable", "found": True, "made": made,
                    "cancelled": cancelled, **res}

        def import_from_lazer(self, progress=None, cancel=None) -> dict:
            """Run the bundled .NET helper to re-export osu!lazer beatmapsets from its
            Realm + files store, then dedup the exported .osz into the Library. The
            (long) export is cancellable."""
            if not self.client_enabled("lazer"):   # disabled in Settings — never read it
                return {"source": "lazer", "found": False, "disabled": True}
            import shutil
            import tempfile
            from .. import client_import
            _eff = cancel if cancel is not None else self._cancel.is_set
            if cancel is None:
                self._cancel.clear()   # fresh op; own the token for this import
            data = client_import.lazer_data_dir()
            if not data:
                return {"source": "lazer", "found": False}
            out = Path(tempfile.mkdtemp(prefix="rosu_lazer_"))
            try:
                ok, detail = self._run_lazer_export(data, out, progress, cancel=_eff)
                if not ok:
                    if detail == "helper_missing":
                        return {"source": "lazer", "found": True, "error": "helper_missing"}
                    if detail == "cancelled":
                        return {"source": "lazer", "found": True, "cancelled": True}
                    self.log.error("import:lazer", detail)
                    return {"source": "lazer", "found": True, "error": "helper_failed",
                            "detail": detail}
                exported = sorted(out.glob("*.osz"))
                res = self.import_osz_folder(out, progress,
                                             source_label="local_osu_lazer")
                # Prove every exported set really reached the Library BEFORE any
                # caller tells the user it is safe to delete them from lazer.
                # "N new sets added" is not that proof: a set already in the
                # Library counts as a duplicate, and a failed copy counts as
                # nothing at all.
                missing = self._not_in_library(exported)
                self.log.info("CLIENT_IMPORT", client="lazer", added=res["new"],
                              made=0, exported=len(exported), missing=len(missing))
                return {"source": "lazer", "found": True,
                        "exported": len(exported), "missing": missing, **res}
            finally:
                shutil.rmtree(out, ignore_errors=True)

        def _run_lazer_export(self, data, out, progress=None, cancel=None):
            """Run the bundled osu!lazer export helper into ``out``, polling ``cancel``
            so a long export can be interrupted (the subprocess is terminated). stderr
            is captured to a temp file and stdout is read by a thread (no pipe-buffer
            deadlock); its ``TOTAL``/``EXPORT`` lines become ``{"kind": "export",
            "done", "total"}`` progress. Returns ``(ok: bool, detail: str)`` —
            detail is ``"cancelled"`` / ``"helper_missing"`` / the helper's stderr
            on failure, ``""`` on success."""
            import subprocess
            import tempfile
            helper = self._lazer_helper()
            if not helper:
                return False, "helper_missing"
            if progress:
                progress({"kind": "phase", "key": "sc_exporting_lazer"})
            errf = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
            try:
                proc = subprocess.Popen([str(helper), str(data), str(out)],
                                        stdout=subprocess.PIPE, stderr=errf,
                                        text=True, encoding="utf-8", errors="replace",
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError as exc:
                errf.close()
                return False, str(exc)[:300]
            seen = {"done": 0, "total": None}

            def read_stdout():
                for line in proc.stdout:
                    done, total = _export_line(line)
                    seen["done"] += done
                    if total is not None:
                        seen["total"] = total
            reader = threading.Thread(target=read_stdout, daemon=True)
            reader.start()
            reported = (0, None)
            try:
                while proc.poll() is None:
                    if cancel is not None and cancel():
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        return False, "cancelled"
                    now = (seen["done"], seen["total"])
                    if progress and now[1] and now != reported:
                        progress({"kind": "export", "done": min(now[0], now[1]),
                                  "total": now[1]})
                        reported = now
                    time.sleep(0.2)
                reader.join(timeout=5)
                errf.seek(0)
                err = errf.read()
            finally:
                errf.close()
            if proc.returncode != 0:
                return False, (err or "helper failed")[:300]
            return True, ""

        def _lazer_helper(self):
            """Locate the bundled lazer-export .exe (works in the dev tree and the
            frozen exe, where PyInstaller extracts data under _MEIPASS/rosu).

            Anchored on the ``rosu`` PACKAGE, not on this module's directory. It
            used to be ``Path(__file__).parent / "assets"``, which was correct
            while this code lived in ``rosu/services.py`` — the v1.7 split moved
            it to ``rosu/services/import_svc.py``, so the lookup started pointing
            at ``rosu/services/assets/`` and silently found nothing. Every lazer
            read (Save from lazer, lazer↔stable transfer, the lazer prune steps)
            then failed with "helper missing" when run from source.
            """
            import sys
            import rosu
            name = "RosuLazerExport.exe"
            pkg_root = Path(rosu.__file__).resolve().parent
            candidates = [pkg_root / "assets" / "lazer_export" / name]
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(Path(meipass) / "rosu" / "assets" / "lazer_export" / name)
            for p in candidates:
                if p.exists():
                    return p
            return None

        def client_enabled(self, client: str) -> bool:
            """Per-client on/off (v1.4). A disabled client's controls are hidden in
            the UI and it is never launched/written to. osu!lazer defaults on;
            osu!(stable) defaults off (enable in Settings)."""
            if client == "stable":
                return bool(self.cfg.stable_enabled)
            if client == "lazer":
                return bool(self.cfg.lazer_enabled)
            return True   # non-client sources (library/drive/merged) aren't gated here

        def _dispatch_to_client(self, target: str, files, progress=None,
                                cancel=None) -> dict:
            """Launch osu! (``target`` = ``"lazer"``/``"stable"``) to import an explicit
            list of ``.osz`` files, with the per-client staging + batching the client
            needs, and flag the sets present in that client. Shared by the Dashboard
            import (from Output) and the Shortcuts lazer↔stable transfer (from a temp
            export). Stages COPIES, so the caller's originals survive.
    
            Does NOT clear the cancel token — the caller owns it, so a cancel raised
            during an earlier phase of the same operation (e.g. a transfer's export
            step) still stops the dispatch. ``cancel`` (a queued job's own token)
            overrides the shared ``_cancel`` when given."""
            if not self.client_enabled(target):
                # Disabled in Settings — never launch/write to this client (the UI
                # already hides its controls; this is the belt-and-suspenders guard).
                return {"disabled": True, "sent": 0, "files": 0, "batches": 0}
            _eff = cancel if cancel is not None else self._cancel.is_set
            if target == "stable":
                exe = self.cfg.osu_stable_exe or config.detect_stable_exe()
                # osu!(stable) *moves* each .osz into its Songs folder on import; a
                # cross-drive move fails with "Error moving file". Stage copies on the
                # install drive so the move is a same-drive rename, and the source is
                # left intact. It also imports one file per launch (batching makes it
                # fail), so send max_batch_files=1.
                files = self._stage_for_stable(files, exe)
                batch_kw = {"max_batch_files": 1}
            else:
                exe = self.cfg.osu_lazer_exe or config.detect_osu_exe()
                # osu!lazer consumes the source .osz on import; stage copies so the
                # source survives too, consistent with stable.
                files = self._stage_copies(files, self.cfg.data_path / "_import_stage")
                batch_kw = {}
    
            def _prog(i, total, n):
                self.log.info("OSU_IMPORT", target=target, batch=f"{i}/{total}", files=n)
                if progress:
                    progress({"kind": "import", "batch": i, "total": total, "files": n})
    
            res = osu_import.import_files(exe, files, progress=_prog,
                                          cancel=_eff, **batch_kw)
            # Optimistically flag the dispatched sets as present in osu! so the Search
            # 'Where' column shows the 🎮 marker (item F2 / user feedback).
            sent = res.get("sent", len(files))
            for f in files[:sent]:
                t = parsing.parse_osz_entry(f.name, 0)
                if t is not None and t.beatmapset_id is not None:
                    self.db.set_in_osu(t.beatmapset_id, client=target)
            if sent:
                self.db._bump()   # let Search/Artists see the new 🎮 flags on reload
            self.log.info("OSU_IMPORT_DONE", target=target, files=res["files"],
                          batches=res["batches"])
            return res

        def _stage_copies(self, files, stage_dir):
            """Copy ``files`` into ``stage_dir`` (clearing prior leftovers first) so the
            osu! client consumes the COPIES and the Output folder is preserved — the
            same batch can then also go to the other client. Clears the read-only bit
            so osu can move each file. Returns the staged paths, or the originals if
            staging can't be set up (or per-file, on a copy error)."""
            import os
            import shutil
            stage = Path(stage_dir)
            try:
                if stage.exists():
                    for old in stage.glob("*.osz"):   # clear leftovers osu already took
                        try:
                            old.unlink()
                        except OSError:
                            pass
                stage.mkdir(parents=True, exist_ok=True)
            except OSError:
                return files
            staged = []
            for f in files:
                dst = stage / f.name
                try:
                    shutil.copy2(f, dst)
                    try:
                        os.chmod(dst, 0o666)   # clear read-only so osu can move it
                    except OSError:
                        pass
                    staged.append(dst)
                    
                    if getattr(self.cfg, "export_prune", False):
                        from ..prune import prune_osz
                        prune_osz(dst, mode=getattr(self.cfg, "prune_mode", "video_only"))
                except OSError as exc:
                    # Do NOT substitute the Output original: osu! would consume it and
                    # break the "Output is preserved" guarantee, silently. Log and skip
                    # — the set stays in Output (and the Library) to retry.
                    self.log.error("import:stage", f"{f.name}: {str(exc)[:150]}")
            return staged or files

        def _stage_for_stable(self, files, exe=None):
            """Stage on the osu!(stable) install drive, so its import-move is a
            same-drive rename. Derives the install dir from the configured exe (custom
            paths work), falling back to auto-detection; returns the Output paths
            unchanged if neither can be located."""
            from .. import client_import
            install = None
            if exe:
                try:
                    install = Path(exe).resolve().parent
                except OSError:
                    install = None
            if install is None or not install.exists():
                songs = client_import.stable_songs_dir()
                install = songs.parent if songs else None
            if install is None:
                return files
            return self._stage_copies(files, install / "_rosu_import")

        def installed_summary(self, progress=None) -> dict:
            """Read-only counts for the Shortcuts (Kısayollar) tab: how many beatmap
            sets live in each place — osu!lazer, osu!(stable), the Library and the
            Drive backup.
    
            ``lazer['count']`` is ``None`` when lazer is installed: its set list lives
            in an unreadable Realm database (only the bundled .NET helper can
            enumerate it), so we report presence without a number here and fill the
            number in after a transfer/import. ``stable`` counts ``Songs/`` subfolders
            (≈ one per set), which is cheap. ``installed`` reflects on-disk detection;
            ``enabled`` reflects the per-client Settings toggle (v1.4).
            """
            from .. import client_import
            songs = client_import.stable_songs_dir()
            stable_count = (sum(1 for _ in client_import.iter_stable_folders(songs))
                            if songs is not None else 0)
            lazer_installed = client_import.lazer_data_dir() is not None
            # lazer's set list is Realm-opaque, so we can't count it directly. Fill the
            # number from the Library sets Rosu has recorded as present in lazer
            # (``in_osu_lazer``) and flag it so the UI can explain where it came from.
            lazer_count = len(self.db.osu_client_ids("lazer")) if lazer_installed else None
            return {
                "lazer": {"installed": lazer_installed, "count": lazer_count,
                          "from_library": True, "enabled": bool(self.cfg.lazer_enabled)},
                "stable": {"installed": songs is not None, "count": stable_count,
                           "enabled": bool(self.cfg.stable_enabled)},
                "library": {"count": self.db.counts().get("in_library", 0)},
                "drive": {"connected": bool(self.cfg.drive_connected),
                          "count": self.db.drive_count()},
            }

        def _not_in_library(self, exported_paths) -> list[str]:
            """Of these exported .osz, which are NOT physically in the Library?

            The helper names each file ``<beatmapsetId> Artist - Title.osz``, so
            the id is the leading number. A set with no id, or whose row is not
            ``in_library``, is reported by name — the caller must be able to say
            exactly what did not make it across.
            """
            import re
            lib = self.cfg.library_path
            missing: list[str] = []
            for p in exported_paths:
                p = Path(p)
                m = re.match(r"(\d+)", p.name)
                row = self.db.find_track_row(int(m.group(1)) if m else None, p.name)
                if row is None or not row["in_library"]:
                    missing.append(p.name)
                    continue
                fn = row["filename"]
                if not fn or not (lib / fn).exists():
                    missing.append(p.name)
            return missing

        def lazer_store_stats(self) -> dict:
            """Size of osu!lazer's content-addressed file store (``files/``).

            This is the only signal Rosu has that a "Delete ALL beatmaps" inside
            lazer really happened: lazer's set list lives in a Realm database Rosu
            cannot read, so it cannot count sets — but the store it keeps them in
            is plain files on disk, and emptying the collection shrinks it
            dramatically. Read-only. ``{"found", "path", "files", "bytes"}``.
            """
            from .. import client_import
            data = client_import.lazer_data_dir()
            if data is None:
                return {"found": False, "path": "", "files": 0, "bytes": 0}
            store = Path(data) / "files"
            n = total = 0
            if store.is_dir():
                for p in store.rglob("*"):
                    try:
                        if p.is_file():
                            n += 1
                            total += p.stat().st_size
                    except OSError:
                        pass
            return {"found": True, "path": str(store), "files": n, "bytes": total}

        def send_library_to_client(self, target: str = "lazer", progress=None,
                                   cancel=None, skip_existing: bool = True) -> dict:
            """Import Library sets into an osu! client — the return leg of the
            lazer round-trip (save → delete in lazer → prune → send back).

            ``skip_existing`` leaves out sets Rosu has recorded as already in that
            client, so re-running does not pointlessly re-send everything.
            """
            if not self.client_enabled(target):
                return {"target": target, "sent": 0, "skipped": 0,
                        "disabled": True, "cancelled": False}
            lib = self.cfg.library_path
            skip = self._client_set_ids(target) if skip_existing else set()
            files, skipped = [], 0
            for r in self.db.library_tracks():
                fn = r.get("filename")
                if not fn:
                    continue
                bid = r.get("beatmapset_id")
                if bid and bid in skip:
                    skipped += 1
                    continue
                p = lib / fn
                if p.exists():
                    files.append(p)
            if not files:
                return {"target": target, "sent": 0, "skipped": skipped,
                        "cancelled": False}
            res = self._dispatch_to_client(target, files, progress, cancel=cancel)
            self.log.info("LIBRARY_TO_CLIENT", client=target,
                          sent=res.get("sent", 0), skipped=skipped)
            return {"target": target, "sent": res.get("sent", 0),
                    "skipped": skipped, "cancelled": res.get("cancelled", False)}

        def unpack_and_import(self, targets, skip_duplicates: bool = True,
                              progress=None) -> dict:
            """Shortcut ⑤: unpack every NEW pack in Packs/ into Output, then import the
            result into the given osu! client(s). With ``skip_duplicates`` (default) each
            target only receives Output sets it doesn't already have — so re-unpacking
            sets that came from that client doesn't pointlessly re-send them. Both the
            unpack and the send honor the cancel token. Returns ``{"extract": {...},
            "imports": {target: {sent, skipped, ...}}, "cancelled": bool}``.
            """
            self._cancel.clear()
            plans = self.prescan_all(progress)
            approved = [(Path(p.zip_path), p.parsed) for p in plans if p.kind == "new"]
            if approved or self.has_loose_osz():
                extract_res = self.extract(approved, progress)
            else:
                extract_res = {"packs": 0, "tracks": 0}
            imports: dict = {}
            if not self._cancel.is_set():
                files = osu_import.output_osz_files(self.cfg.output_path)
                for target in targets:
                    if self._cancel.is_set():
                        break
                    target_ids = self._client_set_ids(target) if skip_duplicates else set()
                    if target_ids:
                        send = [f for f in files
                                if (pt := parsing.parse_osz_entry(f.name, 0)) is None
                                or pt.beatmapset_id not in target_ids]
                    else:
                        send = list(files)
                    res = self._dispatch_to_client(target, send, progress)
                    imports[target] = {**res, "skipped": len(files) - len(send)}
            return {"extract": extract_res, "imports": imports,
                    "cancelled": self._cancel.is_set()}

        def save_installed_to_library(self, sources, progress=None) -> dict:
            """Shortcut ③: import the beatmaps installed in the given osu! client(s)
            (``"lazer"``/``"stable"``) straight into the Library (dedup is automatic —
            reuses the existing client-import pipeline). Returns ``{source: {...}}``."""
            out: dict = {}
            for s in sources:
                if s == "stable":
                    out["stable"] = self.import_from_stable(progress)
                elif s == "lazer":
                    out["lazer"] = self.import_from_lazer(progress)
            return out

        def transfer_between_clients(self, source: str, target: str,
                                     progress=None) -> dict:
            """Shortcut ①/②: copy the beatmaps installed in one osu! client into the
            other, skipping sets the target already has (id dedup — cheap for a stable
            target; a lazer target relies on lazer's own import-time dedup). ``source``
            and ``target`` are ``"lazer"``/``"stable"``. Returns
            ``{"source","target","found","transferred","skipped","cancelled"}`` or
            ``{"error": ...}``.
            """
            import shutil
            import tempfile
            if source == target:
                return {"error": "same_client"}
            target_exe = (self.cfg.osu_stable_exe or config.detect_stable_exe()
                          if target == "stable"
                          else self.cfg.osu_lazer_exe or config.detect_osu_exe())
            if not target_exe or not Path(target_exe).exists():
                return {"error": "no_target_exe", "source": source, "target": target}
            self._cancel.clear()   # own the token for the whole transfer (export → send)
            skip_ids = self._client_set_ids(target)
            stage = Path(tempfile.mkdtemp(prefix="rosu_xfer_"))
            try:
                osz, skipped = self._export_client_sets(source, stage, skip_ids, progress)
                found = len(osz) + skipped   # total examined = sent + already-in-target
                if self._cancel.is_set():
                    return {"source": source, "target": target, "found": found,
                            "transferred": 0, "skipped": skipped, "cancelled": True}
                if not osz:
                    return {"source": source, "target": target, "found": found,
                            "transferred": 0, "skipped": skipped, "cancelled": False}
                res = self._dispatch_to_client(target, osz, progress)
                transferred = res.get("sent", 0)
                self.log.info("CLIENT_TRANSFER", source=source, target=target,
                              found=found, transferred=transferred, skipped=skipped)
                return {"source": source, "target": target, "found": found,
                        "transferred": transferred, "skipped": skipped,
                        "cancelled": res.get("cancelled", False)}
            finally:
                shutil.rmtree(stage, ignore_errors=True)

        def _client_set_ids(self, client: str) -> set[int]:
            """Beatmapset ids already in ``client`` — used to skip re-sending them on a
            transfer. For **stable** we read the real ``Songs/`` folder ids
            (authoritative). For **lazer**, whose set list is Realm-opaque, we fall back
            to the ids Rosu has recorded as present there (``in_osu_lazer``); combined
            with lazer's own import-time dedup this stops repeated transfers re-zipping
            sets already sent. An empty set means "skip nothing"."""
            from .. import client_import
            if client == "stable":
                songs = client_import.stable_songs_dir()
                if songs is None:
                    return set()
                ids: set[int] = set()
                for folder in client_import.iter_stable_folders(songs):
                    bid = client_import.beatmapset_id_for_folder(folder)
                    if bid is not None:
                        ids.add(bid)
                return ids
            return self.db.osu_client_ids(client)

        def _export_client_sets(self, source: str, stage, skip_ids,
                                progress=None, cancel=None) -> tuple[list, int]:
            """Materialise the beatmaps installed in ``source`` as ``.osz`` files under
            ``stage``, skipping any whose id is in ``skip_ids`` (already in the target).
            Returns ``(osz_paths, skipped_count)``. ``cancel`` (a queued job's own
            token) overrides the shared ``_cancel`` when given."""
            from .. import client_import
            _eff = cancel if cancel is not None else self._cancel.is_set
            stage = Path(stage)
            stage.mkdir(parents=True, exist_ok=True)
            out: list = []
            skipped = 0
            if source in ("lazer", "stable") and not self.client_enabled(source):
                return out, skipped   # disabled client contributes nothing (v1.4)
            if source == "stable":
                songs = client_import.stable_songs_dir()
                if songs is None:
                    return out, skipped
                folders = list(client_import.iter_stable_folders(songs))
                for i, folder in enumerate(folders, 1):
                    if _eff():
                        break
                    bid = client_import.beatmapset_id_for_folder(folder)
                    if skip_ids and bid is not None and bid in skip_ids:
                        skipped += 1
                        continue
                    # Never fabricate id 0 for a set with no resolvable id — a "0 …"
                    # name re-parses to beatmapset_id 0 and would collapse every id-less
                    # set onto the same merged-export dedup key (silent data loss).
                    if bid is not None:
                        dest = stage / client_import._osz_name_for(folder, bid)
                    else:
                        dest = stage / f"{folder.name}.osz"
                    try:
                        client_import.zip_folder_to_osz(folder, dest)
                        out.append(dest)
                    except OSError as exc:
                        self.log.error("xfer:zip", str(exc)[:200])
                    if progress:
                        progress({"kind": "export", "done": i, "total": len(folders)})
                return out, skipped
            # source == "lazer": re-export via the bundled .NET helper, then filter.
            data = client_import.lazer_data_dir()
            if data is None or _eff():
                return out, skipped
            ok, detail = self._run_lazer_export(data, stage, progress, cancel=_eff)
            if not ok:
                if detail not in ("cancelled", "helper_missing"):
                    self.log.error("xfer:lazer", detail)
                return out, skipped
            for p in client_import.iter_osz_in_folder(stage):
                if _eff():
                    break
                t = parsing.parse_osz_entry(p.name, 0)
                if skip_ids and t is not None and t.beatmapset_id in skip_ids:
                    skipped += 1
                    try:
                        p.unlink()
                    except OSError:
                        pass
                    continue
                out.append(p)
            return out, skipped

