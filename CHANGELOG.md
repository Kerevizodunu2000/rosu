# Changelog

All notable changes to **Rosu** (osu! beatmap archive manager) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> Note: version control (git) was introduced at **v0.2.0**. The v0.1.0 entry below is
> documented from the shipped state and run logs (v0.1.0 first ran 2026-07-12), even
> though no source snapshot predates the first commit.

## [Unreleased]

## [1.6.2] - 2026-07-19

**Security & correctness patch** — no new features.

### Security
- **Fixed a denial-of-service in the mania skillset (MSD) scan.** A crafted `.osu`
  with an absurd hit-object timestamp could make the skillset window loop run for
  effectively forever (CPU pinned + out-of-memory) — triggered automatically when
  importing an untrusted pack. Hit-object times are now sanity-bounded when parsed,
  and the window loop is independently hard-capped, so no map can hang the scan.

### Fixed
- **Star-range export no longer drops maps above 12★.** Leaving the `★≤` bound at
  the slider cap now means "no upper bound"; it previously imposed a silent 12★
  ceiling (the histogram's "Export this range" inherited the same limit).
- **The visual Filters panel no longer wipes hand-typed filters.** Adjusting a panel
  control used to keep only free text; it now preserves other typed filters too
  (`status=`, `mapper=`, `cs=`, …), replacing only the fields the panel owns.

## [1.6.1] - 2026-07-19

Documentation patch — no functional changes.

### Changed
- **README** refreshed to document shipped v1.1–v1.6 features: Library Health, Shortcuts job queue,
  per-difficulty star ratings & query-syntax search, mania skillset ratings, the visual Filters panel,
  and star-range export; roadmap updated through v1.6.

### Fixed
- **THIRD-PARTY-LICENSES.md** now lists **rosu-pp-py** (local star-rating engine, v1.5).

## [1.6.0] - 2026-07-19

**Mania skillset ratings + a visual filters panel + star-range export.** Rosu now
estimates *what kind* of mania difficulty each chart is — not just its star — and the
Search tab gains a point-and-click way to filter your Library.

### Added
- **Rosu Skillset Rating (mania)** — a local, offline estimate of each mania
  difficulty across Etterna's seven skillsets (stream, jumpstream, handstream,
  stamina, jackspeed, chordjack, technical) plus an overall, stored per difficulty.
  It is an in-house heuristic (labelled as such, not an Etterna-MSD port) and is
  swappable — a closer algorithm can replace the numbers later with no data migration.
  Pure Python: needs no engine or internet.
  - **Map Details**: a skillset **radar** beside the difficulty table (select a mania
    difficulty to see its breakdown) and a new *Skill* column.
  - **Search**: a *Skill* column showing each set's hardest mania chart's overall +
    dominant skill (e.g. `5.42 CJ`), with a per-difficulty breakdown on hover.
  - **Packs**: double-click a present pack for its **average mania skillset radar**.
  - **Settings → “Compute Skillset Ratings (mania)”** scans the whole Library
    (cancellable, resumable); new maps are rated automatically at unpack / refresh.
- **Visual Filters panel** in Search — a collapsible panel with a **dual-handle star
  slider** + min/max boxes, ruleset toggles (our own glyphs; a ruleset you own no maps
  of is disabled), a mania key-count picker, and BPM / length / AR / OD fields. It
  composes the existing query syntax into the search box, so it doubles as a way to
  learn the syntax. A blank control adds no filter.
- **Export by star range** — the Shortcuts export gains `★≥ / ★≤` bounds (Library
  sets only), and the Search star histogram gains an **“Export this range”** button
  that hands the selection to the export flow.

### Notes
- The skillset heuristic is a first pass calibrated by eye; the numbers are meant to
  rank a chart's skills relative to each other and will be tuned against real charts.
- No new dependency — the skillset engine is pure Python.

## [1.5.0] - 2026-07-19

**Metadata & rosu-pp foundation** — Rosu now knows each map's star rating and every
difficulty's attributes, with a much richer, filterable Search.

### Added
- **Local star ratings** for every difficulty via **rosu-pp-py** (a pinned, compiled
  dependency; import-guarded so the app still runs without it). Computed at unpack /
  "Refresh Library", and for the whole Library from the Search **Distribution** flow.
- **Per-difficulty data**: a new normalized `difficulties` table stores each `.osu`'s
  star, mania key count, CS/AR/OD/HP, mode, difficulty name and MD5 — parsed from
  *every* `.osu` in a set (previously only one representative diff was read).
