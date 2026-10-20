using System.IO.Compression;
using System.Text;
using Realms;

// RosuLazerExport — Rosu's bridge to osu!lazer's client.realm + files/ store.
//
//   RosuLazerExport --capabilities                   -> "CAPS export list delete"
//   RosuLazerExport list   <data-dir>                -> "SET\t<id>\t<bytes>\t<name>" per set
//   RosuLazerExport export <data-dir> <out-dir> [--ids <file>] [--limit N]
//                                                    -> "TOTAL <n>", then "EXPORT <id>\t<file>" per set
//   RosuLazerExport delete <data-dir> <ids-file>     -> "DELETED <id>" per set
//   RosuLazerExport <data-dir> <out-dir> [limit]     (legacy form = export)
//
// Everything except `delete` opens the Realm dynamic + READ-ONLY, so no schema
// tracking and no write. `delete` is the one writer, and it only ever flips the
// same DeletePending flag lazer's own "delete" uses (lazer purges those sets and
// their now-unreferenced files on its next start). It never touches files/:
// lazer shares one stored copy between every set with a byte-identical file.
// Before writing, `delete` (1) proves the file opens read-only — i.e. this
// helper's Realm needs no file-format upgrade, so the write cannot leave a file
// lazer is unable to open — and (2) copies client.realm aside as an undo path
// (the newest few are kept; lazer purges the sets on its next start anyway).

// Rosu reads stdout/stderr as UTF-8; the console default on Windows is the OEM
// code page, which would garble (or fail to decode) non-ASCII artist names.
Console.OutputEncoding = new UTF8Encoding(false);

string[] caps = { "export", "list", "delete" };
if (args.Length == 1 && args[0] == "--capabilities")
{
    Console.WriteLine("CAPS " + string.Join(" ", caps));
    return 0;
}
if (args.Length >= 1 && args[0] == "list")
    return args.Length >= 2 ? List(args[1]) : Usage();
if (args.Length >= 1 && args[0] == "delete")
    return args.Length >= 3 ? Delete(args[1], args[2]) : Usage();
if (args.Length >= 1 && args[0] == "export")
{
    if (args.Length < 3) return Usage();
    HashSet<int> ids = null;
    int lim = int.MaxValue;
    for (int i = 3; i < args.Length - 1; i++)
    {
        if (args[i] == "--ids") ids = ReadIds(args[i + 1]);
        else if (args[i] == "--limit" && int.TryParse(args[i + 1], out var n) && n > 0) lim = n;
    }
    if (ids != null && ids.Count == 0) { Console.Error.WriteLine("no ids to export"); return 5; }
    return Export(args[1], args[2], ids, lim);
}
if (args.Length >= 2)   // legacy: <data> <out> [limit]
    return Export(args[0], args[1], null,
                  args.Length >= 3 && int.TryParse(args[2], out var l) ? l : int.MaxValue);
return Usage();

static int Usage()
{
    Console.Error.WriteLine("usage: RosuLazerExport <lazer-data-dir> <output-dir> [maxSets]");
    Console.Error.WriteLine("       RosuLazerExport list <lazer-data-dir>");
    Console.Error.WriteLine("       RosuLazerExport export <lazer-data-dir> <output-dir> [--ids <file>] [--limit N]");
    Console.Error.WriteLine("       RosuLazerExport delete <lazer-data-dir> <ids-file>");
    return 2;
}

static Realm OpenReadOnly(string dataDir, out int code)
{
    code = 0;
    string realmPath = Path.Combine(dataDir, "client.realm");
    if (!File.Exists(realmPath))
    {
        Console.Error.WriteLine($"client.realm not found at: {realmPath}");
        code = 3;
        return null;
    }
    try
    {
        return Realm.GetInstance(new RealmConfiguration(realmPath) { IsDynamic = true, IsReadOnly = true });
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine("Could not open client.realm (close osu!lazer and try again): " + ex.Message);
        code = 4;
        return null;
    }
}

static int OnlineId(IRealmObject set)
{
    try { return set.DynamicApi.Get<int>("OnlineID"); }
    catch { return -1; }
}

static IQueryable<IRealmObject> LiveSets(Realm realm) =>
    realm.DynamicApi.All("BeatmapSet").Filter("DeletePending == false");

