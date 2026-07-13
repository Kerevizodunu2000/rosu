# RosuLazerExport

Standalone .NET 8 helper for **Rosu**. Reads osu!lazer's `client.realm` + `files/`
content store and re-exports every submitted beatmapset as an `.osz` (item 15).

It opens the Realm **dynamically + read-only** (`IsDynamic = true`), so it needs no
model classes and doesn't have to track lazer's ever-incrementing `schema_version`.
For each `BeatmapSet` (where `DeletePending == false`) it pairs every
`RealmNamedFileUsage.Filename` with its content at
`files/<hash[0]>/<hash[0..2]>/<hash>` and zips them into `<OnlineID> Artist - Title.osz`.

## Build

Requires the .NET 8 SDK. Produces a self-contained single-file exe (end users need
no .NET runtime):

```bash
dotnet publish -c Release
cp bin/Release/net8.0/win-x64/publish/RosuLazerExport.exe \
   ../../osu_archiver/assets/lazer_export/RosuLazerExport.exe
```

The committed `osu_archiver/assets/lazer_export/RosuLazerExport.exe` is that output;
Rosu bundles it (see `rosu.spec`) and invokes it via `services.import_from_lazer`.

## Run

```
RosuLazerExport.exe <lazer-data-dir> <output-dir> [maxSets]
```

`<lazer-data-dir>` is the folder holding `client.realm` (default `%APPDATA%\osu`).
Prints `EXPORT <id>` per set to stdout and a `done exported=… skipped=… missingFiles=…`
summary to stderr. Close osu!lazer first for the most reliable read.
