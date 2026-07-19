# SPDX-License-Identifier: GPL-3.0-or-later
"""Space-saving feature to strip heavy assets from mapsets."""
import os
import shutil
import zipfile
import tempfile
from pathlib import Path

# Per-entry uncompressed-size cap: refuse to read a zip member past this size
# so a crafted/zip-bomb entry (tiny compressed, huge declared file_size) can't
# be inflated into memory. Library .osz files aren't always security_scan'd
# before reaching here (e.g. a manually-dropped or mirror-downloaded file), so
# this module can't assume the archive was already vetted — fail closed.
_MAX_ENTRY_BYTES = 200 * 1024 * 1024


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


def prune_osz(osz_path: Path | str, mode: str = 'video_only', max_unessential_size: int = 2 * 1024 * 1024) -> int:
    """
    Remove non-essential files from an .osz to save space.
    mode="video_only": Only removes .mp4, .avi, .flv, .mpg files.
    mode="heavy_assets": Keeps only .osu, audio, backgrounds, and small hitsounds/images. Removes .osb and large images.
    Returns bytes freed. If nothing was freed, returns 0.
    """
    p = Path(osz_path)
    if not p.exists():
        return 0
    
    essential_assets = set()
    osu_files = []
    
    if mode == 'heavy_assets':
        try:
            with zipfile.ZipFile(p, 'r') as zf:
                for info in zf.infolist():
                    lower_name = info.filename.lower()
                    if lower_name.endswith('.osu'):
                        if info.file_size > _MAX_ENTRY_BYTES:
                            return 0   # suspicious .osu size — fail closed, don't prune
                        osu_files.append(info.filename)
                        text = zf.read(info.filename).decode('utf-8', errors='replace')
                        for asset in get_osu_assets(text):
                            norm = asset.lower().replace("\\", "/")
                            essential_assets.add(norm)
        except (zipfile.BadZipFile, OSError):
            return 0
            
        if not osu_files:
            return 0
        
    freed = 0
    temp_fd, temp_path = tempfile.mkstemp(dir=p.parent, suffix=".osz")
    os.close(temp_fd)
    
    try:
        with zipfile.ZipFile(p, 'r') as zf_in:
            with zipfile.ZipFile(temp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf_out:
                for info in zf_in.infolist():
                    name_lower = info.filename.lower()

                    is_essential = True
                    if mode == 'video_only':
                        if name_lower.endswith(('.mp4', '.avi', '.flv', '.mpg')):
                            is_essential = False
                    else: # heavy_assets
                        is_essential = False
                        if name_lower.endswith('.osu'):
                            is_essential = True
                        elif any(name_lower.endswith(asset) for asset in essential_assets):
                            is_essential = True
                        elif name_lower.endswith(('.wav', '.ogg', '.mp3')):
                            if info.file_size <= max_unessential_size:
                                is_essential = True
                        elif name_lower.endswith(('.jpg', '.png', '.jpeg')):
                            if info.file_size <= 500 * 1024:
                                is_essential = True

                    if is_essential:
                        if info.file_size > _MAX_ENTRY_BYTES:
                            # Fail closed rather than inflate a suspiciously large
                            # member into memory (possible zip bomb). Raise (rather
                            # than return) so the outer handler still cleans up the
                            # partially-written temp file.
                            raise ValueError(f"entry too large: {info.filename}")
                        zf_out.writestr(info, zf_in.read(info.filename))
                    else:
                        freed += info.file_size

        if freed <= 0:
            os.remove(temp_path)
            return 0

        # Keep the original recoverable (Recycle Bin) WITHOUT gating the
        # swap's atomicity on it: copy it aside first (the live file at `p`
        # is never touched by this), then do the actual swap-in with a
        # SINGLE `os.replace(temp_path, p)` — an atomic rename that has no
        # instant where `p` is missing, unlike a rename-aside-then-swap-back
        # sequence (which a crash or a second I/O failure mid-recovery could
        # leave stuck with `p` absent and the real file stranded under a
        # temp name). Only trash the copy last, once the swap is done.
        trash_fd, trash_copy = tempfile.mkstemp(dir=p.parent, suffix=".osz.orig")
        os.close(trash_fd)
        try:
            shutil.copy2(str(p), trash_copy)
        except Exception:
            os.remove(trash_copy)
            raise
        try:
            os.replace(temp_path, str(p))   # atomic: p always has valid content
        except Exception:
            os.remove(trash_copy)   # p untouched; drop the now-unneeded copy
            raise
        try:
            from send2trash import send2trash
            send2trash(trash_copy)
        except Exception:
            try:
                os.remove(trash_copy)
            except OSError:
                pass
        return freed
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return 0
