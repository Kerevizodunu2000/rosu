# Changelog

All notable changes to **Rosu** (osu! beatmap archive manager) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> Note: version control (git) was introduced at **v0.2.0**. The v0.1.0 entry below is
> documented from the shipped state and run logs (v0.1.0 first ran 2026-07-12), even
> though no source snapshot predates the first commit.

## [Unreleased]

Roadmap for v0.6.0 → v0.8.0 is tracked in
`docs/superpowers/specs/2026-07-13-osu-archiver-v0.3-to-v0.8-roadmap-design.md`.

## [0.5.0] — 2026-07-13

The app has a name and an identity: **Rosu** (rose + osu!).

### Added
- **New theme "Pink · Darker" (item 23)** — deeper than Pink · Dark, near-black with
  a rose undertone. 12 themes total.
- **Icon design system (item 19)**: 20 icon concepts + 20 geometric-rose variations
  designed and archived under `docs/icons/`; `assets/icon_lab.py` generates them all
  and finalises the chosen one to `.png/.ico/splash`. The winner is a geometric rose
  (white facets on osu! pink).

### Changed
- **Renamed to Rosu**: app title, window title, splash wordmark, exe name
  (`rosu.exe`, built from `rosu.spec`) and the app icon are all Rosu now. (The Python
  package stays `osu_archiver` internally.)
- **Pink · Light is clearly pink (item 2)**: its surfaces are pink-tinted instead of
  the White theme's pure white, so the two no longer look alike.

## [0.4.0] — 2026-07-13

Search & tables: the search no longer freezes, the library is browsable, and the
tables are more useful.

### Fixed
- **Search freeze (item 10)**: typing a common word (e.g. "hardcore") froze the app.
  Root cause was an N+1 query — one JOIN per candidate row to attach its source
  packs, on every keystroke. Now sources are attached in one bulk query to only the
  displayed rows, the search runs off the UI thread, and keystrokes are debounced
  (~250 ms). Searching "hardcore" over 1225 tracks dropped from a freeze to ~2 ms.

### Added
- **Browse the whole library (item 11)**: an empty search box now lists every track,
  name-sorted, so the library is browsable without typing.
- **Double-click a cell to copy just that field (item 3)** — id, source, BPM, etc.
- **Right-click → "Copy names"** copies the selected rows' names, one per line — a
  reliable way to grab a multi-selection's names, distinct from Ctrl+C's full TSV
  (item 13).
- **Dashboard "possibly missing" is now a link (item 12)** → jumps to the Packs tab
  filtered to only the missing rows (new "Only missing" toggle there).
- **Artist sort options (item 14)**: longest/shortest average length and
  highest/lowest average BPM, plus new Avg length / Avg BPM columns.

### Changed
- **Code & Mode filled for red missing rows (item 8)**: a missing Standard pack row
  now shows its Code (series+number, e.g. `S1821`) and Mode (from the series), so
  those columns aren't blank.
- **Column sizing (item 22)**: table columns size once (name stretches, the rest
  auto-fit), sampling ~50 rows so auto-fit stays cheap even when browsing everything.

## [0.3.0] — 2026-07-13

Critical fixes: the app no longer breaks when its folder is moved, and several
buttons/settings now behave as users expect.

### Added
- **Folder self-heal (item 20)**: on launch the app validates its working folders
  and, if it was moved/renamed, compares how much data sits at the configured path
  vs. the folder next to the exe and offers to re-point to wherever the real data
  is — with a confirmation dialog. Recovers Library/data/logs after a move,
  preserves a Library deliberately kept on another drive, and never silently
  recreates empty folders at a dead path. New pure `pathheal` module + 6 tests.
- **Empty-Packs helper (item 4)**: pressing "Unpack Archives" with an empty `Packs/`
  now explains the situation and offers a **native file picker** to import archives
  from anywhere (copies them into `Packs/`, then unpacks). Native on Windows/macOS.

