# osu! Archive Manager — v0.3.0 → v0.8.0 Roadmap & Design

> Design of record for the 26-item enhancement effort requested 2026-07-13.
> Companion to `HANDOFF.md` (current shipped state = **v0.2.0**). Supersedes ad-hoc notes.
> Written by the brainstorming flow; research findings for Drive & client-import are baked in below.

## Locked decisions (from the user)

1. **Sequencing:** quick fixes first. Order = **v0.3 → v0.4 → v0.5 → v0.6 → v0.7 (auto-import) → v0.8 (Drive)**.
   Rationale the user chose: fastest visible progress; the two big researched features come last.
2. **Item 19 "20 designs" = icon design.** Produce ~20 **icon concepts** in the theme
   **osu-pink + Rose (🌹) + Round + Question-mark (?)**. Present them in a shareable gallery; the user
   picks ONE; that becomes the icon *everywhere* (app `.ico`/`.png`, splash, window title, taskbar/tab).
   Tooling may be added if needed; default plan is self-contained SVG concepts rendered to PNG/ICO.
3. **osu! API (client_id/secret):** NOT configured now. Keep the existing offline gap logic. No code change;
   just don't prompt the user to set it up. (It is safe — client-credentials grant, `scope=public`, app-level
   read-only public data, cannot touch the account. Stored locally in gitignored `config.json`.)

## Cross-cutting: item 21 — versioning

- **`git init` the repo** (currently no `.git`). Baseline commit captures the shipped v0.2.0 state.
- One commit (or a small set) **per version batch**; bump the version string; maintain `CHANGELOG.md`
  (Keep-a-Changelog style); update `README.md` when user-facing behavior changes; write a memory note.
- Version string lives in `config.py`/app metadata + `--version`. Confirm and bump each batch.
- Commits stay local until the user asks to push to GitHub. Co-author trailer per house style.

## Cross-cutting note: folder rename already broke config (item 20 is urgent)

