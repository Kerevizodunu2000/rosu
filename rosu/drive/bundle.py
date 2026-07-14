# SPDX-License-Identifier: GPL-3.0-or-later
"""Bundle .osz beatmap sets into fixed-size, append-only chunk archives (v0.8).

Uploading thousands of tiny .osz one-by-one to Drive is slow, so we pack them
into ``chunk-NNNN.zip`` archives (stored, not recompressed — .osz are already
zips). Chunks are immutable and append-only: new/changed tracks always go into a
*new* chunk; existing chunks are never rewritten. The manifest records which
chunk holds each track.

Filesystem-touching but dependency-free (stdlib zipfile/hashlib); unit-tested by
building real files under tmp_path.
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Iterable

_CHUNK_RE = re.compile(r"-(\d+)\.zip$", re.IGNORECASE)
_HASH_BUF = 1024 * 1024


def chunk_name(index: int, device_id: str) -> str:
    """Per-device chunk archive name. The device id keeps chunk names unique in
    the shared Drive folder, so two installs (or a lost local cache) can never
    write two different ``chunk-0000.zip`` files that collide by name."""
    return f"chunk-{device_id}-{index:04d}.zip"


def parse_chunk_index(name: str) -> int | None:
    m = _CHUNK_RE.search(str(name).replace("\\", "/"))
    return int(m.group(1)) if m else None


def next_chunk_index(manifest: dict) -> int:
    """One past the highest chunk index referenced by the manifest (0 if empty)."""
    highest = -1
    for entry in manifest.values():
        if not isinstance(entry, dict):
            continue
        idx = parse_chunk_index(entry.get("chunk", ""))
        if idx is not None and idx > highest:
            highest = idx
    return highest + 1


def plan_chunks(items: Iterable[dict], chunk_bytes: int,
                start_index: int, device_id: str) -> list[dict]:
    """Greedily group ``items`` (each a dict with a ``size``) into chunks whose
    total stays under ``chunk_bytes``.

    A single item larger than ``chunk_bytes`` gets its own chunk (an .osz can't
    be split). Chunk names are per-device (see :func:`chunk_name`). Returns
    ``[{"index", "name", "items": [...]}, ...]``.
    """
    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be positive")
    chunks: list[dict] = []
    cur: list[dict] = []
    cur_size = 0
    idx = start_index
    for it in items:
        size = int(it["size"])
        if cur and cur_size + size > chunk_bytes:
            chunks.append({"index": idx, "name": chunk_name(idx, device_id),
                           "items": cur})
            idx += 1
            cur, cur_size = [], 0
        cur.append(it)
        cur_size += size
    if cur:
        chunks.append({"index": idx, "name": chunk_name(idx, device_id),
                       "items": cur})
    return chunks


def sha256_file(path: Path) -> str:
    """SHA-256 of a file, streamed in fixed buffers (large .osz safe)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(_HASH_BUF), b""):
            h.update(block)
    return h.hexdigest()


def write_chunk(members: Iterable[Path], out_path: Path) -> Path:
    """Zip ``members`` (flattened to basenames) into ``out_path`` atomically.

    Uses ZIP_STORED (the .osz are already compressed) and writes to a ``.part``
    file first, replacing the target only on full success — never leaves a
    half-written chunk.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".part")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            for m in members:
                m = Path(m)
                z.write(m, arcname=m.name)
        tmp.replace(out_path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return out_path
