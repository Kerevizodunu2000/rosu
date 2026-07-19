<div align="center">

<img src="rosu/assets/icon.png" width="128" alt="Rosu" />

<h1>Rosu</h1>

<p>
  <b>A desktop manager for osu! beatmap-pack archives</b><br/>
  unpack&nbsp;·&nbsp;dedupe&nbsp;·&nbsp;track&nbsp;gaps&nbsp;·&nbsp;back&nbsp;up&nbsp;·&nbsp;import&nbsp;straight&nbsp;into&nbsp;osu!
</p>

<p><sub><i>rose&nbsp;+&nbsp;osu!</i></sub></p>

<p>
  <a href="https://github.com/Kerevizodunu2000/rosu/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/Kerevizodunu2000/rosu?label=release&labelColor=2b2b2b&color=ff66aa"></a>
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
- A dedicated **Shortcuts** tab with an installed-music summary (osu!lazer / osu!(stable) / Library / Drive set counts) and one-tap actions: **transfer** sets between osu!lazer ↔ osu!(stable) (skipping what the target already has), **save** an installed client straight into the Library, **unpack Packs and import** to either/both clients (with a skip-duplicates choice), **export** {Library | Drive-backed | a client | all-merged} to **zip/7z** (single or split into 1 GB / 500 MB volumes, with optional **★≥ / ★≤** star bounds on Library sets, optionally uploaded to Drive with a shareable link), and **dedupe** the Library (preview + confirm, Recycle Bin). Long operations are cancellable and show live progress in the job queue.

**Cloud backup (Google Drive)**
- **Back up your Library to Google Drive** — log in once (loopback OAuth + PKCE, the minimal `drive.file` scope so Rosu only ever sees the files it creates). New `.osz` are uploaded incrementally as fixed-size, append-only chunk archives; re-running uploads only what's new. A pre-backup dialog previews the new-set count and total size and lets you cap how many sets to send this run and pick the chunk size — including an **Individual (one file per set)** mode.
- **Location tracking** — Rosu records which Drive chunk holds each backed-up set, and the Search table shows where every map lives: 🎮 osu!lazer · 🕹️ osu!(stable) · 💾 Library · ☁️ Drive.
- Optionally, a processed pack archive can be **uploaded to Drive and removed locally** right after unpacking, to reclaim disk space.
- The OAuth refresh token is stored in the **OS keyring** (Windows Credential Manager), never in `config.json`.

**Know what's gone**
- **Lost-map detection** (optional; needs osu! API credentials): flags owned beatmapsets that no longer exist on osu! — deleted or taken down — so you know what's already unrecoverable. Rosu is the only pack-level archiver that surfaces this.

**Search, metadata & reporting**
- Relevance-ranked **Music Search** (tokenized AND on artist/title/name; optional tag/mapper search) with per-difficulty **Star** and **Keys** columns, a **Skill** column for mania (overall + dominant skillset, e.g. `5.42 CJ`), and location badges (🎮 lazer · 🕹️ stable · 💾 Library · ☁️ Drive).
- **Query-syntax filters** — combine free text with `star>5`, `mode=mania`, `key=7`, `bpm>=180`, `length=4:03`, `status=ranked`, `artist=`/`mapper=`/`name=`, and CS/AR/OD/HP bounds; diff-level filters must match on the *same* difficulty.
- **Visual Filters panel** — a collapsible Search sidebar with a dual-handle star slider, ruleset toggles (disabled when you own no maps of that mode), mania key picker, and BPM/length/AR/OD fields; writes the query syntax for you.
- **Map Details** (double-click a result) — every difficulty's mode, keys, star, CS·AR·OD·HP, and (for mania) a **skillset radar**; plus osu!-API metadata when enriched.
- **Star histogram** (Search → Distribution) — click/drag a range, double-click to search it, or **Export this range** straight into Shortcuts.
- **Rosu Skillset Rating (mania)** — a local, offline heuristic across Etterna's seven skillsets + overall (not an Etterna port; swappable). Rated at unpack/refresh; whole-Library rescan from Settings. Packs: double-click a present pack for its average mania radar.
- **Local star ratings** via **rosu-pp-py** (pinned, import-guarded) for every difficulty; optional **osu!-API metadata enrichment** (ranked status, dates, play/favourite counts, genre, language) from Settings.
- Browsable **Artists** tab with sortable aggregates (avg. star, length, BPM) and an instant filter box.
- Auto-generated **Excel report** (`data/tracking.xlsx`) with per-category sheets, an Artists sheet, and a Summary — confirmed-red rows only.
- One-click cell copy, Ctrl+C for a full TSV of the selection, and right-click "Copy names".

