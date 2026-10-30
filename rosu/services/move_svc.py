# SPDX-License-Identifier: GPL-3.0-or-later
"""Move the Library to another folder or drive (v1.9, safety-gated).

The database only stores Library file *names*, so "tracking" a move means
getting every file to the new folder intact and then pointing the config at
it. Nothing is ever lost on the way:

1. every file is copied to a private temp file in the destination, flushed to
   disk, and its SHA-256 compared with the original before it takes its name;
2. only when ALL files arrived (a second pass picks up files added meanwhile)
   does the config switch to the new folder; files that still land in the old
   folder afterwards are copied in a final pass, or reported;
3. the old copies are then — only if asked, only where the Recycle Bin works,
   and only while each is unchanged since its copy was checked — sent to the
   Recycle Bin, never deleted outright.

A cancel or a failure before the switch leaves the Library exactly where it
was and removes only the copies this run made. A destination that is (or holds)
Output, Packs, data or logs is refused: Unpack clears Output, for one.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from pathlib import Path

from .. import diskspace, jobs
from ..fsutil import dir_writable, place_new

_BUF = 1024 * 1024
_FREE_MARGIN = 512 * 1024 * 1024


def _library_files(lib: Path) -> tuple[list[Path], list[str], list[str]]:
    """Top-level files to move, names of subfolders that stay, and names of
    symlinked entries that are skipped."""
    files, dirs, links = [], [], []
    try:
        for p in sorted(lib.iterdir()):
            if p.is_symlink():
                links.append(p.name)
            elif p.is_dir():
                dirs.append(p.name)
            elif p.is_file() and not p.name.endswith(".part"):
                files.append(p)
    except OSError:
        pass
    return files, dirs, links


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(_BUF), b""):
            h.update(block)
    return h.hexdigest()


def _same_file(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _unlink(p: Path) -> None:
    """Best-effort removal of a copy this run made (read-only bit included)."""
    try:
        os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass


def _stamp(p: Path) -> tuple[int, int]:
    st = p.stat()
    return st.st_size, st.st_mtime_ns


def _copy_verified(src: Path, dest: Path, cancel) -> bool | None:
    """Copy ``src`` to ``dest`` through a private temp file next to it, hashing
    both sides and syncing to disk. True when ``dest`` now holds identical
    bytes, None when cancelled. Raises OSError on failure (temp removed)."""
    fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=".rosu-move-", suffix=".part")
    tmp = Path(tmp_name)
    h = hashlib.sha256()
    try:
        # The temp file's handle is taken over first, so it is closed even
        # when the source cannot be opened.
        with open(fd, "wb") as fout, open(src, "rb") as fin:
            for block in iter(lambda: fin.read(_BUF), b""):
                if cancel():
                    raise InterruptedError
                h.update(block)
                fout.write(block)
            fout.flush()
            os.fsync(fout.fileno())
        if _sha256(tmp) != h.hexdigest() or tmp.stat().st_size != src.stat().st_size:
            raise OSError(f"{src.name}: the copy does not match the original")
        shutil.copystat(src, tmp)
        try:
            place_new(tmp, dest)   # never replaces a file that appeared meanwhile
        except FileExistsError:
            raise OSError(f"{dest.name}: a file with this name appeared at the destination") from None
        return True
    except InterruptedError:
        _unlink(tmp)
        return None
    except OSError:
        _unlink(tmp)
        raise


class LibraryMoveMixin:
        def _reserved_dirs(self) -> list[Path]:
            cfg = self.cfg
            return [cfg.output_path, cfg.packs_path, cfg.data_path, cfg.logs_path]

        def library_move_plan(self, dest, progress=None) -> dict:
            """Read-only preview of moving the Library to ``dest`` (nothing is
            created). ``{"dest", "files", "bytes", "same", "conflicts",
            "subfolders", "links", "free", "enough_space", "error"?}``;
            ``error`` is ``same`` / ``inside`` / ``reserved`` / ``not_writable``
            / ``no_library``."""
            lib = Path(self.cfg.library_path)
            try:
                dest = Path(dest).expanduser().resolve()
                src = lib.resolve()
            except OSError:
                return {"error": "not_writable"}
            base = {"dest": str(dest), "files": 0, "bytes": 0, "same": 0,
                    "conflicts": [], "subfolders": [], "links": [], "free": None,
                    "enough_space": False}
            if not lib.is_dir():
                return {**base, "error": "no_library"}
            if dest == src or _same_file(dest, src):
                return {**base, "error": "same"}
            if src in dest.parents or dest in src.parents:
                return {**base, "error": "inside"}
            for r in self._reserved_dirs():
                try:
                    r = r.resolve()
                except OSError:
                    continue
                if dest == r or r in dest.parents or dest in r.parents:
                    return {**base, "error": "reserved"}
            existing = dest
            while not existing.exists() and existing.parent != existing:
                existing = existing.parent
            if not existing.is_dir() or not dir_writable(existing):
                return {**base, "error": "not_writable"}
            files, dirs, links = _library_files(lib)
            total = same = 0
            conflicts = []
            for i, f in enumerate(files, 1):
                size = f.stat().st_size
                total += size
                there = dest / f.name
                if there.exists() or there.is_symlink():
                    # The same name already at the destination: fine when it is
                    # an identical, separate file; a conflict otherwise — and
                    # always when it is the very same file under another path
                    # (a link or junction), which a "move" would then destroy.
                    if there.is_file() and not there.is_symlink() and not _same_file(there, f) \
                            and there.stat().st_size == size and _sha256(there) == _sha256(f):
                        same += 1
                    else:
                        conflicts.append(f.name)
                if progress:
                    progress({"kind": "move_plan", "done": i, "total": len(files)})
            sp = diskspace.space(existing, total, _FREE_MARGIN)
            return {**base, "files": len(files), "bytes": total, "same": same,
                    "conflicts": conflicts[:200], "subfolders": dirs, "links": links,
                    "free": sp.free, "enough_space": sp.fits}

        def _move_files(self, files, new: Path, verified: dict, made: list, res: dict,
                        progress, cancel) -> None:
            """Copy + verify ``files`` into ``new``; record each original's
            stamp in ``verified`` and each new copy in ``made``."""
            for i, f in enumerate(files, 1):
                target = new / f.name
                if target.exists() or target.is_symlink():
                    if target.is_file() and not target.is_symlink() and not _same_file(target, f) \
                            and target.stat().st_size == f.stat().st_size \
                            and _sha256(target) == _sha256(f):
                        res["same"] += 1
                        verified[f] = _stamp(f)
                        continue
                    raise OSError(f"{f.name}: a different file already exists there")
                before = _stamp(f)
                if _copy_verified(f, target, cancel) is None:
                    raise InterruptedError
                made.append(target)
                verified[f] = before
                res["moved"] += 1
                res["bytes"] += before[0]
                if progress:
                    progress({"kind": "move", "done": i, "total": len(files), "name": f.name})

        def move_library(self, dest, remove_old: bool = False,
                         progress=None, cancel=None) -> dict:
            """Copy + verify every Library file into ``dest``, then switch the
            config to it (see the module docstring). ``{"dest", "moved",
            "same", "bytes", "late", "left_behind", "old_removed",
            "old_failed", "old_kept", "cancelled", "error"?}``."""
            from .. import client_remove, config
            _eff = cancel if cancel is not None else (lambda: False)
            plan = self.library_move_plan(dest)
            res = {"dest": plan.get("dest", str(dest)), "moved": 0, "same": 0, "bytes": 0,
                   "late": 0, "left_behind": [], "old_removed": 0, "old_failed": 0,
                   "old_kept": False, "cancelled": False}
            if plan.get("error"):
                return {**res, "error": plan["error"]}
            if plan["conflicts"]:
                return {**res, "error": "conflicts", "conflicts": plan["conflicts"]}
            if not plan["enough_space"]:
                return {**res, "error": "no_space"}
            old = Path(self.cfg.library_path)
            new = Path(plan["dest"])
            made: list[Path] = []                 # copies this run created (undo on failure)
            verified: dict[Path, tuple] = {}      # original -> (size, mtime) when checked
            try:
                new.mkdir(parents=True, exist_ok=True)
                for _pass in range(2):            # the second pass catches files added meanwhile
                    files = [f for f in _library_files(old)[0] if f not in verified]
                    self._move_files(files, new, verified, made, res, progress, _eff)
            except InterruptedError:
                for p in made:
                    _unlink(p)
                return {**res, "moved": 0, "bytes": 0, "same": 0, "cancelled": True}
            except OSError as exc:
                for p in made:
                    _unlink(p)
                self.log.error("library:move", str(exc)[:300])
                return {**res, "moved": 0, "bytes": 0, "same": 0, "error": "copy_failed",
                        "detail": str(exc)[:300]}

            # Every file is at the destination, verified: switch.
            previous = self.cfg.library_dir
            self.cfg.library_dir = str(new)
            try:
                config.save_config(self.cfg)
            except OSError as exc:
                self.cfg.library_dir = previous   # memory and disk must agree
                self.log.error("library:move_save", str(exc)[:300])
                return {**res, "error": "config_save", "detail": str(exc)[:300]}
            # Anything a running import wrote to the old folder just before the
            # switch is copied too (writers use the new folder from now on).
            late = [f for f in _library_files(old)[0] if f not in verified]
            for f in late:
                try:
                    if self._move_one_late(f, new, verified, made):
                        res["late"] += 1
                    else:
                        res["left_behind"].append(f.name)
                except (OSError, InterruptedError):
                    res["left_behind"].append(f.name)
            self.log.info("LIBRARY_MOVE", old=str(old), new=str(new), files=len(verified),
                          bytes=res["bytes"])
            if remove_old:
                if not client_remove.recycle_bin_available(old):
                    res["old_kept"] = True   # no Recycle Bin there: never delete outright
                else:
                    self._recycle_old(old, new, verified, res, _eff)
            self.db._bump()
            return res

        def _move_one_late(self, f: Path, new: Path, verified: dict, made: list) -> bool:
            target = new / f.name
            if target.exists():
                return False   # a different file took the name meanwhile: leave both
            before = _stamp(f)
            if _copy_verified(f, target, lambda: False):
                made.append(target)
                verified[f] = before
                return True
            return False

        def _recycle_old(self, old: Path, new: Path, verified: dict, res: dict, cancel) -> None:
            from send2trash import send2trash
            for f, stamp in verified.items():
                if cancel():
                    break
                target = new / f.name
                try:
                    # Only an original that is still exactly what was copied, and
                    # whose copy is a separate file, may go.
                    if _stamp(f) != stamp or not target.is_file() or _same_file(target, f) \
                            or target.stat().st_size != stamp[0]:
                        res["old_failed"] += 1
                        continue
                    send2trash(str(f))
                    res["old_removed"] += 1
                except OSError as exc:
                    res["old_failed"] += 1
                    self.log.error("library:move_recycle", f"{f.name}: {str(exc)[:150]}")

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
