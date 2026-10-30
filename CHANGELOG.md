# Changelog

All notable changes to **Rosu** (osu! beatmap archive manager) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> Note: version control (git) was introduced at **v0.2.0**. The v0.1.0 entry below is
> documented from the shipped state and run logs (v0.1.0 first ran 2026-07-12), even
> though no source snapshot predates the first commit.

## [Unreleased]

### Added
- Automatic, signed updates for the Windows exe. When a newer release is out, Rosu
  downloads it in the background, checks its signature and SHA-256, and installs it when
  you click **Restart now** (or on the next start). A new version that fails to start is
  rolled back and skipped. Turn it off with **Install updates automatically** in Settings.
- Settings shows how much of your Google Drive storage is used, how much Rosu's folder
  takes and how much is in Drive's trash. A Drive backup now checks for free space first
  and doesn't start when the upload won't fit. If Drive fills up during a backup, it
  stops cleanly and keeps everything uploaded so far; run it again after freeing space.
- **Unpack** and **Copy to Library** check the free space first. When it is short they
  refuse before writing anything, with a message naming the drive, the space needed and
  the space free. A disk that fills up during the run stops it cleanly with "disk full":
  beatmaps already written stay, and the archive stays in Packs.
- **Export** and **Import to osu!** check the free space first and refuse before writing
  anything, with a message naming the drive. A disk that fills up during an export stops
  it cleanly: the archives already finished are kept and nothing is uploaded. Moving loose
  `.osz` from Packs to Output on another drive is checked too.

### Changed
- Library refresh and other lookups by file name are faster on large libraries.
  Existing libraries get the speed-up the first time Rosu opens them.
- Exporting from a large Library is faster.

### Fixed
- A refused or disk-full **Unpack** from the Shortcuts tab no longer goes on to send
  Output to osu!: the job shows as failed and says which drive is short.
- A full disk during **Copy to Library** no longer leaves a truncated beatmap in the
  Library or overwrites a good copy already there.
- One set that fails no longer stops Refresh Library: it is skipped, counted in the
  status line and detailed in the Logs tab.
- A map with an infinite beat length gets no BPM instead of 0.
- A prune error is logged instead of stopping the prune.
- A beatmap with an infinite, NaN or huge number in it no longer stops a Library
  refresh or reads as an empty set. Rosu treats a difficulty setting, game mode, note
  time or key count it can't use as missing.
- A mania note with such a number is skipped when rating the difficulty.
- An archive is removed from Packs only after every beatmap in it was extracted. A
  cancelled Unpack, a beatmap that failed to extract or one with a name Rosu can't read
  now keeps the archive (the Logs tab says why), and the track count shows what was
  really extracted.
- One corrupt or unreadable archive no longer stops the whole Unpack: it is skipped and
  left in Packs.
- On a drive with no Recycle Bin (removable, network), Rosu no longer removes archives or
  Output files for good: they are kept and the Dashboard says how many.
- **Remove already-added** removes an archive only when every beatmap in it is in the
  library; a partly added or unreadable archive stays.
- A loose `.osz` that replaces a file already in Output sends the old one to the Recycle
  Bin instead of deleting it.
- An export named with a dot (`my.maps.zip`) is written under that name, not `my.zip`.
- Pruning a Library set now puts a copy of the original in the Recycle Bin before it
  rewrites the set, so a failed Recycle Bin step no longer loses the unpruned original.
  On a drive without a Recycle Bin (removable or network), pruning is skipped.
- On a drive with no Recycle Bin (removable, network), **Remove from osu!** no longer
  deletes osu!(stable) folders for good, even with **Save to Library, then remove**: it
  removes nothing and says why.
- Pruning heavy assets keeps the background and audio a difficulty references from a
  subfolder (such as `sub/bg.jpg`) instead of removing them.
- Exports and staged imports with pruning on no longer fill the Recycle Bin with a full
  copy of every set.
- Save and Remove now checks every file of a set, not only the difficulties, so a set
  whose Library copy was pruned or is incomplete is kept in osu!. The copy it saves
  first is never auto-pruned.
- Purging the Library marks as memory-only only the sets whose files actually went to the
  Recycle Bin.
- An interrupted mirror download no longer leaves a stray `.osz` in the Library.
- When Rosu can't prepare a copy of a beatmap for import (for example, the disk is full
  or access is denied), it no longer sends osu! the original from Output or the Library.
  Only the copies that worked are sent, and the Dashboard and Shortcuts say how many were
  not sent and that they are still in Output.

