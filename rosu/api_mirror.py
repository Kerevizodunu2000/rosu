# SPDX-License-Identifier: GPL-3.0-or-later
"""osu! third-party mirror API client (Mino/Catboy).

Downloads come from an unofficial community mirror, not the official osu!
servers — callers are expected to get informed consent before invoking this
(see the repair confirmation dialogs in the UI layer)."""

import urllib.request
from pathlib import Path
from tempfile import NamedTemporaryFile

from . import __version__

MIRROR_URL = "https://catboy.best/d/{}"
_USER_AGENT = f"Rosu/{__version__} (+https://github.com/Kerevizodunu2000/rosu)"

# A beatmapset .osz is realistically well under this; a mirror serving more
# (compromised, misbehaving, or a MITM) is refused rather than filling disk.
_MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024

def download_osz(beatmapset_id: int, dest_path: Path | str, progress=None) -> bool:
    """Download an .osz from a mirror (Catboy). Returns True on success."""
    url = MIRROR_URL.format(beatmapset_id)
    req = urllib.request.Request(url, headers={'User-Agent': _USER_AGENT})
    tmp_path = None

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                return False

            total_size = int(resp.headers.get('Content-Length', 0))
            if total_size > _MAX_DOWNLOAD_BYTES:
                return False
            downloaded = 0

            with NamedTemporaryFile(delete=False, suffix=".osz.part", dir=Path(dest_path).parent) as tmp:
                tmp_path = Path(tmp.name)
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > _MAX_DOWNLOAD_BYTES:
                        return False
                    tmp.write(chunk)
                    if progress and total_size > 0:
                        progress({"kind": "download", "done": downloaded, "total": total_size})

            tmp_path.replace(dest_path)
            return True

    except Exception:
        return False
    finally:
        try:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
