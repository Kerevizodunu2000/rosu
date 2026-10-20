# SPDX-License-Identifier: GPL-3.0-or-later
"""Small file-system helpers shared by the services (v1.10 review)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def place_new(tmp: Path, dest: Path) -> None:
    """Give the finished temp file ``tmp`` the name ``dest`` — but never replace
    a file that is already there, even one that appeared a moment ago. Raises
    :class:`FileExistsError` then (``tmp`` is left for the caller to remove)."""
    if os.name == "nt":
        os.rename(tmp, dest)        # refuses an existing name on Windows
        return
    try:
        os.link(tmp, dest)          # refuses an existing name
    except FileExistsError:
        raise
    except OSError:                 # no hard links here (FAT, exFAT, some shares)
        if os.path.lexists(dest):
            raise FileExistsError(str(dest)) from None
        os.replace(tmp, dest)
        return
    os.unlink(tmp)


def dir_writable(folder: Path) -> bool:
    """Whether a file can be created in ``folder``. ``os.access`` does not
    answer this on Windows (it ignores ACLs), so a throw-away file is tried."""
    try:
        with tempfile.TemporaryFile(dir=folder):
            return True
    except OSError:
        return False