- **Search — Star & Keys columns**: the Star column lists each difficulty's exact
  star (e.g. `1.05, 2.14, 6.22`), with a per-diff hover breakdown; a Keys column shows
  mania key counts.
- **Map Details dialog** (double-click a result): every difficulty's Difficulty/Mode/
  Keys/Star/CS·AR·OD·HP with sortable, tooltip-explained columns, plus the osu!-API
  metadata (ranked status, dates, play/favourite counts, genre, language).
- **Query-syntax search**: `star>5`, `mode=mania`, `key=7`, `bpm>=180`, `cs`/`ar`/`od`/
  `hp`, `status=ranked`, `length` as `4:03` or seconds, and `artist=`/`mapper=`/`name=`
  (contains) — combinable with free text; diff-level filters must hold on the *same*
  difficulty.
- **Interactive star histogram** (Search → Distribution): click a bar for its count/%,
  drag to select a range, double-click to jump to a Search at that star range.
- **osu!-API metadata enrichment** (opt-in, Settings): ranked status/dates, play &
  favourite counts, genre and language; also refreshes lost-map availability.
- **Artists tab**: average-star column and sort.
- **About**: website link and app-wide "hover a link to see where it goes".

### Changed
- **Library Health** moved from the Dashboard to Settings; **Enrich from osu! API**
  lives in Settings and processes the whole Library in one cancellable run.
- The app now starts **maximized**; About's third-party notices render as formatted
  Markdown instead of raw text.

## [1.4.2] - 2026-07-18

**Mini polish release** on the v1.4.1 Settings commit model.

### Changed
- **A client's path field now hides/shows the moment its Enable box is
  (un)ticked**, even with Auto-Save off — the visual reacts instantly while the
  setting itself still commits on Save (Discard re-ticks the box and the field
  comes straight back). Same for the client's "import installed songs" button
  on the tab.
- **Cleaner client rows**: the separate "osu!lazer executable" / "osu!(stable)
  executable" labels are gone — each client is one row where the **Enable
  osu!lazer / Enable osu!(stable) checkbox is the row's label**, aligned in the
  same column as the other setting names, with the path field + Browse beside
  it (the field describes itself via placeholder text and tooltip).
- **Settings form alignment**: every label — including the new Enable
  checkboxes — is now vertically centered on its field box instead of sitting
  slightly above it.

## [1.4.1] - 2026-07-18

**Bug-fix + polish release** for issues found live-testing v1.4.0.

