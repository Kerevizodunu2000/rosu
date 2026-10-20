# SPDX-License-Identifier: GPL-3.0-or-later
"""Remove beatmap sets from an osu! client (v1.8, HANDOFF 4.1) — Qt-free.

Two clients, two completely different mechanisms; never one code path for both:

* **osu!(stable)** keeps every set as a plain folder under ``Songs/``. Removing a
  set means sending that folder to the Recycle Bin (recoverable). Every name is
  resolved against the detected Songs folder first: anything that is not a real,
  direct child directory of it is refused, never deleted.
* **osu!lazer** stores files content-addressed and *shares* one copy between every
  set holding that byte-identical file, indexed by ``client.realm``. Deleting
  files would break other sets and leave Realm pointing at nothing, so Rosu never
  touches ``files/``. Sets are soft-deleted through the bundled Realm helper
  (``delete`` command) with the same ``DeletePending`` flag lazer's own "delete"
  uses; lazer finishes the cleanup itself on its next start.

Helpers here only plan and resolve; :mod:`rosu.services.removal_svc` does the
work, off the UI thread.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import client_import

FILTERS = ("all", "backed_up", "not_backed_up")
SORTS = ("largest", "smallest", "name")


def folder_size(path: Path) -> int:
    """Total bytes of the files under ``path`` (symlinks not followed)."""
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for f in files:
            try:
                total += (Path(root) / f).lstat().st_size
            except OSError:
                pass
    return total


def stable_candidates(songs_dir: Path, backed_up_ids: set[int],
                      cancel=None, progress=None) -> list[dict]:
    """Every set folder in ``songs_dir`` → ``{"key","name","beatmapset_id",
    "size","backed_up"}``. ``backed_up`` = the set has a real ``.osz`` in the
    Library (the caller decides what counts, see ``RemovalMixin``)."""
    folders = list(client_import.iter_stable_folders(songs_dir))
    out: list[dict] = []
    for i, folder in enumerate(folders, 1):
        if cancel is not None and cancel():
            break
        bid = client_import.beatmapset_id_for_folder(folder)
        out.append({"key": folder.name, "name": folder.name,
                    "beatmapset_id": bid, "size": folder_size(folder),
                    "backed_up": bid is not None and bid in backed_up_ids})
        if progress:
            progress({"kind": "remove_scan", "done": i, "total": len(folders),
                      "name": folder.name})
    return out


def select(sets: list[dict], which: str = "all", sort: str = "largest",
           limit: int | None = None) -> list[dict]:
    """Filter (all / backed up / not backed up), order and cap a scan. Pure."""
    if which == "backed_up":
        rows = [s for s in sets if s.get("backed_up")]
    elif which == "not_backed_up":
        rows = [s for s in sets if not s.get("backed_up")]
    else:
        rows = list(sets)
    if sort == "smallest":
        rows.sort(key=lambda s: (s.get("size") or 0, str(s.get("name")).lower()))
    elif sort == "name":
        rows.sort(key=lambda s: str(s.get("name")).lower())
    else:
        rows.sort(key=lambda s: (-(s.get("size") or 0), str(s.get("name")).lower()))
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return rows


def resolve_stable_folder(songs_dir: Path, name: str) -> Path | None:
    """The set folder ``name`` inside ``songs_dir`` — or None when ``name`` is not
    exactly one plain path component naming an existing, non-symlink directory
    directly under it. This is the only way a removal target is ever built."""
    if not name or name in (".", "..") or "/" in name or "\\" in name \
            or os.sep in name or (os.altsep and os.altsep in name) or ":" in name:
        return None
    try:
        root = Path(songs_dir).resolve(strict=True)
        target = Path(songs_dir) / name
        if target.is_symlink() or not target.is_dir():
            return None
        if target.resolve(strict=True).parent != root:
            return None
    except OSError:
        return None
    return target


# --- is the client running? ---------------------------------------------------
def osu_process_paths(runner=None) -> list[str] | None:
    """Executable paths of every running ``osu!.exe`` (stable and lazer share that
    image name). ``[]`` when none run, None when it cannot be determined (not
    Windows, or PowerShell unavailable) — callers treat None as "unknown"."""
    if sys.platform != "win32" and runner is None:
        return []
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
           "Get-Process -Name 'osu!' -ErrorAction SilentlyContinue | "
           "ForEach-Object { if ($_.Path) { $_.Path } else { '?' } }"]
    try:
        if runner is not None:
            out = runner(cmd)
        else:
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return [ln.strip() for ln in (out or "").splitlines() if ln.strip()]


def client_running(client: str, paths: list[str] | None) -> bool:
    """Is ``client`` ("stable"/"lazer") among the running ``osu!.exe`` paths?

    lazer installs under ``…\\osulazer\\``; anything else named ``osu!.exe`` is
    taken to be stable. A process whose path could not be read (``"?"``) counts
    as BOTH — when in doubt, the destructive action waits.
    """
    if not paths:
        return False
    for p in paths:
        if p == "?":
            return True
        is_lazer = "osulazer" in p.lower().replace("/", "\\")
        if (client == "lazer") == is_lazer:
            return True
    return False


# --- lazer helper protocol ------------------------------------------------------
def parse_helper_capabilities(stdout: str) -> set[str]:
    """``RosuLazerExport --capabilities`` prints ``CAPS export list delete``.
    An older helper prints its usage instead, which yields an empty set."""
    for line in (stdout or "").splitlines():
        parts = line.strip().split()
        if parts and parts[0] == "CAPS":
            return set(parts[1:])
    return set()


def parse_helper_list(stdout: str) -> list[dict]:
    """``RosuLazerExport list`` → one ``SET\\t<id>\\t<bytes>\\t<name>`` line per
    beatmapset still present (not pending deletion). Malformed lines are skipped."""
    out: list[dict] = []
    for line in (stdout or "").splitlines():
        parts = line.rstrip("\r\n").split("\t", 3)
        if len(parts) != 4 or parts[0] != "SET":
            continue
        try:
            bid = int(parts[1])
            size = max(0, int(parts[2]))
        except ValueError:
            continue
        if bid <= 0:
            continue
        name = parts[3].strip() or str(bid)
        out.append({"key": str(bid), "name": name, "beatmapset_id": bid, "size": size})
    return out


def parse_helper_deleted(stdout: str) -> set[int]:
    """Ids the helper reports as soft-deleted (``DELETED <id>`` lines)."""
    ids: set[int] = set()
    for line in (stdout or "").splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[0] == "DELETED" and parts[1].isdigit():
            ids.add(int(parts[1]))
    return ids
