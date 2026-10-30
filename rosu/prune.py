# SPDX-License-Identifier: GPL-3.0-or-later
"""Space-saving: strip heavy assets from mapsets.

Two storage shapes are handled, because the two osu! clients store beatmaps
differently:

* **.osz archives** (Rosu's Library) — :func:`prune_osz` rewrites the zip without
  the unwanted members, atomically, and only after a copy of the original has
  reached the Recycle Bin (a throwaway copy can opt out with
  ``keep_original=False``).
* **loose folders** (osu!(stable)'s ``Songs/<set>/``) — :func:`prune_folder`
  recycles the unwanted files in place. Stable reads the folder from disk, so a
  missing video simply means no video.

Both refuse (free nothing) on a drive without a Recycle Bin, where "recycling"
would delete for good.

**osu!lazer is deliberately absent.** Lazer stores every file content-addressed
under ``files/<h>/<hh>/<hash>`` and references it from ``client.realm`` by hash,
so (a) deleting a file leaves the Realm row pointing at nothing and (b) the same
hash is shared by *every* set containing that byte-identical asset — removing one
set's video can break other sets. Pruning lazer has to go through lazer's own
model (the bundled Realm helper), never through the filesystem.
"""
import os
import shutil
import stat
import zipfile
import tempfile
from pathlib import Path

from . import client_remove
from .zipread import TooBig, read_capped


def _discard(path) -> None:
    """Delete a temp/working file, best effort.

    Clears the read-only bit first: ``shutil.copy2`` copies an .osz's mode bits
    along with its content, so the aside-copy of a read-only Library file is
    itself read-only and a plain ``os.remove`` raises ``PermissionError`` on
    Windows — which used to leave a stray ``*.osz.orig`` behind in the Library
    folder on every prune attempt against such a file.
    """
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    try:
        os.remove(path)
    except OSError:
        pass

# Per-entry uncompressed-size cap: refuse to read a zip member past this size
# so a crafted/zip-bomb entry (tiny compressed, huge declared file_size) can't
# be inflated into memory. Library .osz files aren't always security_scan'd
# before reaching here (e.g. a manually-dropped or mirror-downloaded file), so
# this module can't assume the archive was already vetted — fail closed.
_MAX_ENTRY_BYTES = 200 * 1024 * 1024

VIDEO_EXTS = (".mp4", ".avi", ".flv", ".mpg", ".mpeg", ".wmv", ".mov", ".m4v")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp")
_AUDIO_EXTS = (".wav", ".ogg", ".mp3")
# heavy_assets keeps the exact extension list it shipped with, so upgrading
# cannot silently change what an existing configuration removes.
_HEAVY_IMAGE_EXTS = (".jpg", ".png", ".jpeg")
_HEAVY_IMAGE_CAP = 500 * 1024
_MAX_UNESSENTIAL_DEFAULT = 2 * 1024 * 1024

# What each mode strips. `heavy_assets` is the original v1.7 behaviour and stays
# bit-for-bit; the other three were added in v1.7.1 so the choice is made at the
# point of use instead of being buried in Settings.
MODES = ("video_only", "images_only", "video_and_images", "heavy_assets")

# Modes that decide purely by extension need no .osu parse at all.
_BY_EXTENSION = {
    "video_only": VIDEO_EXTS,
    "images_only": IMAGE_EXTS,
    "video_and_images": VIDEO_EXTS + IMAGE_EXTS,
}


def _is_removable(name_lower: str, size: int, mode: str, essential: set[str],
                  max_audio: int = _MAX_UNESSENTIAL_DEFAULT) -> bool:
    """Should this member be stripped under ``mode``? A ``.osu`` never is —
    losing one deletes a difficulty, which is not "saving space"."""
    if name_lower.endswith(".osu"):
        return False
    exts = _BY_EXTENSION.get(mode)
    if exts is not None:
        return name_lower.endswith(exts)
    # heavy_assets: keep what a .osu references, plus small audio/images.
    if any(name_lower.endswith(asset) for asset in essential):
        return False
    if name_lower.endswith(_AUDIO_EXTS):
        return size > max_audio
    if name_lower.endswith(_HEAVY_IMAGE_EXTS):
        return size > _HEAVY_IMAGE_CAP
    return True


def get_osu_assets(text: str) -> set[str]:
    """Parse an .osu file text to extract AudioFilename and Background image paths."""
    assets = set()
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section == "General":
            if line.lower().startswith("audiofilename:"):
                assets.add(line.split(":", 1)[1].strip())
        elif section == "Events":
            # 0,0,"bg.jpg",0,0
            if line.startswith("0,"):
                parts = line.split(",")
                if len(parts) >= 3:
                    bg = parts[2].strip('"')
                    assets.add(bg)
    return assets


