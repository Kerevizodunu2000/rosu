using System.IO.Compression;
using Realms;

// Usage: RosuLazerExport <lazer-data-dir> <output-dir>
// Reads <data>/client.realm (dynamic + read-only, so no schema-version tracking)
// and rebuilds each submitted beatmapset into <output>/<id> Artist - Title.osz by
// pairing every RealmNamedFileUsage.Filename with its content in <data>/files/.
if (args.Length < 2)
{
    Console.Error.WriteLine("usage: RosuLazerExport <lazer-data-dir> <output-dir>");
    return 2;
}

string dataDir = args[0];
string outDir = args[1];
// optional 3rd arg: stop after N sets (for quick validation)
int limit = args.Length >= 3 && int.TryParse(args[2], out var l) ? l : int.MaxValue;
string realmPath = Path.Combine(dataDir, "client.realm");
string filesRoot = Path.Combine(dataDir, "files");

if (!File.Exists(realmPath))
{
    Console.Error.WriteLine($"client.realm not found at: {realmPath}");
    return 3;
}
Directory.CreateDirectory(outDir);

var config = new RealmConfiguration(realmPath) { IsDynamic = true, IsReadOnly = true };
Realm realm;
try
{
    realm = Realm.GetInstance(config);
}
catch (Exception ex)
{
    Console.Error.WriteLine("Could not open client.realm (close osu!lazer and try again): " + ex.Message);
    return 4;
}

int exported = 0, skipped = 0, missingFiles = 0;
using (realm)
{
    var sets = realm.DynamicApi.All("BeatmapSet").Filter("DeletePending == false");
    foreach (var setObj in sets)
    {
        dynamic set = setObj;

        int onlineId;
        try { onlineId = (int)set.OnlineID; }
        catch { onlineId = -1; }
        if (onlineId <= 0) { skipped++; continue; }   // unsubmitted/local sets have no id

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

        string baseName = Sanitize($"{onlineId} {artist} - {title}".Trim());
        if (string.IsNullOrWhiteSpace(baseName)) baseName = onlineId.ToString();
        string oszPath = Path.Combine(outDir, baseName + ".osz");
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
                    string src = Path.Combine(filesRoot, hash.Substring(0, 1),
                                              hash.Substring(0, 2), hash);
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
            exported++;
            Console.WriteLine($"EXPORT {onlineId}");   // one line per set -> progress
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

static string Sanitize(string s)
{
    foreach (char c in Path.GetInvalidFileNameChars())
        s = s.Replace(c, '_');
    return s.Trim();
}
