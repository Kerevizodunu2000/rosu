# RosuLazerExport

Standalone .NET 8 helper for **Rosu**: Rosu's only bridge to osu!lazer's
`client.realm` database and its content-addressed `files/` store.

## Commands

```
RosuLazerExport --capabilities                    # "CAPS export list delete"
RosuLazerExport list   <lazer-data-dir>           # one "SET\t<id>\t<bytes>\t<name>" line per set
RosuLazerExport export <lazer-data-dir> <out-dir> [--ids <file>] [--limit N]
                                                   # "TOTAL <n>", then "EXPORT <id>\t<file name>" per set
RosuLazerExport delete <lazer-data-dir> <ids-file> # "BACKUP <path>" then "DELETED <id>" per set
RosuLazerExport <lazer-data-dir> <out-dir> [maxSets]   # legacy form = export
```

`<lazer-data-dir>` is the folder holding `client.realm` (default `%APPDATA%\osu`).
An ids file is one beatmapset id per line. Summaries go to stderr
(`done exported=… skipped=… missingFiles=…`, `done listed=…`, `done deleted=…`).
All output is UTF-8 (artist and title names are not limited to the console code
page). Close osu!lazer first.

* **`list` / `export`** open the Realm **dynamically + read-only** (`IsDynamic`,
  `IsReadOnly`), so they need no model classes, never track lazer's schema version
  and cannot write. For each `BeatmapSet` with `DeletePending == false`, `export`
  pairs every `RealmNamedFileUsage.Filename` with its content at
  `files/<hash[0]>/<hash[0..2]>/<hash>` and zips them into `<OnlineID> Artist - Title.osz`.
  Two live sets can share an OnlineID (an edited copy): the second becomes
  `… (2).osz` instead of overwriting the first.
* **`delete`** is the only writer, and it only sets `DeletePending = true` on the
  chosen sets — exactly what lazer's own "delete" does; lazer purges those sets and
  any now-unreferenced files itself on its next start. It never touches `files/`
  (one stored file is shared by every set containing those bytes). Before writing it
  1. opens the database **read-only** first — if this helper's Realm needed a
     file-format upgrade to open it, that fails and nothing is written (a writable
     open could otherwise leave a file lazer cannot read), and
  2. copies `client.realm` to `client.realm.rosu-<timestamp>.bak` next to it (the
     newest three are kept). With lazer closed, putting that copy back as
     `client.realm` undoes the deletion — but only until lazer starts again, because
     lazer purges the sets' files on start. That is why Rosu always saves lazer sets
     to the Library first and removes only those whose Library copy holds every
     difficulty byte for byte.

## Build

Requires the .NET 8 SDK. Produces a self-contained single-file exe (end users need
no .NET runtime):

```bash
dotnet publish -c Release
cp bin/Release/net8.0/win-x64/publish/RosuLazerExport.exe \
   ../../rosu/assets/lazer_export/RosuLazerExport.exe
```

The committed `rosu/assets/lazer_export/RosuLazerExport.exe` is that output;
Rosu bundles it (see `rosu.spec`) and invokes it from `rosu/services/import_svc.py`
(export) and `rosu/services/removal_svc.py` (list/delete).

## Before shipping a helper with `delete` (v1.8)

Rosu only offers *Remove from osu! → osu!lazer* when the bundled helper answers
`--capabilities` with `delete`. The committed binary predates the command, so the
feature stays disabled until a rebuilt helper has been verified on a real install:

1. Back up `%APPDATA%\osu` (the whole folder), close osu!lazer.
2. Build as above, then run `RosuLazerExport list %APPDATA%\osu` and pick two test sets
   (one with a non-ASCII artist, e.g. Björk, to check the UTF-8 output).
3. Put their ids in `ids.txt` and run `RosuLazerExport delete %APPDATA%\osu ids.txt`;
   it should print `BACKUP …` and two `DELETED` lines.
4. Start osu!lazer: the two sets must be gone, everything else intact, no errors.
   Close it, check `files/` shrank (the sets' unshared files are purged).
5. Undo test: close lazer, replace `client.realm` with the `.bak` copy, start lazer —
   the sets are back (their files may need a re-download if lazer already purged them).
6. Only then copy the new exe to `rosu/assets/lazer_export/` and commit it.
