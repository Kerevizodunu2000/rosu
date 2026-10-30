# Performance baseline: a 100,000-set library

This is the "measure" step of the measure-then-Rust rule (AGENTS.md, **Rust**;
`.claude/skills/rust/SKILL.md` section 1). It profiles Rosu's Qt-free service
layer on a generated library of 100,000 sets and names the slowest paths. No app
code was changed.

## Setup

| | |
|---|---|
| Machine | Intel Xeon @ 2.30 GHz, 4 cores, 15.7 GB RAM (a shared cloud container; other jobs ran on it at the same time, so absolute times are noisy) |
| OS | Linux 6.18.44 (x86_64, glibc 2.39) |
| Python | 3.13.16 |
| rosu-pp-py | 4.0.2 |
| Library sets (N) | 100000 (the full size; nothing was reduced) |
| Sample | 1000 (export, read_metadata and the fingerprint sample root) |
| Pack sets | 1000 sets in 10 pack zips (extract uses all of them) |
| Generation time | 119.9 s, 2.1 GB for the Library and Packs (2.3 GB after profiling) |
| Total profiling time | about 73 minutes, almost all of it `refresh` |

Commands (`$LIB` is a scratch folder outside the repo):

```bash
python3 tools/make_big_library.py $LIB --n 100000 --seed 0
python3 tools/profile_library.py $LIB --json result.json --markdown result.md
```

The tables below are the profiler's `--markdown` output. Read the numbers with
these limits in mind:

- **Every path ran once with cProfile and tracemalloc on, so the wall times
  include that overhead.** Python-heavy code (parsing, loops) is slowed more than
  native code and SQLite, so use the numbers to rank paths, not as absolute speeds.
- tracemalloc counts Python allocations only (not SQLite or rosu-pp memory), and
  cProfile sees only the calling thread.
- The top-10 lists leave out the profiler script's own frames.
- The generated maps are small (80 to 220 hit objects per difficulty, 2 to 4
  difficulties, a 4-second WAV). Real maps are usually bigger, so the per-set
  parse and MSD costs here are probably lower than on a real library. The shares
  between functions are what carries over.
- `startup` is a reopen of the 100,000-set database after `refresh`.
  `fingerprint` was skipped: `fpcalc` is not installed on this machine, so the
  path is not measured (the tool reports `skipped` with the reason).
