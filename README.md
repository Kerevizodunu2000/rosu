<div align="center">

<img src="rosu/assets/icon.png" width="128" alt="Rosu" />

<h1>Rosu</h1>

<p>
  <b>A desktop manager for osu! beatmap-pack archives</b><br/>
  unpack&nbsp;·&nbsp;dedupe&nbsp;·&nbsp;track&nbsp;gaps&nbsp;·&nbsp;back&nbsp;up&nbsp;·&nbsp;import&nbsp;straight&nbsp;into&nbsp;osu!
</p>

<p><sub><i>rose&nbsp;+&nbsp;osu!</i></sub></p>

<p>
  <a href="https://github.com/Kerevizodunu2000/rosu/releases"><img alt="Latest release" src="https://img.shields.io/badge/release-v1.0.0-ff66aa?labelColor=2b2b2b"></a>
  <a href="LICENSE"><img alt="License: GPL-3.0-or-later" src="https://img.shields.io/badge/license-GPL--3.0--or--later-ff66aa?labelColor=2b2b2b"></a>
  <img alt="Platform: Windows" src="https://img.shields.io/badge/platform-Windows-ff66aa?labelColor=2b2b2b&logo=windows&logoColor=white">
  <img alt="Python 3.13" src="https://img.shields.io/badge/python-3.13-ff66aa?labelColor=2b2b2b&logo=python&logoColor=white">
  <img alt="Built with PySide6" src="https://img.shields.io/badge/built%20with-PySide6-ff66aa?labelColor=2b2b2b&logo=qt&logoColor=white">
</p>

<p>
  <a href="#features">Features</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#gap-detection">Gap detection</a> ·
  <a href="#installation">Install</a> ·
  <a href="#themes">Themes</a> ·
  <a href="#build-the-exe">Build</a> ·
  <a href="#license">License</a>
</p>

</div>

Rosu bulk-extracts `.zip`/`.7z`/`.tar` beatmap packs into a deduplicated `.osz` library, tracks everything — including **where each map lives** (osu!, your Library, the cloud) — in a local SQLite database, flags real gaps in numbered pack series in an Excel report, and imports the results into **either osu! client** with one click. It can also pull beatmaps you've already installed straight into the library, **back the whole library up to your Google Drive**, and flag maps that no longer exist on osu!.

> **Note:** background logic, code, and logs are English by design. Only the user-facing UI is localized (English/Turkish, switchable in Settings).

## Features

**Archive pipeline**
- Reads and counts every archive dropped into `Packs/` — **.zip, .7z, .tar (.gz/.bz2/.xz)**.
- Extracts everything into a flat `Output/` folder, flattening Spotlight-style `osu!/` / `osu!mania/` subfolders while still recording their original source.
- Archives that also contain non-music files (readmes, images…) are flagged, with a dedicated "with extra files" filter in the Packs tab.
- Detects and asks before re-processing a pack that's already been seen (fully vs. partially imported).
- Processed `.zip`/`.7z`/`.tar` files move to the Recycle Bin, never a permanent delete.

**Library & import**
- **Copy to Library** deduplicates `.osz` files by beatmapset id into a permanent `Library/` backup; re-uploads with a different size are refreshed instead of skipped.
- **Import to osu!** sends `Output/`'s `.osz` files to your osu! client in batches through osu!'s own safe import pipeline — with separate **osu!lazer** and **osu!(stable)** targets, progress, cancel support, and a reminder not to close osu! mid-import.
- **Import already-installed songs** (Settings): pulls beatmaps straight from an existing **osu!(stable)** `Songs/` folder or an **osu!lazer** install (via a bundled, self-contained .NET 8 helper that reads `client.realm` read-only — no .NET install required) and dedupes them into the Library.
- **Refresh Library Data** rescans `Library/`, backfills metadata, and timestamps files that have disappeared instead of silently dropping them.

**Shortcuts (one-click flows)**
- A dedicated **Shortcuts** tab with an installed-music summary (osu!lazer / osu!(stable) / Library / Drive set counts) and one-tap actions: **transfer** sets between osu!lazer ↔ osu!(stable) (skipping what the target already has), **save** an installed client straight into the Library, **unpack Packs and import** to either/both clients (with a skip-duplicates choice), **export** {Library | Drive-backed | a client | all-merged} to **zip/7z** (single or split into 1 GB / 500 MB volumes, optionally uploaded to Drive with a shareable link), and **dedupe** the Library (preview + confirm, Recycle Bin). Long operations are cancellable.

**Cloud backup (Google Drive)**
- **Back up your Library to Google Drive** — log in once (loopback OAuth + PKCE, the minimal `drive.file` scope so Rosu only ever sees the files it creates). New `.osz` are uploaded incrementally as fixed-size, append-only chunk archives; re-running uploads only what's new. A pre-backup dialog previews the new-set count and total size and lets you cap how many sets to send this run and pick the chunk size — including an **Individual (one file per set)** mode.
- **Location tracking** — Rosu records which Drive chunk holds each backed-up set, and the Search table shows where every map lives: 🎮 osu!lazer · 🕹️ osu!(stable) · 💾 Library · ☁️ Drive.
- Optionally, a processed pack archive can be **uploaded to Drive and removed locally** right after unpacking, to reclaim disk space.
- The OAuth refresh token is stored in the **OS keyring** (Windows Credential Manager), never in `config.json`.

**Know what's gone**
- **Lost-map detection** (optional; needs osu! API credentials): flags owned beatmapsets that no longer exist on osu! — deleted or taken down — so you know what's already unrecoverable. Rosu is the only pack-level archiver that surfaces this.

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
- Optional startup **update check** against GitHub Releases with a one-click download banner (on by default, fails silently offline).

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
4. Click **Import → osu!lazer** or **Import → osu!(stable)** to hand them off to your osu! client.
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
Processed/    Archives moved aside after unpacking (when that disposal mode is chosen)
Quarantine/   Rejected hostile archives (zip-bomb / path-traversal), never auto-deleted
data/         memory.db (SQLite — single source of truth) + tracking.xlsx + Drive cache
logs/         app-YYYY-MM-DD.log + log_formats.md
config.json   Application settings (osu! API key kept here; Drive token in the OS keyring)
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

Rosu 1.0 is the first public release. Beyond it, the focus is:

- **Deeper library tooling** — richer per-map metadata (star rating / ranked status / dates) from the osu! API, partial-pack detection, and collection management.
- **Cross-platform** — macOS and Linux from the same Python codebase, packaged via PyInstaller.
- **More UI languages and themes.**

Extra numbered pack series (ST/SC/T/L/P/A and beyond) are already auto-supported by the gap-detection logic as they appear.

See [`CHANGELOG.md`](CHANGELOG.md) for the full, version-by-version history.

## License

Rosu is free software, licensed under the **[GNU General Public License v3.0 or later](LICENSE)**.

Copyright © 2026 Halil Şafak Şimşek.

**Contact:** halilsafaksimsek@gmail.com

Rosu is distributed in the hope that it will be useful, but **WITHOUT ANY WARRANTY** — see the [GNU GPL v3](LICENSE) for details. Bundled third-party components keep their own licenses; see [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md). The same notices are available in-app via **Settings → About / Licenses**.

Rosu is an unofficial, fan-made tool — not affiliated with or endorsed by ppy Pty Ltd or osu!. "osu!" is used descriptively; the "Rosu" name and glyphs are the author's own.
