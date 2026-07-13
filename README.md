# Rosu 🌹

**A desktop manager for osu! beatmap-pack archives — unpack, dedupe, track gaps, and import straight into osu!.**
*(Rosu = **rose** + **osu!**)*

![Latest release](https://img.shields.io/github/v/release/Kerevizodunu2000/rosu)
![License](https://img.shields.io/github/license/Kerevizodunu2000/rosu)
![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white)
![Built with PySide6](https://img.shields.io/badge/built%20with-PySide6-41CD52?logo=qt&logoColor=white)

Rosu bulk-extracts `.zip`/`.7z`/`.tar` beatmap packs into a deduplicated `.osz` library, tracks everything in a local SQLite database, flags real gaps in numbered pack series in an Excel report, and imports the results into osu! with one click — or pulls beatmaps you've already installed straight into that library.

> **Note:** background logic, code, and logs are English by design. Only the user-facing UI is localized (English/Turkish, switchable in Settings).

## Table of Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [How it works](#how-it-works)
- [Gap detection](#gap-detection)
- [Installation](#installation)
- [Usage](#usage)
- [Themes](#themes)
- [Folder layout](#folder-layout)
- [Run from source](#run-from-source)
- [Build the exe](#build-the-exe)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [License](#license)

## Features

**Archive pipeline**
- Reads and counts every archive dropped into `Packs/` — **.zip, .7z, .tar (.gz/.bz2/.xz)**.
- Extracts everything into a flat `Output/` folder, flattening Spotlight-style `osu!/` / `osu!mania/` subfolders while still recording their original source.
- Archives that also contain non-music files (readmes, images…) are flagged, with a dedicated "with extra files" filter in the Packs tab.
- Detects and asks before re-processing a pack that's already been seen (fully vs. partially imported).
- Processed `.zip`/`.7z`/`.tar` files move to the Recycle Bin, never a permanent delete.

**Library & import**
- **Copy to Library** deduplicates `.osz` files by beatmapset id into a permanent `Library/` backup; re-uploads with a different size are refreshed instead of skipped.
- **Import to osu!** sends `Output/`'s `.osz` files to osu! in batches through osu!'s own safe import pipeline, with progress, cancel support, and a reminder not to close osu! mid-import.
- **Import already-installed songs** (Settings): pulls beatmaps straight from an existing **osu!(stable)** `Songs/` folder or an **osu!lazer** install (via a bundled, self-contained .NET 8 helper that reads `client.realm` read-only — no .NET install required) and dedupes them into the Library.
- **Refresh Library Data** rescans `Library/`, backfills metadata, and timestamps files that have disappeared instead of silently dropping them.

**Search, metadata & reporting**
- Relevance-ranked **Music Search** (exact > prefix > word > substring, with a fuzzy tiebreak) and a browsable **Artists** tab with sortable aggregates (avg. length, avg. BPM).
- Rich per-track metadata parsed from each `.osz`'s `.osu` files: BPM, length, mapper/creator, mode, source, tags, difficulty count. Malformed names fall back to "Unknown" without breaking the import.
- Auto-generated **Excel report** (`data/tracking.xlsx`) with per-category sheets, an Artists sheet, and a Summary — confirmed-red rows only.
- One-click cell copy, Ctrl+C for a full TSV of the selection, and right-click "Copy names".

**Safety & robustness**
- Archive extraction is hardened against path traversal (drive-relative/ADS entry names) and zip-bomb/disk-exhaustion (size caps before unpacking).
- Guarded, countdown-confirmed deletions before removing physical Library copies.
- Crash-safe report writes (a locked `tracking.xlsx` no longer aborts an import) and clean shutdown of background workers.
- **Folder self-heal**: if the app's own folder is moved or renamed, it detects the mismatch on launch and offers (with confirmation) to re-point to wherever `Library/`/`data/`/`logs/` actually live.

**Customization**
- 12 built-in themes (see [Themes](#themes)); toggles in Settings apply immediately, no save step.
- Mouse-wheel guard on dropdowns so scrolling never silently changes a value.
- English/Turkish UI switch.

## Screenshots

<!-- ![Dashboard](screenshots/dashboard.png) -->
<!-- ![Packs tab](screenshots/packs.png) -->
<!-- ![Search tab](screenshots/search.png) -->
<!-- ![Settings tab](screenshots/settings.png) -->

*Screenshots will be added to `screenshots/` in a future update.*

## How it works

Rosu's pipeline moves beatmaps through four stages:

1. **Packs** — drop `.zip` / `.7z` / `.tar(.gz/.bz2/.xz)` beatmap-pack archives into `Packs/`. Rosu scans and counts them.
2. **Output** — "Unpack Archives" extracts every pack into a flat `Output/` folder as `.osz` files, records each one to the local database, regenerates the Excel report, and recycles the processed archive.
3. **Library** — "Copy to Library" deduplicates `Output/`'s `.osz` files into a permanent `Library/` backup (by beatmapset id; repeat copies just increment a counter instead of creating `01`/`02` duplicates).
4. **osu!** — "Import to osu!" hands `Output/`'s `.osz` files to osu! in batches, which imports them through its own, trusted import pipeline.

Beatmaps you've already installed can skip straight to step 3 via **Settings → Import installed songs**, which reads them out of osu!(stable) or osu!lazer directly.

## Gap detection

Rosu highlights *missing* packs in the Excel report, but only when it can be confident:

- **Standard series (S / SM / ST / SC)**: osu! numbers these gaplessly, so a missing number in the sequence is a genuine gap → shown **red** (e.g. `S1821`, `SM363`). No network access needed.
- **Featured / Spotlights / Theme / Artist / Loved / Tournament / unofficial packs**: these aren't gaplessly numbered, so offline detection can't tell a real gap from an intentional one — they're **listed, never marked red**, to avoid false positives.
- **Optional osu! API reference**: enter an osu! API v2 `client_id` + `client secret` in Settings and run "Update Reference." Rosu fetches the authoritative, published pack list and cross-checks every category (including Spotlights) against it — gap detection becomes **100% accurate** for all pack types, not just Standard.

## Installation

1. Go to the [Releases page](https://github.com/Kerevizodunu2000/rosu/releases).
2. Download the latest `rosu.exe` (or `rosu-<version>.exe`).
3. Run it — no installer, no dependencies. On first launch Rosu creates its working folders next to the executable.

## Usage

1. Drop your beatmap-pack archives into the `Packs/` folder created next to `rosu.exe`.
2. Click **Unpack Archives** to extract them into `Output/` and generate the tracking report.
3. Click **Copy to Library** to back up the extracted `.osz` files into your permanent `Library/`.
4. Click **Import to osu!** to hand them off to your osu! client.
5. Use **Search** to find tracks by artist/title/id, **Artists** to browse aggregates, and **Dashboard** for an at-a-glance summary (including a link straight to any possibly-missing packs).
6. Already have beatmaps installed? Open **Settings → Import installed songs** to pull them from osu!(stable) or osu!lazer without re-downloading anything.

## Themes

12 themes, switchable instantly from the Settings tab:

Dark *(default)*, White, Pink, Pink · Light, Pink · Dark, Pink · Darker, Nord, Dracula, Catppuccin Mocha, Catppuccin Latte, Solarized Dark, Solarized Light.

## Folder layout

```
Packs/        Incoming .zip/.7z/.tar pack archives (input)
Output/       Extracted, flattened .osz files (current batch) — staged for import to osu!
Library/      Permanent, deduplicated .osz backup
data/         memory.db (SQLite — single source of truth) + tracking.xlsx
logs/         app-YYYY-MM-DD.log + log_formats.md
config.json   Application settings
```

## Run from source

```bash
pip install -r requirements.txt
python run.py
```

## Build the exe

Builds a single self-contained `rosu.exe` — end users don't need Python or any dependencies installed.

```bash
pip install -r requirements-dev.txt
pyinstaller rosu.spec
# output: dist/rosu.exe  (rename to rosu-<version>.exe when publishing a release)
```

## Testing

```bash
python -m pytest tests/ -q
```

## Roadmap

- **v0.8**: Google Drive sync for the Library.
- **macOS support**: same Python codebase, packaged as a `.app`/`.dmg` via PyInstaller's macOS runner.
- Additional UI languages and themes.
- Extra pack series are already auto-supported by the gap-detection logic (ST/SC/T/L/P/A and beyond) as they appear.

See [`CHANGELOG.md`](CHANGELOG.md) for the full, version-by-version history.

## License

Released under the [MIT License](LICENSE). Copyright © 2026 Halil Şafak Şimşek.
