# osu! Archive Manager — Handoff

> Read this first in a fresh session to know exactly where we are. Full design/spec lives in
> `C:\Users\halil\.claude\plans\imdi-benim-elimde-birka-floofy-rose.md` (v0.1 + v0.2 sections).
> Persistent memory: `C:\Users\halil\.claude\projects\C--Desktop-Osu\memory\` (index in `MEMORY.md`).

## 1. What this is

A **Windows desktop app** (Python 3.13 + **PySide6/Qt6** + **SQLite**) that manages the user's
osu! beatmap pack archives. Location: **`C:\Desktop\Osu`**. Ships as a single **PyInstaller `.exe`**
(no install for end users). Will be published on **GitHub, versioned**. macOS is a future goal
(Qt is cross-platform; add a macOS CI job later — no code rewrite).

**Status: v0.5.0 shipped and verified. The app is now named "Rosu" (rose + osu!).**
Location **`C:\Desktop\osu_archiver\`** (self-heals stale paths — item 20). Runnable exe:
**`C:\Desktop\osu_archiver\rosu.exe`** (built from `rosu.spec`; `--version`→`0.5.0`, `--selftest`→OK).
Icon = geometric rose (white facets on osu! pink); `assets/icon_lab.py` regenerates it.
Python package stays `osu_archiver` internally. GitHub: **github.com/Kerevizodunu2000/rosu** (private).

> **Roadmap & design of record (v0.3→v0.8):**
> `docs/superpowers/specs/2026-07-13-osu-archiver-v0.3-to-v0.8-roadmap-design.md`.
> Version history: `CHANGELOG.md`. Repo under **git**, tags `v0.2.0`…`v0.5.0` pushed.
> **Done:** v0.3 (items 20,4,5,6,7,9) · v0.4 (10,11,3,13,22,8,12,14) · v0.5 (2,23,19+rebrand).
> **Next:** v0.6 (16,17,18,24,25) → v0.7 auto-import (15) → v0.8 Drive (11) → final report (26).
> Commits must NOT add a Claude co-author trailer (user wants only their name in Contributors).

UI language: **EN default + TR** (Settings). All background/code/logs are **English only**.

## 2. Core flow

`Packs/` (incoming `.zip`) → **Unpack Archives** button → `Output/` (flat `.osz`) → record to
`data/memory.db` + regenerate `data/tracking.xlsx` + move zips to Recycle Bin → **Copy to Library**
(dedup into `Library/`) → **Import to osu!** (batched `osu!.exe` CLI/IPC). **Refresh Library Data**
re-scans `Library/`, backfills metadata, marks disappeared files.

## 3. File / module map

```
osu_archiver/
  app.py          bootstrap: AppContext (cfg/db/log/i18n/services), theme, window icon, splash
  config.py       Config dataclass, config.json load/save, THEMES tuple, detect_osu_exe()
  logsvc.py       structured logging + ACTION codes + writes logs/log_formats.md
  models.py       dataclasses + category constants + CONFIDENT_GAP_CATEGORIES + MODE_NAMES
  parsing.py      PURE: pack name → series/number/category; .osz entry → id/artist/title (Unknown fallback)
  osz_meta.py     read BPM/length/mapper/mode/source/tags from .osu files inside an .osz (best-effort)
  gaps.py         PURE: confidence-aware red rows (Standard confident; others need reference)
  db.py           SQLite repo (schema v2 + migrations), packs/tracks/track_sources, artists, search_candidates
  search.py       PURE: relevance ranking (exact>prefix>word>substring + rapidfuzz tiebreak)
  osu_api.py      optional osu! API v2 client → data/reference.json (authoritative pack list)
  extractor.py    scan Packs/, prescan (re-add detection), extract flat + read metadata + dispose zip
  library.py      Output→Library dedup copy; refresh (present/disappeared + metadata backfill)
  excel_report.py openpyxl: per-category sheets + Artists + Summary; only confirmed-red
  osu_import.py   batch osu!.exe launches, cancel support, ETA estimate
  services.py     orchestration (no Qt): extract/copy/import/refresh/search/artists/reference/gaps
  theming.py      11 theme palettes → generated QSS (fixes header + selection contrast)
  i18n.py         EN/TR string tables + human_duration()
  workers.py      Worker(QThread): progressed(object)/succeeded/failed
  ui/ main_window dashboard_tab search_tab artists_tab packs_tab logs_tab settings_tab
       copy_table.py (click=clean name, Ctrl+C=TSV, SortItem numeric sort)  progress_panel.py
  assets/ make_icon.py → icon.ico/png + splash.png  (concept D "o!" monogram, pink)
