# SPDX-License-Identifier: GPL-3.0-or-later
"""Audio fingerprints (v1.10) — Qt-free.

Finds the same song across different beatmap sets: re-encodes, re-uploads,
TV-size cuts. Each set's audio is summarised by Chromaprint's ``fpcalc`` (an
LGPL tool bundled with the app; see ``THIRD-PARTY-LICENSES.md``) into a "raw"
fingerprint — one 32-bit value per ~0.124 s of sound. Two recordings of the
same song share long runs of near-identical values, so:

* candidates come from an inverted index of 20-bit value prefixes (cheap, and
  it scales to thousands of sets without comparing every pair);
* each candidate pair is then aligned by its most common offset and scored by
  the share of matching bits over the overlap (``1 - bit error rate``).

Nothing here deletes anything: callers get groups and decide.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ITEM_SECONDS = 0.1238            # one raw value per 4096/3 samples at 11025 Hz
FP_SECONDS = 120                 # how much of each song is fingerprinted
MIN_OVERLAP = 80                 # ~10 s of aligned sound before a score counts
SAME_SONG = 0.85                 # 1 - bit error rate; unrelated audio sits near 0.5
_KEY_SHIFT = 12                  # 20-bit prefixes for the index and alignment
_INDEX_ITEMS = 480               # index the first ~60 s …
_INDEX_STEP = 2                  # … every second value
_MIN_SHARED = 8                  # index hits before a pair is worth scoring
_COMMON = 200                    # a prefix shared by this many sets says nothing


# --- fpcalc ----------------------------------------------------------------------
def fpcalc_path() -> Path | None:
    """The bundled ``fpcalc`` (frozen build or ``rosu/assets/fpcalc``), else one
    on PATH; None when there is none."""
    name = "fpcalc.exe" if sys.platform == "win32" else "fpcalc"
    roots = [Path(__file__).resolve().parent / "assets" / "fpcalc"]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.insert(0, Path(meipass) / "rosu" / "assets" / "fpcalc")
    for root in roots:
        if (root / name).is_file():
            return root / name
    found = shutil.which("fpcalc")
    return Path(found) if found else None


def parse_fpcalc(text: str) -> tuple[float, list[int]] | None:
    """``fpcalc -json -raw`` output → ``(duration_seconds, values)``."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    fp = data.get("fingerprint") if isinstance(data, dict) else None
    if not isinstance(fp, list) or not fp:
        return None
    try:
        values = [int(v) & 0xFFFFFFFF for v in fp]
        duration = float(data.get("duration") or 0.0)
    except (TypeError, ValueError):
        return None
    return duration, values


class ToolError(Exception):
    """fpcalc could not be run, or did not finish (blocked, missing, timed
    out): nothing is known about the audio, so the attempt is not remembered."""


_FORMATS = {".mp3": "mp3", ".ogg": "ogg", ".wav": "wav", ".flac": "flac"}


def _run(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise ToolError(str(exc)[:200]) from exc


def probe(fpcalc: Path, timeout: float = 20) -> bool:
    """Whether ``fpcalc`` starts and answers at all (an antivirus block, a
    damaged or wrong-architecture binary all fail here, once, up front)."""
    try:
        proc = _run([str(fpcalc), "-version"], timeout)
    except ToolError:
        return False
    return proc.returncode == 0 and "fpcalc" in (proc.stdout + proc.stderr).lower()


def compute(audio: Path, fpcalc: Path, timeout: float = 60) -> tuple[float, list[int]] | None:
    """Fingerprint one audio file: None when fpcalc ran but could not read it
    (worth remembering); :class:`ToolError` when fpcalc itself failed."""
    args = [str(fpcalc), "-json", "-raw", "-length", str(FP_SECONDS)]
    fmt = _FORMATS.get(Path(audio).suffix.lower())
    if fmt:   # decode as what the set says it is, never as whatever it sniffs
        args += ["-format", fmt]
    proc = _run(args + [str(audio)], timeout)
    return parse_fpcalc(proc.stdout) if proc.returncode == 0 else None


# --- storage ---------------------------------------------------------------------
def pack(values: list[int]) -> bytes:
    from array import array
    a = array("I", values)
    if sys.byteorder != "little":
        a.byteswap()
    return a.tobytes()


def unpack(blob: bytes):
    """The stored values as a compact ``array("I")`` (indexes and slices like a
    list, at a tenth of the memory — a big Library holds many of these)."""
    from array import array
    a = array("I")
    a.frombytes(blob[: len(blob) - len(blob) % a.itemsize])
    if sys.byteorder != "little":
        a.byteswap()
    return a


# --- comparison --------------------------------------------------------------------
def match(a: list[int], b: list[int], min_overlap: int = MIN_OVERLAP) -> tuple[float, int]:
    """``(score, offset)``: the share of equal bits where ``b`` lines up best
    against ``a`` (``b[i]`` ~ ``a[i + offset]``); ``(0.0, 0)`` when they never
    overlap enough to judge."""
    if not a or not b:
        return 0.0, 0
    where: dict[int, list[int]] = defaultdict(list)
    for i, v in enumerate(a):
        bucket = where[v >> _KEY_SHIFT]
        if len(bucket) < 8:
            bucket.append(i)
    offsets: Counter = Counter()
    for j, v in enumerate(b):
        for i in where.get(v >> _KEY_SHIFT, ()):
            offsets[i - j] += 1
    best = (0.0, 0)
    for off, _n in offsets.most_common(3) or [(0, 0)]:
        lo, hi = max(0, -off), min(len(b), len(a) - off)
        n = hi - lo
        if n < min_overlap:
            continue
        errors = sum((a[j + off] ^ b[j]).bit_count() for j in range(lo, hi))
        score = 1.0 - errors / (32.0 * n)
        if score > best[0]:
            best = (score, off)
    return best


def same_song_groups(fps: dict, threshold: float = SAME_SONG) -> list[list]:
    """Groups (2+ members, by key) of fingerprints that are the same song.

    ``fps`` maps any key (a track id) to its raw values. Candidates are found
    through an inverted index of value prefixes, scored with :func:`match`,
    and joined transitively. Candidates are counted one set at a time, so the
    memory stays proportional to the Library, not to the number of pairs."""
    keys = list(fps)
    order = {k: i for i, k in enumerate(keys)}
    index: dict[int, list] = defaultdict(list)
    prefixes: dict = {}
    for key in keys:
        own = {v >> _KEY_SHIFT for v in fps[key][:_INDEX_ITEMS:_INDEX_STEP]}
        prefixes[key] = own
        for k in own:
            index[k].append(key)
    parent = {k: k for k in keys}

    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for x in keys:
        shared: Counter = Counter()
        for k in prefixes[x]:
            members = index[k]
            if 2 <= len(members) <= _COMMON:
                for y in members:
                    if order[y] > order[x]:
                        shared[y] += 1
        for y, n in shared.items():
            if n < _MIN_SHARED or root(x) == root(y):
                continue
            if match(fps[x], fps[y])[0] >= threshold:
                parent[root(y)] = root(x)
    groups: dict = defaultdict(list)
    for k in keys:
        groups[root(k)].append(k)
    return sorted((sorted(g, key=str) for g in groups.values() if len(g) > 1),
                  key=lambda g: str(g[0]))


def cpu_budget() -> int:
    """Worker count for fingerprinting many files (leave the UI a core)."""
    return max(1, min(4, (os.cpu_count() or 2) - 1))