### Changed
- **Settings toggles apply immediately (item 6)**: checkboxes (incl. "Auto-copy to
  Library after unpacking") now take effect the moment you toggle them, like
  Language/Theme — no separate Save press needed. Fixes auto-copy silently not
  running because the box was checked but never saved.
- **Friendlier empty/error states (item 5)**: "Copy to Library" and "Open Excel/
  log_formats" now show a clear message when there's nothing to act on / the file
  isn't generated yet, instead of doing nothing.

### Removed
- **"Clear Output after importing to osu!" option (item 7)**: removed from Settings
  and config — osu! consumes the `.osz` on import, so Output empties itself.

### Verified
- BPM/length/mapper metadata is fully populated for all 1225 library tracks via
  "Refresh Library Data" (item 9 — working as designed, no code change).

## [0.2.0] — 2026-07-13

Second release. Categories, confidence-aware "missing" detection, richer UI, and metadata.

### Added
- **Pack categories** (Standard / Featured / Spotlights / Theme / Artist / Loved / Tournament /
  Other) with an `.osu`-derived category system and DB schema v2 (additive migrations).
- **Confidence-aware red rows**: interior numeric gaps flagged red only for gaplessly-numbered
  Standard series; other categories are list-only offline. Optional osu! API reference makes red
  100% accurate for every category.
- **osu! API v2 client** (`osu_api.py`): client-credentials grant, `scope=public`, fetches the
  authoritative pack list to `data/reference.json` (opt-in via Settings client id/secret).
- **`.osu` metadata** read from inside each `.osz`: BPM, length, mapper/creator, mode, source, tags.
- **Artists tab**: per-artist aggregates.
- **Relevance-ranked search** (exact > prefix > word > substring, rapidfuzz tiebreak) with rich,
  responsive columns and full-archive-name copy.
- **Packs search + filter**.
- **Excel report**: per-category sheets + Artists + Summary (confirmed-red only).
- **Copy UX**: single-click a cell → clean name; Ctrl+C → TSV of selected rows.
- **11 themes** (Dark, White, Pink, Pink-Light, Pink-Dark, Nord, Dracula, Catppuccin Mocha/Latte,
  Solarized Dark/Light) generated from palettes for consistent header/selection contrast.
- **Import to osu!**: confirmation dialog (count/batches/ETA), cancel support.
- **Auto-backup-after-extract** setting.
- **"o!" monogram icon + splash** (pink concept).
- Robust extraction: malformed names fall back to "Unknown" and read the real artist/title from
  the `.osu`; extraction never crashes (try/except + WARN).

### Changed
- Renamed the primary action button to **"Unpack Archives"**.
- Progress panel now reports 0→100 with per-archive and per-`.osz` detail.

## [0.1.0] — 2026-07-12

Initial release. The core archive-management pipeline.

### Added
- **Core pipeline**: scan `Packs/` for incoming `.zip` → **Unpack** to `Output/` as flat `.osz` →
  record to `data/memory.db` + regenerate `data/tracking.xlsx` → dispose zips (Recycle Bin) →
  **Copy to Library** (dedup into `Library/`) → **Import to osu!** (batched `osu!.exe` launches).
- **Dedup by beatmapset id** (numeric filename prefix); duplicates increment `copy_attempts`,
  never create `01/02` copies.
- **Refresh Library Data**: re-scan `Library/`, mark disappeared files, backfill metadata.
- **Re-add detection** dialog when a previously seen pack reappears.
- **SQLite** store (`data/memory.db`, schema v1): packs, tracks, track_sources.
- **Structured logging** with ACTION codes + generated `logs/log_formats.md`.
- **Excel tracking report** (openpyxl).
- **PySide6/Qt6 desktop UI** with six tabs: Dashboard, Search, Artists, Packs, Logs, Settings.
- **EN/TR** localization; English-only code/logs.
- Single-file **PyInstaller** build (`osu-archiver.spec`) + GitHub Actions build workflow.

[Unreleased]: https://github.com/Kerevizodunu2000/rosu/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.5.0
[0.4.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.4.0
[0.3.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.3.0
[0.2.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.2.0
[0.1.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.1.0