static string DisplayName(dynamic set, int onlineId)
{
    string artist = "", title = "";
    try
    {
        foreach (var bObj in set.Beatmaps)
        {
            dynamic b = bObj;
            var md = b.Metadata;
            artist = (string)(md.Artist ?? "");
            title = (string)(md.Title ?? "");
            break;
        }
    }
    catch { /* metadata optional; id-only name still dedups fine */ }
    string name = $"{artist} - {title}".Trim(' ', '-');
    return string.IsNullOrWhiteSpace(name) ? onlineId.ToString() : name;
}

static string StorePath(string filesRoot, string hash) =>
    Path.Combine(filesRoot, hash.Substring(0, 1), hash.Substring(0, 2), hash);

static HashSet<int> ReadIds(string path)
{
    var ids = new HashSet<int>();
    try
    {
        foreach (var line in File.ReadAllLines(path))
            if (int.TryParse(line.Trim(), out var id) && id > 0) ids.Add(id);
    }
    catch (Exception ex) { Console.Error.WriteLine("could not read ids: " + ex.Message); }
    return ids;
}

static int List(string dataDir)
{
    var realm = OpenReadOnly(dataDir, out int code);
    if (realm == null) return code;
    string filesRoot = Path.Combine(dataDir, "files");
    int listed = 0;
    using (realm)
    {
        foreach (var setObj in LiveSets(realm))
        {
            int onlineId = OnlineId(setObj);
            if (onlineId <= 0) continue;
            dynamic set = setObj;
            long bytes = 0;
            try
            {
                foreach (var fObj in set.Files)
                {
                    dynamic nfu = fObj;
                    string hash = (string)nfu.File.Hash;
                    if (string.IsNullOrEmpty(hash)) continue;
                    var fi = new FileInfo(StorePath(filesRoot, hash));
                    if (fi.Exists) bytes += fi.Length;
                }
            }
            catch { /* size is informational */ }
            string name = DisplayName(set, onlineId).Replace('\t', ' ').Replace('\n', ' ').Replace('\r', ' ');
            Console.WriteLine($"SET\t{onlineId}\t{bytes}\t{name}");
            listed++;
        }
    }
    Console.Error.WriteLine($"done listed={listed}");
    return 0;
}

static int Export(string dataDir, string outDir, HashSet<int> onlyIds, int limit)
{
    var realm = OpenReadOnly(dataDir, out int code);
    if (realm == null) return code;
    string filesRoot = Path.Combine(dataDir, "files");
    Directory.CreateDirectory(outDir);

    int exported = 0, skipped = 0, missingFiles = 0;
    // How many sets this run will look at, first — Rosu turns the EXPORT lines
    // into a real progress bar against it.
    int planned = 0;
    foreach (var setObj in LiveSets(realm))
    {
        int id = OnlineId(setObj);
        if (id > 0 && (onlyIds == null || onlyIds.Contains(id))) planned++;
    }
    Console.WriteLine($"TOTAL {Math.Min(planned, limit)}");
    // Two live sets can share an OnlineID (an edited copy, a re-import): each
    // gets its own file instead of the second overwriting the first.
    var writtenNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    using (realm)
    {
        foreach (var setObj in LiveSets(realm))
        {
            int onlineId = OnlineId(setObj);
            if (onlineId <= 0) { skipped++; continue; }   // unsubmitted/local sets have no id
            if (onlyIds != null && !onlyIds.Contains(onlineId)) continue;
            dynamic set = setObj;

            string dn = DisplayName(set, onlineId);
            string baseName = Sanitize(dn == onlineId.ToString() ? dn : $"{onlineId} {dn}");
            if (string.IsNullOrWhiteSpace(baseName)) baseName = onlineId.ToString();
            string fileName = baseName + ".osz";
            for (int n = 2; writtenNames.Contains(fileName); n++)
                fileName = $"{baseName} ({n}).osz";
            string oszPath = Path.Combine(outDir, fileName);
            string tmp = oszPath + ".part";

            try
            {
                int written = 0;
                using (var fs = File.Create(tmp))
                using (var zip = new ZipArchive(fs, ZipArchiveMode.Create))
                {
                    foreach (var fObj in set.Files)
                    {
                        dynamic nfu = fObj;
                        string fn = (string)nfu.Filename;
                        string hash = (string)nfu.File.Hash;
                        if (string.IsNullOrEmpty(fn) || string.IsNullOrEmpty(hash))
                            continue;
                        string src = StorePath(filesRoot, hash);
                        if (!File.Exists(src)) { missingFiles++; continue; }
                        var entry = zip.CreateEntry(fn.Replace('\\', '/'), CompressionLevel.Fastest);
                        using var es = entry.Open();
                        using var ss = File.OpenRead(src);
                        ss.CopyTo(es);
                        written++;
                    }
                }
                if (written == 0) { File.Delete(tmp); skipped++; continue; }
                if (File.Exists(oszPath)) File.Delete(oszPath);
                File.Move(tmp, oszPath);
                writtenNames.Add(fileName);
                exported++;
                Console.WriteLine($"EXPORT {onlineId}\t{fileName}");   // one line per set
                if (exported >= limit) break;
            }
            catch (Exception ex)
            {
                try { File.Delete(tmp); } catch { }
                Console.Error.WriteLine($"skip {onlineId}: {ex.Message}");
            }
        }
    }

    Console.Error.WriteLine($"done exported={exported} skipped={skipped} missingFiles={missingFiles}");
    return 0;
}

