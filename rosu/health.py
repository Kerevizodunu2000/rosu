# SPDX-License-Identifier: GPL-3.0-or-later
"""Library integrity, health & disk-usage computation (pure, I/O-free).

The service scans the Library folder and reads the DB, then hands plain data to
these functions so the logic stays unit-testable:

* :func:`disk_usage`   — how much space the Library uses and over how many files.
* :func:`biggest_sets` — the largest ``.osz`` on disk (where the space goes).
* :func:`scrub`        — reconcile the DB "memory" with what's actually on disk:
  **orphans** (files with no DB row), **dead links** (rows the DB thinks are
  physically present but whose file is gone) and intentionally memory-only rows.
* :func:`verify_classify` — compare a freshly re-hashed file against the hash
  recorded when it was backed up: ``ok`` / ``mismatch`` / ``unhashed``.

Everything here is read-only reporting — Rosu never modifies or deletes a
beatmap as part of a health check.
"""
from __future__ import annotations

from typing import Iterable, Mapping


def disk_usage(disk_files: Mapping[str, int]) -> dict:
    """Total bytes + file count from an on-disk Library scan.

    ``disk_files`` maps ``filename -> size_bytes`` for every ``.osz`` in the
    Library folder.
    """
    total = sum(int(s or 0) for s in disk_files.values())
    return {"files": len(disk_files), "total_bytes": total}


def biggest_sets(db_rows: Iterable[dict], disk_files: Mapping[str, int],
                 n: int = 20) -> list[dict]:
    """The ``n`` largest ``.osz`` on disk, annotated with their display name
    when the DB knows it. Ties break on filename for a stable order."""
    name_by_file = {r.get("filename"): r.get("display_name")
                    for r in db_rows if r.get("filename")}
    items = [{"filename": fn, "size_bytes": int(sz or 0),
              "display_name": name_by_file.get(fn)}
             for fn, sz in disk_files.items()]
    items.sort(key=lambda x: (-x["size_bytes"], x["filename"]))
    return items[:max(0, n)]


def scrub(db_rows: Iterable[dict], disk_files: Mapping[str, int]) -> dict:
    """Reconcile the DB library memory with the files actually on disk.

    * **present**    — DB rows whose file is on disk (healthy).
    * **orphans**    — files on disk that no DB row references (sorted names).
    * **dead_links** — rows flagged ``in_library`` (physically present) whose
      file is missing. A ``memory``/``disappeared`` row is *not* a dead link —
      the DB already knows it has no physical copy.
    * **memory**     — count of intentionally memory-only rows.
    """
    disk_names = set(disk_files)
    rows = list(db_rows)
    by_name: dict[str, dict] = {}
    for r in rows:
        fn = r.get("filename")
        if fn:
            by_name.setdefault(fn, r)

    present = disk_names & set(by_name)
    orphans = sorted(disk_names - set(by_name))
    dead_links = [r for fn, r in by_name.items()
                  if fn not in disk_names and r.get("in_library")]
    memory = sum(1 for r in rows if r.get("library_status") == "memory")
    return {"present": len(present), "orphans": orphans,
            "dead_links": dead_links, "memory": memory}


def verify_classify(computed: str | None, stored: str | None) -> str:
    """Classify a re-hashed Library file against its backup-time hash.

    ``unhashed`` means there is no reference hash to check against (the set was
    never backed up), so a mismatch cannot be asserted — it is not an error.
    """
    if not stored:
        return "unhashed"
    return "ok" if computed == stored else "mismatch"