def _aside_name(p: Path) -> Path:
    """Where to put the pre-prune copy that goes to the Recycle Bin.

    It used to be a ``tempfile.mkstemp`` name (``tmpab12cd.osz.orig``), which made
    the Recycle Bin entry unidentifiable — restoring it gave back a file nobody
    could match to a beatmap. Naming it after the set is the difference between a
    recoverable original and a mystery blob.
    """
    base = p.with_name(p.name + ".orig")
    if not base.exists():
        return base
    for i in range(2, 1000):
        cand = p.with_name(f"{p.name}.{i}.orig")
        if not cand.exists():
            return cand
    return base


def _essential_assets(zf, mode: str) -> set[str] | None:
    """The asset filenames the .osu files reference, for ``heavy_assets``.

    ``None`` means "refuse to prune this archive" (no .osu at all, or a
    suspiciously large one). Extension-driven modes need no parse and get an
    empty set.
    """
    if mode != "heavy_assets":
        return set()
    essential: set[str] = set()
    found_osu = False
    for info in zf.infolist():
        if not info.filename.lower().endswith(".osu"):
            continue
        if info.file_size > _MAX_ENTRY_BYTES:
            return None   # suspicious .osu size — fail closed, don't prune
        found_osu = True
        try:
            text = read_capped(zf, info, _MAX_ENTRY_BYTES).decode("utf-8", errors="replace")
        except TooBig:
            return None   # the declared size lied — fail closed, don't prune
        for asset in get_osu_assets(text):
            essential.add(asset.lower().replace("\\", "/"))
    return essential if found_osu else None


def scan_osz(osz_path: Path | str, mode: str = "video_only") -> tuple[int, int]:
    """``(archive_size_on_disk, removable_bytes)`` — a *preview*, reading only the
    zip's central directory so nothing is decompressed and nothing is written.

    ``removable_bytes`` is the uncompressed size of the members that would go.
    For the formats this actually targets (video, jpg/png) that is within a
    rounding error of the disk saving, and it is the SAME number
    :func:`prune_osz` reports afterwards, so the preview and the result agree.
    """
    p = Path(osz_path)
    try:
        total = p.stat().st_size
    except OSError:
        return (0, 0)
    try:
        with zipfile.ZipFile(p, "r") as zf:
            essential = _essential_assets(zf, mode)
            if essential is None:
                return (total, 0)
            removable = sum(info.file_size for info in zf.infolist()
                            if _is_removable(info.filename.lower(), info.file_size,
                                             mode, essential))
    except (zipfile.BadZipFile, OSError):
        return (total, 0)
    return (total, removable)


