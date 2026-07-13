"""Self-heal working-folder paths when the app (or its folder) has moved — item 20.

``config.json`` stores absolute paths for Packs/Output/Library/data/logs. If the
user renames or moves the app folder, those paths go stale. The old code would
then silently recreate empty folders at the stale location (even polluting an
unrelated folder that happens to sit there) while the real data stays next to the
exe. So "the configured folder exists" is NOT enough — it may be empty junk.

This module compares, per folder, the *amount of data* at the configured path
versus the same-named folder next to the exe, and prefers whichever actually holds
the data. That single rule handles every case:

* moved, old folder gone            → re-point to the exe-adjacent folder
* moved, old folder recreated empty → re-point (exe-adjacent has the real data)
* deliberate custom path with data  → preserved (it outweighs the empty default)
* first run / empty place           → create the structure next to the exe

PURE: no Qt, no config I/O. ``diagnose`` reads the filesystem read-only and returns
a plan; ``apply_fix`` mutates a Config in memory. Saving is the caller's job.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Config attribute -> canonical folder name (as created next to the exe/root).
CANONICAL_DIRS = (
    ("packs_dir", "Packs"),
    ("output_dir", "Output"),
    ("library_dir", "Library"),
    ("data_dir", "data"),
    ("logs_dir", "logs"),
)


@dataclass
class PathFix:
    attr: str            # Config attribute, e.g. "library_dir"
    label: str           # canonical folder name, e.g. "Library"
    old: str             # currently-configured path
    new: str             # proposed path (the one that actually holds the data)
    new_exists: bool     # the proposed folder already exists
    new_has_data: bool   # ...and it already contains data (real data recovered)


@dataclass
class Diagnosis:
    status: str                       # "healthy" | "relocated" | "fresh"
    base: str                         # app root used for candidates (exe/repo dir)
    root_old: str
    root_new: str
    fixes: list[PathFix] = field(default_factory=list)

    def has_changes(self) -> bool:
        return bool(self.fixes) or self.root_old != self.root_new


def _weight(p: Path) -> int:
    """Cheap 'how much real data is here' score: total size of immediate files
    plus a small bump per immediate sub-entry. Non-recursive, so it stays fast
    even for an 11GB flat Library (stat() only, no reads). -1 if it doesn't exist.
    """
    if not p.exists():
        return -1
    total = 0
    try:
        with os.scandir(p) as it:
            for entry in it:
                total += 1  # any entry counts a little
                try:
                    if entry.is_file():
                        total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        return -1
    return total


def diagnose(cfg, base) -> Diagnosis:
    """Inspect configured paths vs. the exe-adjacent folders and propose fixes.

    For each working folder, keep whichever of {configured path, exe-adjacent
    folder} actually holds the data; re-point when they differ.
    """
    base = Path(base)
    fixes: dict[str, PathFix] = {}

    # Pass 1 — data wins: re-point a folder only when the exe-adjacent copy holds
    # strictly more data than the configured one (recovers real data after a move).
    for attr, name in CANONICAL_DIRS:
        old_p = Path(getattr(cfg, attr))
        cand = base / name
        if cand == old_p:
            continue  # already the exe-adjacent default (ensure_dirs will create it)

        w_old = _weight(old_p)
        w_cand = _weight(cand)
        if w_old >= 0 and w_cand >= 0:
            chosen_cand = w_cand > w_old               # tie -> keep configured
        else:
            chosen_cand = w_old < 0                    # configured missing -> take exe-adjacent
        if chosen_cand:
            fixes[attr] = PathFix(attr=attr, label=name, old=str(old_p),
                                  new=str(cand), new_exists=w_cand >= 0,
                                  new_has_data=w_cand > 0)

    # Pass 2 — follow the move: if the app clearly relocated (real data recovered,
    # or the configured root is gone), also bring along any *empty* folder still
    # pointing outside the new home. Folders that hold real data are preserved
    # (e.g. a Library the user deliberately keeps on another drive).
    relocating = any(f.new_has_data for f in fixes.values()) or not Path(cfg.root).exists()
    if relocating:
        for attr, name in CANONICAL_DIRS:
            if attr in fixes:
                continue
            old_p = Path(getattr(cfg, attr))
            cand = base / name
            if cand == old_p or _weight(old_p) > 0:
                continue  # already home, or holds real data -> keep
            fixes[attr] = PathFix(attr=attr, label=name, old=str(old_p),
                                  new=str(cand), new_exists=cand.exists(),
                                  new_has_data=_weight(cand) > 0)

    fixes = [fixes[attr] for attr, _ in CANONICAL_DIRS if attr in fixes]  # canonical order
    if not fixes:
        status = "healthy"
    elif any(f.new_exists for f in fixes):
        status = "relocated"     # re-pointing to a real, existing folder -> confirm in UI
    else:
        status = "fresh"         # only creating structure next to the exe -> silent

    root_old = cfg.root
    if fixes or not Path(root_old).exists():
        root_new = str(base)
    else:
        root_new = root_old
    return Diagnosis(status=status, base=str(base), root_old=root_old,
                     root_new=root_new, fixes=fixes)


def apply_fix(cfg, diag: Diagnosis) -> None:
    """Re-point the Config in memory to the diagnosed paths (caller saves)."""
    cfg.root = diag.root_new
    for f in diag.fixes:
        setattr(cfg, f.attr, f.new)


def summary_lines(diag: Diagnosis) -> list[str]:
    """Human-readable 'old -> new' lines for the confirmation dialog."""
    lines: list[str] = []
    if diag.root_old != diag.root_new:
        lines.append(f"root:  {diag.root_old}  ->  {diag.root_new}")
    for f in diag.fixes:
        tag = " (data found)" if f.new_has_data else ""
        lines.append(f"{f.label}:  {f.old}  ->  {f.new}{tag}")
    return lines
