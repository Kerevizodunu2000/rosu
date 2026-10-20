# SPDX-License-Identifier: GPL-3.0-or-later
"""Move the Library to another folder or drive (v1.9, safety-gated).

The database only stores Library file *names*, so "tracking" a move means
getting every file to the new folder intact and then pointing the config at
it. Nothing is ever lost on the way:

1. every file is copied to ``<name>.part`` and its SHA-256 compared with the
   original before it takes its real name;
2. only when ALL files arrived (a second pass picks up any file added
   meanwhile) does the config switch to the new folder;
3. the old copies are then — only if asked, and only where the Recycle Bin
   works — sent to the Recycle Bin, never deleted outright.

A cancel or a failure before the switch leaves the Library exactly where it
was and removes only the copies this run made.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from .. import jobs

_BUF = 1024 * 1024
_FREE_MARGIN = 512 * 1024 * 1024


def _library_files(lib: Path) -> tuple[list[Path], list[str]]:
    """Top-level files to move, and the names of subfolders that stay."""
    files, dirs = [], []
    try:
        for p in sorted(lib.iterdir()):
            if p.is_symlink():
                continue
            if p.is_dir():
                dirs.append(p.name)
            elif p.is_file() and not p.name.endswith(".part"):
                files.append(p)
    except OSError:
        pass
    return files, dirs


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(_BUF), b""):
            h.update(block)
    return h.hexdigest()


def _copy_verified(src: Path, dest: Path, cancel) -> bool | None:
    """Copy ``src`` to ``dest`` through ``dest.part``, hashing both sides.
    True when ``dest`` now holds identical bytes, None when cancelled.
    Raises OSError on I/O failure (``.part`` removed)."""
    part = dest.with_name(dest.name + ".part")
    h = hashlib.sha256()
    try:
        with open(src, "rb") as fin, open(part, "wb") as fout:
            for block in iter(lambda: fin.read(_BUF), b""):
                if cancel():
                    raise InterruptedError
                h.update(block)
                fout.write(block)
        if _sha256(part) != h.hexdigest() or part.stat().st_size != src.stat().st_size:
            raise OSError(f"{src.name}: the copy does not match the original")
        shutil.copystat(src, part)
        os.replace(part, dest)
        return True
    except InterruptedError:
        part.unlink(missing_ok=True)
        return None
    except OSError:
        part.unlink(missing_ok=True)
        raise


class LibraryMoveMixin:
        def library_move_plan(self, dest, progress=None) -> dict:
            """Read-only preview of moving the Library to ``dest``. ``{"dest",
            "files", "bytes", "same", "conflicts", "subfolders", "free",
            "enough_space", "error"?}``; ``error`` is ``same`` / ``inside`` /
            ``not_writable`` / ``no_library``."""
            lib = Path(self.cfg.library_path)
            try:
                dest = Path(dest).expanduser().resolve()
                src = lib.resolve()
            except OSError:
                return {"error": "not_writable"}
            base = {"dest": str(dest), "files": 0, "bytes": 0, "same": 0,
                    "conflicts": [], "subfolders": [], "free": None, "enough_space": False}
            if not lib.is_dir():
                return {**base, "error": "no_library"}
            if dest == src:
                return {**base, "error": "same"}
            if src in dest.parents or dest in src.parents:
                return {**base, "error": "inside"}
            try:
                dest.mkdir(parents=True, exist_ok=True)
                probe = dest / ".rosu-write-test"
                probe.write_bytes(b"")
                probe.unlink()
            except OSError:
                return {**base, "error": "not_writable"}
            files, dirs = _library_files(lib)
            total = same = 0
            conflicts = []
            for i, f in enumerate(files, 1):
                size = f.stat().st_size
                total += size
                there = dest / f.name
                if there.exists():
                    # The same name already at the destination: fine when it is
                    # the same file, a conflict otherwise (never overwritten).
                    if there.is_file() and there.stat().st_size == size and \
                            _sha256(there) == _sha256(f):
                        same += 1
                    else:
                        conflicts.append(f.name)
                if progress:
                    progress({"kind": "move_plan", "done": i, "total": len(files)})
            try:
                free = shutil.disk_usage(dest).free
            except OSError:
                free = None
            return {**base, "files": len(files), "bytes": total, "same": same,
                    "conflicts": conflicts[:200], "subfolders": dirs,
                    "free": free,
                    "enough_space": free is None or free >= total + _FREE_MARGIN}

        def move_library(self, dest, remove_old: bool = False,
                         progress=None, cancel=None) -> dict:
            """Copy + verify every Library file into ``dest``, then switch the
            config to it (see the module docstring). ``{"dest", "moved",
            "same", "bytes", "old_removed", "old_kept", "cancelled",
            "error"?}``."""
            from .. import client_remove, config
            _eff = cancel if cancel is not None else (lambda: False)
            plan = self.library_move_plan(dest)
            res = {"dest": plan.get("dest", str(dest)), "moved": 0, "same": 0, "bytes": 0,
                   "old_removed": 0, "old_kept": False, "cancelled": False}
            if plan.get("error"):
                return {**res, "error": plan["error"]}
            if plan["conflicts"]:
                return {**res, "error": "conflicts", "conflicts": plan["conflicts"]}
            if not plan["enough_space"]:
                return {**res, "error": "no_space"}
            old = Path(self.cfg.library_path)
            new = Path(plan["dest"])
            made: list[Path] = []          # copies this run created (undo on failure)
            verified: list[Path] = []      # originals proven to be at the destination
            try:
                for _pass in range(2):     # the second pass catches files added meanwhile
                    files = [f for f in _library_files(old)[0] if f not in verified]
                    for i, f in enumerate(files, 1):
                        target = new / f.name
                        if target.exists():
                            if target.is_file() and target.stat().st_size == f.stat().st_size \
                                    and _sha256(target) == _sha256(f):
                                res["same"] += 1
                                verified.append(f)
                                continue
                            raise OSError(f"{f.name}: a different file already exists there")
                        ok = _copy_verified(f, target, _eff)
                        if ok is None:
                            raise InterruptedError
                        made.append(target)
                        verified.append(f)
                        res["moved"] += 1
                        res["bytes"] += f.stat().st_size
                        if progress:
                            progress({"kind": "move", "done": i, "total": len(files),
                                      "name": f.name})
            except InterruptedError:
                for p in made:
                    p.unlink(missing_ok=True)
                return {**res, "moved": 0, "bytes": 0, "cancelled": True}
            except OSError as exc:
                for p in made:
                    p.unlink(missing_ok=True)
                self.log.error("library:move", str(exc)[:300])
                return {**res, "moved": 0, "bytes": 0, "error": "copy_failed",
                        "detail": str(exc)[:300]}

            # Every file is at the destination, verified: switch.
            self.cfg.library_dir = str(new)
            config.save_config(self.cfg)
            self.log.info("LIBRARY_MOVE", old=str(old), new=str(new), files=len(verified),
                          bytes=res["bytes"])
            if remove_old:
                if client_remove.recycle_bin_available(old):
                    from send2trash import send2trash
                    for f in verified:
                        try:
                            send2trash(str(f))
                            res["old_removed"] += 1
                        except OSError as exc:
                            self.log.error("library:move_recycle", f"{f.name}: {str(exc)[:150]}")
                else:
                    res["old_kept"] = True   # no Recycle Bin there: never delete outright
            self.db._bump()
            return res

        def build_library_move_job(self, dest, remove_old: bool = False) -> jobs.Job:
            """Queue an ALREADY-PREVIEWED Library move (the Move dialog showed the
            plan and took a countdown confirmation). Disk lane: no other job
            writes the Library while it moves."""
            job = jobs.Job(jobs.new_id(), "job_library_move", kind="library_move")
            job.ctx["options"] = {"dest": str(dest), "remove_old": bool(remove_old)}

            def s_move(ctx, progress, cancel):
                ctx["result"] = self.move_library(dest, remove_old, progress, cancel)

            job.steps = [jobs.Step("job_step_library_move", jobs.Lane.DISK, s_move)]
            job.finalize = lambda ctx: ctx.get("result", {"moved": 0})
            return job
