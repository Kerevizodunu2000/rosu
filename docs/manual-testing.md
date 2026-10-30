# Rosu manual testing handoff (v2.0 line)

This file is for the owner and for the Claude Code session on the owner's Windows PC.
The cloud factory built and merged the features below with offline tests and Windows CI.
CI cannot click through the real app, touch a real Google account, or fill a real disk.
Those checks are listed here.

> [!IMPORTANT]
> **Instructions for Claude Code on the owner's PC**
> - Work on **copies**. Use a scratch Packs/Output/Library folder and a **backed-up**
>   osu! install. Never point a destructive test at the owner's real Songs folder or
>   lazer data folder without a backup.
> - Never commit `config.json`, `rosu/drive/oauth_client.json`, `rosu/report_token.txt`,
>   `docs/client_secret_*.json`, any `.env` file, or `Settings-2.png`. Never paste
>   secrets, tokens, the owner's name, e-mail or Windows user path into an issue,
>   commit or screenshot. Crop or blur screenshots.
> - Don't push to `main` and don't create tags or releases. Report each problem as a
>   GitHub issue labeled `factory` (template at the end). The cloud factory fixes it.
> - Commits, if any, use the owner's git identity with no `Co-Authored-By` or other
>   trailers.

## 1. What changed since the last plan

The plan moved a lot in this round:

- **Rust:** measured first, as the rule says. The PyO3 module reached only 1.78x on
  metadata reads and 1.0x on extraction, without the profiler. That is below the merge
  bar, so it is parked on branch `parked/rust-osu-core` and the app stays pure Python.
  The hot paths got Python fixes instead: an index, sorting and an `.osu` overflow fix.
- **New, from owner requests:**
  - signed automatic updates, plus a notice after an update and a restart that waits
    for running tasks
  - disk-space checks everywhere and a Dashboard **Disks** card
  - Google Drive storage quota in Settings
- **Data-safety work:**
  - Recycle Bin guards. Nothing is deleted for good on removable or network drives,
    or when a file is too large for the Recycle Bin.
  - Safer Unpack, Import and Remove.
- **Accessibility:** light-theme contrast now meets WCAG, and disabled controls have
  their own look.
