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
import zipfile
import zlib
from pathlib import Path

from . import client_import
from .zipread import read_capped

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
    folders = [f for f in client_import.iter_stable_folders(songs_dir) if is_set_folder(f)]
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


def is_set_folder(folder: Path) -> bool:
    """A beatmap set folder holds at least one ``.osu`` directly inside it. Only
    those are ever listed or removed, so a misdetected Songs folder (one that is
    really Documents, say) offers nothing to remove."""
    try:
        return any(p.is_file() for p in Path(folder).glob("*.osu"))
    except OSError:
        return False


def resolve_stable_folder(songs_dir: Path, name: str) -> Path | None:
    """The set folder ``name`` inside ``songs_dir`` — or None when ``name`` is not
    exactly one plain path component naming an existing, non-symlink set folder
    (see :func:`is_set_folder`) directly under it. This is the only way a removal
    target is ever built."""
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
    return target if is_set_folder(target) else None


_BITBUCKET = r"Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket\Volume"


def _volume_bin(path: Path) -> dict:
    """Windows only: the drive type and the per-user Recycle Bin settings of the
    volume holding ``path``. Reads the registry (KEY_READ), never writes it."""
    import ctypes
    import shutil
    import winreg
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    k32.GetDriveTypeW.restype = wintypes.UINT
    k32.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    k32.GetVolumePathNameW.restype = wintypes.BOOL
    k32.GetVolumeNameForVolumeMountPointW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR,
                                                      wintypes.DWORD]
    k32.GetVolumeNameForVolumeMountPointW.restype = wintypes.BOOL
    try:
        resolved = str(Path(path).resolve())
        drive = os.path.splitdrive(resolved)[0]
        # UNC share: never a Recycle Bin
        fixed = bool(drive) and not drive.startswith("\\\\") \
            and k32.GetDriveTypeW(drive + "\\") == 3   # DRIVE_FIXED
        mount = ctypes.create_unicode_buffer(32768)   # MAX path length in wide chars
        if not k32.GetVolumePathNameW(resolved, mount, len(mount)):
            raise ctypes.WinError(ctypes.get_last_error())
        name = ctypes.create_unicode_buffer(64)   # "\\?\Volume{GUID}\" is 49 chars
        if not k32.GetVolumeNameForVolumeMountPointW(mount.value, name, len(name)):
            raise ctypes.WinError(ctypes.get_last_error())
        guid = name.value[name.value.index("{"):name.value.index("}") + 1]
        values: dict[str, int | None] = {"NukeOnDelete": None, "MaxCapacity": None}
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _BITBUCKET + "\\" + guid,
                                0, winreg.KEY_READ) as key:
                for v in values:
                    try:
                        values[v] = int(winreg.QueryValueEx(key, v)[0])
                    except FileNotFoundError:
                        pass   # missing value: the Windows default
        except FileNotFoundError:
            pass   # missing key: the Windows defaults
        return {"fixed": fixed, "nuke": values["NukeOnDelete"],
                "max_mb": values["MaxCapacity"], "total": shutil.disk_usage(mount.value).total}
    except (ctypes.ArgumentError, ValueError, TypeError) as exc:
        # a wrong ctypes signature or an odd registry value: fail closed
        raise OSError(f"Recycle Bin settings unreadable: {exc}") from exc


def recycle_bin_available(path: Path, reader=None) -> bool:
    """Will the Recycle Bin take files deleted under ``path``? Only on a fixed local
    drive whose bin is not turned off (``NukeOnDelete``); elsewhere Windows deletes
    for good without asking (send2trash suppresses the prompt). Errors: False.
    Non-Windows without a ``reader``: True."""
    if reader is None and sys.platform != "win32":
        return True
    try:
        info = (reader or _volume_bin)(path)
        return bool(info["fixed"]) and not info["nuke"]
    except (OSError, AttributeError):
        return False