The exe folder was renamed `C:\Desktop\Osu` → `C:\Desktop\osu_archiver`, but `config.json` still points every
path at the old `C:\Desktop\Osu\...`. This is exactly the failure item 20 must self-heal. It is the FIRST task
of v0.3.0. (The persistent-memory dir also moved: `...\projects\C--Desktop-Osu\` → `...\C--Desktop-osu-archiver\`.)

---

## v0.3.0 — Critical fixes  (items 20, 4, 5, 6, 7, 9)

### 20 — Folder self-heal + path warning (FIRST)
- On startup, after loading `config.json`, validate every working dir (`packs/output/library/data/logs`, and `root`).
- For any missing dir, look for a same-named folder **next to the exe / repo root** (`<base>/Packs`, `<base>/Output`,
  `<base>/Library`, `<base>/data`, `<base>/logs`).
  - **All/most found next to the exe** → show a confirmation dialog: *"Belirtilen konumda klasörler yok.
    Şu an burada bulunan bu klasörleri yeni konum olarak ayarlayayım mı?"* → on confirm, rebase config paths to the
    exe-adjacent locations and save.
  - **Not found anywhere** → offer to create a fresh structure next to the exe (first-run behavior), or let the user
    Browse to pick a root.
- Derive dependent artifacts from the rebased root: `data/tracking.xlsx` ("open logs Excel"), `data/memory.db`,
  `logs/`. Any lost-location action (e.g. "Open logs") must re-resolve from current config, and if the normal
  expected location has the file, auto-select it; otherwise show a specific warning, not a silent failure.
- Show a startup toast/summary of what was re-pointed.
- **Design principle:** treat `root` as the single source of truth; store child dirs as derived-but-overridable.
  When `root` is stale, offer to rebase; keep explicit per-dir overrides working.

### 4 — Empty Packs handling + native picker (+ macOS note)
- "Unpack Archives" with an empty `Packs/` (or none) → friendly message:
  *"Packs klasörü boş. Doldurup tekrar deneyin, ya da bir klasör/dosya seçin."* with a **Browse…** button that
  opens the native `QFileDialog` (folder or archive files). Chosen source is unpacked in place / copied in.
- `QFileDialog` is cross-platform → macOS gets its native dialog for free (documented for the future).
- File-type filter starts as `*.zip`; expands to all supported formats in item 24.

### 5 — Friendly, specific button error states
- "Import to osu!" on empty `Output/` → clear message ("Output klasörü boş; önce arşiv açın / kütüphaneden gönderin"),
  not a raw "Output is empty".
- Audit every action button (Unpack, Copy to Library, Import, Refresh, Update reference) for specific empty/error
  messages instead of generic strings.

### 6 — Auto-copy to Library after unpack actually runs
- The `auto_backup_after_extract` (a.k.a. "Auto-Copy to library after unpacking") setting is ON but copy doesn't run
  automatically after Unpack. Fix the orchestration so extract → (if setting) copy-to-Library is chained in one flow.

### 7 — Remove "Clear output after import to osu!"
- Remove the `clear_output_after_import` option from Settings UI and stop honoring it (files vanish after import
  anyway). Migrate config gracefully (ignore stale key).

### 9 — Verify BPM/length backfill
- Investigate the "durations/BPM were empty then filled" observation. Expected cause: **"Refresh Library Data"**
  backfilled metadata from the `.osz` files. Confirm it's deterministic/idempotent; document. Code change only if a
  real bug surfaces.

---

## v0.4.0 — Search & tables  (items 10, 11-search, 3, 13, 22, 8, 12, 14)

### 10 — Search performance / freeze (must run on low-end HW)
- Symptom: typing freezes the app after a few chars (e.g. "hardc" ok → "hardco" spikes CPU/hangs).
- Likely cause: per-keystroke synchronous ranking over all 1146+ tracks on the UI thread, rapidfuzz scoring the full
  set, no debounce, table fully rebuilt each keystroke.
- Fixes (layered): **debounce** input (~150–250 ms); run ranking **off the UI thread** (worker) or make it cheap;
  cheap prefix/substring pre-filter BEFORE any rapidfuzz; cache the candidate corpus; virtualize/limit rows rendered;
  drop stale results if a newer keystroke arrived. Target: smooth on a basic machine.

### 11 (search part) — List even when the box is empty
- Empty query → show all tracks (virtualized/limited), so the user can browse the whole library. Depends on the
  perf/virtualization work above.

### 3 — Double-click a cell → copy that specific cell
- Keep single-click = clean name+artist. Add **double-click on any cell** (ID, Source, BPM, …) → copy that exact
  cell value.

### 13 — Multi-select → copy names only (newline-separated)
- Selecting multiple rows and copying yields **just the names, one per line** — distinct from the existing Ctrl+C
  (TSV of full rows). Likely a dedicated shortcut/menu action.

### 22 — Column sizing without manual resize
- Tables must lay out sensibly on first render and on window changes: Name column **Stretch**, others
  **ResizeToContents**/interactive, sane minimums; no more "name column tiny until I drag the window".

### 8 — Compute Code & Mode for red/missing rows
- In Archives/Packs, fill **Code** from series+number and **Mode** from series/session so missing (red) rows aren't
  blank. Reuse `parsing.py` conventions.

### 12 — Dashboard "possibly missing" → jump to filtered Archives
- Clicking the Dashboard "possibly missing" section navigates to the Archives/Packs tab with a **"show only missing"**
  filter applied (add that filter option to the tab).

### 14 — Artists tab sort options
- Add sorts: **longest average length**, **longest BPM**, and their reverses (shortest avg, lowest BPM).

---

## v0.5.0 — Theme & icon design  (items 2, 23, 19)

### 2 — Pink-Light must differ from White
- Pink-Light currently reads like White (the user's desktop is pink, compounding it). Push more pink tint into the
  Pink-Light palette so it's clearly distinct from White.

### 23 — Add "Pink Darker" theme
- New palette "Pink Darker" (darker than Pink-Dark) in `theming.py`/`config.THEMES`.

### 19 — Icon design (the ~20 concepts)
- Produce ~20 icon concepts combining **osu-pink + Rose + Round + Question-mark**. Present in a shareable gallery
  (Artifact) for the user to choose ONE.
- Default approach: hand-authored **SVG** concepts (crisp, themeable) rendered to PNG for preview; chosen concept
  baked into `assets/` `icon.ico` + `icon.png` + `splash.png`, wired into window/taskbar. Add an SVG→ICO step to
  `make_icon.py`. Only add an image-gen MCP/skill if SVG proves insufficient.

---

## v0.6.0 — Confirm UX & archive variety  (items 16, 17, 18, 24, 25)

### 16 — Mouse-wheel guard on multi-option controls
- Settings combos change on accidental wheel scroll. Install an event filter so a control **ignores wheel unless
  deliberately engaged**; when the user does scroll it, **expand to reveal all options** with a ~100 ms delay so an
  accidental change is noticeable and reversible. Apply to all risky multi-option controls.

### 17 — Physical-copy delete: confirm + perceived-3s/real-4.2s countdown
- Unchecking "keep physical .osz copy in Library" → confirmation dialog stating files WILL be deleted; a countdown the
  user reads as **3-2-1** but that actually gates the confirm button for **~4.2 s** (perceived 3 s, real >4 s).

### 18 — osu! import close-warning
- After packs are sent to osu!, show: *"İşlem bitene kadar osu!'yu kapatmayın; UI'ı kapatabilirsiniz."*

### 24 — More archive formats
- Unpack rar/7z/tar/etc., not just zip. Add a dependency (candidates: `patool`+backends, `py7zr`, `rarfile`+unrar,
  or `libarchive`) — pick one that bundles cleanly in PyInstaller. Native picker filter lists all supported formats.

### 25 — Archives containing non-music files → separate section
- After extracting the `.osz`/music out of an archive, if the archive also held non-music files (txt, images, etc.),
  flag it into a distinct **"archives with extra files"** section/list (music still extracted normally).

---

## v0.7.0 — Auto-import from installed osu! (item 15)  — research done

Detect installs; turn installed beatmapsets into `.osz` in the Library, dedup by beatmapset id.

- **osu!(stable) — straightforward, pure Python:** detect `%LOCALAPPDATA%\osu!\osu!.exe`; read `BeatmapDirectory`
  from `osu!.<winuser>.cfg` (fallback `<install>\Songs`). Enumerate Songs/ folders (`{id} {Artist} - {Title}`);
  id from folder-name numeric prefix, fallback to `.osu` `BeatmapSetID` (reuse `osz_meta.py`). Zip folder **contents**
  at archive root, **preserving nested subfolders** (storyboard/skin) and UTF-8 names → `.osz` → existing dedup.
- **osu!lazer — hard:** data dir `%APPDATA%\osu` (Roaming; independent of the lazer exe path, relocatable — check for
  `client.realm` separately). Files are a SHA-256 content store; `client.realm` (Realm DB, schema ~51, migrating)
  maps sets→files+original names. **No Python Realm reader exists**; peppy will never ship first-party batch export.
  - **Phase 1 (ship with v0.7):** add a generic **"import a folder of .osz/.olz into Library"** action, and in
    Settings guide the user to run a free third-party exporter (e.g. BeatmapExporter) once, then point us at its
    export folder.
  - **Phase 2 (optional, later):** a small **separately-compiled .NET console helper** using `realm-dotnet`
    (dynamic schema) reads `client.realm` + `files/` → emits `.osz`/manifest; invoked via `subprocess` from the exe.
    Treat as recurring maintenance tied to lazer's schema. Decide at v0.7 time whether to attempt Phase 2.
- **osu-vs-library comparison (bridges item 11):** with client contents readable, compute the set difference and tag
  tracks: **"osu'da kayıtlı" / "library'de kayıtlı" / both**, and surface counts (e.g. 2400 vs 2200).

---

## v0.8.0 — Google Drive sync (item 11)  — research done, its own detailed plan

Single-user, multi-device ("GitHub-like push/pull"). End users do **not** create a Google Cloud project.

- **Auth:** OAuth 2.0 **Desktop-app** client, loopback redirect + **PKCE(S256)**, one shared `client_id/secret`
  embedded in the exe (accepted for installed apps; PKCE is the real defense). Consent screen **published to
  Production** (self-serve/instant because the scope is non-sensitive) to avoid the Testing 100-user cap and the
  7-day refresh-token expiry. Developer does the one-time Cloud Console setup.
- **Scope:** `drive.file` only (app sees only files it created — privacy; works across devices under same account).
- **Libraries:** `google-auth` + `google-auth-oauthlib` for the auth dance only; hand-roll the ~6 Drive REST calls
  with `requests`. **Avoid `google-api-python-client`** (recurring PyInstaller breakage).
- **Sync model:** content-addressed **manifest** table in `data/memory.db`
  (`beatmapset_id` → sha256 `content_hash` → `drive_file_id` → `remote_hash` → `state ∈
  {local_only, synced, cloud_only, conflict}`), mirrored into each file's Drive **`appProperties`** so a fresh device
  rebuilds the manifest from Drive alone. Push = upload new/changed by hash diff; Pull = download missing.
- **"Remove local, keep metadata, download on demand" (explicit user ask):** local delete flips the manifest row to
  **`cloud_only`** (tombstone, not deletion); UI shows a cloud badge + "download" affordance; metadata stays visible.
- **Immutability:** `.osz` treated as immutable blobs → conflicts reduce to "deleted on A / present on B"; no 3-way
  merge needed for v1.
- **Large files:** **resumable uploads**, 8–16 MiB chunks, retry/resume on drop, modest parallelism (3–5). Bottleneck
  is home upload bandwidth, not API quota.
- **Token storage:** `keyring` (Windows Credential Manager now; macOS Keychain later, same API). Persist refresh
  token only.
- **⚠ Biggest risk — storage ceiling:** consumer free Google storage is **15 GB** (→ **5 GB** for new/unverified-phone
  accounts, May 2026), shared with Gmail/Photos. An **11 GB+** library nearly fills it. UI must show available
  headroom before a push and suggest Google One as an option. Design around this from day one.
- **Developer one-time steps:** create Cloud project → configure consent screen (External, scope `drive.file`) →
  create Desktop-app OAuth client → **Publish to Production** → embed `client_id/secret` → ship.

---

## Final — item 26: end-to-end verification report

After the features land, verify the whole journey: install exe → archive all osu! songs → upload to Drive → on a
second machine, same Drive login → pull → auto-install. Document where it works, where it fails, and remedies.
(Depends on v0.7 + v0.8.)

## Open decisions deferred to their phase (re-confirm when we get there)

- **v0.6 item 24:** which archive-format library to depend on (bundling-friendliness decides).
- **v0.7 item 15:** whether to attempt lazer Phase 2 (.NET helper) now or ship Phase-1 fallback only.
- **v0.8 item 11:** Google storage ceiling strategy (accept 15 GB, or design "cloud-only offload" as the primary mode
  so local footprint stays small); confirm we ship one shared OAuth client (developer registers it).

## Testing / verification per batch

Extend the existing pytest suite (25 passing) with unit tests for each new pure-logic piece (path rebasing, gap
Code/Mode computation, search perf pre-filter, artist sort keys, manifest diffing). Headless Qt smoke for UI wiring.
Run the real 1146-track DB where relevant. No success claim without running the verification (evidence first).