### Fixed
- **"Auto-Save off" now genuinely means manual.** Checkboxes and the
  processed-zip combo used to apply immediately in BOTH modes; with Auto-Save
  off they now only mark the tab as having unsaved changes ("Unsaved changes —
  press Save."), commit on Save, restore on Discard, and trigger the leave
  guard. In Auto-Save mode everything still applies instantly. (Language/Theme
  stay live in both modes — they're visual pickers; the physical-copy switch
  keeps its own guarded confirm because turning it off deletes files.)
- **Stored osu! API credentials can no longer be wiped.** "Update reference"
  and "Scan for lost maps" used to write the credential fields into the config
  before validating them — a click with empty fields erased saved credentials.
  They now refuse to overwrite stored credentials with empty fields. (If your
  Client ID/Secret vanished, this was the cause — re-enter them once; sorry.)

### Added
- **Packs tab → osu! pack pages**: double-click a red (missing) row to open
  that pack's page at `osu.ppy.sh/beatmaps/packs/<code>`; a single click copies
  the link (Ctrl-select several missing rows to collect all their links, e.g.
  to queue downloads); right-click any pack for an "Open osu! page" action.
- **Report form input checks**: the optional reply e-mail must look like a real
  address (obvious typos are caught before sending); the title is capped at 200
  and the description at 5 000 characters with a live counter (the server's own
  limits, so nothing is silently cut); the attach button states the 3 MB image
  cap; and the dialog now always shows that the same report can be sent from
  <https://rosu-web.vercel.app/report>.

### Changed
- The Dashboard banner says **"Missing:"** when the osu! reference has been
  synced (the gap list is then authoritative) and keeps the cautious
  **"Possibly missing:"** wording otherwise.

## [1.4.0] - 2026-07-18

**Settings overhaul** — per-client on/off, Auto-Save, and an in-app bug-report
form — plus a batch of fixes from live-testing.

### Added
- **Per-client enable/disable toggles** (Settings): osu!lazer and osu!(stable) can
  each be turned off (defaults: lazer **on**, stable **off**). A disabled client
  disappears from the whole app — its exe path row in Settings, its Dashboard
  import button, and its Shortcuts controls (summary column, save/unpack buttons,
  both transfer directions and its export source) — and is never launched or
  written to. The Shortcuts tab shows a hint naming what's hidden and why, so
  nothing looks silently broken.
- **Save ⇄ Auto-Save** (Settings): in Auto-Save mode (default) every setting —
  including paths and API credentials — applies immediately and the Save button
  disappears; switch to manual Save to get the explicit button and the
  unsaved-changes guard back.
- **Report a problem / send feedback** (Settings): a form (title + description +
  optional screenshot + optional reply e-mail) that submits to Rosu's hosted
  endpoint (<https://rosu-web.vercel.app>). Includes a clear privacy disclosure;
  nothing is sent until you press Send. If sending fails, the dialog offers
  **click-to-copy** of rosu.app@gmail.com and a link that opens the same form
  **on the web** instead.
- **Packs tab: download link** — a hint pointing at the official
  <https://osu.ppy.sh/beatmaps/packs> listing, so missing (red) packs are one
  click from their source.
- **GitHub community files**: issue templates (bug/feature + links to the web
  report form), a pull-request checklist, `SECURITY.md` (private disclosure
  policy) and a Contributor Covenant `CODE_OF_CONDUCT.md`.

### Changed
- **"Scan for lost maps" now walks your whole library across runs.** Sets that
  were never checked are asked about first (previously each run could re-check
  the same first 500), and the result says exactly where the scan stands —
  e.g. "Checked 500 this run … 1 200 not checked yet: run again to continue" —
  with a tooltip explaining the 500-per-run API-friendly batching.
- **Refreshing is now visible.** The Shortcuts ⟳ blanks the counts to "…" while
  re-counting; the Search/Packs/Artists reload buttons clear their table for a
  beat and re-fill it, so a refresh never looks like a dead button.
- **osu! API requests identify themselves** with a proper User-Agent and are
  paced (~2–3 requests/s) per osu!'s API guidance.

### Fixed
- **A failed Drive upload no longer shows a ✓ tick in the job queue.** The upload
  step (and the job) is now marked failed with the error kept as the row tooltip,
  and a dialog tells you the export archives are still safely on disk — only the
  upload failed.
- **Bogus "unsaved settings" warning.** A path picked via Browse under Auto-Save
  was never committed (and later triggered an unsaved-changes prompt); Browse
  picks now commit immediately, and switching Auto-Save off first commits
  anything pending instead of retroactively flagging it unsaved.
- **"Open file location" hardened** — the reveal command now invokes
  `explorer.exe` by its full Windows path.
- A queued job with no runnable steps (e.g. every source disabled) completes
  immediately instead of sitting as a stuck pending row.

## [1.3.3] - 2026-07-16

### Changed
- **Contact address is now rosu.app@gmail.com** (README and in-app About → Licenses),
  replacing the previous personal email.
- **Google Drive backup now uses Rosu's own dedicated Google Cloud project.** The
  Drive sign-in screen now shows "Rosu" as the app; the scope and behaviour are
  unchanged (per-file `drive.file` access only). If you had already connected Drive,
  reconnect once from Settings after updating.

## [1.3.2] - 2026-07-16

### Changed
- **Redesigned the Google Drive "Connected" page** shown in the browser after you
  sign in. It's now on Rosu's pink brand with an animated tick, adapts to your
  light/dark theme, and reads more clearly. When sign-in succeeds Rosu brings its
  own window back to the front, so you return to the app automatically. The page no
  longer implies the browser tab closes by itself — browsers don't allow a script
  to close a tab you opened yourself, so it just invites you to close it.

## [1.3.1] - 2026-07-16

**Bug-fix release** for issues found while testing v1.3.0.

### Fixed
- **Double-click "open file location" opened Documents** for the Dashboard Output
  view (and any archive whose path contained spaces). The reveal command quoted
  the whole `/select,<path>` token, so Explorer didn't recognise the switch; it now
  passes `/select,` outside the quotes and the path inside, selecting the file
  correctly.
- **osu!lazer installed-music count now shows a number.** osu!lazer's own list
  can't be read directly, so the count is derived from your Library sets recorded
  as installed in osu!lazer, with a tooltip explaining where the number comes from.
- **Export was hard to follow in the queue.** The export job now names the source,
  archive file, and format (e.g. "Export Library → MyExport.zip"), the steps say
  where sets are gathered from and what file is written, and the row tooltip shows
  the destination folder.
- **A large single-archive or 7z export couldn't be cancelled** mid-write — cancel
  was only checked once per volume. It's now honoured between files, and cancelling
  removes the partial archive.
- **A job that finished could still be labelled "cancelled".** If you clicked cancel
  but the last step (e.g. a Drive upload) already completed, the job is now marked
  **Done** and its result is shown, instead of "cancelled" while the file was in fact
  uploaded.
- **The cancel button showed an empty box** in some themes (the `✕` glyph didn't
  render). Job and step buttons now use a `×` that renders everywhere.
- **Running jobs can now be cancelled** reliably (not just queued ones), and each
  step has its own remove button: removing one step strikes it through and the job
  **continues** with the rest, instead of only being able to cancel the whole job.
- **About → Licenses now shows a contact line** for reporting bugs / suggestions.

### Note
- Google Drive requires the CI build's OAuth client secret to be set correctly for
  the shipped `.exe`; see the repo's release process.

## [1.3.0] - 2026-07-16

**A job queue on the Shortcuts tab.** Every shortcut action is now a
**queued job broken into named sub-steps** with live status, so you can see exactly
which phase it's in, **cancel jobs one at a time** (the rest keep going), and **run
work concurrently** — a disk operation runs while a Drive upload runs. Plus a few
quick-UX wins that came out of testing.

### Added
- **Job queue** on the Shortcuts tab. Clicking Transfer / Save /
  Unpack / Export / Dedupe now **adds a job to the queue** instead of locking the
  tab. Each job shows its **sub-steps** (e.g. unpack → *Pre-scan → Extract → Send to
  osu!lazer → Send to osu!(stable)*) with a per-step status glyph and progress bar.
  - **Per-item cancel** — each queued/running job has its own ✕; cancelling one
    interrupts just that job and the rest keep going. Cancellation is per-job, so it
    can never disturb another job's in-flight Drive upload.
  - **Concurrent lanes** — local-disk work runs on one lane, Google-Drive upload on
    another, and they overlap. An export that has finished writing and is uploading
    frees the disk lane, so the next queued disk job starts immediately.
  - **Dedupe still confirms first** — a dedupe job scans, then **waits** for your
    explicit confirmation (previewing the count) before recycling anything.
  - A **"Clear finished"** button tidies completed/failed/cancelled jobs.
- **Double-click an archive → open its file location.** Double-click a row in the
  Dashboard (packs or Output view) to reveal the file in your file manager (selected
  in Explorer on Windows); Search/Library rows get an **"Open file location"**
  right-click entry for Library files.
- **Auto-refresh a tab when you open it** — a new Settings toggle (default **on**):
  switching to a tab refreshes its data automatically. Turn it off to keep data
  static until you refresh manually. The Shortcuts summary gains a **⟳ refresh**
  button for that case.
- **Random N export** — an "Export a random sample of N sets" option on the export
  action, instead of exporting everything.

### Changed
- Shortcuts buttons stay **enabled** while jobs run (queue several at once) — the
  old single-operation lock, shared progress bar and single Cancel button are gone,
  replaced by the per-job queue.

### Internal
- New pure `rosu/jobs.py` (job/step/lane model + synchronous runner + the
  lane-scheduling decision, unit-tested) and `rosu/ui/job_queue.py` (the live
  scheduler). Service methods gained a backward-compatible per-job `cancel` token so
  a queued job is fully isolated from the shared cancel used elsewhere. 252 tests;
  adversarial code + security review (2 HIGH + several MED fixed), `--selftest` OK.

## [1.2.0] - 2026-07-15

**Library Maturity — the Shortcuts tab.** One place for the common
one-click flows over the music you already have: see what's installed where, move
sets between clients, back it up / export it, and tidy duplicates.

### Added
- **Shortcuts tab** with an **installed-music summary** (osu!lazer / osu!(stable) /
  Library / Drive-backup set counts) and one-click actions:
  - **Transfer between clients** — osu!lazer ↔ osu!(stable), skipping sets the
    target already has (id-based dedup; a lazer target reuses what Rosu already
    knows is installed there rather than re-scanning everything).
  - **Save installed music to Library** — pull osu!lazer / osu!(stable) straight
    into the Library (automatic dedup).
  - **Unpack Packs → import to osu!** — unpack new packs and send them to
    osu!lazer / osu!(stable) / both, with an **"Only new (skip duplicates)"** vs
    **"Send all anyway"** choice so sets already in the target aren't re-sent.
  - **Export** — bundle {Library | Drive-backed | osu!lazer | osu!(stable) |
    all-merged} into **zip or 7z**, as a single file or split into **1 GB / 500 MB**
    volumes, with optional **upload to Google Drive** and a **shareable link** (the
    export archive only, under the `drive.file` scope). New pure `rosu/exporter.py`.
  - **Dedupe Library** — Recycle redundant duplicate `.osz` (extra copies of a set
    you already have), keeping the canonical file. It **previews the count and
    explains the criterion (matching beatmapset id) and never deletes without an
    explicit confirmation.**
- Long operations (client transfer, export, unpack, the osu!lazer read) are now
  **cancellable**, and the Drive upload shows progress.

### Fixed
- **Sort crash on large tables.** Sorting a big Search/Library table (thousands of
  rows, some with empty numeric cells) spammed the console with `RecursionError`
  from a `QTableWidgetItem.__lt__` override that re-entered itself through PySide's
  virtual trampoline. The comparison no longer calls `super().__lt__` and falls
  back to a safe string compare.
- **Crash on language change** when a scanned archive had been moved/deleted — the
  Dashboard now tolerates a vanished file instead of raising `FileNotFoundError`.
- A **share link can no longer be requested without uploading**, and the Drive
  upload / share controls explain themselves when Drive isn't connected;
  disconnecting Drive mid-upload now warns first. If a file is shared but its link
  can't be retrieved, the user is told (it is public and should be reviewed).
- Export now names the file after its source (`rosu-export-<source>.zip`) and the
  completion dialog shows exactly **where** it was saved.
- Shortcut status messages re-translate when you switch language.

### Notes
- Everything destructive uses the Recycle Bin (recoverable); Drive sharing is
  always opt-in and per-file.

## [1.1.0] - 2026-07-15

**Library Maturity — integrity, health & disk insight.** The first feature minor
of the Library Maturity line: know what your Library actually holds, where its
disk space goes, and whether the files are intact.

### Added
- **Library Health** (a new Dashboard button) — a read-only report that:
  - **Disk usage:** total size on disk and the **biggest beatmap sets**, so you
    can see where the space goes.
  - **DB ↔ disk scrub:** reconciles Rosu's memory with the actual files —
    **orphans** (files on disk with no record), **dead links** (records whose
    file is missing), and how many sets are intentionally memory-only.
  - **Verify (SHA-256):** re-hashes each backed-up set and compares it to the
    checksum stored when it was backed up, flagging **corruption or drift**
    (or "un-backed-up" when there's no reference hash). Runs off the UI thread
    with progress and is cancellable.
- New pure `rosu/health.py` module (unit-tested) backing the above.

### Notes
- Everything here is **read-only** — a health check never modifies or deletes a
  beatmap. Reclaiming space by pruning heavy assets, moving the Library across
  drives, and watch-folder auto-import are planned for later minors of this line.

## [1.0.1] - 2026-07-15

Search-relevance patch (first minor of the Library Maturity line).

### Fixed
- **Search returned unrelated maps.** Searching an artist like **"Hatsune Miku"**
  surfaced maps that merely had *miku* in their tags. Two causes, both fixed:
  the database recalled on a whole-query `tags LIKE '%…%'`, and the ranker had a
  weak fallback onto `tags`/`source`. Search now **tokenizes** the query and every
  word must hit a **strong** field (name / artist / title); a row's rank is its
  weakest word, so "all words as prefixes" beats "all words as substrings". The
  `source` fallback is **gone** (it flooded results).

### Added
- **"Also search tags / mapper"** toggle on the Search tab — off by default.
  When on, creator/tags are matched too, but only ever at the lowest tier, so a
  tag hit can never outrank a real name/artist/title match.
- **Filter box on the Artists tab** — instantly narrows the artist list by name,
  client-side (no reload), matching the Search/Packs tabs.

## [1.0.0] - 2026-07-15

First public release. Rounds Rosu out into a safe, legal, presentable app: it
imports to either osu! client, never shows a broken/empty screen, hardens archive
handling, tracks where every map lives (osu! · Library · Drive), and can flag maps
that no longer exist on osu!. Hardened through extended live testing on a real
~1400-track library.

### Added
- **Import to both osu! clients.** The single "Import to osu!" button is now two
  explicit targets — **Import → osu!lazer** and **Import → osu!(stable)** — each
  enabled/validated against its own configured executable (both auto-detected on
  first run). Settings gained a second path picker for the osu!(stable) executable,
  and the Dashboard hides the button for whichever client isn't installed.
- **Dashboard Output view.** After unpacking (when `Packs/` is consumed) the
  Dashboard now lists the unpacked beatmaps in `Output/` with a count, instead of
  going blank.
- **Where a map lives** — location markers across the Search table: 🎮 osu!lazer ·
  🕹️ osu!(stable) · 💾 Library · ☁️ Drive, with a legend tooltip. New per-client
  tracking columns (`in_osu_stable` / `in_osu_lazer`) are set both when you import
  to a client and when you pull already-installed songs. Library rows that are
  backed up show **which Drive chunk** holds them.
- **In-app About / Licenses** (Settings → About / Licenses): app version, the
  GPL-3.0 summary with a no-warranty + osu!/ppy non-affiliation notice, and the
  full bundled third-party license notices.
- **Lost-map detection** (optional, needs osu! API credentials): a "Scan for lost
  maps" action flags owned beatmapsets that no longer exist on osu! (deleted /
  taken down) — Rosu is the only pack-level archiver that can tell you what's
  already unrecoverable.
- **Loose `.osz` handling.** Dropping raw `.osz` files straight into `Packs/`
  (with no archive to unpack) now moves them into `Output/` tagged with a **Direct**
  source, instead of the old dead-end "no archives found" message.
- **Backup options dialog.** "Back up to Drive" now opens a dialog with a preview
  of the new-set count and total size, a "back up only N sets this run" limit, and
  a selectable chunk size — including an **Individual (one file per set)** mode.
- **Upload to Drive & remove** — a fourth "processed `.zip` action" (shown only
  while Drive is connected): after unpacking, the original archive is uploaded to
  your Drive `Packs/` folder and removed locally to reclaim disk, with a safe
  fallback to the `Processed/` folder if Drive is momentarily unavailable.
- **Remove already-known** button on the Dashboard: recycle/delete the `Output/`
  `.osz` that are already in your Library, in one action.
- **Startup update check** against GitHub Releases with a non-intrusive banner and
  one-click download; toggle in Settings (on by default, fails silently offline).
- **Refresh button** on Search, Artists, and Packs to re-pull the list on demand
  (imports already refresh live; this is a manual trigger).
- **Release integrity:** each release `.exe` is now published with a matching
  SHA-256 checksum.

### Changed
- **Archive-security hardening.** A single shared guard now validates every
  format (zip / tar / 7z) up front — combined uncompressed-size ceiling,
  entry-count cap, decompression-ratio cap, and path-traversal / absolute /
  drive-relative member-name rejection — before anything is written to disk.
- **Output is preserved after importing.** Both clients now consume *staged copies*
  of the `.osz`, so `Output/` survives an import to either osu!lazer or osu!(stable)
  (previously importing to lazer emptied it).
- **Google Drive polish.** Upload blocks raised to 32 MiB; the browser consent page
  is a branded, theme-aware page that **auto-closes and returns to Rosu**; the
  window refocuses after a successful connect; disconnect now asks for confirmation
  and shows a toast; the "Individual" upload mode uploads each set under its own
  `.osz` name instead of a chunk archive.
- **Import from osu!lazer** now shows a busy/progress indicator instead of a frozen
  window while the .NET helper re-exports beatmaps.
- **Search table layout.** The Name column shows the **title only** (the artist has
  its own column and the Artists tab) while a copy still yields the full clean name;
  numeric columns are centered and text columns left-aligned; column widths are
  capped so a row fits without horizontal scrolling.
- **Wider default window** (1280×760) so the tables breathe.
- **Third-party notices** now list every component actually bundled in the exe
  (keyring + its backend, py7zr's codec dependencies, the embedded .NET runtime).
- **Dashboard Copy to Library** is hidden when "Auto-copy to Library after
  unpacking" is enabled (it's redundant then), and a manual copy where everything
  is already in the Library now says so plainly instead of a bare "0 added".
- **Quit/leave guard.** Closing the window or leaving Settings while an operation is
  running now warns before interrupting it.
- **Brand consistency:** the app identifies itself as **Rosu** everywhere (window,
  splash, Excel report header), dropping the old internal "osu! Archive Manager"
  string.

### Fixed
- **osu!(stable) "Error moving file" on import.** Root cause: osu!(stable) imports
  only **one `.osz` per client launch** (unlike osu!lazer, which takes many). Rosu
  now hands stable one file per launch — verified 30/30 importing cleanly with
  `Output/` preserved. (An earlier cross-drive-staging theory was wrong; this was
  the real cause.)
- **Crash when importing from an installed client** — a legacy `NOT NULL`
  constraint on the `packs` table rejected the synthetic source pack; the table is
  now migrated to drop it.
- **"0 added, N already had"** maps now correctly show their osu! location in the
  **Where** column (they were left blank).
- **Prompt cancel.** Cancelling a Drive backup or a lost-map scan now stops
  promptly via dedicated cancel tokens, and cancel is honoured *during* a rate-limit
  retry-backoff rather than only between calls.

### Security
- **Hostile archives are refused and quarantined.** A zip-bomb (by total size,
  entry count, or decompression ratio) or a path-traversal archive is rejected
  before extraction and moved to a `Quarantine/` folder (never silently deleted,
  never overwriting a previously quarantined file), with a clear in-app message.

## [0.8.1] - 2026-07-14

Bug-fix and polish batch from live testing of v0.8.0.

### Fixed
- **Artists tab no longer freezes.** It rebuilt the entire (~1000-row) table
  synchronously on *every* tab focus. It now rebuilds only when the data or the
  chosen sort actually changed (a `data_generation` counter), coalesces paint
  updates, uses resizable fixed-width columns instead of per-row auto-measurement,
  and its per-artist song list no longer runs an N+1 query.
- **Import "N added, 0 already had" miscount.** Re-importing beatmaps already in your
  Library counted every one as "new" because it compared file bytes (an osu!lazer
  re-export never byte-matches the stored copy). New-vs-duplicate is now decided by
  beatmapset id.
- **Search refreshes live** after an import / Copy to Library / Refresh, instead of
  showing stale rows until you leave and re-open the tab.
- **Blank Source for maps already in osu!.** Beatmaps imported from an installed osu!
  client are now tagged `local_osu_lazer` / `local_osu_stable` in the Sources column
  (via a hidden synthetic source pack).

### Changed
- **osu! import batch size 40 → 64** files per launch (still well within the Windows
  command-line limit). The "one-by-one" tail some users saw is osu!lazer's own serial
  import, not Rosu's batching.
- **Resizable table columns** (Search, Packs, Artists) — drag a header border to
  resize; long names/artists now show a full-text tooltip and rows are a touch taller.
- **Google Drive:** the browser "you can close this tab" page is now a branded,
  theme-aware page with distinct success/error states; the Connect button is disabled
  up front (with a clear message) when the `keyring` package is missing, instead of
  failing only after the whole sign-in completes.

### Added
- **Unsaved-settings guard** — leaving Settings (or quitting) with unsaved path/API
  edits warns with Save / Discard / Cancel; **Ctrl+S** saves.
- **Hover tooltips** on the main controls across every tab (translated, theme-aware).
- Settings Language/Theme dropdowns now line up with the folder pickers.
- README contact e-mail.

## [0.8.0] - 2026-07-14

Google Drive backup: log in once and back up your Library to the cloud as
bundled archives, with per-track location tracking (item 11).

### Added
- **Google Drive backup (item 11)** — a new `rosu/drive/` package and a
  "Back up to Drive" action on the Dashboard. Logging in once (Settings →
  Google Drive) uploads new Library `.osz` to a designated Drive folder as
  **fixed-size, append-only chunk archives** (`chunk-NNNN.zip`); re-running
  uploads only what's new (incremental). A per-device **manifest shard**
  (`manifest-<deviceId>.json`) records which chunk holds each beatmapset, so a
  second machine can later rebuild its state from Drive.
- **OAuth Desktop-app login** — loopback (127.0.0.1) + **PKCE**, the
  non-sensitive **`drive.file`** scope (Rosu only ever sees the files it creates,
  never the rest of your Drive), with the refresh token stored in the **OS
  keyring** (Windows Credential Manager), never in `config.json`.
- **Location badges** in the Search/browse table — 🎮 osu! · 💾 Library ·
  ☁️ Drive — backed by additive tracking columns `in_drive` / `in_osu` /
  `drive_chunk` / `drive_hash` (DB schema v3).
- Settings **Connect / Disconnect Google Drive**, a configurable chunk size, and
  a per-install `device_id`.

### Notes
- Built on the standard library (urllib + `http.server`) to match the app's
  stdlib-only HTTP policy; the only new runtime dependency is `keyring`. The
  OAuth client is embedded at build time from a CI secret and never committed.
- Bidirectional cross-device sync, offload / free-space, and import-to-osu! from
  Drive are planned for v0.8.1 / v0.8.2.

## [0.7.1] - 2026-07-13

Security & robustness hardening from a full code + security review (no new features).

### Security
- **Archive path-traversal hardening**: reject a drive-relative / ADS `.osz` entry
  name such as `D:evil.osz` that could otherwise escape the flat Output folder on
  Windows, plus a containment check so a written file can never land outside Output.
  Pin **`py7zr>=1.1.3`** (fixes CVE-2022-44900 / CVE-2026-23879) and pre-validate
  every `.7z` member name and total size before extracting.
- **Decompression caps** (zip-bomb / disk-exhaustion guard): 500 MB per `.osz` and
  a total ceiling before unpacking a `.7z`.

### Fixed
- **No more permanent loss of un-backed-up beatmaps**: clearing Output before a
  re-extract now moves `.osz` to the Recycle Bin (Send2Trash) instead of an
  unrecoverable delete — matching every other guarded deletion in the app.
- **Stale Library copies are refreshed**: a re-uploaded beatmapset (same name,
  different size) is now re-copied into the Library instead of being kept stale as
  an "up-to-date" duplicate.
- **Report write is crash-safe**: if `tracking.xlsx` is open in Excel, an
  extract/import no longer aborts mid-run (which could strand freshly extracted
  files) — it logs `EXCEL_LOCKED` and continues. Report writes are also serialized
  so two background operations can't corrupt the workbook.
- **Clean shutdown**: closing the window now cancels and joins background workers
  before the database is closed, preventing "closed database" / deleted-widget
  errors when quitting mid-operation.
- **Reference sync survives rate limits**: an osu! API 429 now honours
  `Retry-After` and retries the page instead of discarding the whole sync.
- Corrected the cancelled-import toast (it counted beatmaps but said "batches").
- Added a regression test covering the archive path-traversal guard.

## [0.7.0] - 2026-07-13

Auto-import the songs already installed in your osu! client (item 15).

### Added
- **Import from osu!(stable)** — detects the `Songs/` folder (honouring a custom
  `BeatmapDirectory`), zips each installed beatmapset back into an `.osz`
  (preserving storyboard/skin subfolders) and dedups it into the Library. Pure
  Python; resolves the beatmapset id from the folder prefix or a `.osu`'s
  `BeatmapSetID`, and skips sets you already have.
- **Import from osu!lazer** — a bundled, self-contained .NET 8 helper
  (`RosuLazerExport`) reads lazer's `client.realm` **dynamically + read-only**
  (no schema-version coupling) and re-exports every submitted beatmapset from the
  hash-addressed `files/` store into `.osz`, which Rosu then dedups into the
  Library. Validated against a real 1200+ beatmap lazer install. Source in
  `tools/RosuLazerExport/`.
- Both live under **Settings → Import installed songs**, and run off the UI thread
  with progress.

## [0.6.0] - 2026-07-13

Safer confirmations and more archive formats.

### Added
- **More archive formats (item 24)**: unpack **7z** (py7zr) and **tar/tar.gz/
  tar.bz2/tar.xz** in addition to zip. A new `archives` module hides the per-format
  differences; the "choose archives" picker filters to all supported types.
- **Archives with extra files (item 25)**: if a pack archive also held non-music
  files (readmes, images…), the pack is flagged with how many, and the Packs tab
  has a new "With extra files" filter to review them (music is still extracted).
- **Mouse-wheel guard on dropdowns (item 16)**: scrolling over a combo box no longer
  changes its value by accident — after a short pause it opens the list so you pick
  deliberately. Applied to Language/Theme/zip-action and the Packs/Artists dropdowns.
- **osu! close warning (item 18)**: after dispatching an import, a reminder that osu!
  keeps importing in the background — don't close osu! until it finishes (the window
  is fine to close).

### Changed
- **Deleting Library copies is guarded (item 17)**: turning off "keep physical .osz
  copies in Library" now asks for confirmation behind a visible 3·2·1 countdown that
  actually waits ~4.2 s, then moves the Library's `.osz` to the Recycle Bin while
  keeping their info in memory.

## [0.5.0] - 2026-07-13

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

## [0.4.0] - 2026-07-13

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

## [0.3.0] - 2026-07-13

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

## [0.2.0] - 2026-07-13

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

## [0.1.0] - 2026-07-12

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

[Unreleased]: https://github.com/Kerevizodunu2000/rosu/compare/v1.3.3...HEAD
[1.3.3]: https://github.com/Kerevizodunu2000/rosu/compare/v1.3.2...v1.3.3
[1.3.2]: https://github.com/Kerevizodunu2000/rosu/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/Kerevizodunu2000/rosu/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/Kerevizodunu2000/rosu/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/Kerevizodunu2000/rosu/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Kerevizodunu2000/rosu/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/Kerevizodunu2000/rosu/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/Kerevizodunu2000/rosu/compare/v0.8.1...v1.0.0
[0.8.1]: https://github.com/Kerevizodunu2000/rosu/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.8.0
[0.7.1]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.7.1
[0.7.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.7.0
[0.6.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.6.0
[0.5.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.5.0
[0.4.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.4.0
[0.3.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.3.0
[0.2.0]: https://github.com/Kerevizodunu2000/rosu/releases/tag/v0.2.0
