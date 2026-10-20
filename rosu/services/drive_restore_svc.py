# SPDX-License-Identifier: GPL-3.0-or-later
"""Browse and restore the Google Drive backup (v1.8, HANDOFF 4.2).

The backup (``backup_to_drive``) writes append-only ``chunk-<device>-NNNN.zip``
archives (or one ``.osz`` per set in "individual" mode) plus one manifest shard
per device. Until now nothing read them back: a backed-up set could not be
listed, let alone retrieved. Here:

* :meth:`drive_catalog` merges every device's shard (downloaded from Drive, so a
  lost local cache or a second PC still sees everything) into one list, marking
  which archives are really on Drive and which sets the Library already has.
* :meth:`drive_restore` downloads only the archives that hold the chosen sets,
  extracts just those members — each name checked, each size capped, each file
  verified against the SHA-256 recorded at backup time — and imports them into
  the Library through the normal dedup pipeline.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import zipfile
from pathlib import Path

from .. import jobs
from ..columns import has_library_copy

_SHARD_CAP = 64 * 1024 * 1024          # a manifest shard is JSON text — never this big
_MEMBER_CAP = 1024 * 1024 * 1024       # no beatmap set is 1 GB; refuse anything claiming to be
_COPY_BUF = 1024 * 1024
_FREE_MARGIN = 256 * 1024 * 1024       # never fill a disk to the last byte
_RESERVED = re.compile(r"(?i)^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\.|$)")


def _safe_member_name(name) -> str | None:
    """A restorable member is one plain ``*.osz`` filename — nothing with a path,
    no Windows device name (``NUL.osz``) and no trailing dot or space."""
    if not isinstance(name, str) or not name or name in (".", "..") or len(name) > 200:
        return None
    if any(c in name for c in '/\\:*?"<>|') or any(ord(c) < 32 for c in name):
        return None
    if _RESERVED.match(name) or name != name.rstrip(" ."):
        return None
    return name if name.lower().endswith((".osz", ".olz")) else None


def _int(v, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError, OverflowError):
        return default


def _free_bytes(path: Path) -> int | None:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def _device_of(chunk: str) -> str:
    """``chunk-<device>-0003.zip`` → ``<device>``; an individual ``.osz`` → ''."""
    if chunk.startswith("chunk-") and chunk.lower().endswith(".zip"):
        return chunk[len("chunk-"):].rsplit("-", 1)[0]
    return ""


class DriveRestoreMixin:
        def _drive_root(self, client) -> str:
            from .. import config
            folder = self.cfg.drive_folder_id or client.ensure_folder("Rosu")
            if folder != self.cfg.drive_folder_id:
                self.cfg.drive_folder_id = folder
                config.save_config(self.cfg)
            return folder

        def _effective_manifest(self, client, listing, progress=None,
                                cancel=None) -> tuple[dict, int] | None:
            """Every device's shard merged (remote copies first, this device's
            local shard last so it wins). Returns ``(entries, shard_count)``, or
            None when ``cancel`` fired."""
            from ..drive import manifest
            from ..drive.auth import DriveError
            cache = self.cfg.drive_cache_path / "remote"
            cache.mkdir(parents=True, exist_ok=True)
            shards: list[dict] = []
            names = sorted(f["name"] for f in listing
                           if str(f.get("name", "")).startswith(manifest.SHARD_PREFIX)
                           and str(f.get("name", "")).endswith(manifest.SHARD_SUFFIX))
            by_name = {f["name"]: f for f in listing}
            for i, name in enumerate(names, 1):
                if cancel is not None and cancel():
                    return None
                if "/" in name or "\\" in name:
                    continue
                dest = cache / name
                try:
                    client.download_file(by_name[name]["id"], dest, max_bytes=_SHARD_CAP)
                    shards.append(manifest.load_shard(dest))
                except (DriveError, OSError) as exc:
                    self.log.error("drive:catalog_shard", f"{name}: {str(exc)[:150]}")
                if progress:
                    progress({"kind": "drive_catalog", "done": i, "total": len(names)})
            own = manifest.shard_name(self.cfg.device_id)
            local = manifest.load_shard(self.cfg.drive_cache_path / own)
            if local:
                shards.append(local)
            devices = len(names) + (1 if local and own not in names else 0)
            return manifest.merge_shards(shards), devices

        def drive_catalog(self, progress=None, cancel=None) -> dict:
            """What the Drive backup holds. ``{"entries": [...], "devices",
            "missing", "orphans"}`` or ``{"error": ...}`` (``"cancelled"`` when
            ``cancel`` fired). Read-only."""
            from ..drive.auth import DriveError
            if not self._drive_auth().is_connected():
                return {"error": "not_connected"}
            try:
                client = self._make_drive_client()
                folder = self._drive_root(client)
                listing = client.list_folder(folder)
                merged = self._effective_manifest(client, listing, progress, cancel)
            except DriveError as exc:
                self.log.error("drive:catalog", str(exc)[:300])
                return {"error": "drive", "detail": str(exc)[:300]}
            if merged is None:
                return {"error": "cancelled"}
            effective, devices = merged

            on_drive = {f["name"] for f in listing}
            lib = self.cfg.library_path
            in_lib_ids: set[int] = set()
            in_lib_names: set[str] = set()
            for r in self.db.library_tracks():
                fn = r.get("filename")
                if fn and has_library_copy(r) and (lib / fn).is_file():
                    in_lib_names.add(fn)
                    if r.get("beatmapset_id") is not None:
                        in_lib_ids.add(int(r["beatmapset_id"]))

            entries: list[dict] = []
            referenced: set[str] = set()
            skipped = 0
            for key, e in effective.items():
                # Shards come from Drive: one malformed entry is skipped, it never
                # takes the whole catalog down.
                if not isinstance(e, dict):
                    skipped += 1
                    continue
                chunk = e.get("chunk")
                name = e.get("name")
                if not isinstance(chunk, str) or not isinstance(name, str):
                    skipped += 1
                    continue
                md = e.get("metadata") if isinstance(e.get("metadata"), dict) else {}
                bid = e.get("beatmapset_id")
                bid = bid if isinstance(bid, int) and not isinstance(bid, bool) and bid > 0 \
                    else None
                digest = e.get("hash")
                referenced.add(chunk)
                entries.append({
                    "key": str(key), "name": name, "chunk": chunk,
                    "size": max(0, _int(e.get("size"))),
                    "hash": digest if isinstance(digest, str) else "",
                    "beatmapset_id": bid,
                    "artist": str(md.get("artist") or ""),
                    "title": str(md.get("title") or ""),
                    "device": _device_of(chunk),
                    "this_device": _device_of(chunk) == self.cfg.device_id,
                    "on_drive": chunk in on_drive,
                    "in_library": (bid is not None and bid in in_lib_ids)
                                  or name in in_lib_names,
                })
            if skipped:
                self.log.error("drive:catalog", f"{skipped} malformed manifest entries skipped")
            orphans = sorted(n for n in on_drive
                             if (n.startswith("chunk-") and n.endswith(".zip")
                                 or n.lower().endswith(".osz")) and n not in referenced)
            entries.sort(key=lambda x: (str(x["artist"]).lower(), str(x["title"]).lower(),
                                        str(x["name"]).lower()))
            self.log.info("DRIVE_CATALOG", sets=len(entries), devices=devices,
                          missing=sum(1 for x in entries if not x["on_drive"]),
                          orphans=len(orphans))
            return {"entries": entries, "devices": devices,
                    "missing": sum(1 for x in entries if not x["on_drive"]),
                    "orphans": orphans}

        def drive_restore(self, entries, progress=None, cancel=None) -> dict:
            """Fetch the chosen catalog ``entries`` back into the Library (fetch +
            import in one call; the queued job runs the two halves on their own
            lanes). ``{"restored","already","failed":[{name,reason}],"cancelled"}``
            or ``{"error": ...}``."""
            work = self.cfg.data_path / "_drive_restore" / "direct"
            try:
                fetched = self.drive_restore_fetch(entries, work, progress, cancel)
                return self.drive_restore_import(fetched, progress)
            finally:
                shutil.rmtree(work, ignore_errors=True)

        def drive_restore_fetch(self, entries, work: Path, progress=None, cancel=None) -> dict:
            """Download each archive holding a chosen set (once), extract only the
            wanted members into ``work/osz`` and verify each against its recorded
            SHA-256. Nothing is imported yet. ``{"stage","got","failed",
            "cancelled"}`` or ``{"error": ...}``."""
            from ..drive.auth import DriveError
            _eff = cancel if cancel is not None else (lambda: False)
            if not self._drive_auth().is_connected():
                return {"error": "not_connected"}
            wanted: dict[str, list[dict]] = {}
            failed: list[dict] = []
            for e in entries or []:
                name = _safe_member_name(e.get("name"))
                if name is None:
                    failed.append({"name": str(e.get("name"))[:120], "reason": "bad_name"})
                    continue
                wanted.setdefault(str(e.get("chunk") or ""), []).append({**e, "name": name})
            work = Path(work)
            shutil.rmtree(work, ignore_errors=True)
            stage = work / "osz"
            stage.mkdir(parents=True, exist_ok=True)
            got: list[dict] = []
            cancelled = False
            try:
                client = self._make_drive_client()
                listing = {f["name"]: f for f in client.list_folder(self._drive_root(client))}
            except DriveError as exc:
                self.log.error("drive:restore", str(exc)[:300])
                return {"error": "drive", "detail": str(exc)[:300], "failed": failed}
            total = sum(len(v) for v in wanted.values())
            done = 0
            for chunk, items in wanted.items():
                if _eff():
                    cancelled = True
                    break
                meta = listing.get(chunk)
                if meta is None:
                    failed += [{"name": it["name"], "reason": "not_on_drive"} for it in items]
                    continue
                if progress:
                    progress({"kind": "phase", "key": "drv_downloading", "name": chunk})
                individual = chunk.lower().endswith((".osz", ".olz"))
                raw = work / ("single.osz" if individual else "chunk.zip")
                listed = _int(meta.get("size"), -1)
                cap = (listed + _COPY_BUF if listed >= 0
                       else _MEMBER_CAP if individual
                       else max(_int(self.cfg.drive_chunk_bytes) * 2, _MEMBER_CAP))
                # Room for the download, the extracted sets and their Library copies.
                members = sum(min(max(0, _int(it.get("size"))) or _MEMBER_CAP, _MEMBER_CAP)
                              for it in items)
                need_work = cap + (0 if individual else members) + _FREE_MARGIN
                need_lib = members + _FREE_MARGIN
                free_work = _free_bytes(work)
                free_lib = _free_bytes(self.cfg.library_path)
                if (free_work is not None and free_work < need_work) or \
                        (free_lib is not None and free_lib < need_lib):
                    self.log.error("drive:restore_space", f"{chunk}: not enough free disk space")
                    failed += [{"name": it["name"], "reason": "disk_full"} for it in items]
                    continue
                try:
                    client.download_file(meta["id"], raw, max_bytes=cap)
                except (DriveError, OSError) as exc:
                    self.log.error("drive:restore_download", f"{chunk}: {str(exc)[:150]}")
                    failed += [{"name": it["name"], "reason": "download"} for it in items]
                    continue
                try:
                    for it in items:
                        if _eff():
                            cancelled = True
                            break
                        ok, reason = (self._take_single(raw, it, stage) if individual
                                      else self._take_member(raw, it, stage))
                        if ok:
                            got.append(it)
                        else:
                            failed.append({"name": it["name"], "reason": reason})
                        done += 1
                        if progress:
                            progress({"kind": "restore", "done": done, "total": total,
                                      "name": it["name"]})
                finally:
                    raw.unlink(missing_ok=True)
            return {"stage": str(stage), "got": got, "failed": failed, "cancelled": cancelled}

        def drive_restore_import(self, fetched: dict, progress=None) -> dict:
            """Import what :meth:`drive_restore_fetch` verified into the Library and
            mark those sets as backed up on Drive."""
            if fetched.get("error"):
                return {"error": fetched["error"], "detail": fetched.get("detail", ""),
                        "restored": 0, "already": 0, "failed": fetched.get("failed", [])}
            got, failed = fetched.get("got") or [], list(fetched.get("failed") or [])
            if not got:
                return {"restored": 0, "already": 0, "failed": failed,
                        "cancelled": bool(fetched.get("cancelled"))}
            # A restore never replaces a Library file: the same name with the same
            # bytes is already there; the same name with other bytes (an edited or
            # newer version) is left alone and reported.
            stage, lib = Path(fetched["stage"]), self.cfg.library_path
            present = 0
            restored: list[dict] = []
            for it in got:
                existing = lib / it["name"]
                if not existing.exists():
                    restored.append(it)
                    continue
                (stage / it["name"]).unlink(missing_ok=True)
                if self._same_file(existing, it):
                    present += 1
                    restored.append(it)
                else:
                    failed.append({"name": it["name"], "reason": "library_conflict"})
            res = self.import_osz_folder(stage, progress, source_label="drive_backup",
                                         physical_copy=True)
            for it in restored:
                row = self.db.find_track_row(it.get("beatmapset_id"), it["name"])
                if row:
                    self.db.set_drive_state(row["id"], True, it["chunk"], it.get("hash") or "")
            already = int(res.get("duplicates", 0)) + present
            self.log.info("DRIVE_RESTORE", restored=res.get("new", 0), already=already,
                          failed=len(failed), cancelled=bool(fetched.get("cancelled")))
            return {"restored": int(res.get("new", 0)), "already": already,
                    "failed": failed, "cancelled": bool(fetched.get("cancelled"))}

        def _same_file(self, path: Path, it: dict) -> bool:
            """Is ``path`` the backed-up file ``it``? By SHA-256 when the manifest
            recorded one, else by size (an old shard)."""
            try:
                if it.get("hash"):
                    return self._verify(path, it["hash"])
                size = _int(it.get("size"))
                return size > 0 and path.stat().st_size == size
            except OSError:
                return False

        @staticmethod
        def _verify(path: Path, expected: str) -> bool:
            if not expected:
                return True   # entries from an old shard may predate hashing
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for block in iter(lambda: fh.read(_COPY_BUF), b""):
                    h.update(block)
            return h.hexdigest() == expected.lower()

        def _take_member(self, chunk_path: Path, it: dict, stage: Path) -> tuple[bool, str]:
            """Stream one member out of a chunk archive into ``stage`` and verify it."""
            dest = stage / it["name"]
            try:
                with zipfile.ZipFile(chunk_path) as zf:
                    try:
                        info = zf.getinfo(it["name"])
                    except KeyError:
                        return False, "not_in_archive"
                    want = _int(it.get("size"))
                    if info.file_size > _MEMBER_CAP or (want and info.file_size != want):
                        return False, "size_mismatch"
                    written = 0
                    with zf.open(info) as src, open(dest, "wb") as out:
                        for block in iter(lambda: src.read(_COPY_BUF), b""):
                            written += len(block)
                            if written > info.file_size:   # lying header: stop, don't fill the disk
                                raise ValueError("member larger than declared")
                            out.write(block)
            except Exception as exc:   # bad zip, zlib error, encrypted, truncated…
                dest.unlink(missing_ok=True)
                self.log.error("drive:restore_extract",
                               f"{it['name']}: {type(exc).__name__}: {str(exc)[:150]}")
                return False, "corrupt"
            if not self._verify(dest, it.get("hash") or ""):
                dest.unlink(missing_ok=True)
                return False, "hash_mismatch"
            return True, ""

        def _take_single(self, raw: Path, it: dict, stage: Path) -> tuple[bool, str]:
            """Individual-mode backup: the downloaded file IS the ``.osz``."""
            if not self._verify(raw, it.get("hash") or ""):
                return False, "hash_mismatch"
            try:
                shutil.copyfile(raw, stage / it["name"])
            except OSError:
                return False, "corrupt"
            return True, ""

        def build_drive_restore_job(self, entries) -> jobs.Job:
            """Queue a restore of catalog ``entries`` (chosen in the Drive browser):
            download + verify on the DRIVE lane, then import on the DISK lane so the
            Library is only written by one job at a time."""
            entries = [dict(e) for e in (entries or [])]
            job = jobs.Job(jobs.new_id(), "job_drive_restore", kind="drive_restore")
            job.ctx["options"] = {"restore_sets": len(entries)}
            work = self.cfg.data_path / "_drive_restore" / f"job{job.id}"
            job.on_cleanup.append(lambda: shutil.rmtree(work, ignore_errors=True))

            def s_fetch(ctx, progress, cancel):
                ctx["fetched"] = self.drive_restore_fetch(entries, work, progress, cancel)

            def s_import(ctx, progress, cancel):
                ctx["result"] = self.drive_restore_import(ctx.get("fetched") or {}, progress)

            job.steps = [jobs.Step("job_step_drive_fetch", jobs.Lane.DRIVE, s_fetch),
                         jobs.Step("job_step_drive_import", jobs.Lane.DISK, s_import)]
            job.finalize = lambda ctx: ctx.get("result", {"restored": 0, "failed": []})
            return job