### Removed
- The **Delete permanently** processed-archive action. Existing settings switch to
  Recycle Bin.

## [1.10.0] - 2026-10-20

**Find the same song across different sets — by listening to it.**

### Added
- **Same song, different sets…** (Shortcuts). Rosu fingerprints each Library set's audio
  (the first two minutes, with Chromaprint's `fpcalc`) and groups the sets whose songs
  match — re-encodes, re-uploads, TV-size cuts — whatever their names or set ids say. A
  candidate index keeps this fast on large Libraries, and fingerprints are cached per file,
  so a second scan only listens to new or changed sets.
  - Nothing is selected for you (different sets of one song are often different maps);
    **Select extras** ticks all but the set with the most difficulties in each group.
  - One set of every song always stays; the chosen ones go to the Recycle Bin after a
    countdown confirmation, through the same queued job as the Library dedup.
- Chromaprint `fpcalc` 1.6.2 (LGPL-2.1-or-later, with FFmpeg inside) is bundled with the
  exe. It is not kept in git: `tools/fetch_fpcalc.py` downloads the official release and
  checks a pinned SHA-256 (CI runs it before building).

### Fixed
Found by the v1.10 code and security review (before release):
- A same-song scan whose fpcalc was blocked (an antivirus), timed out or could not write its
  temp file no longer marks those sets "unreadable" for good: only audio fpcalc really could
  not read is remembered; the rest is tried again next scan, and a fpcalc that does not start
  at all is reported before anything is scanned.
- Sets recycled from the same-song list are marked as no longer in the Library (they kept
  showing as present until a Library refresh).
- Grouping keeps its memory proportional to the Library size (it held every candidate pair at
  once) and stores fingerprints compactly — large Libraries scan without a memory spike.
- Fingerprints of sets that left the Library no longer take part in grouping.
- The same-song dialog stops its scan however it is closed, and its Recycle button waits for
  a fresh list after "Scan again".
- fpcalc decodes each file as the format its name says, and gets no input stream.
- Watch folder: one import batch at a time (saving other settings no longer queues the same
  files twice), a cancelled import counts as failed, failed imports wait 5 min, then 10, 20 …
  up to 2 h, and nothing is staged while the Library's drive is unplugged.
- Move Library and Copy to Output never replace a file that appears at the very last moment
  (an exclusive rename/link instead of a check-then-replace); the move preview tests whether
  the destination is writable by creating a throw-away file (Windows ignores the old check);
  a source that cannot be opened no longer leaks a file handle and a stray temp file.

Found by the v1.9 code and security review:
- **Move Library** is safer end to end: each file is written to a private temp file,
  synced and hash-checked before it takes its real name; Output, Packs, `data` and `logs`
  are refused as destinations, as is a folder Rosu cannot write to; links in the way count
  as conflicts; if the new setting cannot be saved, the Library stays where it was; files
  added during the move are carried over afterwards (any that could not be are listed);
  and the old copies are only recycled after a fresh check that they still match.
- **Watch folder**: a big catch-up is imported in batches (100 files / 2 GB); a file is
  marked handled only after the import reports it done, so a failed or interrupted import
  is retried (after a five-minute pause, so a full disk is not retried every few seconds);
  files that are not archives are skipped once; the import checks free space first;
  downloads that arrive while Rosu is closed are added at the next start, once settled.
- "Copy to Output" writes through a temp file, so a failed copy never leaves a half-written
  `.osz` for Import to osu! to pick up.
- Archives are read with a size cap everywhere (set details, prune, covers, the client
  removal fingerprint), so a crafted `.osz` cannot exhaust memory.
- Cover thumbnails only decode JPEG, PNG and BMP data and are cached atomically; closing
  Rosu waits for background work (and the thumbnailer) to stop first.
- Path repair no longer "repairs" a healthy root, and only rewrites paths that were inside
  the old root.
- A Library on a drive that is offline no longer stops Rosu from starting.
- Search recall: a word after punctuation (`(TV Size)`, `feat.Artist`) now counts as the
  start of a word when ranking candidates.
- Search ◀ ▶: going back and then typing before that result arrived kept the new search
  out of the history.
- Logs tab: details are shown literally in tooltips, and after midnight a live line is
  only added to the day it belongs to.
- A hand-edited `config.json` with `"false"` (a string) for an on/off setting no longer
  reads as on.

## [1.9.0] - 2026-10-20

**Browse the Library your way, move it anywhere, and let new downloads come in by themselves.**

### Added
- **Search, your way.**
  - Right-click a column header to hide or show columns; the choice is remembered (the
    name column always stays).
  - **★ Saved** keeps the current search (text, filters and the tags toggle) under a
    name; one click runs it again (up to 50).
  - **◀ ▶** (Alt+←/→) step back and forward through the last 16 searches; a burst of
    live-search typing counts as one step.
  - **▦ Gallery** shows the results as cover art (each set's background, the first 500);
    double-click a cover for its details. Thumbnails are made in the background and
    cached under `data/covers`.
  - **Export…** writes the listed sets to CSV (opens in Excel; spreadsheet formulas in
    titles are neutralised) or JSON.
  - Right-click sets → **Copy to Output (for Import to osu!)** stages exactly those Library
    sets for the Dashboard's Import to osu!.
- **Move Library…** (Shortcuts): move the Library to another folder or drive. The preview
  shows the files, their size, the free space there and anything in the way (a different
  file with the same name blocks the move; it is never overwritten). Every file is
  copied and checked against its SHA-256 before Rosu switches to the new folder;
  afterwards the old copies can go to the Recycle Bin (left alone on a drive without
  one). A cancel or a failed copy changes nothing.
- **Watch a folder** (Settings, opt-in): new `.osz` files that land in the chosen folder
  (say, Downloads) are added to the Library by a quiet background job (ones that arrive
  while Rosu is closed, at the next start). Files already there when watching starts are
  left alone, a file is taken only once it has stopped changing, and your files are never
  moved or deleted.
- **Logs tab as a table**: any day's log in columns (time, level, action, details,
  message), with "Errors only" and a word filter; today's grows live.

### Changed
- The osu!lazer export shows real progress (sets done / total) with the updated helper
  (it now prints the total first); an older helper keeps the moving bar.

### Fixed
- **Searching a common word could miss the best match.** The candidate list was capped
  in table order before ranking; matches where every word starts a word of the name,
  artist or title are now collected first.
- **Library verify's progress bar never filled** when some files were missing or pruned
  (only hashed files counted).
- The v1.8 "Remove" job step label replaced the dedup job's "Recycle duplicates" text
  (both used one translation key); a test now fails on any repeated key.
- Turning crash reports on in Auto-Save mode left Settings looking unsaved.

## [1.8.0] - 2026-10-20

**Take sets out of osu!, and get sets back from your Drive backup.**

### Added
- **Remove from osu!** (Shortcuts → *Remove from osu!…*). Pick a client and see every
  set in it — its size and whether the Library already holds it — filtered (all /
  already in the Library / not in the Library), ordered and capped, before a countdown
  confirmation. Two modes:
  - **Save to Library, then remove** copies each set into the Library first (always as a
    real file, even with memory-only imports) and removes only the sets whose Library
    `.osz` holds every one of their difficulties byte for byte. A matching set id is not
    enough: a local edit, an extra difficulty or an unrelated map sharing the id stays in
    osu! and is listed. A Library file is never overwritten.
  - **Remove only** (osu!(stable) only) says up front how many of the chosen sets have
    no Library copy, and is refused when the Songs folder is on a drive without a
    Recycle Bin (removable or network), where Windows would delete for good.

  Refused while osu! is running — and when that cannot be checked.
  osu!(stable): each set's `Songs/` folder goes to the Recycle Bin; every name is
  resolved inside the detected Songs folder first (and must hold a `.osu`), anything
  else is refused.
  osu!lazer: never touched on disk (lazer shares one stored copy between every set with
  a byte-identical file), and always saved to the Library first, since lazer purges
  removed sets on its next start. The bundled helper gains `list` and `delete` commands
  that flip lazer's own `DeletePending` flag, after proving the database opens read-only
  with this helper's Realm (so the write cannot upgrade the file format) and after
  copying `client.realm` aside (newest three kept). **The shipped helper binary is
  unchanged**, so lazer removal shows as "not available yet" until the helper is rebuilt
  and verified on a real lazer install (`tools/RosuLazerExport/README.md`).
- **Drive backup browser + restore** (Shortcuts → *Browse Drive backup…*). Lists every
  set the Google Drive backup holds — merging the manifest of every PC that backs up
  into it — with a filter, which PC backed it up, and whether the Library already has
  it; flags archives that are no longer on Drive and backup files no manifest lists.
  Restoring downloads only the archives that hold the chosen sets, extracts just those
  members (plain `.osz` names only, size-capped, after a free-space check), verifies each
  against the SHA-256 recorded at backup time and imports them through the normal dedup
  pipeline — download on the Drive lane, import on the disk lane. A restore never
  replaces a Library file: a same-named file with other bytes is left alone and
  reported. One unreadable archive member or malformed manifest entry is skipped, not
  fatal.
- **Report tracking link.** After "Report a problem", Rosu shows (and copies) the
  report's private status link from rosu-web.
- **Opt-in anonymous crash reports** (Settings, off by default). An unexpected error —
  uncaught, or caught by a background task — sends its type, a short message with file
  paths, quoted text and e-mail addresses removed, and the `module:function` names of
  the stack, plus
  the Rosu version and OS. Disk/network errors, cancellations and Rosu's own handled
  errors are never sent; each distinct crash is sent once per session.

### Changed
- The update check asks Rosu's site (`/api/latest-version`) first and falls back to
  GitHub; the banner links the new `.exe` directly (plus "What's new"), with the
  release-notes excerpt as its tooltip. Every link must match this project's release
  pages or assets exactly (no `..`, `%`-escapes or foreign hosts); the report status
  link is rebuilt from rosu-web's own address.
- The lazer helper writes UTF-8 output and gives two sets that share an id separate
  export files instead of overwriting one with the other.
- A dialog closed while its background scan still runs no longer has to wait for it.
- The collection sync has its own cancel token, like every other long scan.

### Removed
- A dead `_clear_osz` re-export from `rosu.services`.

### Fixed
- **Search "Mode" column showed only one mode for mixed sets.** It read the mode of
  the alphabetically-first difficulty, stored once and never refreshed, while
  `mode=mania` and the Filters panel match any difficulty. A set with an osu! and a
  7K chart read "osu!" yet appeared under `mode=mania`. Mode (Search and Artists) now
  lists every difficulty's mode, e.g. "osu!, osu!mania".
- **Sets imported straight from osu!(stable) / osu!lazer had blank Mode, Keys, Star,
  BPM and length** until a "Refresh Library", and permanently with physical copies
  off. The import now reads each new set's difficulties once, like unpacking does.
- **Memory-only sets showed the 💾 Library marker** and offered "Open location" for a
  file that was never kept. The Library Health check also counted them as dead links.
- **The Library status column showed raw English tokens** ("present", "memory",
  "disappeared") in the Turkish UI; it is now translated.
- **Where column sorting** grouped osu!(stable)-only sets with osu!lazer ones; the sort
  now follows the icons shown.
- Zipping a Songs folder that holds a file dated before 1980 (zip's earliest date) no
  longer fails; the date is stored as 1980.

## [1.7.1] - 2026-07-27

> **First published release of the v1.7 line.** v1.7.0 was tagged in the changelog but never released, so this build carries both: the v1.7.0 work below and everything in this section. Upgrading from v1.6.3 gets all of it at once.

**Live-test correctness batch: search no longer hides results, and the star histogram
now describes the library it claims to describe.**

### Fixed
- **Nothing could read osu!lazer when running from source — a regression from the v1.7 services
  split.** `_lazer_helper` located the bundled `RosuLazerExport.exe` with
  `Path(__file__).parent / "assets"`, which was right while the code lived in `rosu/services.py`;
  the split moved it to `rosu/services/import_svc.py`, so the lookup pointed at
  `rosu/services/assets/` and quietly found nothing. Every lazer read — Save from lazer, the
  lazer↔stable transfer, the lazer prune steps — failed. It is now anchored on the `rosu` package
  rather than the module's directory, with a regression test. (The frozen exe was unaffected: its
  `_MEIPASS` fallback still resolved.)
- **And the failure gave advice that could not work:** every error, including a missing helper,
  was reported as "close osu!lazer completely and try again". The three cases are now told apart
  and the underlying detail is shown.
- **Search results were silently capped at 500.** `Services.search` never passed a limit, so
  every query inherited `rosu.search.search`'s 500 default — a star range holding 1600 sets
  listed exactly 500 of them and looked complete, while browsing with an empty box (which used
  5000) showed far more. Searching now uses the same 5000 limit, and when a result really is
  truncated the count line says so ("Showing 5000 of 8123") instead of presenting the cap as
  the whole answer. The pre-ranking recall cap that fed the ranker is no longer a flat 2000
  either: it scales with the requested limit (never below the old 2000), so relevant rows are
  no longer dropped before they are ever scored.
- **The star histogram was built from the current search result, not the library.** It binned
  `self._last_rows` — at most one (capped) page — while telling the user it was the library's
  distribution. It now comes from the whole Library via the service layer.
- **The histogram and a star-range search could never agree.** The bars binned each set's
  `star_max` (its hardest difficulty only), but clicking a bar searches `star>=lo star<hi`,
  which matches *any* difficulty — so a set with a 2★ and a 5★ chart was drawn in the 5★ bar
  yet turned up in the 2★ search. Both sides now speak the same unit: the histogram bins
  **difficulties**, matching the `star>=` filter and the Search "Star" column. The bar labels
  state the unit, and the remaining honest asymmetry (N difficulties can live in fewer than N
  sets) is spelled out on screen — e.g. "1493 difficulties in 1254 sets".
- **A second export could overwrite the first export's archive while it was still uploading.**
  The suggested filename was a constant per source (`rosu-export-library.zip`), so accepting it
  twice sent both jobs to the same path; because the DRIVE lane deliberately overlaps the DISK
  lane, job 2's archive write could land on the exact file job 1 was uploading. The default name
  is now timestamped, a queued or uploading job reserves its destination (a second export aimed
  at it is refused, not silently allowed), and a split export asks before overwriting existing
  `.partNN` volumes — which the save dialog never checked.
- **The Drive share link was not clickable, selectable or copyable.** It was rendered by
  `QMessageBox`, which draws plain text, so a correct and genuinely public link was inert. The
  export-complete dialog now shows a real anchor (with the app-wide hover-to-see-the-target
  behaviour), copies the link to the clipboard as soon as it opens, and offers a Copy button
  that does not close the dialog.

- **Pruned sets were invisible.** `is_pruned` existed in the UI only as the hidden condition for a
  right-click menu entry, so a pruned set looked identical to a whole one and the only way back was
  a context item that was never found. Pruned sets now say so in the Library column (with a tooltip
  explaining what was removed and that the map still plays), are listable with a `pruned=yes`
  search, and Map Details shows a banner plus a first-class **Restore (re-download)** button.
- **Two different exports could render as the same queue row.** The row title carries only the
  source and archive name, so exports differing in random-N, star range, split size or
  upload/share were indistinguishable. Each row now spells out every choice that was made — and
  once a job finishes, the share link it produced.
- **The skillset scan and Library verify results were misleading.** "707 rated, 1922 scanned"
  never said that the rating is mania-only by design; re-running reported "0, 0, 0" because
  already-scanned sets are skipped, which read as a failure. Verify listed "mismatch" and
  "un-backed-up" without saying what either meant, never said it is read-only, never showed
  *which* files mismatched, and omitted the `pruned` bucket v1.7 introduced — so pruning looked
  like it lost sets from the totals. All reworded, and mismatched filenames are now listed.

### Added
- **Prune is now a dialog, not a single button that decided for you.** The old button silently
  used whatever `prune_mode` was set in Settings, ran over the whole Library, and reported only a
  count and a total once it had already made its choices. It now asks, up front:
  - **Where** — Rosu Library or osu!(stable). osu!lazer is listed but disabled, with the reason
    stated plainly: lazer stores every file by content hash and **shares one copy between all sets
    containing that asset**, so deleting files would break other sets and leave `client.realm`
    pointing at something that no longer exists. Doing it safely means going through lazer's own
    database, which arrives with the "remove maps from a client" feature. This is a technical
    constraint, not a setting.
  - **What** — video only · images only (backgrounds included) · video + images · smart clean-up
    (the previous `heavy_assets` behaviour, unchanged, now with a tooltip saying what it keeps).
  - **How many and in what order** — biggest-saving-first, smallest-first or by name, and a limit
    ("prune the 200 that free the most"). Only sets that would actually free something are ever
    counted, so the number in the button is the number of sets that really change.
  - **A preview** — how many sets would change and how much they would free, from a read-only scan
    (the zip's directory is read; nothing is decompressed or written), followed by a 3-second
    countdown confirmation naming the source, the mode, the total, and how to undo it. The per-set
    list is one click away rather than filling the dialog: scrolling 1922 rows is not how anyone
    decides whether to prune, but "these exact sets will change" still has to be showable.
- osu!(stable) can be pruned at all now: it stores beatmaps as loose files rather than archives,
  so a folder-mode prune was written for it. It refuses any folder that resolves outside the
  detected `Songs` directory, refuses folders with no `.osu` in them, never removes a `.osu`, and
  sends what it does remove to the Recycle Bin.
- Histogram bin mode: keep the data-driven ranges (which produce edges like 3.94–4.55) or switch
  to plain whole-star buckets (0–1, 1–2, 2–3 …). Empty buckets inside the range are kept so the
  axis reads continuously.
- `pruned=yes` / `pruned=no` search filter.
- Queueing the **identical** action twice in a row now asks whether you meant to. Only a
  consecutive repeat is questioned — if another job was queued in between, repeating is
  deliberate and goes straight through.
- A test that resolves every literal `t("…")` key in the source against the string table. v1.7.0
  shipped ~15 strings written as `t(key, default="…")`; there is no such fallback, so they would
  have rendered as raw key names and nothing would have failed until someone opened that screen.

- **Undoing a prune.** "How do I get my videos back?" had no answer beyond a per-map right-click.
  Shortcuts → **Restore pruned maps** now asks where the files should come back **from**, and says
  what each route costs: the **Recycle Bin** (free, byte-identical, instant — Rosu opens it and
  says what to look for rather than reaching into it) or an **osu! mirror** (`catboy.best`,
  explicitly named as third-party). It also states why the official osu! servers are not an
  option: downloads there need a signed-in account and the public API has no download endpoint.
  Prune's own Recycle Bin copy is now named after the set (`Artist - Title.osz.orig`) instead of
  a tempfile name, so restoring it by hand gives back something identifiable.
- **The "pruned" badge no longer over-claims.** Prune is per-location, but one flag made a row read
  as though every copy of the set had been stripped — including the osu!lazer copy, which was
  untouched. Schema v11 records *where* (`pruned_sources`), the badge names those places, and the
  tooltip says outright that copies elsewhere were not touched. `is_pruned` stays Library-only on
  purpose: letting a client-side prune set it would make the Library scan skip a file it never
  touched, and the bulk restore re-download one that was never pruned.
- **Which maps were pruned, when, and how** is now recorded (schema v10: `pruned_at`,
  `prune_mode`) and logged one line per set, instead of only a run total.
- **Prune osu!lazer** (Shortcuts, and reached by picking osu!lazer in the Prune dialog) — lazer's
  files cannot be stripped in place, so pruning it means going the long way round, and these steps
  *are* that prune: save everything into the Library → you delete the beatmaps in lazer's own
  Maintenance screen → Rosu measures lazer's file store to confirm it really emptied → prune the
  Library (optional) → send it all back. Every step is explained before it runs and confirmed
  before it acts. **The delete step is gated on proof**: it does not unlock until every set lazer
  exported is verified present in the Library, by beatmapset id and by file — "N new sets added"
  is not proof, since an already-known set counts as a duplicate and a failed copy counts as
  nothing. And Rosu never claims lazer was emptied when its file store says otherwise (it offers an
  explicit override, since only the user can see lazer's screen). Picking osu!lazer in the Prune
  dialog leads here instead of just refusing.
- The star histogram's selection now says how many **sets** searching that range will list, not
  just how many difficulties the bars hold — "2727 difficulties" followed by "1509 matches" read
  as a bug. Both bin modes also explain themselves on hover.

### Changed
- **The lost-map scan has no per-run cap.** It stopped after 500 API calls, so a 1922-set library
  needed four manual runs to finish once — which read as the scan giving up. It now walks the
  whole library and the button doubles as Cancel, so the length is the user's choice.
- **The pack-reference sync can be cancelled** (the button doubles as Cancel). A cancelled sync is
  deliberately *not* saved: a half-fetched reference would mark real packs as missing.
- Settings' Prune Mode now offers all four modes (it had only two) and explains each on hover.
  It is the default used by auto-prune and export-prune, which have no dialog to ask in.
- `PruneDialog` cancels an in-flight scan when the source or mode changes and re-runs, discarding
  the superseded result. Found while driving the real dialog: refusing to start the new scan left
  the *previous* source's rows on screen, presented as the new source's.
- The job queue's cancel (×) and per-step skip buttons rendered as **empty boxes**: the shared
  button style pads 16px on each side, so a 30px fixed-width button had no room left for its
  label. They now use a dedicated `#iconbtn` style with near-zero padding.
- The prune job is no longer titled "Prune Library" — it prunes osu!(stable) too, and the row's
  detail line names the source.
- Settings kept showing "Backing up into this Drive folder: …" after Disconnect, describing
  something that was no longer happening. It now appears only while connected (the folder id is
  still remembered, so reconnecting reuses the same folder).
- Settings now names the Google Drive folder Rosu backs up into, as a link, and explains why a
  "Rosu" folder it did not create is invisible to it: Rosu asks for the narrow `drive.file`
  permission, which only ever exposes files this app created — so a folder made by hand, or one
  created by a pre-v1.3.3 Rosu (a different Google client), cannot be found and a new one is made
  instead. The narrow scope is deliberate and is not changing; older backups are still in Drive.
- `Database.count_filtered_tracks` and `Database.difficulty_stars` — locked accessors for the
  untruncated match count and the per-difficulty star values.

## [1.7.0] - 2026-07-20

**Space-saving (Prune) + services package split + collection sync + map repair.**

### Added
- **Prune**: recycle non-essential heavy files (video only, or video + large images) from Library `.osz`
  sets to save disk space — in place, on-the-fly on export/import (the persisted Library copy stays
  untouched), or as a Shortcuts batch action (scan → preview + confirm → recycle, same gated pattern as
  Dedupe). Settings: Auto-Prune / Export Prune toggles + Prune Mode. Originals go to the Recycle Bin.
- **Sync Collections** (Settings): reads osu!(stable)'s `collection.db` and tags matching Library maps with
  their collection name.
- **Repair** (Search, right-click a missing/pruned map): re-downloads it from a third-party osu! mirror —
  disclosed as such, with a confirmation dialog, before any download starts — and clears its pruned flag on
  success.
- Schema v9: `tracks.is_pruned` / `tracks.original_size`.
- `Database.bulk()`: a deferred-commit transaction context manager for multi-statement writes.
- `upsert_difficulties` rewritten as a single `INSERT ... ON CONFLICT DO UPDATE` (was a per-diff
  SELECT+INSERT/UPDATE loop); a fresh `NULL` star still never overwrites a star already stored.

### Changed
- **`rosu/services.py` (2041 lines) split into a `rosu/services/` package** of mixins (core / extract /
  library / import / health / metadata / export / collection) combined into the same public `Services`
  facade — every call site and every test is unchanged.
- `library.copy_to_library` no longer overwrites an already-pruned Library file just because its size no
  longer matches a freshly re-imported original.
- Library Health's SHA-256 verify no longer reports a pruned file as a "mismatch" (pruning intentionally
  changes the file's bytes — it's counted separately now instead of reading as corruption).

### Fixed
This release's new code (prune/collections/repair, and the mechanical parts of the services split) had not
been exercised before this pass found and fixed:
- Four call sites imported `from PyQt5.QtWidgets import QMessageBox` in this PySide6-only app — a guaranteed
  `ModuleNotFoundError` the moment they ran. Switched to PySide6, and moved dialog presentation for the two
  service-layer sites into the UI layer (the service layer stays Qt-free, matching the rest of the codebase).
- The collection-sync and map-repair actions were unreachable: they built a job object with an invalid
  constructor shape and submitted it to `self.job_queue`, an attribute never assigned on the Settings/Search
  tabs (the real job queue is owned locally by the Shortcuts tab). Rewired through the existing off-thread
  `Worker` pattern already used by every other Settings/Search action.
- About 15 new UI strings assumed `i18n.t(key, default="...")` was a supported fallback; it isn't (a missing
  key just displays the raw key). All added properly to `rosu/i18n.py`, in English and Turkish.
- Prune: a zip member's declared size is now capped before being read into memory (zip-bomb guard) —
  previously unbounded. Verified by an adversarial security pass: a real, correctly-compressed zip bomb and
  a hand-patched size-lying archive were both refused cleanly with no memory growth.
- Prune: the swap-in sequence is now a single atomic rename (`os.replace(temp, original)`) with the original
  copied aside (not moved) beforehand purely for Recycle Bin recoverability — there is no longer any instant
  where the Library file could be left missing, even if the rename itself fails or the process is killed
  mid-operation. (The original fix in this pass — rename-aside-then-swap-back-on-failure — closed the
  reported data-loss bug but left a narrower window if the *recovery* rename also failed; this redesign
  removes that window entirely rather than narrowing it further.)
- The Shortcuts batch prune action was marking every scanned file as pruned regardless of whether any bytes
  were actually freed — which then permanently excluded that file from ever being refreshed by a later
  import — and was silently ignoring the configured Prune Mode (always ran video-only).
- **`collection.db` parsing had no cap on its length-prefix decoding** — a malformed/tampered file could
  drive a multi-GB read attempt or peg a CPU core from a file only a few bytes long. Both the ULEB128
  continuation-byte count and the decoded string length are now capped before any large read is attempted.
- Repairing a fully-missing (not just pruned) map didn't mark it back as present in the Library, so it kept
  showing as missing in Search until an unrelated Refresh reconciled it.
- The repair action's context-menu label was hardcoded in Turkish regardless of the UI language; wired
  through `i18n.py` like every other menu action.
- "Sync Collections" now hides when osu!(stable) is disabled, consistent with every other stable-only control
  (collection.db only exists for osu!(stable)).
- Several places read/wrote the database directly instead of through a locked accessor, a real race risk now
  that they run off the UI thread; added locked `Database` methods and routed through those instead.
- The mirror downloader now caps response size against both the declared and the actual byte count, so a
  misbehaving/compromised mirror can't fill the disk; its consent dialog now also names the copyright
  responsibility, matching the existing Google Drive public-share warning's precedent.
- Two existing Settings buttons and one new one had been switched to an undefined style class and rendered
  unstyled; reverted to the existing button style.

### Tests
- New: `tests/test_prune.py`, `tests/test_collections.py`, `tests/test_api_mirror.py`,
  `tests/test_services_prune.py`; extended `tests/test_library_dedup.py` and `tests/test_job_builders.py`.
  427 tests total (was 375). Shipped only after two independent adversarial review passes (general
  correctness + a security-focused pass that live-tested the zip-bomb guard, the swap failure modes, and the
  collection.db parser against real crafted inputs rather than reasoning about them statically).

## [1.6.3] - 2026-07-19

**Hardening patch** — robustness, safety nets and test depth ahead of v1.7; no new
features. Driven by four independent code-analysis reports, every finding verified
against the code first.

### Fixed
- **Clean errors instead of raw tracebacks on malformed server replies.** A non-JSON
  body from the Google Drive API, the Google OAuth token endpoint, or the osu! API
  (proxy interstitials, truncated replies) now surfaces as a readable, typed error
  message in the UI instead of a bare `JSONDecodeError` from a worker thread.
- **A database that fails to open no longer kills the app silently.** Startup now
  shows an error dialog naming the database file and the error (with guidance to
  back the file up and report), instead of dying with an invisible traceback in the
  windowed exe; `--selftest` prints the failure reason and exits non-zero.
- **Archive safety scan fails closed.** If an archive's compressed size cannot be
  read, the scan now refuses the archive; previously the decompression-ratio check
  was silently skipped in that case (the 30 GiB total-size cap still applied).

### Changed
- The bug-report dialog's data disclosure now also mentions the optional contact
  e-mail among the things sent.
- Dashboard and Shortcuts root layout spacing aligned with the other tabs (10 px).

### Tests
- New global test isolation (`tests/conftest.py`): every test's config file is
  auto-redirected to a temp path, making the v1.4.1 creds-wipe class of accidents
  structurally impossible; Qt defaults to offscreen.
- 16 new tests: malformed-reply guards (Drive client/auth, osu! API), archive
  fail-closed, `msd_for_diffs` filtering, the 16 MB `.osu` bomb guard and parser
  fallback, `ON DELETE CASCADE`, small db methods (`mode_set_counts`,
  `set_pack_extra`, `mark_library_memory`), the Drive share-link consent dialog,
  i18n en/tr completeness, and the startup error helper. 375 tests total.

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

[Unreleased]: https://github.com/Kerevizodunu2000/rosu/compare/v1.8.0...HEAD
[1.8.0]: https://github.com/Kerevizodunu2000/rosu/compare/v1.7.1...v1.8.0
[1.7.1]: https://github.com/Kerevizodunu2000/rosu/compare/v1.6.3...v1.7.1
[1.6.3]: https://github.com/Kerevizodunu2000/rosu/compare/v1.6.2...v1.6.3
[1.6.2]: https://github.com/Kerevizodunu2000/rosu/compare/v1.6.0...v1.6.2
[1.6.0]: https://github.com/Kerevizodunu2000/rosu/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/Kerevizodunu2000/rosu/compare/v1.4.2...v1.5.0
[1.4.2]: https://github.com/Kerevizodunu2000/rosu/compare/v1.4.1...v1.4.2
[1.4.1]: https://github.com/Kerevizodunu2000/rosu/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/Kerevizodunu2000/rosu/compare/v1.3.3...v1.4.0
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
