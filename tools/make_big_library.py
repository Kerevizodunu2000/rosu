# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate a synthetic Rosu library for profiling (see tools/profile_library.py).

    python tools/make_big_library.py TARGET [--n 100000] [--seed 0] [--force]

Writes, under TARGET (stdlib only, no network):

* ``Library/``  N ``<id> <Artist> - <Title>.osz`` sets, 2-4 difficulties each,
  plus a tiny ``audio.wav``;
* ``Packs/``    a few ``S<number> - Rosu Perf Pack #<number>.zip`` archives that
  together hold about 1% of N further sets (ids not used in the Library);
* ``Output/``   empty;
* ``.rosu-perf-library``  a marker. The profiler only runs on a folder that has it,
  and ``--force`` only clears a non-empty folder that has it.

The same ``--n`` and ``--seed`` give byte-identical files (fixed zip timestamps,
fixed member order, one seeded generator per set).
"""
from __future__ import annotations

import argparse
import io
import math
import random
import shutil
import sys
import time
import wave
import zipfile
from pathlib import Path

MARKER = ".rosu-perf-library"
_ZIP_DATE = (2020, 1, 1, 0, 0, 0)

ARTISTS = ["Neon", "Crystal", "Velvet", "Hollow", "Lunar", "Solar", "Echo", "Pixel",
           "Aurora", "Cobalt", "Ember", "Static", "Glass", "Violet", "Marble", "Nova",
           "Rusty", "Silver", "Midnight", "Paper", "Distant", "Gentle", "Wild", "Frozen"]
ARTIST_TAILS = ["Garden", "Project", "Club", "Orchestra", "Wave", "Society", "Machine",
                "Parade", "Union", "Collective", "Radio", "Factory"]
TITLE_WORDS = ["Dream", "Storm", "Harbor", "Signal", "Mirror", "Thunder", "Whisper",
               "Gravity", "Horizon", "Voyage", "Silence", "Carnival", "Lantern", "Orbit",
               "River", "Eclipse", "Shadow", "Summer", "Winter", "Circuit", "Garden",
               "Memory", "Falling", "Rising", "Endless", "Broken", "Golden", "Hidden"]
TAGS = ["stream", "jump", "farm", "tech", "speed", "vocal", "anime", "rock", "electronic",
        "piano", "classical", "marathon", "chill", "hardcore", "tv size", "remix"]
CREATORS = [f"Mapper{i:02d}" for i in range(40)]
SOURCES = ["", "", "", "Rhythm Game", "Visual Novel", "Anime Opening", "Film"]
DIFF_NAMES = ["Easy", "Normal", "Hard", "Insane", "Expert"]
# (mode number, weight): mostly standard and mania, some taiko and catch.
MODES = [(0, 60), (3, 25), (1, 8), (2, 7)]


def _tones(rnd: random.Random, count: int = 16) -> list[bytes]:
    """A pool of short tone WAVs (4 s, 4 kHz, 8-bit mono), built once per run."""
    pool = []
    for _ in range(count):
        f1, f2 = rnd.uniform(220, 880), rnd.uniform(220, 880)
        frames = bytes(
            int(128 + 60 * math.sin(2 * math.pi * f1 * i / 4000)
                + 60 * math.sin(2 * math.pi * f2 * i / 4000))
            for i in range(4000 * 4))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(1)
            w.setframerate(4000)
            w.writeframes(frames)
        pool.append(buf.getvalue())
    return pool


def _hit_objects(rnd: random.Random, mode: int, keys: int, level: int) -> list[str]:
    n = rnd.randint(80, 160) + level * 20
    step = max(90, 480 - level * 70)
    t = 1000
    lines = []
    for _ in range(n):
        t += rnd.randint(step // 2, step * 3 // 2)
        if mode == 3:
            col = rnd.randrange(keys)
            x = col * 512 // keys + 256 // keys
            if rnd.random() < 0.2:
                lines.append(f"{x},192,{t},128,0,{t + rnd.randint(150, 600)}:0:0:0:0:")
            else:
                lines.append(f"{x},192,{t},1,0,0:0:0:0:")
        elif mode == 1:
            lines.append(f"256,192,{t},1,{rnd.choice((0, 0, 8))},0:0:0:0:")
        elif mode == 2:
            lines.append(f"{rnd.randint(0, 512)},192,{t},1,0,0:0:0:0:")
        elif rnd.random() < 0.2:
            x, y = rnd.randint(0, 400), rnd.randint(0, 384)
            lines.append(f"{x},{y},{t},2,0,L|{x + 100}:{y},1,100")
        else:
            lines.append(f"{rnd.randint(0, 512)},{rnd.randint(0, 384)},{t},1,0,0:0:0:0:")
    return lines


def _osu(rnd: random.Random, set_id: int, artist: str, title: str, mode: int, keys: int,
         level: int, tags: str, creator: str, source: str) -> str:
    cs = keys if mode == 3 else rnd.choice((3, 4, 4, 5))
    ar = min(10, 3 + level * 1.5 + rnd.random())
    od = min(10, 3 + level * 1.5 + rnd.random())
    return "\n".join([
        "osu file format v14", "",
        "[General]", "AudioFilename: audio.wav", "AudioLeadIn: 0", f"Mode: {mode}", "",
        "[Editor]", "DistanceSpacing: 1", "BeatDivisor: 4", "GridSize: 4", "",
        "[Metadata]", f"Title:{title}", f"TitleUnicode:{title}", f"Artist:{artist}",
        f"ArtistUnicode:{artist}", f"Creator:{creator}", f"Version:{DIFF_NAMES[level]}",
        f"Source:{source}", f"Tags:{tags}", "BeatmapID:0", f"BeatmapSetID:{set_id}", "",
        "[Difficulty]", f"HPDrainRate:{round(4 + level, 1)}", f"CircleSize:{cs}",
        f"OverallDifficulty:{od:.1f}", f"ApproachRate:{ar:.1f}", "SliderMultiplier:1.4",
        "SliderTickRate:1", "",
        "[Events]", "",
        "[TimingPoints]", f"0,{rnd.choice((300, 333.33, 375, 428.57, 500))},4,2,0,60,1,0", "",
        "[HitObjects]", *_hit_objects(rnd, mode, keys, level), ""])


def _zinfo(name: str, method: int) -> zipfile.ZipInfo:
    zi = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
    zi.compress_type = method
    zi.external_attr = 0o644 << 16
    return zi


def make_set(seed: int, index: int, set_id: int, tones: list[bytes]) -> tuple[str, bytes]:
    """One ``.osz``: ``(filename, bytes)``. Depends only on (seed, index, set_id)."""
    rnd = random.Random(f"{seed}:{index}")
    artist = rnd.choice(ARTISTS)
    if rnd.random() < 0.5:
        artist += " " + rnd.choice(ARTIST_TAILS)
    title = " ".join(rnd.choice(TITLE_WORDS) for _ in range(rnd.randint(1, 3)))
    mode = rnd.choices([m for m, _ in MODES], [w for _, w in MODES])[0]
    keys = rnd.choice((4, 5, 6, 7, 8))
    tags = " ".join(rnd.sample(TAGS, rnd.randint(2, 5)))
    creator, source = rnd.choice(CREATORS), rnd.choice(SOURCES)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for level in range(rnd.randint(2, 4)):
            text = _osu(rnd, set_id, artist, title, mode, keys, level, tags, creator, source)
            name = f"{artist} - {title} ({creator}) [{DIFF_NAMES[level]}].osu"
            zf.writestr(_zinfo(name, zipfile.ZIP_DEFLATED), text)
        zf.writestr(_zinfo("audio.wav", zipfile.ZIP_DEFLATED), rnd.choice(tones))
    return f"{set_id} {artist} - {title}.osz", buf.getvalue()


def _clear(target: Path) -> None:
    for child in target.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def generate(target: Path, n: int, seed: int, force: bool) -> str | None:
    """Write the library. Returns an error message (nothing written) or None."""
    if target.exists() and not target.is_dir():
        return f"{target} is not a folder"
    if target.is_dir() and any(target.iterdir()):
        if not force:
            return f"{target} is not empty (use --force to regenerate a generated folder)"
        if not (target / MARKER).is_file():
            return f"{target} is not empty and has no {MARKER} marker: refusing to clear it"
        _clear(target)
    for sub in ("Library", "Packs", "Output"):
        (target / sub).mkdir(parents=True, exist_ok=True)

    pack_sets = max(4, round(n / 100))
    packs = max(2, pack_sets // 100)
    total = n + pack_sets
    ids = random.Random(seed).sample(range(1000, 1000 + 8 * total), total)
    tones = _tones(random.Random(seed))

    for i in range(n):
        name, data = make_set(seed, i, ids[i], tones)
        (target / "Library" / name).write_bytes(data)
        if (i + 1) % 10000 == 0:
            print(f"  library {i + 1}/{n}", flush=True)

    index, per, extra = n, pack_sets // packs, pack_sets % packs
    for p in range(packs):
        number = 1001 + p
        count = per + (1 if p < extra else 0)
        zip_name = f"S{number} - Rosu Perf Pack #{number}.zip"
        with zipfile.ZipFile(target / "Packs" / zip_name, "w") as zf:
            for _ in range(count):
                name, data = make_set(seed, index, ids[index], tones)
                zf.writestr(_zinfo(name, zipfile.ZIP_STORED), data)
                index += 1
    (target / MARKER).write_text(f"rosu perf library\nn={n}\nseed={seed}\n", encoding="utf-8")
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a synthetic Rosu library.")
    ap.add_argument("target", type=Path)
    ap.add_argument("--n", type=int, default=100000, help="Library sets (default 100000)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--force", action="store_true",
                    help="clear and regenerate a folder that has the generator's marker")
    args = ap.parse_args(argv)
    if args.n < 1:
        ap.error("--n must be at least 1")
    start = time.perf_counter()
    err = generate(args.target, args.n, args.seed, args.force)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    print(f"Generated {args.n} sets in {args.target} in {time.perf_counter() - start:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
