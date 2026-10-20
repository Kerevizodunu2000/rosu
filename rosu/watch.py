# SPDX-License-Identifier: GPL-3.0-or-later
"""Watch folder (v1.9) — Qt-free helpers.

Opt-in: while Rosu runs, new ``.osz`` files that appear in one chosen folder
(say, Downloads) are added to the Library. The files themselves are never
moved or deleted. What was already in the folder when watching was turned on
is left alone; downloads that arrive while Rosu is closed are added the next
time it runs. A file is taken only once its size and time have stopped
changing between two looks (a download still being written is not ready), and
only marked as handled once the import reports it done.

State (which files were handled) lives in ``data/watch_state.json`` for the
folder it belongs to; pointing the watcher at another folder starts afresh.
"""
from __future__ import annotations

import json
from pathlib import Path

MAX_SEEN = 20000
BATCH_FILES = 100                  # per import job; the rest follow in the next
BATCH_BYTES = 2 * 1024 ** 3


def key(name: str, size: int, mtime_ns: int) -> str:
    return f"{name}|{size}|{mtime_ns}"


def list_osz(folder: Path) -> dict[str, tuple[int, int]]:
    """``{file name: (size, mtime_ns)}`` for the ``.osz`` files directly in
    ``folder`` (no symlinks, nothing in subfolders)."""
    out: dict[str, tuple[int, int]] = {}
    try:
        for p in Path(folder).iterdir():
            if p.suffix.lower() != ".osz" or p.is_symlink() or not p.is_file():
                continue
            st = p.stat()
            out[p.name] = (st.st_size, st.st_mtime_ns)
    except OSError:
        pass
    return out


def ready(folder: Path, seen, previous: dict, busy=()) -> tuple[list[Path], dict, bool]:
    """Files to import now (one batch), the listing to compare against next
    time, and whether more is waiting (a file still changing, or the rest of a
    big catch-up) so the caller looks again soon. Keys in ``busy`` are being
    imported already."""
    now = list_osz(folder)
    take: list[Path] = []
    pending = False
    total = 0
    for name, (size, mtime) in sorted(now.items()):
        k = key(name, size, mtime)
        if k in seen or k in busy:
            continue
        if size > 0 and previous.get(name) == (size, mtime) and len(take) < BATCH_FILES \
                and (not take or total + size <= BATCH_BYTES):
            take.append(Path(folder) / name)
            total += size
        else:
            pending = True
    return take, now, pending


def baseline(folder: Path) -> dict[str, None]:
    """Everything already in the folder, as handled (watching starts now)."""
    return dict.fromkeys(key(n, s, m) for n, (s, m) in sorted(list_osz(folder).items()))


def load_state(path: Path, folder: Path) -> dict[str, None] | None:
    """The handled-file keys for ``folder``, oldest first (an ordered dict used
    as a set); None when the state is missing, unreadable or belongs to
    another folder."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("folder") != str(folder):
        return None
    seen = data.get("seen")
    return dict.fromkeys(s for s in seen if isinstance(s, str)) if isinstance(seen, list) else None


def save_state(path: Path, folder: Path, seen) -> None:
    items = list(seen)[-MAX_SEEN:]          # the oldest handled files go first
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".part")
        tmp.write_text(json.dumps({"folder": str(folder), "seen": items}), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass
