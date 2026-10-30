# SPDX-License-Identifier: GPL-3.0-or-later
"""Time the slow paths of Rosu's service layer on a generated library.

    python tools/make_big_library.py TARGET --n 100000
    python tools/profile_library.py TARGET [--sample 1000] [--no-profile] [--json OUT.json] [--markdown OUT.md]

Runs on the folder made by ``make_big_library.py`` and nothing else: it refuses a
folder without that tool's marker, and a folder it has already profiled (the
``data/`` folder exists; regenerate with ``make_big_library.py --force``). Every file
it writes stays inside TARGET (databases, logs, the report workbook, ``Processed/``
with the pack zips, ``Exports/`` and a ``tmp/`` work folder). It imports only the
Qt-free service layer.

Each path is run once with cProfile and tracemalloc on, so the wall times include
that overhead: use them to rank the paths, not as absolute speeds. ``--no-profile``
times each path with ``time.perf_counter`` only (no peak memory, no top list), for
before/after speed comparisons. tracemalloc sees
Python allocations only, and cProfile sees only the calling thread. Paths run in
dependency order (refresh, then the reopen that is ``startup``, search, prescan,
extract, export, read_metadata, fingerprint) and are reported in the order of NAMES.
"""
from __future__ import annotations

import argparse
import cProfile
import json
import os
import platform
import pstats
import shutil
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rosu import beatmap, config, fingerprint, msd, ratings  # noqa: E402
from rosu.db import Database  # noqa: E402
from rosu.logsvc import LogService  # noqa: E402
from rosu.services import Services  # noqa: E402

MARKER = ".rosu-perf-library"
NAMES = ("startup", "refresh", "search", "prescan", "extract", "export",
         "read_metadata", "fingerprint")
# (query, search_tags): words come from the generator's word lists.
QUERIES = (("", False), ("artist=Neon", False), ("title=Dream", False),
           ("farm", True), ("star>4", False))


def _ram_gb() -> float | None:
    try:
        return round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2**30, 1)
    except (AttributeError, ValueError, OSError):
        pass
    try:   # Windows
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                        ("tpf", ctypes.c_ulonglong), ("apf", ctypes.c_ulonglong),
                        ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong),
                        ("ave", ctypes.c_ulonglong)]
        st = Status(length=ctypes.sizeof(Status))
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
        return round(st.total / 2**30, 1)
    except (AttributeError, OSError):
        return None


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def machine() -> str:
    ram = _ram_gb()
    return f"{_cpu_model()}, {os.cpu_count()} cores, {ram if ram else '?'} GB RAM"


def make_cfg(root: Path) -> config.Config:
    """The only way a Config is built here: rooted in the target, nothing leaves it."""
    cfg = config._fill_defaults(config.Config(root=str(root)))
    cfg.zip_disposal = "move"                  # packs go to <root>/Processed, not the bin
    cfg.clear_output_before_extract = False    # no bin either for Output's .osz files
    cfg.auto_backup_after_extract = False
    cfg.auto_prune = False
    cfg.export_prune = False
    return cfg


def open_services(root: Path):
    cfg = make_cfg(root)
    cfg.ensure_dirs()
    log = LogService(cfg.logs_path)
    db = Database(cfg.db_path)
    return cfg, db, Services(cfg, db, log)


def measure(name: str, fn, profile: bool = True):
    """Run ``fn()`` once under cProfile and tracemalloc → ``(entry, fn's value)``.

    With ``profile=False`` only the wall time is taken: peak memory ``None``, no top list.
    """
    if not profile:
        t0 = time.perf_counter()
        value = fn()
        return ({"name": name, "status": "ok", "wall_s": round(time.perf_counter() - t0, 4),
                 "peak_mem_bytes": None, "top": [], "detail": None}, value)
    prof = cProfile.Profile()
    tracemalloc.start(1)
    t0 = time.perf_counter()
    prof.enable()
    try:
        value = fn()
    finally:
        prof.disable()
        wall = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    rows = []
    for (path, line, func), (_cc, nc, _tt, ct, _callers) in pstats.Stats(prof).stats.items():
        if path == __file__ or "_lsprof" in func:   # the harness itself is not a finding
            continue
        rows.append((ct, f"{Path(path).name}:{line}({func})", nc))
    rows.sort(key=lambda r: r[0], reverse=True)
    top = [{"function": f, "ncalls": nc, "cumtime_s": round(ct, 4)} for ct, f, nc in rows[:10]]
    return ({"name": name, "status": "ok", "wall_s": round(wall, 4), "peak_mem_bytes": peak,
             "top": top, "detail": None}, value)


def skipped(name: str, reason: str) -> dict:
    return {"name": name, "status": "skipped", "wall_s": None, "peak_mem_bytes": None,
            "top": [], "detail": reason}


