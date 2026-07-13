"""Auto-import songs already installed in an osu! client (item 15).

PURE helpers (no Qt): locate osu!(stable) and osu!lazer, turn what's installed
into ``.osz`` files, and resolve beatmapset ids so the normal dedup pipeline can
take over.

* **osu!(stable)** keeps each beatmapset as an extracted folder under ``Songs/``;
  we zip a folder's contents back into an ``.osz`` (pure Python).
* **osu!lazer** keeps files hash-named in a ``files/`` store indexed by a Realm
  database — unreadable from Python — so a bundled .NET helper re-exports the
  ``.osz`` files and we import that folder with :func:`iter_osz_in_folder`.
"""
from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path
from typing import Iterator

_ID_PREFIX = re.compile(r"^(\d+)\s")


# --- osu!(stable) -----------------------------------------------------------
def stable_install_dir() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    base = Path(local) / "osu!"
    return base if (base / "osu!.exe").exists() or base.exists() else None


def _read_beatmap_dir(cfg_path: Path, base: Path) -> Path | None:
    try:
        for line in cfg_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().lower().startswith("beatmapdirectory"):
                _, _, val = line.partition("=")
                val = val.strip()
                if val:
                    p = Path(val)
                    return p if p.is_absolute() else (base / val)
    except OSError:
        pass
    return None


def stable_songs_dir() -> Path | None:
    """The osu!(stable) Songs folder — honouring a custom BeatmapDirectory."""
    base = stable_install_dir()
    if not base or not base.exists():
        return None
    for cfg in sorted(base.glob("osu!.*.cfg")):
        d = _read_beatmap_dir(cfg, base)
        if d and d.exists():
            return d
    songs = base / "Songs"
    return songs if songs.exists() else None


def iter_stable_folders(songs_dir: Path) -> Iterator[Path]:
    for p in sorted(Path(songs_dir).iterdir()):
        if p.is_dir():
            yield p


def _read_setid_from_osu(osu_path: Path) -> int | None:
    try:
        for line in osu_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("BeatmapSetID"):
                _, _, val = line.partition(":")
                val = val.strip()
                if val.lstrip("-").isdigit() and int(val) > 0:
                    return int(val)
                return None
    except OSError:
        pass
    return None


def beatmapset_id_for_folder(folder: Path) -> int | None:
    """Prefer the numeric folder-name prefix; fall back to a .osu's BeatmapSetID."""
    m = _ID_PREFIX.match(folder.name)
    if m:
        return int(m.group(1))
    for osu in sorted(folder.glob("*.osu")):
        bid = _read_setid_from_osu(osu)
        if bid:
            return bid
    return None


def zip_folder_to_osz(folder: Path, dest_osz: Path) -> Path:
    """Zip a Songs/ folder's *contents* into an .osz, preserving nested subfolders
    (storyboards/skins). Stored (no compression) since the media is already packed."""
    folder = Path(folder)
    dest_osz = Path(dest_osz)
    dest_osz.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest_osz.with_suffix(dest_osz.suffix + ".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(folder).as_posix())
    tmp.replace(dest_osz)
    return dest_osz


def _osz_name_for(folder: Path, beatmapset_id: int) -> str:
    """An .osz filename the pipeline can dedup by id: '<id> <clean folder name>.osz'."""
    name = folder.name
    if _ID_PREFIX.match(name):
        return f"{name}.osz"
    return f"{beatmapset_id} {name}.osz"


# --- osu!lazer --------------------------------------------------------------
def lazer_data_dir() -> Path | None:
    """The osu!lazer data folder (holds client.realm + files/) — %APPDATA%\\osu."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        d = Path(appdata) / "osu"
        if (d / "client.realm").exists():
            return d
    return None


# --- shared -----------------------------------------------------------------
def iter_osz_in_folder(folder: Path) -> Iterator[Path]:
    """Every .osz/.olz directly under ``folder`` (used to import an exports dir)."""
    folder = Path(folder)
    if not folder.exists():
        return
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in (".osz", ".olz"):
            yield p
