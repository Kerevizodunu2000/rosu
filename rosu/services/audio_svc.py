# SPDX-License-Identifier: GPL-3.0-or-later
"""Same song, different sets (v1.10): fingerprint the Library's audio and group
sets whose songs match (see :mod:`rosu.fingerprint`).

Fingerprints are cached in the database per Library file (name, size and
modification time), so a second run only reads new or changed sets. Finding
groups is read-only; recycling sets is a separate, explicitly confirmed job
that reuses the Library dedup's Recycle-Bin removal.
"""
from __future__ import annotations

import shutil
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import fingerprint, jobs
from ..zipread import copy_capped, read_capped
from ..columns import has_library_copy

_AUDIO_CAP = 64 * 1024 * 1024     # no beatmap audio is this big
_OSU_CAP = 4 * 1024 * 1024


def _audio_member(zf: zipfile.ZipFile) -> zipfile.ZipInfo | None:
    """The audio file the set's first ``.osu`` names (``AudioFilename:``)."""
    from ..prune import get_osu_assets
    by_name = {i.filename.replace("\\", "/").lower(): i for i in zf.infolist() if not i.is_dir()}
    for info in sorted(by_name.values(), key=lambda i: i.filename.lower()):
        if not info.filename.lower().endswith(".osu") or info.file_size > _OSU_CAP:
            continue
        text = read_capped(zf, info, _OSU_CAP).decode("utf-8", errors="replace")
        for asset in get_osu_assets(text):
            hit = by_name.get(asset.replace("\\", "/").lower())
            if hit is not None and hit.filename.lower().endswith((".mp3", ".ogg", ".wav", ".flac")):
                return hit
    return None


def _fingerprint_osz(osz: Path, fpcalc: Path, work: Path) -> tuple[float, list[int]] | None:
    """Extract one set's audio to ``work`` and fingerprint it."""
    tmp = None
    try:
        with zipfile.ZipFile(osz) as zf:
            info = _audio_member(zf)
            if info is None or not 0 < info.file_size <= _AUDIO_CAP:
                return None
            fd, name = tempfile.mkstemp(dir=work, suffix=Path(info.filename).suffix.lower())
            tmp = Path(name)
            with open(fd, "wb") as out:
                copy_capped(zf, info, out, _AUDIO_CAP)
    except Exception:   # unreadable / truncated / encrypted archive
        if tmp is not None:
            tmp.unlink(missing_ok=True)
        return None
    try:
        return fingerprint.compute(tmp, fpcalc)
    finally:
        tmp.unlink(missing_ok=True)


class AudioMixin:
        def fingerprint_library(self, progress=None, cancel=None) -> dict:
            """Fingerprint every Library set that has no up-to-date fingerprint.
            ``{"computed","cached","failed","cancelled"}`` or ``{"error":
            "no_fpcalc"}``. Several fpcalc processes run side by side; the
            results are written to the database from this thread."""
            fpcalc = fingerprint.fpcalc_path()
            if fpcalc is None:
                return {"error": "no_fpcalc"}
            _eff = cancel if cancel is not None else (lambda: False)
            lib = self.cfg.library_path
            known = self.db.audio_fingerprint_stamps()
            todo: list[tuple[int, Path, int, int]] = []
            cached = 0
            for r in self.db.library_tracks():
                fn = r.get("filename")
                if not fn or not has_library_copy(r):
                    continue
                p = lib / fn
                try:
                    st = p.stat()
                except OSError:
                    continue
                stamp = (fn, st.st_size, st.st_mtime_ns)
                if known.get(int(r["id"])) == stamp:
                    cached += 1
                else:
                    todo.append((int(r["id"]), p, st.st_size, st.st_mtime_ns))
            res = {"computed": 0, "cached": cached, "failed": 0, "cancelled": False}
            work = Path(tempfile.mkdtemp(prefix="rosu_fp_"))
            try:
                with ThreadPoolExecutor(fingerprint.cpu_budget()) as pool:
                    futures = []
                    for item in todo:
                        futures.append((item, pool.submit(_fingerprint_osz, item[1], fpcalc, work)))
                    for i, ((tid, path, size, mtime), fut) in enumerate(futures, 1):
                        if _eff():
                            res["cancelled"] = True
                            for _item, f in futures:
                                f.cancel()
                            break
                        out = fut.result()
                        if out is None:
                            res["failed"] += 1
                            # Remember the miss too, so a set without readable
                            # audio is not retried on every run.
                            self.db.save_audio_fingerprint(tid, path.name, size, mtime, 0.0, b"")
                        else:
                            duration, values = out
                            self.db.save_audio_fingerprint(tid, path.name, size, mtime, duration,
                                                           fingerprint.pack(values))
                            res["computed"] += 1
                        if progress:
                            progress({"kind": "fingerprint", "done": i, "total": len(todo),
                                      "name": path.name})
            finally:
                shutil.rmtree(work, ignore_errors=True)
            self.log.info("AUDIO_FINGERPRINT", **res)
            return res

        def same_song_report(self, progress=None) -> dict:
            """Groups of Library sets whose songs match, each set with what the
            UI shows. ``{"groups": [[set, …], …], "fingerprinted": n}``."""
            fps = {tid: fingerprint.unpack(blob)
                   for tid, blob in self.db.audio_fingerprints().items() if blob}
            groups = fingerprint.same_song_groups(fps)
            rows = {int(r["id"]): r for r in self.db.library_tracks()}
            lib = self.cfg.library_path
            out = []
            for g in groups:
                sets = []
                for tid in g:
                    r = rows.get(tid)
                    if not r or not r.get("filename") or not has_library_copy(r):
                        continue
                    try:
                        size = (lib / r["filename"]).stat().st_size
                    except OSError:
                        continue
                    sets.append({"track_id": tid, "filename": r["filename"],
                                 "beatmapset_id": r.get("beatmapset_id"),
                                 "artist": r.get("artist") or "", "title": r.get("title") or "",
                                 "creator": r.get("creator") or "",
                                 "diff_count": r.get("diff_count") or 0, "size": size})
                if len(sets) > 1:
                    out.append(sets)
            return {"groups": out, "fingerprinted": len(fps)}

        def build_recycle_sets_job(self, filenames) -> jobs.Job:
            """Recycle ALREADY-CONFIRMED Library files (chosen in the same-song
            dialog) through the Library dedup's Recycle-Bin removal. Only plain
            names of files that are directly in the Library are taken."""
            lib = self.cfg.library_path
            names = [n for n in dict.fromkeys(str(f) for f in (filenames or []))
                     if n and "/" not in n and "\\" not in n and (lib / n).is_file()]
            job = jobs.Job(jobs.new_id(), "job_same_song_recycle", kind="dedup")
            job.ctx["options"] = {"sets": len(names)}

            def s_remove(ctx, progress, cancel):
                ctx["result"] = self.dedup_library(names=names, progress=progress, cancel=cancel)

            job.steps = [jobs.Step("job_step_remove", jobs.Lane.DISK, s_remove)]
            job.finalize = lambda ctx: ctx.get("result", {"removed": 0, "freed_bytes": 0, "groups": 0})
            return job