def run(target: Path, sample: int, profile: bool = True) -> tuple[int, int, list[dict]]:
    def timed(name, fn):
        return measure(name, fn, profile)

    tempfile.tempdir = str(target / "tmp")   # before any service: stages stay inside TARGET
    Path(tempfile.tempdir).mkdir(exist_ok=True)
    lib_files = sorted((target / "Library").glob("*.osz"))
    n = len(lib_files)
    sample = min(sample, n)
    results: dict[str, dict] = {}
    opened = []   # every Database, closed at the end
    try:
        cfg, db, svc = open_services(target)   # first open on the empty DB: not measured
        opened.append(db)
        results["refresh"], res = timed("refresh", svc.refresh)
        results["refresh"]["detail"] = res
        db.close()

        def reopen():
            c, d, s = open_services(target)
            opened.append(d)
            return c, d, s
        results["startup"], (cfg, db, svc) = timed("startup", reopen)
        results["startup"]["detail"] = {"reopened_after_refresh": True, "sets": n}

        def search():
            out = []
            for query, tags in QUERIES:
                t0 = time.perf_counter()
                page = svc.search_page(query, tags)
                out.append({"query": query or "(all)", "tags": tags, "rows": len(page["rows"]),
                            "total": page["total"], "wall_s": round(time.perf_counter() - t0, 4)})
            return out
        results["search"], res = timed("search", search)
        results["search"]["detail"] = res

        results["prescan"], plans = timed("prescan", svc.prescan_all)
        kinds: dict[str, int] = {}
        for p in plans:
            kinds[p.kind] = kinds.get(p.kind, 0) + 1
        results["prescan"]["detail"] = {"packs": len(plans), "kinds": kinds}

        approved = [(Path(p.zip_path), p.parsed) for p in plans]
        results["extract"], res = timed("extract", lambda: svc.extract(approved))
        results["extract"]["detail"] = {k: res[k] for k in ("packs", "tracks", "loose")}
        results["extract"]["detail"]["rejected"] = len(res["rejected"])

        dest = target / "Exports" / "sample"
        results["export"], res = timed(
            "export", lambda: svc.export_sets("library", dest, "zip", limit=sample))
        results["export"]["detail"] = {"count": res["count"], "archives": len(res["archives"])}

        def read_metadata():
            diffs_seen = 0
            for p in lib_files[:sample]:
                _meta, diffs, raw = beatmap.read_osz_full(p)
                ratings.stars_for_diffs(diffs, raw)
                msd.msd_for_diffs(diffs, raw)
                diffs_seen += len(diffs)
            return diffs_seen
        results["read_metadata"], res = timed("read_metadata", read_metadata)
        results["read_metadata"]["detail"] = {"sets": sample, "difficulties": res}

        if fingerprint.fpcalc_path() is None:
            results["fingerprint"] = skipped("fingerprint", "fpcalc not found")
        else:
            fp_root = target / "fingerprint_sample"
            fcfg, fdb, fsvc = open_services(fp_root)
            opened.append(fdb)
            for p in lib_files[:sample]:
                shutil.copyfile(p, fcfg.library_path / p.name)
            fsvc.refresh()   # setup, not measured
            entry, res = timed("fingerprint", fsvc.fingerprint_library)
            if "error" in res:
                entry = skipped("fingerprint", f"fingerprint_library: {res['error']}")
            elif res.get("computed", 0) == 0:
                entry = skipped("fingerprint", f"no fingerprint computed {res}")
            else:
                entry["detail"] = res
            results["fingerprint"] = entry
    finally:
        for d in opened:
            d.close()
    return n, sample, [results[name] for name in NAMES]


def _mem(b: int | None) -> str:
    return "-" if b is None else f"{b / 2**20:.1f} MiB"


def _wall(s: float | None) -> str:
    return "-" if s is None else f"{s:.2f} s"


def text_table(results: list[dict]) -> str:
    lines = [f"{'path':<14}{'status':<9}{'wall time':>12}{'peak memory':>14}"]
    lines += [f"{r['name']:<14}{r['status']:<9}{_wall(r['wall_s']):>12}{_mem(r['peak_mem_bytes']):>14}"
              for r in results]
    return "\n".join(lines)


def markdown(report: dict) -> str:
    out = [f"- Machine: {report['machine']}", f"- OS: {report['os']}",
           f"- Python: {report['python']}", f"- Library sets (N): {report['n']}",
           f"- Sample: {report['sample']}", "",
           "## Summary", "", "| Path | Status | Wall time | Peak memory | Detail |",
           "|---|---|---|---|---|"]
    for r in report["results"]:
        detail = json.dumps(r["detail"]).replace("|", "/") if r["detail"] is not None else ""
        out.append(f"| {r['name']} | {r['status']} | {_wall(r['wall_s'])} | "
                   f"{_mem(r['peak_mem_bytes'])} | {detail} |")
    for r in report["results"]:
        if r["status"] != "ok" or not r["top"]:   # skipped, or timed with --no-profile
            continue
        out += ["", f"## {r['name']}: top 10 by cumulative time", "",
                "| Function | Calls | Cumulative time |", "|---|---|---|"]
        out += [f"| `{t['function']}` | {t['ncalls']} | {t['cumtime_s']:.3f} s |" for t in r["top"]]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Profile Rosu's services on a generated library.")
    ap.add_argument("target", type=Path)
    ap.add_argument("--sample", type=int, default=1000,
                    help="sets for export, read_metadata and fingerprint (default 1000)")
    ap.add_argument("--no-profile", action="store_true",
                    help="time each path with perf_counter only (no cProfile, no tracemalloc)")
    ap.add_argument("--json", type=Path, metavar="PATH")
    ap.add_argument("--markdown", type=Path, metavar="PATH")
    args = ap.parse_args(argv)
    target = args.target.resolve()
    if not (target / MARKER).is_file():
        print(f"error: {target} has no {MARKER} marker: not a generated library", file=sys.stderr)
        return 2
    if (target / "data").exists():
        print(f"error: {target} was already profiled (data/ exists): regenerate it with "
              "make_big_library.py --force", file=sys.stderr)
        return 2
    n, sample, results = run(target, max(1, args.sample), profile=not args.no_profile)
    report = {"machine": machine(), "os": platform.platform(), "python": platform.python_version(),
              "n": n, "sample": sample, "results": results}
    print(text_table(results))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