**Library health & settings**
- **Library Health** (Settings) — read-only disk-usage total + biggest sets, a DB↔disk scrub (orphans / dead links / memory-only), and a cancellable off-thread **SHA-256 verify** against backup-time hashes.
- Per-client **enable/disable** toggles (lazer on, stable off by default) — a disabled client vanishes app-wide (Settings path row, Dashboard import, Shortcuts).
- **Save ⇄ Auto-Save** for Settings; **Report a problem** posts to the hosted form (with e-mail / web-form fallback).
- Optional startup **update check** against GitHub Releases with a one-click download banner (on by default, fails silently offline).

**Shortcuts job queue**
- Long Shortcuts actions run as queued **jobs** with named sub-steps, live status, per-item cancel, and **DISK/DRIVE concurrency** (a disk export can run while a Drive upload proceeds). Double-click an archive row to reveal it in the file manager.

**Safety & robustness**
- Archive extraction is hardened against path traversal (drive-relative/ADS entry names) and zip-bomb/disk-exhaustion (size caps before unpacking).
- Guarded, countdown-confirmed deletions before removing physical Library copies.
- Crash-safe report writes (a locked `tracking.xlsx` no longer aborts an import) and clean shutdown of background workers.
- **Folder self-heal**: if the app's own folder is moved or renamed, it detects the mismatch on launch and offers (with confirmation) to re-point to wherever `Library/`/`data/`/`logs/` actually live.

**Customization**
- 12 built-in themes (see [Themes](#themes)); toggles in Settings apply immediately in Auto-Save mode.
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

> **First run — the "Windows protected your PC" / "unknown publisher" screen is expected.** Because Rosu is a new, independently-built app that isn't code-signed with a (paid) certificate, **Windows SmartScreen** warns the first time you run it. This is normal for small open-source apps — it means *"Windows doesn't recognize this yet,"* **not** *"this is malware."* To run it: click **More info** → **Run anyway** (Turkish: *Ek bilgi* → *Yine de çalıştır*). You'll only see it once on that PC. Rosu is [GPL-3.0 open source](LICENSE) and every release ships a **`.sha256` checksum** so you can verify your download is untampered. (The warning goes away over time as more people run the app, and fully disappears if the project is ever code-signed — see [Build the exe](#build-the-exe).)

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

**Shipped through v1.6:** public essentials (v1.0) · Library Health & disk insight (v1.1) · Shortcuts tab
(v1.2) · job queue (v1.3) · Settings overhaul + hosted bug report (v1.4) · per-difficulty star ratings,
query-syntax search & osu!-API enrichment (v1.5) · mania skillset ratings, visual Filters panel & star-range
export (v1.6).

**Next on the Library Maturity line:** space-saving (prune heavy assets from `.osz` files), audio-fingerprint
dedup, and deeper browsing UX — then the v2.0 capstone. Later lines add a music player, collections, sync
hardening, an AI coach, streamer overlays, and cross-platform builds (macOS/Linux).

Extra numbered pack series (ST/SC/T/L/P/A and beyond) are already auto-supported by the gap-detection logic as
they appear.

See [`CHANGELOG.md`](CHANGELOG.md) for the full, version-by-version history.

## Community & support

- **Website** — **<https://rosu-web.vercel.app>**
- **Report a bug or request a feature** — from inside the app (**Settings → Report a problem**), or fill in the form at **<https://rosu-web.vercel.app/report>** (title + description + an optional screenshot). Prefer e-mail? **rosu.app@gmail.com**. GitHub users can also [open an issue](https://github.com/Kerevizodunu2000/rosu/issues).
- **Security issues** — please report privately; see [SECURITY.md](SECURITY.md).
- **Follow Rosu:**
  - Instagram — <https://www.instagram.com/rosu.app/>
  - YouTube — <https://www.youtube.com/@RosuApp>
  - Reddit — <https://www.reddit.com/user/RosuApp/>
  - X (Twitter) — <https://x.com/RosuApp>

## License

Rosu is free software, licensed under the **[GNU General Public License v3.0 or later](LICENSE)**.

Copyright © 2026 Halil Şafak Şimşek.

**Contact:** rosu.app@gmail.com

Rosu is distributed in the hope that it will be useful, but **WITHOUT ANY WARRANTY** — see the [GNU GPL v3](LICENSE) for details. Bundled third-party components keep their own licenses; see [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md). The same notices are available in-app via **Settings → About / Licenses**.

Rosu is an unofficial, fan-made tool — not affiliated with or endorsed by ppy Pty Ltd or osu!. "osu!" is used descriptively; the "Rosu" name and glyphs are the author's own.