def recycle_bin_fits(path: Path, reader=None) -> bool:
    """Does ``path`` (a file, or a folder's total) fit in its volume's Recycle Bin?
    The limit is ``MaxCapacity`` MB, or 5% of the volume when unset; a bigger item
    Windows deletes for good. Errors: False. Non-Windows without a ``reader``: True."""
    if reader is None and sys.platform != "win32":
        return True
    try:
        info = (reader or _volume_bin)(path)
        p = Path(path)
        size = folder_size(p) if p.is_dir() else p.stat().st_size
        limit = (info["max_mb"] * 1024 * 1024 if info["max_mb"] is not None
                 else info["total"] * 5 // 100)
        return size <= limit
    except (OSError, AttributeError):
        return False


# --- is it really in the Library? ---------------------------------------------
# A set counts as saved only when a Library .osz holds every one of its
# difficulties byte for byte. Matching the set id alone is not enough: a local
# edit, an extra difficulty or an unrelated unsubmitted map that happens to
# carry the same id prefix would otherwise be removed with no copy anywhere.
_OSU_CAP = 32 * 1024 * 1024   # a .osu is text; anything bigger is not a beatmap


def _osu_key(rel: str) -> str:
    return rel.replace("\\", "/").lower()   # Windows names are case-insensitive


def _stream_crc(fh) -> tuple[int, int]:
    """``(size, crc32)`` of an open binary stream, read in chunks so a large
    video is never held in memory whole."""
    size, crc = 0, 0
    while block := fh.read(1024 * 1024):
        size += len(block)
        crc = zlib.crc32(block, crc)
    return size, crc


def folder_fingerprint(folder: Path, *, every_file: bool = False
                       ) -> dict[str, tuple[int, int]] | None:
    """``{relative .osu name: (size, crc32)}`` for a stable set folder; None when
    it cannot be read (or holds an oversized ``.osu``). ``every_file`` maps
    every file of the folder, not only the ``.osu`` (a symlinked one: None)."""
    folder = Path(folder)
    out: dict[str, tuple[int, int]] = {}
    try:
        for root, _dirs, files in os.walk(folder, followlinks=False):
            for f in files:
                is_osu = f.lower().endswith(".osu")
                if not is_osu and not every_file:
                    continue
                p = Path(root) / f
                if p.is_symlink() or (is_osu and p.stat().st_size > _OSU_CAP):
                    return None
                with p.open("rb") as fh:
                    out[_osu_key(p.relative_to(folder).as_posix())] = _stream_crc(fh)
    except OSError:
        return None
    return out


def osz_fingerprint(path: Path, *, every_file: bool = False
                    ) -> dict[str, tuple[int, int]] | None:
    """The same map for a ``.osz``, computed from the members' actual bytes
    (reading verifies each stored CRC too). None for a missing, truncated or
    otherwise unreadable archive — it proves nothing. ``every_file`` maps
    every member, not only the ``.osu``."""
    out: dict[str, tuple[int, int]] = {}
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if info.filename.lower().endswith(".osu"):
                    if info.file_size > _OSU_CAP:
                        return None
                    data = read_capped(zf, info, _OSU_CAP)
                    out[_osu_key(info.filename)] = (len(data), zlib.crc32(data))
                elif every_file:
                    with zf.open(info) as fh:   # reading to the end checks the CRC
                        out[_osu_key(info.filename)] = _stream_crc(fh)
    except Exception:   # BadZipFile, zlib.error, encrypted, EOF, unsupported method…
        return None
    return out


def covers(have: dict | None, want: dict | None) -> bool:
    """Does archive fingerprint ``have`` hold every entry of ``want`` byte for
    byte? A set with no ``.osu`` at all is never "covered"."""
    if not have or not want or not any(k.endswith(".osu") for k in want):
        return False
    return all(have.get(k) == v for k, v in want.items())


# --- is the client running? ---------------------------------------------------
def osu_process_paths(runner=None) -> list[str] | None:
    """Executable paths of every running ``osu!.exe`` (stable and lazer share that
    image name). ``[]`` when none run (or not on Windows), None when it could not
    be determined — PowerShell missing, timed out or failing. ``runner(cmd)``
    returns ``(returncode, stdout)`` (tests)."""
    if sys.platform != "win32" and runner is None:
        return []
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
           "Get-Process -Name 'osu!' -ErrorAction SilentlyContinue | "
           "ForEach-Object { if ($_.Path) { $_.Path } else { '?' } }"]
    try:
        if runner is not None:
            rc, out = runner(cmd)
        else:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            rc, out = proc.returncode, proc.stdout
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if rc != 0:
        return None
    return [ln.strip() for ln in (out or "").splitlines() if ln.strip()]


def client_running(client: str, paths: list[str] | None) -> bool:
    """Is ``client`` ("stable"/"lazer") among the running ``osu!.exe`` paths?

    lazer installs under ``…\\osulazer\\``; anything else named ``osu!.exe`` is
    taken to be stable. Callers check ``paths is None`` (could not tell) first
    and refuse; here a process whose path could not be read (``"?"``) counts
    as BOTH — when in doubt, the destructive action waits.
    """
    if paths is None:
        return True
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


def parse_helper_exported(stdout: str) -> dict[str, int]:
    """``EXPORT <id>\\t<file name>`` lines → ``{file name: id}`` (what the helper
    wrote for which set; an older helper prints bare ``EXPORT <id>`` lines,
    which carry no file name and are skipped)."""
    out: dict[str, int] = {}
    for line in (stdout or "").splitlines():
        parts = line.rstrip("\r\n").split("\t", 1)
        head = parts[0].split()
        if len(parts) == 2 and len(head) == 2 and head[0] == "EXPORT" and head[1].isdigit():
            name = parts[1].strip()
            if name and "/" not in name and "\\" not in name:
                out[name] = int(head[1])
    return out


def parse_helper_deleted(stdout: str) -> set[int]:
    """Ids the helper reports as soft-deleted (``DELETED <id>`` lines)."""
    ids: set[int] = set()
    for line in (stdout or "").splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[0] == "DELETED" and parts[1].isdigit():
            ids.add(int(parts[1]))
    return ids
