# SPDX-License-Identifier: GPL-3.0-or-later
"""Download Chromaprint's fpcalc (the audio-fingerprint tool Rosu bundles) into
``rosu/assets/fpcalc/`` and check it against a pinned SHA-256.

The binary is not kept in git: CI runs this before PyInstaller, and a developer
runs it once to get audio fingerprints when running from source.

    python tools/fetch_fpcalc.py            # this platform
    python tools/fetch_fpcalc.py windows    # the Windows build (CI)

Chromaprint is LGPL-2.1-or-later and the official fpcalc build includes FFmpeg
(LGPL-2.1-or-later); see THIRD-PARTY-LICENSES.md.
"""
from __future__ import annotations

import hashlib
import io
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "1.6.2"
BASE = f"https://github.com/acoustid/chromaprint/releases/download/v{VERSION}/"
BUILDS = {
    "windows": (f"chromaprint-fpcalc-{VERSION}-windows-x86_64.zip", "fpcalc.exe",
                "b74369726676670af3ab0eadff45f960cf969fdf4a87a971ba37eaf8d530e874"),
    "linux": (f"chromaprint-fpcalc-{VERSION}-linux-x86_64.tar.gz", "fpcalc",
              "c968ad4a0821592a79b158fb2e1f46cbe0a22a0a1dbc0743c67d68e75d15d2bb"),
}
DEST = Path(__file__).resolve().parent.parent / "rosu" / "assets" / "fpcalc"


def fetch(platform: str) -> Path:
    archive, member, sha256 = BUILDS[platform]
    with urllib.request.urlopen(BASE + archive, timeout=120) as resp:
        data = resp.read(64 * 1024 * 1024)
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise SystemExit(f"{archive}: SHA-256 {digest} does not match the pinned {sha256}")
    if archive.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            name = next(n for n in zf.namelist() if n.rsplit("/", 1)[-1] == member)
            payload = zf.read(name)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            info = next(m for m in tf.getmembers() if m.isfile() and m.name.rsplit("/", 1)[-1] == member)
            payload = tf.extractfile(info).read()
    DEST.mkdir(parents=True, exist_ok=True)
    out = DEST / member
    out.write_bytes(payload)
    out.chmod(0o755)
    return out


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ("windows" if sys.platform == "win32" else "linux")
    print(fetch(target))