static int Delete(string dataDir, string idsFile)
{
    var ids = ReadIds(idsFile);
    if (ids.Count == 0) { Console.Error.WriteLine("no ids to delete"); return 5; }
    string realmPath = Path.Combine(dataDir, "client.realm");

    // 1. Read-only probe: if this fails, a writable open could need a file-format
    //    upgrade lazer may not understand — so stop before writing anything.
    int matched = 0;
    var probe = OpenReadOnly(dataDir, out int code);
    if (probe == null) return code;
    using (probe)
        foreach (var setObj in LiveSets(probe))
            if (ids.Contains(OnlineId(setObj))) matched++;
    if (matched == 0) { Console.Error.WriteLine("done deleted=0 (none of the ids are in lazer)"); return 0; }

    // 2. Undo path: a copy of the database as it was before this write.
    string backup = realmPath + ".rosu-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".bak";
    try { File.Copy(realmPath, backup, overwrite: false); }
    catch (Exception ex)
    {
        Console.Error.WriteLine("could not back up client.realm, nothing deleted: " + ex.Message);
        return 6;
    }
    Console.WriteLine("BACKUP " + backup);
    PruneBackups(realmPath, keep: 3);

    // 3. The write: flag the chosen sets exactly as lazer's own delete does.
    Realm realm;
    try { realm = Realm.GetInstance(new RealmConfiguration(realmPath) { IsDynamic = true }); }
    catch (Exception ex)
    {
        Console.Error.WriteLine("Could not open client.realm for writing (close osu!lazer and try again): " + ex.Message);
        return 4;
    }
    var deleted = new List<int>();
    using (realm)
    {
        try
        {
            realm.Write(() =>
            {
                foreach (var setObj in LiveSets(realm).ToList())
                {
                    int id = OnlineId(setObj);
                    if (!ids.Contains(id)) continue;
                    setObj.DynamicApi.Set("DeletePending", true);
                    deleted.Add(id);
                }
            });
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("delete failed, nothing changed: " + ex.Message);
            return 7;
        }
    }
    foreach (var id in deleted) Console.WriteLine($"DELETED {id}");
    Console.Error.WriteLine($"done deleted={deleted.Count}");
    return 0;
}

// Each backup is a full copy of client.realm; keep only the newest few.
static void PruneBackups(string realmPath, int keep)
{
    try
    {
        string dir = Path.GetDirectoryName(realmPath) ?? ".";
        var old = Directory.GetFiles(dir, Path.GetFileName(realmPath) + ".rosu-*.bak")
            .OrderByDescending(f => Path.GetFileName(f), StringComparer.Ordinal)
            .Skip(keep);
        foreach (var f in old)
            try { File.Delete(f); } catch { /* best effort */ }
    }
    catch { /* best effort: a failed cleanup never fails the delete */ }
}

static string Sanitize(string s)
{
    foreach (char c in Path.GetInvalidFileNameChars())
        s = s.Replace(c, '_');
    return s.Trim();
}