- `extract` ran with `zip_disposal = "move"` and `clear_output_before_extract =
  False`, so no file left the target folder (see the profiler's docstring).

## Results

### Summary

| Path | Status | Wall time | Peak memory | Detail |
|---|---|---|---|---|
| startup | ok | 0.00 s | 0.0 MiB | {"reopened_after_refresh": true, "sets": 100000} |
| refresh | ok | 4321.75 s | 296.9 MiB | {"added": 100000, "disappeared": 0, "enriched": 0, "present": 100000} |
| search | ok | 8.32 s | 104.1 MiB | [{"query": "(all)", "tags": false, "rows": 5000, "total": 100000, "wall_s": 0.6825}, {"query": "artist=Neon", "tags": false, "rows": 4088, "total": 4088, "wall_s": 0.7126}, {"query": "title=Dream", "tags": false, "rows": 5000, "total": 6899, "wall_s": 0.7978}, {"query": "farm", "tags": true, "rows": 5000, "total": 20000, "wall_s": 4.5265}, {"query": "star>4", "tags": false, "rows": 5000, "total": 60030, "wall_s": 1.4221}] |
| prescan | ok | 0.34 s | 19.0 MiB | {"packs": 10, "kinds": {"new": 10}} |
| extract | ok | 36.05 s | 0.8 MiB | {"packs": 10, "tracks": 1000, "loose": 0, "rejected": 0} |
| export | ok | 6.27 s | 97.9 MiB | {"count": 1000, "archives": 1} |
| read_metadata | ok | 31.92 s | 0.2 MiB | {"sets": 1000, "difficulties": 3003} |
| fingerprint | skipped | - | - | "fpcalc not found" |

### startup: top 10 by cumulative time

| Function | Calls | Cumulative time |
|---|---|---|
| `db.py:188(__init__)` | 1 | 0.002 s |
| `db.py:205(_init_schema)` | 1 | 0.001 s |
| `~:0(<method 'commit' of 'sqlite3.Connection' objects>)` | 1 | 0.001 s |
| `_local.py:227(__str__)` | 22 | 0.001 s |
| `_local.py:289(drive)` | 14 | 0.001 s |
| `config.py:177(_fill_defaults)` | 1 | 0.001 s |
| `~:0(<method 'execute' of 'sqlite3.Connection' objects>)` | 8 | 0.001 s |
| `_local.py:257(_parse_path)` | 13 | 0.001 s |
| `_local.py:717(mkdir)` | 7 | 0.001 s |
| `config.py:160(ensure_dirs)` | 1 | 0.001 s |

### refresh: top 10 by cumulative time

| Function | Calls | Cumulative time |
|---|---|---|
| `library_svc.py:64(refresh)` | 1 | 4321.752 s |
| `library.py:156(refresh_library)` | 1 | 4321.472 s |
| `msd.py:201(msd_for_diffs)` | 100000 | 1736.538 s |
| `msd.py:132(skillset)` | 74048 | 1416.484 s |
| `beatmap.py:235(read_osz_full)` | 100000 | 1414.996 s |
| `beatmap.py:61(parse_osu_sections)` | 400015 | 1258.024 s |
| `beatmap.py:147(read_osu_diff)` | 300015 | 994.702 s |
| `~:0(<method 'execute' of 'sqlite3.Connection' objects>)` | 974055 | 807.585 s |
| `db.py:844(find_track_row)` | 100000 | 778.546 s |
| `msd.py:86(_score_window)` | 15468052 | 599.816 s |

### search: top 10 by cumulative time

| Function | Calls | Cumulative time |
|---|---|---|
| `metadata_svc.py:423(search_page)` | 5 | 7.527 s |
| `search.py:165(search_counted)` | 4 | 6.691 s |
| `search.py:130(rank_all)` | 1 | 2.368 s |
| `db.py:1142(attach_difficulties_bulk)` | 5 | 2.314 s |
| `~:0(<method 'fetchall' of 'sqlite3.Cursor' objects>)` | 64 | 1.838 s |
| `search.py:90(_strong_score)` | 20000 | 1.350 s |
| `db.py:912(search_candidates)` | 1 | 1.202 s |
| `~:0(<method 'execute' of 'sqlite3.Connection' objects>)` | 67 | 0.860 s |
| `search.py:70(_token_strength)` | 20000 | 0.715 s |
| `db.py:1039(filtered_tracks)` | 3 | 0.631 s |

### prescan: top 10 by cumulative time

| Function | Calls | Cumulative time |
|---|---|---|
| `extract_svc.py:39(prescan_all)` | 1 | 0.318 s |
| `db.py:417(known_track_ids)` | 1 | 0.209 s |
| `~:0(<method 'fetchall' of 'sqlite3.Cursor' objects>)` | 1 | 0.158 s |
| `extractor.py:50(prescan_pack)` | 10 | 0.104 s |
| `extractor.py:39(read_osz_entries)` | 10 | 0.102 s |
| `archives.py:240(open_reader)` | 10 | 0.070 s |
| `archives.py:210(__init__)` | 10 | 0.070 s |
| `archives.py:115(__init__)` | 10 | 0.069 s |
| `__init__.py:1375(__init__)` | 10 | 0.069 s |
| `__init__.py:1491(_RealGetContents)` | 10 | 0.067 s |

### extract: top 10 by cumulative time

| Function | Calls | Cumulative time |
|---|---|---|
| `extract_svc.py:54(extract)` | 1 | 36.046 s |
| `extractor.py:76(extract_pack)` | 10 | 35.574 s |
| `msd.py:201(msd_for_diffs)` | 1000 | 17.087 s |
| `beatmap.py:235(read_osz_full)` | 1000 | 14.088 s |
| `msd.py:132(skillset)` | 743 | 13.944 s |
| `beatmap.py:61(parse_osu_sections)` | 4013 | 12.650 s |
| `beatmap.py:147(read_osu_diff)` | 3013 | 10.016 s |
| `msd.py:86(_score_window)` | 154117 | 5.901 s |
| `~:0(<method 'split' of 'str' objects>)` | 692942 | 4.332 s |
| `~:0(<method 'append' of 'list' objects>)` | 1948705 | 3.095 s |

### export: top 10 by cumulative time

| Function | Calls | Cumulative time |
|---|---|---|
| `export_svc.py:21(export_sets)` | 1 | 6.258 s |
| `export_svc.py:67(_gather_export_sources)` | 1 | 4.842 s |
| `export_svc.py:88(lib_files)` | 1 | 4.842 s |
| `~:0(<built-in method builtins.sorted>)` | 1 | 4.842 s |
| `_local.py:207(__lt__)` | 1532161 | 2.822 s |
| `_local.py:198(_parts_normcase)` | 3064322 | 1.592 s |
| `_local.py:252(_from_parsed_string)` | 100003 | 1.163 s |
| `_abc.py:130(with_segments)` | 100006 | 1.129 s |
| `_local.py:498(__init__)` | 102010 | 0.972 s |
| `_local.py:117(__init__)` | 102010 | 0.827 s |

### read_metadata: top 10 by cumulative time

| Function | Calls | Cumulative time |
|---|---|---|
| `msd.py:201(msd_for_diffs)` | 1000 | 18.071 s |
| `msd.py:132(skillset)` | 820 | 14.760 s |
| `beatmap.py:235(read_osz_full)` | 1000 | 13.195 s |
| `beatmap.py:61(parse_osu_sections)` | 4003 | 11.775 s |
| `beatmap.py:147(read_osu_diff)` | 3003 | 9.290 s |
| `msd.py:86(_score_window)` | 171307 | 6.347 s |
| `~:0(<method 'split' of 'str' objects>)` | 695845 | 3.938 s |
| `~:0(<method 'append' of 'list' objects>)` | 2144899 | 3.309 s |
| `beatmap.py:179(read_mania_notes)` | 820 | 3.110 s |
| `beatmap.py:129(fill_track_meta)` | 1000 | 2.631 s |

## Slowest paths and what to do

By measured wall time the three slowest paths are `refresh` (4321.75 s),
`extract` (36.05 s) and `read_metadata` (31.92 s). Per set that is 43 ms, 36 ms and
32 ms: all three run the same per-set loop, `read_osz_full` then
`ratings.stars_for_diffs` then `msd.msd_for_diffs`, so the one cost is measured
three times. The verdicts follow section 1 of `.claude/skills/rust/SKILL.md`:
cheap Python fixes first, then port a whole loop, not the body of one.

### 1. refresh: Python fix first

`refresh` at N = 100000 takes 72 minutes. Of the 4321.75 s:

- `find_track_row` is 778.5 s (18%) in 100,000 calls, about 7.8 ms each. For a set
  the database does not know yet it falls back to `SELECT * FROM tracks WHERE
  filename=?`, and `tracks.filename` has no index (`beatmapset_id` does), so
  SQLite scans the whole table every time. The cost grows with the square of N.
- `msd_for_diffs` is 1736.5 s (40%) and `read_osz_full` is 1415.0 s (33%). These
  are the per-set loop shared with extract and read_metadata (below).
- `parse_osu_sections` runs 400,015 times for 300,015 difficulties: the
  representative `.osu` is parsed again in `fill_track_meta`, and mania notes are
  read again from the raw text in `read_mania_notes`.

Fix: add an index on `tracks(filename)` (a migration in `rosu/db.py`) and pass the
already-parsed result of the representative `.osu` into `fill_track_meta` instead of
parsing it a second time. Both are small Python changes and DB access is a poor
candidate for Rust, so this is where the skill says to start. Re-profile after it:
most of what is left is the per-set loop, which is item 2.

### 2. extract: Rust module

`extract` over 1000 pack sets takes 36.05 s (36 ms per set). `extract_pack`'s
time is `msd_for_diffs` 17.1 s (47%) and `read_osz_full` 14.1 s (39%); the file
copy and the database writes are small next to them. Both are pure-Python text
parsing and window loops over every difficulty of every set, and there are no
cheap fixes left in them (`parse_osu_sections` and `_score_window` are already
single-pass).

Move the whole loop, not the functions: one native call that takes a list of
`.osz` paths and returns, per set, the `TrackMeta`, the `DiffMeta` rows and the MSD
results (open the zip, parse every `.osu`, read the mania notes, run the skillset
windows). Star ratings stay with `rosu-pp-py`. The service keeps doing the database
writes. Build it as the skill describes: a PyO3 module under `native/`, a
pure-Python fallback (today's code), parity tests on the same inputs, and a
benchmark in `tools/` that quotes Python against Rust on this library. If it is not
clearly faster, do not merge it. Do this after the fixes in item 1, so the Rust
module replaces what is still slow.

### 3. read_metadata: Rust module (the same module as item 2)

`read_metadata` over 1000 sets takes 31.92 s (32 ms per set): `msd_for_diffs`
18.1 s (57%) and `read_osz_full` 13.2 s (41%). It is the same loop as item 2 with
nothing else in it, so the one native batch function serves both, and `refresh`
too once item 1 is done. It is not a separate port.

### The other paths: leave as is, or a small Python fix

- `search` (8.32 s for 5 queries; 0.68 to 1.42 s each, but 4.53 s for the
  `farm` query with `search_tags=True`, 2.4 s of it in `rank_all` over 20,000
  candidates): leave as is for now. Every query returns a page of 5000 at most;
  capping the candidates for a tag search would be a Python fix if it becomes a
  complaint.
- `export` (6.27 s): 4.84 s of it is `sorted()` over 100,003 `Path` objects in
  `_gather_export_sources`. Sorting by name string, or not sorting before the
  sample, is a Python fix; no Rust.
- `prescan` (0.34 s), `startup` (3.7 ms): leave as is.
- `fingerprint`: not measured here (no `fpcalc`). It needs a run on a machine that
  has it before any verdict.

Each recommendation above becomes its own issue; none is done in this change.

## Profiled vs unprofiled

Items 2 and 3 were acted on in #30. A Rust (PyO3) module was built for the `.osu`
parse and the skillset windows, with a Python fallback and parity tests. It was
measured with `tools/profile_library.py` both with the profiler and with
`--no-profile` (wall time only). The library had N = 10,000 sets with a sample of
1,000, was regenerated before each run, and the four runs went back to back on the
machine above:

| Path | Python, `--no-profile` | Rust, `--no-profile` | Speed-up | Python, profiler | Rust, profiler | Speed-up |
|---|---|---|---|---|---|---|
| read_metadata | 1.60 s | 0.90 s | 1.78x | 32.44 s | 2.09 s | 15.5x |
| extract | 0.40 s | 0.40 s | 1.00x | 3.32 s | 0.61 s | 5.4x |
| refresh | 34.77 s | 24.98 s | 1.39x | 348.54 s | 41.34 s | 8.4x |

cProfile inflated the pure-Python cost about 10x: refresh took 348.54 s profiled
and 34.77 s unprofiled. So parse and MSD looked like nearly all of these paths,
when unprofiled they are only part of them:

- `read_metadata`: rosu-pp star ratings take about 0.50 s per 1,000 sets, and zip
  reading plus MD5 about 0.18 s.
- `extract`: mostly archive extraction, star ratings and database writes.

The module made parse and MSD about 10x faster, but it missed the 2x bar on
`read_metadata` and `extract` without the profiler. It did not merge and is kept on
the branch
[`parked/rust-osu-core`](https://github.com/Kerevizodunu2000/rosu/tree/parked/rust-osu-core).
Revisit it when an unprofiled measurement shows parse/MSD dominating a path users
wait on. The likelier next candidates are star ratings and zip read + MD5.

**Rule for future measurements:** report the unprofiled wall time
(`--no-profile`) next to any profile, and base a Rust decision on the unprofiled
share.
