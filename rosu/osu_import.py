# SPDX-License-Identifier: GPL-3.0-or-later
"""Bulk-import .osz files into osu!lazer via its command-line / IPC pipeline.

osu!lazer imports any beatmap archive passed as a command-line argument. Because
it is single-instance, launching ``osu!.exe file1.osz file2.osz ...`` forwards
the import to the already-running client over its IPC channel. We therefore just
invoke the executable with batches of file paths — osu! does the actual import
through its own (Realm-safe) pipeline; we never touch its database directly.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Callable

# Keep well under the Windows command-line limit (~32767 chars) and cap the
# number of files per launch so a single invocation stays snappy. 64 files at
# ~250 chars/path ≈ 16k chars — still comfortably under the char budget below
# (item 19). The "one-by-one" tail some users see afterwards is osu!lazer's own
# serial per-set import, not our batching.
_MAX_BATCH_FILES = 64
_MAX_BATCH_CHARS = 24000
_BATCH_DELAY_S = 0.3        # once osu! is running, forwarding is cheap
_FIRST_BATCH_DELAY_S = 6.0  # extra time so a cold-starting osu! can boot first
_PER_MAP_IMPORT_S = 0.5     # rough osu!-side import time per beatmap (for ETA)


class OsuNotFoundError(RuntimeError):
    pass


def output_osz_files(output_dir: Path) -> list[Path]:
    return sorted(Path(output_dir).glob("*.osz"))


def batches(files: list[Path], max_files: int = _MAX_BATCH_FILES) -> list[list[Path]]:
    """Group files into command-line batches. ``max_files`` per launch — osu!lazer
    accepts many at once (IPC-forwarded); osu!(stable) only reliably imports ONE
    file per launch (multiple args make it fail with "Error moving file"), so the
    stable path passes ``max_files=1``."""
    out: list[list[Path]] = []
    batch: list[Path] = []
    length = 0
    for f in files:
        cost = len(str(f)) + 3  # quotes + space
        if batch and (len(batch) >= max_files or length + cost > _MAX_BATCH_CHARS):
            out.append(batch)
            batch, length = [], 0
        batch.append(f)
        length += cost
    if batch:
        out.append(batch)
    return out


def estimate_seconds(n_files: int, n_batches: int) -> int:
    """Rough total-time hint (our dispatch + osu!'s serial import)."""
    dispatch = _FIRST_BATCH_DELAY_S + max(0, n_batches - 1) * _BATCH_DELAY_S
    return int(dispatch + n_files * _PER_MAP_IMPORT_S)


def import_files(osu_exe: str, files: list[Path],
                 progress: Callable[[int, int, int], None] | None = None,
                 cancel: Callable[[], bool] | None = None,
                 delay_s: float = _BATCH_DELAY_S,
                 max_batch_files: int = _MAX_BATCH_FILES) -> dict:
    """Send ``files`` to an osu! client in batches (``max_batch_files`` per
    launch; pass 1 for osu!(stable), which imports one file per launch).

    ``cancel`` is polled between batches; when it returns True dispatch stops
    (batches already handed to osu! keep importing on its side). Returns
    ``{"files", "batches", "sent", "cancelled"}``.
    """
    if not osu_exe or not Path(osu_exe).exists():
        raise OsuNotFoundError(osu_exe or "<empty>")
    if not files:
        return {"files": 0, "batches": 0, "sent": 0, "cancelled": False}

    all_batches = batches(files, max_batch_files)
    total = len(all_batches)
    sent = 0
    for i, batch in enumerate(all_batches, start=1):
        if cancel is not None and cancel():
            return {"files": len(files), "batches": total, "sent": sent,
                    "cancelled": True}
        subprocess.Popen([osu_exe, *[str(p) for p in batch]], close_fds=True)
        sent += len(batch)
        if progress:
            progress(i, total, len(batch))
        if i < total:
            # First launch may cold-start osu!; later forwards are cheap.
            time.sleep(_FIRST_BATCH_DELAY_S if i == 1 else delay_s)
    return {"files": len(files), "batches": total, "sent": sent, "cancelled": False}
