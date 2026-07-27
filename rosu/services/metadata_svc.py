# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
import datetime as _dt
import threading
import time
from pathlib import Path

from .. import (
    archives, config, excel_report, extractor, gaps, jobs, library, osu_api,
    osu_import, parsing, search, db, msd, ratings
)
from ..models import ExtractPlan, ParsedPack

_CLIENT_LABEL = {"lazer": "osu!lazer", "stable": "osu!(stable)"}

def now_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()

def _sample_export(files, limit):
    if limit is None or limit <= 0 or len(files) <= limit:
        return files
    import random
    return random.sample(files, limit)


class MetadataMixin:
        def compute_ratings(self, progress=None, max_files: int | None = None) -> dict:
            """Compute local (rosu-pp) star ratings for every Library difficulty and
            store them, refreshing each set's ``star_min``/``star_max`` rollup.
    
            Shaped like :meth:`verify_library`: own cancel token, per-file progress,
            resumable. Never-scanned sets go FIRST, then sets that were scanned but
            still have no star (e.g. parsed before rosu-pp-py was installed) — so a
            re-run after installing the engine actually fills the gap. Returns
            ``{"error": "no_rosu_pp"}`` up front when the engine is unavailable (the
            difficulty rows themselves are still created at ingest / "Refresh Library").
            Otherwise ``{"scanned", "rated", "cancelled", "remaining"}``.
            """
            from .. import ratings
            from ..beatmap import read_osz_full
            if not ratings.available():
                return {"error": "no_rosu_pp"}
            self._ratings_cancel.clear()   # own token: never collides with other ops
            lib = self.cfg.library_path
            rows = [r for r in self.db.library_tracks()
                    if r.get("in_library") and r.get("filename")]
            unscanned = [r for r in rows if not r.get("diffs_scanned_at")]
            missing_star = [r for r in rows
                            if r.get("diffs_scanned_at") and r.get("star_max") is None]
            ordered = unscanned + missing_star
            total = len(ordered) if max_files is None else min(len(ordered), max_files)
            scanned = rated = 0
            cancelled = False
            # 'remaining' = pool items we never reached (cap/cancel). A missing file is
            # 'reached' (skipped, not remaining) so a full run always ends at 0 even
            # if some .osz vanished — re-running wouldn't process them anyway.
            remaining = 0
            for i, r in enumerate(ordered):
                if self._ratings_cancel.is_set():
                    cancelled = True
                    remaining = len(ordered) - i
                    break
                if max_files is not None and scanned >= max_files:
                    remaining = len(ordered) - i
                    break
                p = lib / r["filename"]
                if not p.exists():
                    continue
                _meta, diffs, raw = read_osz_full(p)
                stars = ratings.stars_for_diffs(diffs, raw)
                self.db.upsert_difficulties(r["id"], diffs, stars, now_iso())
                scanned += 1
                if any(v is not None for v in stars.values()):
                    rated += 1
                if progress:
                    progress({"kind": "ratings", "done": scanned, "total": total,
                              "name": r["filename"]})
            self.log.info("COMPUTE_RATINGS", scanned=scanned, rated=rated,
                          cancelled=cancelled, remaining=remaining)
            return {"scanned": scanned, "rated": rated, "cancelled": cancelled,
                    "remaining": remaining}

        def enrich_metadata(self, progress=None, max_calls: int | None = 500) -> dict:
            """Pull live osu!-API metadata (ranked status/dates, play & favourite
            counts, genre, language) plus a fallback star for every Library beatmapset.
    
            Shaped like :meth:`scan_lost_maps`: opt-in + creds-gated, own cancel token,
            never-checked sets first, capped at ``max_calls``, resumable. A successful
            fetch also refreshes ``availability`` (so this doubles as a lost-map scan);
            a 404 marks the set gone. Returns ``{"error": ...}`` when disabled/uncredited,
            else ``{"checked", "updated", "total", "remaining"}``.
            """
            if not self.cfg.enrich_from_api_enabled:
                return {"error": "disabled"}
            if not (self.cfg.osu_client_id and self.cfg.osu_client_secret):
                return {"error": "no_api"}
            self._enrich_cancel.clear()   # own token: never collides with other ops
            when = now_iso()
            rows = self.db.library_tracks()
            # Only the sets NOT yet enriched (api_checked_at IS NULL) — so the progress
            # total is the remaining work, not the whole library, and repeated runs walk
            # forward instead of re-fetching everything.
            unchecked = list(dict.fromkeys(
                r["beatmapset_id"] for r in rows
                if r.get("beatmapset_id") and not r.get("api_checked_at")))
            result = osu_api.beatmapset_details(
                unchecked, self.cfg.osu_client_id, self.cfg.osu_client_secret,
                progress=progress, max_calls=max_calls,
                cancel=self._enrich_cancel.is_set)
            updated = 0
            for bid, data in result.items():
                if data is None:
                    self.db.set_availability(bid, "gone")   # 404 = deleted/taken down
                else:
                    self.db.apply_api_enrichment(bid, data, when)
                    updated += 1
            remaining = max(0, len(unchecked) - len(result))
            self.log.info("ENRICH_METADATA", checked=len(result), updated=updated,
                          total=len(unchecked), remaining=remaining)
            return {"checked": len(result), "updated": updated,
                    "total": len(unchecked), "remaining": remaining}

        def cancel_enrich(self) -> None:
            """Cancel only an in-progress metadata enrichment (leaves other ops alone)."""
            self._enrich_cancel.set()

        def rating_status(self) -> dict:
            """Snapshot for the Search "Distribution" flow: how many in-Library sets
            exist, how many still lack a star, and whether the local engine is present.
            """
            from .. import ratings
            rows = self.db.library_tracks()
            inlib = len(rows)
            unrated = sum(1 for r in rows if r.get("star_max") is None)
            return {"in_library": inlib, "unrated": unrated,
                    "rated": inlib - unrated, "engine": ratings.available()}

        def star_histogram_data(self, scope: str = "library", bins: int = 20,
                                mode: str = "auto") -> dict:
            """Star distribution of the whole Library, binned **per difficulty**.

            Two things this is deliberately NOT: it is not built from the current
            search result (that described at most one capped page while claiming to
            be the library's distribution), and it does not bin ``tracks.star_max``
            (a set's hardest diff only — so a 2★+5★ set landed solely in the 5★
            bucket yet still matched a ``star>=2 star<2.5`` search).

            Returns ``{"bins", "difficulties", "sets", "pairs"}``: the bin tuples,
            how many rated difficulties were counted, how many distinct sets they
            live in, and the raw ``(track_id, star)`` pairs.

            ``pairs`` is what lets the caller answer "and how many SETS will
            searching this range list?" for an arbitrary dragged selection — that
            number is NOT the sum of the bars (one set spans several bars), and
            recomputing it in SQL on every drag event would hammer the DB. A few
            thousand tuples is nothing to hold.

            Synchronous: binning a few thousand floats is microseconds. ``scope``
            is ``"library"`` or ``"all"``; ``mode`` is a :data:`rosu.stats.MODES`
            value.
            """
            from .. import stats
            pairs = self.db.difficulty_stars(scope)
            values = [star for _tid, star in pairs]
            return {"bins": stats.histogram_bins(values, bins, mode),
                    "difficulties": len(values),
                    "sets": len({tid for tid, _star in pairs}),
                    "pairs": pairs}

        def compute_msd(self, progress=None, max_files: int | None = None) -> dict:
            """Compute the in-house Rosu Skillset Rating for every Library set's mania
            difficulties and store them (see :mod:`rosu.msd`).
    
            Shaped like :meth:`compute_ratings`: own cancel token, per-file progress,
            resumable. Never-scanned sets (``msd_scanned_at IS NULL``) go first; a
            visited set is stamped even when it holds no mania chart, so it is never
            re-scanned. Pure-Python — no engine gate (unlike star ratings). Returns
            ``{"scanned", "rated", "cancelled", "remaining"}`` where ``rated`` counts
            sets that yielded at least one mania skillset rating.
            """
            from .. import msd, ratings
            from ..beatmap import read_osz_full
            self._msd_cancel.clear()   # own token: never collides with other ops
            lib = self.cfg.library_path
            rows = [r for r in self.db.library_tracks()
                    if r.get("in_library") and r.get("filename")
                    and not r.get("msd_scanned_at")]
            total = len(rows) if max_files is None else min(len(rows), max_files)
            scanned = rated = 0
            cancelled = False
            remaining = 0
            for i, r in enumerate(rows):
                if self._msd_cancel.is_set():
                    cancelled = True
                    remaining = len(rows) - i
                    break
                if max_files is not None and scanned >= max_files:
                    remaining = len(rows) - i
                    break
                p = lib / r["filename"]
                if not p.exists():
                    continue
                _meta, diffs, raw = read_osz_full(p)
                # MSD attaches to the per-diff rows, which normally already exist (every
                # ingest path writes them). A set never diff-scanned (e.g. a pre-v1.5
                # import not yet refreshed) has none — create them now (stars filled if
                # rosu-pp is present, else left NULL for compute_ratings) so apply_msd has
                # rows to update; already-scanned sets keep their existing rows/stars.
                if not r.get("diffs_scanned_at"):
                    self.db.upsert_difficulties(
                        r["id"], diffs, ratings.stars_for_diffs(diffs, raw), now_iso())
                results = msd.msd_for_diffs(diffs, raw)
                self.db.apply_msd(r["id"], results, now_iso())
                scanned += 1
                if results:
                    rated += 1
                if progress:
                    progress({"kind": "msd", "done": scanned, "total": total,
                              "name": r["filename"]})
            self.log.info("COMPUTE_MSD", scanned=scanned, rated=rated,
                          cancelled=cancelled, remaining=remaining)
            return {"scanned": scanned, "rated": rated, "cancelled": cancelled,
                    "remaining": remaining}

        def cancel_msd(self) -> None:
            """Cancel only an in-progress skillset (MSD) scan (leaves other ops alone)."""
            self._msd_cancel.set()

        def msd_status(self) -> dict:
            """Snapshot for the skillset scan flow: in-Library sets and how many have
            not been MSD-scanned yet."""
            rows = self.db.library_tracks()
            inlib = len(rows)
            unscanned = sum(1 for r in rows if not r.get("msd_scanned_at"))
            return {"in_library": inlib, "unscanned": unscanned,
                    "scanned": inlib - unscanned}

        def mania_radar_for_track(self, track_id: int) -> dict | None:
            """Representative Rosu Skillset Rating for a set: its hardest rated mania
            difficulty (highest ``msd_overall``). Returns ``{overall, skills{...},
            version, keycount, source}`` or ``None`` when the set has no rated mania
            chart. Mirrors v1.5's "``star_max`` as the set's representative".
            """
            from ..models import MsdResult
            best = None
            for d in self.db.difficulties_for_track(track_id):
                if d.get("mode_int") != 3 or d.get("msd_overall") is None:
                    continue
                if best is None or d["msd_overall"] > best["msd_overall"]:
                    best = d
            if best is None:
                return None
            return {
                "overall": best["msd_overall"],
                "skills": {k: best.get(f"msd_{k}") or 0.0 for k in MsdResult.SKILLS},
                "version": best.get("version"), "keycount": best.get("keycount"),
                "source": best.get("msd_source"),
            }

        def mode_counts(self) -> dict:
            """{mode_display: set_count} over the Library — for the Search filters panel."""
            return self.db.mode_set_counts()

        def pack_skillset_summary(self, code: str) -> dict | None:
            """Aggregate Rosu Skillset profile for a pack (v1.6): the AVERAGE of its
            mania sets' representative (hardest-chart) radars, plus the peak overall and
            the mania-set count. ``None`` if the pack code is unknown; ``n == 0`` when the
            pack has no rated mania chart.
            """
            from .models import MsdResult
            pack = self.db.get_pack_by_code(code)
            if pack is None:
                return None
            rows = self.db.mania_msd_for_pack(pack["id"])
            # Per set, keep its hardest mania chart as the representative, then average.
            by_track: dict = {}
            for r in rows:
                cur = by_track.get(r["track_id"])
                if cur is None or r["msd_overall"] > cur["msd_overall"]:
                    by_track[r["track_id"]] = r
            reps = list(by_track.values())
            n = len(reps)
            if n == 0:
                return {"code": code, "n": 0, "overall": 0.0, "peak": 0.0,
                        "skills": {k: 0.0 for k in MsdResult.SKILLS}}
            skills = {k: sum((rep.get(f"msd_{k}") or 0.0) for rep in reps) / n
                      for k in MsdResult.SKILLS}
            return {"code": code, "n": n,
                    "overall": sum(rep["msd_overall"] for rep in reps) / n,
                    "peak": max(rep["msd_overall"] for rep in reps),
                    "skills": skills}

        def _reference(self):
            # Cached: the Packs tab / missing-gap banner ask for this once per series
            # in a loop; without the cache each call re-reads and re-parses
            # reference.json from disk on the UI thread (O(series) I/O).
            if self._reference_cache is None:
                self._reference_cache = osu_api.load_reference(self.cfg.reference_path)
            return self._reference_cache

        def reference_synced(self) -> bool:
            """Whether the authoritative osu! pack reference has been fetched — the
            UI upgrades "possibly missing" wording to a definite "missing" then."""
            return bool(self._reference())

        def update_reference(self, progress=None) -> dict:
            """Re-fetch the osu! pack reference. Cancellable, and a cancelled run
            is NOT saved — a half-fetched reference would silently turn real packs
            into "missing" reds on the Dashboard."""
            self._reference_cancel.clear()   # own token: never collides with other ops
            ref = osu_api.fetch_reference(
                self.cfg.osu_client_id, self.cfg.osu_client_secret,
                progress=(lambda s: progress(s)) if progress else None,
                cancel=self._reference_cancel.is_set)
            if ref.get("cancelled"):
                self.log.info("REFERENCE_SYNC", packs=ref.get("count", 0),
                              cancelled=True, saved=False)
                return ref
            osu_api.save_reference(ref, self.cfg.reference_path)
            self._reference_cache = None   # force a reload of the freshly-written reference
            self.log.info("REFERENCE_SYNC", packs=ref.get("count", 0))
            return ref

        def cancel_reference_sync(self) -> None:
            """Cancel only an in-progress reference sync (leaves other ops alone)."""
            self._reference_cancel.set()

        def scan_lost_maps(self, progress=None, max_calls: int | None = None) -> dict:
            """Flag owned beatmapsets that no longer exist on osu! (item F, v1.0).
    
            Needs osu! API credentials (returns ``{"error": "no_api"}`` otherwise).
            Asks the osu! API about each Library beatmapset id (HTTP 200 = still
            live, 404 = deleted/taken down). It walks the WHOLE library by default
            — the old 500-per-run cap meant a 1922-set library needed four manual
            runs to finish once, which read as the scan giving up. The run is
            gentle (paced + 429 backoff) and cancellable at any moment, so length
            is the user's choice rather than an arbitrary batch size; pass
            ``max_calls`` to cap it deliberately. **Never-checked sets go first**,
            then previously-checked ones (oldest knowledge re-verified). Stores
            each result and returns ``{"checked", "gone", "total", "remaining",
            "cancelled"}`` — ``remaining`` = never-checked sets still left.
            """
            if not (self.cfg.osu_client_id and self.cfg.osu_client_secret):
                return {"error": "no_api"}
            self._lostmap_cancel.clear()   # own token: never collides with import/Drive
            rows = self.db.library_tracks()
            unchecked = list(dict.fromkeys(
                r["beatmapset_id"] for r in rows
                if r.get("beatmapset_id") and not r.get("availability")))
            known = list(dict.fromkeys(
                r["beatmapset_id"] for r in rows
                if r.get("beatmapset_id") and r.get("availability")))
            result = osu_api.beatmapset_availability(
                unchecked + known, self.cfg.osu_client_id, self.cfg.osu_client_secret,
                progress=progress, max_calls=max_calls,
                cancel=self._lostmap_cancel.is_set)
            gone = 0
            for bid, status in result.items():
                self.db.set_availability(bid, status)
                if status == "gone":
                    gone += 1
            total = len(unchecked) + len(known)
            remaining = max(0, len(unchecked) - len(result))
            cancelled = self._lostmap_cancel.is_set()
            self.log.info("LOST_MAP_SCAN", checked=len(result), gone=gone,
                          total=total, remaining=remaining, cancelled=cancelled)
            return {"checked": len(result), "gone": gone, "total": total,
                    "remaining": remaining, "cancelled": cancelled}

        def cancel_lost_scan(self) -> None:
            """Cancel only an in-progress lost-map scan (leaves other ops alone)."""
            self._lostmap_cancel.set()

        def lost_map_count(self) -> int:
            return self.db.lost_map_count()

        def series_rows(self, series: str):
            """Confidence-aware rows for one series (present + any real red gaps)."""
            present = self.db.packs_for_series(series)
            category = present[0]["category"] if present else "Other"
            ref = osu_api.reference_by_series(self._reference()).get(series)
            return gaps.build_rows(series, category, present, ref)

        def pack_known(self, code: str) -> bool:
            """Whether a pack with this code is already recorded (the UI 'known'
            badge / purge-known list). Keeps the UI off the DB handle."""
            return self.db.get_pack_by_code(code) is not None

        def category_list(self) -> list[str]:
            """Distinct pack categories, for the Packs-tab filter combo."""
            return self.db.category_list()

        def packs_overview(self):
            """Every Packs-tab row: each series' confidence-aware gap rows plus the
            uncategorised 'Other' packs. Returns ``(category, GapRow, full_name|None)``
            tuples so the UI needs neither the DB handle nor gaps internals."""
            rows = []
            for s in self.db.series_list():
                present = self.db.packs_for_series(s)
                category = present[0]["category"] if present else "Other"
                code_full = {p["code"]: p["full_name"] for p in present}
                for gr in self.series_rows(s):
                    rows.append((category, gr, code_full.get(gr.code)))
            for p in self.db.packs_for_category("Other"):
                if p.get("series") is None:
                    rows.append(("Other", gaps._present_row(None, p), p["full_name"]))
            return rows

        def compute_missing(self) -> dict[str, list[int]]:
            """Confirmed-missing numbers per series (banner/log). Read-only.
    
            Only Standard series (or reference-validated series) contribute, so the
            banner never shows guessed reds.
            """
            numbered: dict[str, list[int]] = {}
            for s in self.db.series_list():
                for row in self.series_rows(s):
                    if not row.present and row.number is not None:
                        numbered.setdefault(s, []).append(row.number)
            return numbered

        def search(self, query: str, search_tags: bool = False,
                   progress=None, limit: int | None = None) -> list[dict]:
            """Ranked search, or the full name-sorted listing when the box is empty
            (item 11). ``search_tags`` opts into matching creator/tags too (off by
            default — it flooded results). ``progress`` is accepted so it can run in a
            Worker thread."""
            return self.search_page(query, search_tags, progress, limit)["rows"]

        def search_page(self, query: str, search_tags: bool = False,
                        progress=None, limit: int | None = None) -> dict:
            """:meth:`search` plus the honest totals: ``{"rows", "total",
            "limit", "truncated"}``.

            ``total`` is how many tracks matched, not how many are being shown, so
            the UI can say "showing 5000 of 8123". Searching used to pass no limit
            at all and inherit an unannounced 500 — a star range holding 1600 sets
            listed 500 of them and looked complete.
            """
            limit = search.DEFAULT_LIMIT if limit is None else max(1, int(limit))
            if query.strip():
                rows, total = search.search_counted(self.db, query, limit,
                                                    search_tags=search_tags)
            else:
                rows = self.db.all_tracks(limit)
                total = (self.db.count_filtered_tracks([])
                         if len(rows) >= limit else len(rows))
                self.db.attach_sources_bulk(rows)
                self.db.attach_difficulties_bulk(rows)
            self.log.info("SEARCH", query=query or "(all)", results=len(rows),
                          total=total, tags=search_tags)
            return {"rows": rows, "total": total, "limit": limit,
                    "truncated": total > len(rows)}

        def artists(self, metric: str = "count", descending: bool = True) -> list[dict]:
            return self.db.artists_ranked(metric, descending)

        def tracks_by_artist(self, artist: str) -> list[dict]:
            return self.db.tracks_by_artist(artist)