tests/ test_parsing test_gaps test_search   (25 passing)
run.py  requirements.txt  requirements-dev.txt  osu-archiver.spec  .github/workflows/build.yml
```

Working dirs (created next to the exe/repo, configurable in Settings):
`Packs/ Output/ Library/ Processed/ data/ logs/ config.json`.

## 4. Data model (SQLite `data/memory.db`, schema v2)

- **packs**: id, code(UNIQUE), series, number, **category**, full_name, title, mode, season, year,
  track_count, extracted_at, source_zip, status. (series/number NULL for "Other"/unofficial packs.)
- **tracks**: id, beatmapset_id(UNIQUE), filename, artist, title, display_name, **creator, source,
  tags, bpm, length_seconds, mode, diff_count**, first_seen_at, last_seen_at, copy_attempts,
  in_library, library_status(present/disappeared/memory), status_changed_at, size_bytes.
- **track_sources**: track_id, pack_id, subfolder, seen_at (N:N pack↔track; subfolder e.g. `osu!mania/`).
- Migrations are additive (ALTER ADD COLUMN); `_backfill_category()` fills category from series on init.

## 5. Key design decisions (the non-obvious ones)

- **Dedup key = beatmapset id** (numeric filename prefix). Same Artist-Title, different id = different
  song (kept separate). Duplicate → `copy_attempts++`, never a `01/02` copy file.
- **"Red only when genuinely missing"** (the crucial one): osu numbers **Standard (S/SM/ST/SC)**
  gaplessly, so an interior numeric gap is a real missing pack → red offline. **All other categories**
  (Featured/Spotlights/Theme/Artist/Loved/Tournament/Other) are **list-only** offline (no guessed red),
  because their numbers are unreliable (Spotlights share numbers across game modes). With the optional
  **osu! API reference**, red becomes 100% accurate for every category (validated against the real list,
  windowed to owned number range + collected modes). Logic in `gaps.build_rows` / `services.series_rows`.
- **Metadata** parsed from `.osu` inside each `.osz`; also rescues malformed names (no `" - "` →
  artist "Unknown", read real artist/title from `.osu`). Never crashes extraction (try/except + WARN).
- **osu! import is slow because of osu! itself** (serial import + per-map star-difficulty calc), not our
  code. We only improved UX: confirm dialog (count/batches/ETA) + cancel + fast subsequent batches.
- **Themes generated from palettes** (`theming.py`) not per-file QSS — guarantees consistent, fixed
  **header** (light) and **selected-row** (accent + contrast) styling across all 11 themes.
- **Copy behaviour**: single-click a table cell → copies the clean name (missing row → its code);
  Ctrl+C → TSV of selected rows (full archive names for the Sources column).

## 6. Feature status — all 17 v0.2 items DONE

Rename button→"Unpack Archives"(1); 0→100 progress panel w/ archive+osz(2); auto-backup-after-extract
setting(3); category system + confidence red + Other + reference sync(4); selection+header theme
fixes(5,7,10); click/Ctrl+C copy(5.1); 11 themes incl Pink·Light/Dark, Nord, Dracula, Catppuccin,
Solarized(6); rich responsive search columns + full-name copy(8); Packs search+filter(9); Excel category
sheets + Artists(11); relevance-ranked search(12); **Artists tab**(13); import confirm/cancel/ETA(14);
"o!" monogram icon+splash(15); malformed→Unknown(16); `.osu` metadata BPM/len/mapper/mode(17).
v0.1 base (extract/dedup/library/refresh/re-add dialog/logs/Excel) all intact.

## 7. User's REAL data state (important)

The user ran the app last session, so: **`Library/` has 1146 `.osz` (~11GB)**, `Packs/`+`Output/` empty,
zips are in the Recycle Bin, `data/memory.db` has 57 packs / 1146 tracks (migrated to v2, category
backfilled). Confirmed-missing shows correctly: **only S1821 and SM363** (no false Featured/Spotlight red).
**Those 1146 tracks have no metadata yet** (imported pre-v0.2) → user should click **"Refresh Library
Data"** once to backfill BPM/length/mapper (reads all 1146 `.osz`, ~1–2 min; idempotent afterwards).

## 8. Pending / next steps (nothing blocking)

- **Metadata backfill**: user clicks "Refresh Library Data" once (see §7).
- **osu! API reference** (optional): user registers an OAuth app at osu.ppy.sh/home/account/edit →
  pastes client_id/secret in Settings → "Update reference". Then Spotlight/Featured red becomes accurate.
  `osu_api.py` implemented but **not yet tested against the live API** (needs the user's credentials).
- **Icon revision** (see [[osu-archiver-icon-todo]]): redo with osu!'s official palette; keep A(rose)+D,
  explore more variants. Regenerate via `python -m osu_archiver.assets.make_icon`.
- **macOS**: add a macos-latest job to `.github/workflows/build.yml` when wanted.
- Possible polish: live-search debounce/logging noise; per-tab reference caching.

## 9. Run / build / test

```bash
# run from source
pip install -r requirements-dev.txt        # PySide6, openpyxl, Send2Trash, rapidfuzz, pytest, pyinstaller
python run.py
# tests (25 passing)
python -m pytest tests/ -q
# build the single exe (icon + assets bundled via osu-archiver.spec)
pyinstaller osu-archiver.spec               # → dist/osu-archiver.exe
python -m osu_archiver.assets.make_icon     # regenerate icon/splash if changed
```
The end user just double-clicks **`C:\Desktop\Osu\osu-archiver.exe`** (place it beside a `Packs/` folder).

## 10. Environment gotchas

- Python is **Microsoft Store Python 3.13**; pip installs go to `--user`. `PyInstaller` and `rapidfuzz`
  were installed separately (a bundled `pip install pyinstaller` had silently failed once — verify with
  `python -m PyInstaller --version`).
- Shell is Git Bash; run the exe with `MSYS_NO_PATHCONV=1 ./osu-archiver.exe ...`. Qt headless smoke:
  `QT_QPA_PLATFORM=offscreen` (text renders as □ tofu offscreen — cosmetic, real desktop is fine).
- `osu!lazer` exe auto-detected at `%LOCALAPPDATA%/osulazer/current/osu!.exe`.
- No `.git` yet — user will push to GitHub; `.gitignore` already excludes data folders + build output.

## 11. Verification done

25 unit tests pass (parsing categories/robustness, gaps confidence + reference, search ranking).
Headless end-to-end pipeline passes (categories, confident red, real `.osz` metadata, malformed→Unknown,
search, artists). Real-archive extract validated (valid `.osz`, subfolder flatten, Japanese/special chars).
Headless GUI smoke: all 6 tabs, 11 themes, TR/EN switch. Frozen exe `--selftest` OK. Pink theme rendered
to PNG confirming header=light + selection=strong accent. Verified on the user's real 1146-track DB.

## 12. How the user works (see [[user-prefers-batched-questions]])

Wants thorough upfront planning; batch clarifying questions (AskUserQuestion) rather than one at a time.
Keep researching/verifying instead of asserting from memory. Communicates in Turkish; UI-facing replies
in Turkish are welcome.