def prune_osz(osz_path: Path | str, mode: str = 'video_only', max_unessential_size: int = 2 * 1024 * 1024,
              *, keep_original: bool = True) -> int:
    """Remove non-essential files from an .osz to save space.

    ``mode`` is one of :data:`MODES` — ``video_only``, ``images_only``,
    ``video_and_images`` (all three decide purely by extension) or
    ``heavy_assets`` (keeps whatever a ``.osu`` references, plus small
    audio/images, and drops the rest). A ``.osu`` is never removed.

    With ``keep_original`` (the default) a copy of the original goes to the
    Recycle Bin BEFORE the pruned file replaces it, so a failed trash step
    leaves the original untouched; on a drive without a Recycle Bin nothing is
    pruned. ``keep_original=False`` is for throwaway copies (an export, a staged
    import): no Recycle Bin copy, just the swap.

    Returns bytes freed; 0 when nothing was removed (and then the original file
    is not rewritten at all).
    """
    p = Path(osz_path)
    if not p.exists():
        return 0
    if keep_original and not client_remove.recycle_bin_available(p.parent):
        return 0

    try:
        with zipfile.ZipFile(p, 'r') as zf:
            essential_assets = _essential_assets(zf, mode)
    except (zipfile.BadZipFile, OSError):
        return 0
    if essential_assets is None:
        return 0

    freed = 0
    temp_fd, temp_path = tempfile.mkstemp(dir=p.parent, suffix=".osz")
    os.close(temp_fd)

    try:
        with zipfile.ZipFile(p, 'r') as zf_in:
            with zipfile.ZipFile(temp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf_out:
                for info in zf_in.infolist():
                    name_lower = info.filename.lower()
                    if not _is_removable(name_lower, info.file_size, mode,
                                         essential_assets, max_unessential_size):
                        if info.file_size > _MAX_ENTRY_BYTES:
                            # Fail closed rather than inflate a suspiciously large
                            # member into memory (possible zip bomb). Raise (rather
                            # than return) so the outer handler still cleans up the
                            # partially-written temp file.
                            raise ValueError(f"entry too large: {info.filename}")
                        zf_out.writestr(info, read_capped(zf_in, info, _MAX_ENTRY_BYTES))
                    else:
                        freed += info.file_size

        if freed <= 0:
            _discard(temp_path)
            return 0

        # Make the original recoverable FIRST: copy it aside (the live file at
        # `p` is never touched by this) and send that copy to the Recycle Bin.
        # If either step fails, drop the copy and the temp file and leave `p`
        # as it was. Only once the copy is in the Recycle Bin is the pruned file
        # swapped in, with a SINGLE `os.replace(temp_path, p)`: an atomic
        # rename with no instant where `p` is missing. If that swap fails, `p`
        # is still the original and the trashed copy is merely redundant.
        if keep_original:
            trash_copy = str(_aside_name(p))
            try:
                shutil.copy2(str(p), trash_copy)
                from send2trash import send2trash
                send2trash(trash_copy)
            except Exception:
                _discard(trash_copy)
                raise
        os.replace(temp_path, str(p))   # atomic: p always has valid content
        return freed
    except Exception:
        _discard(temp_path)
        return 0


# -- loose folders (osu!(stable)'s Songs/<set>/) ------------------------------
def _folder_essentials(folder: Path, mode: str) -> set[str] | None:
    """``heavy_assets``' referenced-asset set for a Songs folder, or ``None`` to
    refuse (a folder with no ``.osu`` is not a beatmap folder — leave it alone)."""
    osu_files = sorted(folder.rglob("*.osu"))
    if not osu_files:
        return None
    if mode != "heavy_assets":
        return set()
    essential: set[str] = set()
    for osu in osu_files:
        try:
            if osu.stat().st_size > _MAX_ENTRY_BYTES:
                return None
            text = osu.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        for asset in get_osu_assets(text):
            essential.add(asset.lower().replace("\\", "/"))
    return essential


def _folder_targets(folder: Path, mode: str) -> list[Path] | None:
    """Files inside ``folder`` that ``mode`` would remove, or ``None`` to refuse."""
    essential = _folder_essentials(folder, mode)
    if essential is None:
        return None
    out: list[Path] = []
    for p in folder.rglob("*"):
        try:
            if not p.is_file() or p.is_symlink():
                continue          # never follow a link out of the set folder
            size = p.stat().st_size
        except OSError:
            continue
        # The relative path, so "sub/bg.jpg" matches a .osu's "sub/bg.jpg".
        if _is_removable(p.relative_to(folder).as_posix().lower(), size, mode, essential):
            out.append(p)
    return out


def scan_folder(folder: Path | str, mode: str = "video_only") -> tuple[int, int]:
    """``(folder_size, removable_bytes)`` for a loose beatmap folder. Read-only."""
    folder = Path(folder)
    total = 0
    for p in folder.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            pass
    targets = _folder_targets(folder, mode)
    if not targets:
        return (total, 0)
    removable = 0
    for p in targets:
        try:
            removable += p.stat().st_size
        except OSError:
            pass
    return (total, removable)


def prune_folder(folder: Path | str, mode: str = "video_only",
                 root: Path | str | None = None) -> int:
    """Recycle the unwanted files inside a loose beatmap folder. Returns bytes freed.

    Unlike :func:`prune_osz` there is no archive to rewrite — stable reads the
    folder straight from disk, so removing a video just means the map has no
    video. Three guards, because this deletes real files:

    * ``root`` (the Songs directory) is enforced — a folder resolving outside it
      is refused outright, so a stray symlink or a bad path cannot walk the disk;
    * a folder with no ``.osu`` is not a beatmap folder and is left alone;
    * files go to the **Recycle Bin**, never an unlink, so it stays undoable;
      on a drive without one, nothing is removed.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return 0
    if root is not None:
        try:
            folder.resolve().relative_to(Path(root).resolve())
        except (ValueError, OSError):
            return 0          # outside the configured Songs folder — refuse
    if not client_remove.recycle_bin_available(folder):
        return 0              # send2trash would delete for good here
    targets = _folder_targets(folder, mode)
    if not targets:
        return 0
    from send2trash import send2trash
    freed = 0
    for p in targets:
        try:
            size = p.stat().st_size
            send2trash(str(p))
            freed += size
        except Exception:
            continue          # one stubborn file must not abort the rest
    return freed


# -- choosing what to prune (pure) -------------------------------------------
SORTS = ("largest", "smallest", "name")


def select_targets(sets: list[dict], sort: str = "largest",
                   limit: int | None = None) -> list[dict]:
    """Order candidate sets and take the first ``limit``.

    Only sets that would actually free something are eligible — offering to
    "prune 200 sets" and then touching 40 of them would make the preview a lie.
    ``sort`` is a :data:`SORTS` value; ``largest`` means most-freed-first, which
    is what "get my disk space back" actually wants.
    """
    usable = [s for s in sets if s.get("freed", 0) > 0]
    if sort == "smallest":
        usable.sort(key=lambda s: (s.get("freed", 0), s.get("name", "")))
    elif sort == "name":
        usable.sort(key=lambda s: str(s.get("name", "")).lower())
    else:
        usable.sort(key=lambda s: (-s.get("freed", 0), str(s.get("name", ""))))
    if limit is not None and limit > 0:
        usable = usable[:limit]
    return usable
