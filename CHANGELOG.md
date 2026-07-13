# Changelog

All notable changes to **osu! Archive Manager** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> Note: version control (git) was introduced at **v0.2.0**. The v0.1.0 entry below is
> documented from the shipped state and run logs (v0.1.0 first ran 2026-07-12), even
> though no source snapshot predates the first commit.

## [Unreleased]

Roadmap for v0.3.0 → v0.8.0 is tracked in
`docs/superpowers/specs/2026-07-13-osu-archiver-v0.3-to-v0.8-roadmap-design.md`.

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

[Unreleased]: https://example.invalid/compare/v0.2.0...HEAD
[0.2.0]: https://example.invalid/releases/tag/v0.2.0
[0.1.0]: https://example.invalid/releases/tag/v0.1.0