- **Build and CI:**
  - The packaged exe now carries the right 7z BCJ module, and `--selftest` checks the
    codecs.
  - The CI token is read-only, except for the release job.
  - Build secrets are only given to tag builds (PR #66, if merged).
- **Docs:** both READMEs were rewritten (animated banner, screenshots, current features).
- **Still queued:**
  - #62: space check for the client-to-client transfer stage
  - #27, #17–#21: larger items, which may be split
  - rosu-web #31: server-side `html lang`
  - the v2.0 usability audit and polish, then the web 2.0 visuals

## 2. Owner-only steps (settings and keys, not code)

Do these in the browser or the terminal. Claude Code can guide you, but must never see
or store the secret values.

- [ ] **Auto-update signing key.** Until this is done, auto-update stays off and the old
      "new version" banner shows.
      1. On your PC, in the repo: `python tools/update_key.py keygen`.
      2. Put the **seed** into a GitHub secret named `ROSU_UPDATE_SIGNING_KEY`. Store it
         in a password manager, never in a file in the repo.
      3. Put the **public key** hex into `UPDATE_PUBLIC_KEY = "..."` in `rosu/updater.py`
         and ship it in a normal PR. The public key is not secret.
- [ ] **GitHub Environment.** Create an Environment, for example `release`, in Settings →
      Environments.
      - Deployment branches/tags: only tags matching `v*`.
      - Required reviewer: yourself.
      - Move `ROSU_UPDATE_SIGNING_KEY`, `ROSU_OAUTH_CLIENT_JSON` and `ROSU_REPORT_TOKEN`
        into it.
      - Then ask the factory to add `environment: release` to the jobs that use them.
- [ ] **Google OAuth app:** set the publishing status to **In production**, so tokens
      don't expire after 7 days.
- [ ] **`ROSU_REPORT_TOKEN`** secret set (in-app bug reports).
- [ ] **GitHub security settings:** turn on secret scanning, push protection,
      Dependabot alerts, and private vulnerability reporting.
- [ ] **SignPath** (free code signing for open source): apply if you want SmartScreen
      warnings to go away.
- [ ] **rosu-web admin:** log in once with your password and TOTP after the CSP change,
      to confirm the admin panel still works.
- [ ] **Test tag in a fork** (optional): push a tag such as `v0.0.0-test` in a fork. Check
      that the `release` job runs and that the embed steps run only there.

## 3. Set up the PC (Claude Code: do this first)

Needed:
- Windows 10/11
- Git
- Python **3.14**. CI uses 3.14; 3.13 also works. Use the `py` launcher.
- 7-Zip, to make test archives
- osu!(stable) and/or osu!lazer, backed up
- a USB stick (a removable drive has no Recycle Bin)
- a Google account for the Drive tests

```powershell
git clone https://github.com/Kerevizodunu2000/rosu.git
cd rosu
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest tests -q          # expect all passed, a few skipped
python run.py                      # run the app from source
```

Build the exe and smoke-test it the same way CI does:

```powershell
pyinstaller rosu.spec
$p = Start-Process -FilePath dist\rosu.exe -ArgumentList '--selftest' -Wait -PassThru
"selftest exit code: $($p.ExitCode)"   # must be 0
```

Optional test data:
- a large fake library: `python tools/make_big_library.py --help`
- a 7z with the BCJ filter: `7z a -t7z test-bcj.7z SomeProgram.exe`. 7-Zip applies BCJ
  to .exe files by default. Put a real `.osz` next to it in the same archive so Rosu has
  something to extract.

**A small disk for disk-full tests.** Open Disk Management, choose Action → Create VHD,
and make a **fixed-size VHDX of about 300 MB**. Initialize it, format it NTFS, and give
it a letter, for example `R:`. It is a fixed disk, so it has a Recycle Bin. A USB stick
covers the "no Recycle Bin" case.

## 4. Test checklist

Tick each item. If something fails, file an issue (section 5).

### 4.1 Packaged exe
- [ ] `rosu.exe --selftest` exits 0 (above).
- [ ] Unpack a pack that contains `test-bcj.7z` in the **exe**, not from source. It
      extracts without a codec error.

### 4.2 Disk space
- [ ] **Unpack** to Output on `R:`, with more data than `R:` can hold. It refuses before
      writing and names the drive, the space needed and the space free.
- [ ] **Copy to Library** onto `R:` when it is nearly full. Same refusal. If `R:` fills
      up during the run, it stops with "disk full", keeps the finished beatmaps, and
      leaves the archive in Packs.
- [ ] **Export** to `R:`. It refuses up front. Then make `R:` fill up during the run: the
      finished archives stay, there is no `.part` leftover, and nothing is uploaded.
- [ ] **Import to osu!** with the osu! drive nearly full. It refuses and sends nothing.
- [ ] **Shortcuts → Unpack and import** with a short drive. The job shows as failed, the
      send steps are struck through, and the tooltip is in your language.
- [ ] **Dashboard → Disks card:**
  - [ ] one row per drive (Packs, Output, Library, Songs, lazer)
  - [ ] used, total and free, plus a bar
  - [ ] `R:` nearly full shows a **"Low space"** badge
  - [ ] an unplugged USB folder shows "can't read"
  - [ ] the card looks right in both languages and in a light and a dark theme
- [ ] Export from **osu!lazer** or **stable** with a tiny temp drive. Set TEMP to `R:` for
      the test. It refuses before re-exporting, and nothing is written.

### 4.3 Recycle Bin guards (use the USB stick)
- [ ] Put the Library on the USB stick, then **remove duplicates** and **turn off the
      physical copy**. Nothing is deleted; Rosu says there is no Recycle Bin.
- [ ] **Remove from osu!(stable)** with Songs on a drive without a Recycle Bin, including
      with "Save to Library, then remove". It refuses and removes nothing.
- [ ] Remove a file bigger than the Recycle Bin's size limit. Shrink the limit in Recycle
      Bin properties for the test. It is kept, not deleted for good.
- [ ] Turn the Recycle Bin off for a drive in its properties. That drive is treated as
      having no Recycle Bin.

### 4.4 Google Drive (real account)
- [ ] Connect Drive in Settings. The storage line shows used/total, Rosu's folder and
      trash. If your Google account has a 403 or a scope issue, the line simply hides.
      It must never ask for a wider scope.
- [ ] Back up with more data than the free Drive space. It refuses up front with
      needed/free and a hint to empty the trash.
- [ ] If you can, fill Drive during a backup. It stops with "Drive is full", and the
      chunks already uploaded stay and are recorded.

### 4.5 Auto-update (after the signing key, section 2)
- [ ] Release v N (with the public key in it) and then v N+1. These are owner tags; the
      factory never tags. Install v N in a **writable** folder, not Program Files.
- [ ] Start v N. The banner shows the download progress, then "ready" and **Restart
      now**.
- [ ] Press Restart now while a task runs. It arms; **Cancel restart** disarms it. Let
      it run: it restarts once the task ends.
- [ ] After the restart, the notice says once that v N+1 was installed, with up to 3
      lines of notes, and **Dismiss** works.
- [ ] Turn off **Install updates automatically**. Only the old banner shows.
- [ ] Rollback (advanced): make v N+1 fail on start. The next start goes back to v N
      and skips N+1.

### 4.6 Look and feel
- [ ] In the White, Pink · Light, Catppuccin Latte and Solarized Light themes, the
      status text, buttons, progress bars and selected rows are easy to read.
- [ ] Disabled checkboxes, radio buttons and buttons look clearly disabled in every
      theme, and their size doesn't jump.
- [ ] The Shortcuts tab fits a 1280×760 window without clipping. It was close before;
      report it if not.

### 4.7 Website (rosu-web)
- [ ] https://rosu-web.vercel.app in EN, `/tr` and `/ja`: the language switch works.
- [ ] `/tools`: Missing packs, Share card and Wrapped work offline in the browser.
- [ ] Send a test bug report and check that its status link works.
- [ ] The admin panel login works (section 2).

## 5. Reporting a problem

One issue per problem, labeled `factory`, in English:

```
Title: <area>: <what is wrong, in a few words>

Steps: 1. ... 2. ... 3. ...
Expected: ...
Actual: ...
Version / build: v... or commit ..., source or exe
Windows version, theme, language:
Logs tab lines (no personal paths or names):
Screenshot: cropped, nothing personal
```

The cloud factory picks up `factory` issues, fixes them through review, and merges.
