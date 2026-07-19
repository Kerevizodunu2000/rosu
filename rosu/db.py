# SPDX-License-Identifier: GPL-3.0-or-later
"""SQLite persistence layer — the single source of truth ("memory").

Holds three domains:

* **packs**      — one row per processed archive (with its parsed series/number).
* **tracks**     — one row per unique .osz beatmap set, keyed by beatmapset id.
* **track_sources** — which pack(s) a track came from (and the subfolder, if the
  pack nested it under e.g. ``osu!mania/``).

The Excel report and every UI view are projections of this database.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .models import ParsedPack, ParsedTrack

SCHEMA_VERSION = 8

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS packs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT UNIQUE NOT NULL,
    series       TEXT,
    number       INTEGER,
    category     TEXT,
    full_name    TEXT,
    title        TEXT,
    mode         TEXT,
    season       TEXT,
    year         INTEGER,
    track_count  INTEGER DEFAULT 0,
    extracted_at TEXT,
    source_zip   TEXT,
    status       TEXT DEFAULT 'processed'
);
CREATE TABLE IF NOT EXISTS tracks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    beatmapset_id     INTEGER UNIQUE,
    filename          TEXT,
    artist            TEXT,
    title             TEXT,
    display_name      TEXT,
    creator           TEXT,
    source            TEXT,
    tags              TEXT,
    bpm               REAL,
    length_seconds    INTEGER,
    mode              TEXT,
    diff_count        INTEGER DEFAULT 0,
    first_seen_at     TEXT,
    last_seen_at      TEXT,
    copy_attempts     INTEGER DEFAULT 0,
    in_library        INTEGER DEFAULT 0,
    library_status    TEXT,
    status_changed_at TEXT,
    size_bytes        INTEGER DEFAULT 0,
    in_drive          INTEGER DEFAULT 0,
    in_osu            INTEGER DEFAULT 0,
    in_osu_stable     INTEGER DEFAULT 0,
    in_osu_lazer      INTEGER DEFAULT 0,
    drive_chunk       TEXT,
    drive_hash        TEXT,
    availability      TEXT
);
CREATE TABLE IF NOT EXISTS track_sources (
    track_id  INTEGER NOT NULL,
    pack_id   INTEGER,
    subfolder TEXT,
    seen_at   TEXT,
    UNIQUE(track_id, pack_id)
);
CREATE TABLE IF NOT EXISTS difficulties (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id       INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    filename       TEXT NOT NULL,   -- the .osu member name inside the .osz
    version        TEXT,            -- difficulty name ("Insane", "7K Oni", ...)
    mode_int       INTEGER,         -- 0/1/2/3
    mode           TEXT,            -- MODE_NAMES display string
    keycount       INTEGER,         -- mania only: round(CircleSize); NULL otherwise
    cs             REAL,
    ar             REAL,
    od             REAL,
    hp             REAL,
    bpm            REAL,
    length_seconds INTEGER,
    checksum       TEXT,            -- MD5 of the raw .osu bytes (osu!'s per-diff hash)
    star_rating    REAL,
    star_source    TEXT,            -- 'rosu-pp' | 'api' | NULL
    star_mods      TEXT DEFAULT '', -- '' = nomod (v1.5 computes nomod only)
    UNIQUE(track_id, filename)
);
CREATE INDEX IF NOT EXISTS idx_tracks_display ON tracks(display_name);
CREATE INDEX IF NOT EXISTS idx_tracks_lib ON tracks(in_library);
CREATE INDEX IF NOT EXISTS idx_packs_series ON packs(series);
CREATE INDEX IF NOT EXISTS idx_diff_track ON difficulties(track_id);
CREATE INDEX IF NOT EXISTS idx_diff_star ON difficulties(star_rating);
CREATE INDEX IF NOT EXISTS idx_diff_mode_key ON difficulties(mode_int, keycount);
CREATE INDEX IF NOT EXISTS idx_diff_checksum ON difficulties(checksum);
"""

# Indexes on columns that may have just been added by a migration — created
# only after _apply_migrations so they never reference a missing column.
_POST_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
CREATE INDEX IF NOT EXISTS idx_packs_category ON packs(category);
CREATE INDEX IF NOT EXISTS idx_tracks_drive ON tracks(in_drive);
CREATE INDEX IF NOT EXISTS idx_tracks_star_max ON tracks(star_max);
CREATE INDEX IF NOT EXISTS idx_tracks_ranked_status ON tracks(ranked_status);
CREATE INDEX IF NOT EXISTS idx_diff_msd ON difficulties(mode_int, msd_overall);
"""

# Columns added after v1, applied via ALTER for databases upgrading in place.
_MIGRATIONS = {
    "packs": {"category": "TEXT", "extra_count": "INTEGER DEFAULT 0"},
    "tracks": {
        "creator": "TEXT", "source": "TEXT", "tags": "TEXT", "bpm": "REAL",
        "length_seconds": "INTEGER", "mode": "TEXT", "diff_count": "INTEGER DEFAULT 0",
        "in_drive": "INTEGER DEFAULT 0", "in_osu": "INTEGER DEFAULT 0",
        "in_osu_stable": "INTEGER DEFAULT 0", "in_osu_lazer": "INTEGER DEFAULT 0",
        "drive_chunk": "TEXT", "drive_hash": "TEXT",
        "availability": "TEXT",  # NULL/'unknown'/'available'/'gone' (item F, v1.0)
        # -- v1.5 metadata & rosu-pp foundation ------------------------------
        "star_min": "REAL", "star_max": "REAL",   # rollup of difficulties.star_rating
        "diffs_scanned_at": "TEXT",               # NULL = never full-parsed by beatmap.py
        "ranked_status": "TEXT",                  # graveyard/wip/pending/ranked/…/loved
        "ranked_date": "TEXT", "submitted_date": "TEXT", "last_updated": "TEXT",
        "play_count": "INTEGER", "favourite_count": "INTEGER",
        "genre": "TEXT", "language": "TEXT",
        "api_checked_at": "TEXT",                 # NULL = never enriched from the osu! API
        # -- v1.6 Mania MSD (Rosu Skillset Rating) --------------------------
        "msd_scanned_at": "TEXT",                 # NULL = never MSD-scanned by rosu/msd.py
    },
    # -- v1.6 Mania MSD: per-diff skillset ratings (mania-only; NULL elsewhere).
    # Additive ALTERs onto the v1.5 `difficulties` table — same mechanism as tracks.
    "difficulties": {
        "msd_overall": "REAL", "msd_stream": "REAL", "msd_jumpstream": "REAL",
        "msd_handstream": "REAL", "msd_stamina": "REAL", "msd_jackspeed": "REAL",
        "msd_chordjack": "REAL", "msd_technical": "REAL",
        "msd_source": "TEXT",                     # which algorithm produced the values
    },
}


class Database:
    def __init__(self, db_path: Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # Monotonic "data changed" counter — views (e.g. the Artists tab) read it
        # to skip an expensive rebuild when nothing relevant changed (item 10).
        self._generation = 0
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._apply_migrations()
            self._relax_packs_notnull()
            self._conn.executescript(_POST_INDEXES)
            self._backfill_category()
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),))
            self._conn.commit()

    def _backfill_category(self) -> None:
        """Fill category for packs recorded before the column existed."""
        from .parsing import pack_category
        # Synthetic "local library" packs (status='local', item 9) are deliberately
        # left category-less so they never surface in the Packs tab — don't backfill them.
        rows = self._conn.execute(
            "SELECT id, series FROM packs "
            "WHERE category IS NULL AND (status IS NULL OR status <> 'local')").fetchall()
        for r in rows:
            self._conn.execute("UPDATE packs SET category=? WHERE id=?",
                               (pack_category(r["series"]), r["id"]))

    def _apply_migrations(self) -> None:
        """Add any columns missing from an older database (idempotent)."""
        for table, cols in _MIGRATIONS.items():
            existing = {r["name"] for r in
                        self._conn.execute(f"PRAGMA table_info({table})")}
            for name, decl in cols.items():
                if name not in existing:
                    self._conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    def _relax_packs_notnull(self) -> None:
        """Old schemas declared ``packs.series`` (and number/category) NOT NULL.
        Synthetic 'local' source packs store those as NULL, so on such a database
        importing from an installed osu! client raised
        ``IntegrityError: NOT NULL constraint failed: packs.series``. Rebuild the
        table with a nullable schema (SQLite can't drop a column constraint in
        place), preserving all rows. Idempotent: a no-op once already nullable."""
        info = {r["name"]: r for r in self._conn.execute("PRAGMA table_info(packs)")}
        if not any(info.get(c) and info[c]["notnull"]
                   for c in ("series", "number", "category")):
            return  # already nullable (fresh dbs and post-migration dbs)
        # Copy only the columns that exist in both the old table and the canonical
        # schema, so an unexpected extra/missing column can't abort the rebuild.
        canonical = ["id", "code", "series", "number", "category", "full_name",
                     "title", "mode", "season", "year", "track_count",
                     "extracted_at", "source_zip", "status", "extra_count"]
        shared = ", ".join(c for c in canonical if c in info)
        # Do the swap inside ONE explicit transaction so an interruption between
        # DROP TABLE packs and the RENAME can never leave the db without a packs
        # table (which the next launch would silently recreate empty). Python's
        # sqlite3 implicitly COMMITs before DDL in its default mode, so take manual
        # autocommit control for the duration; PRAGMA foreign_keys can't be toggled
        # inside a transaction, so do it outside.
        self._conn.commit()   # flush any pending work before manual txn control
        old_iso = self._conn.isolation_level
        self._conn.isolation_level = None
        try:
            self._conn.execute("PRAGMA foreign_keys=OFF")
            self._conn.execute("BEGIN")
            self._conn.execute("""
                CREATE TABLE packs_new (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    code         TEXT UNIQUE NOT NULL,
                    series       TEXT,
                    number       INTEGER,
                    category     TEXT,
                    full_name    TEXT,
                    title        TEXT,
                    mode         TEXT,
                    season       TEXT,
                    year         INTEGER,
                    track_count  INTEGER DEFAULT 0,
                    extracted_at TEXT,
                    source_zip   TEXT,
                    status       TEXT DEFAULT 'processed',
                    extra_count  INTEGER DEFAULT 0
                )""")
            self._conn.execute(
                f"INSERT INTO packs_new ({shared}) SELECT {shared} FROM packs")
            self._conn.execute("DROP TABLE packs")
            self._conn.execute("ALTER TABLE packs_new RENAME TO packs")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_packs_series ON packs(series)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_packs_category ON packs(category)")
            self._conn.execute("COMMIT")
        except Exception:
            try:
                self._conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.isolation_level = old_iso

    def data_generation(self) -> int:
        """A counter bumped on every write that changes the track set or its
        metadata, so views can cheaply detect staleness (item 10)."""
        return self._generation

    def _bump(self) -> None:
        self._generation += 1

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- packs ---------------------------------------------------------------
    def get_pack_by_code(self, code: str) -> sqlite3.Row | None:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM packs WHERE code=?", (code,))
            return cur.fetchone()

    def upsert_pack(self, p: ParsedPack, track_count: int, extracted_at: str) -> int:
        with self._lock:
            existing = self._conn.execute(
                "SELECT id FROM packs WHERE code=?", (p.code,)).fetchone()
            if existing:
                pid = existing["id"]
                self._conn.execute(
                    """UPDATE packs SET series=?, number=?, category=?, full_name=?,
                       title=?, mode=?, season=?, year=?, track_count=?,
                       extracted_at=?, source_zip=?, status='processed' WHERE id=?""",
                    (p.series, p.number, p.category, p.full_name, p.title, p.mode,
                     p.season, p.year, track_count, extracted_at, p.source_zip, pid))
            else:
                cur = self._conn.execute(
                    """INSERT INTO packs(code, series, number, category, full_name,
                       title, mode, season, year, track_count, extracted_at,
                       source_zip, status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'processed')""",
                    (p.code, p.series, p.number, p.category, p.full_name, p.title,
                     p.mode, p.season, p.year, track_count, extracted_at, p.source_zip))
                pid = cur.lastrowid
            self._conn.commit()
            return pid

    def set_pack_extra(self, code: str, count: int) -> None:
        """Record how many non-music files the pack's source archive held (item 25)."""
        with self._lock:
            self._conn.execute("UPDATE packs SET extra_count=? WHERE code=?",
                               (int(count), code))
            self._conn.commit()

    def get_or_create_local_pack(self, code: str, full_name: str | None = None) -> int:
        """A synthetic "source" pack for beatmaps imported from an installed osu!
        client (item 9), so their provenance (e.g. ``local_osu_lazer``) shows in the
        Sources column. Kept series/category NULL and status='local' so it never
        appears in the Packs tab or as a gap (see ``_backfill_category``)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM packs WHERE code=?", (code,)).fetchone()
            if row:
                return row["id"]
            cur = self._conn.execute(
                "INSERT INTO packs(code, series, number, category, full_name, status) "
                "VALUES(?, NULL, NULL, NULL, ?, 'local')", (code, full_name or code))
            self._conn.commit()
            return cur.lastrowid

    def series_list(self) -> list[str]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT DISTINCT series FROM packs WHERE series IS NOT NULL "
                "ORDER BY series")
            return [r["series"] for r in cur.fetchall()]

    def packs_for_series(self, series: str) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM packs WHERE series=? ORDER BY number", (series,))
            return [dict(r) for r in cur.fetchall()]

    def category_list(self) -> list[str]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT DISTINCT category FROM packs WHERE category IS NOT NULL "
                "ORDER BY category")
            return [r["category"] for r in cur.fetchall()]

    def packs_for_category(self, category: str) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM packs WHERE category=? "
                "ORDER BY series, number, full_name", (category,))
            return [dict(r) for r in cur.fetchall()]

    def all_packs(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM packs ORDER BY category, series, number")
            return [dict(r) for r in cur.fetchall()]

    # -- tracks --------------------------------------------------------------
    def known_track_ids(self) -> set[int]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT beatmapset_id FROM tracks WHERE beatmapset_id IS NOT NULL")
            return {r["beatmapset_id"] for r in cur.fetchall()}

    def _find_track(self, t: ParsedTrack) -> sqlite3.Row | None:
        if t.beatmapset_id is not None:
            return self._conn.execute(
                "SELECT * FROM tracks WHERE beatmapset_id=?",
                (t.beatmapset_id,)).fetchone()
        return self._conn.execute(
            "SELECT * FROM tracks WHERE beatmapset_id IS NULL AND filename=?",
            (t.filename,)).fetchone()

    def upsert_track(self, t: ParsedTrack, seen_at: str,
                     meta=None) -> tuple[int, bool]:
        """Insert a track if new, else refresh it. Returns (id, is_new).

        ``meta`` (optional :class:`~.models.TrackMeta`) enriches the record with
        BPM/length/mapper/etc. and, when the filename had no artist, supplies the
        real artist/title read from the .osu file.
        """
        from .models import UNKNOWN_ARTIST
        artist, title, display = t.artist, t.title, t.display_name
        if meta is not None and (artist == UNKNOWN_ARTIST or not artist) and meta.artist:
            artist = meta.artist
            title = meta.title or title
            display = f"{artist} - {title}" if title else artist
        m_creator = getattr(meta, "creator", None) if meta else None
        m_source = getattr(meta, "source", None) if meta else None
        m_tags = getattr(meta, "tags", None) if meta else None
        m_bpm = getattr(meta, "bpm", None) if meta else None
        m_len = getattr(meta, "length_seconds", None) if meta else None
        m_mode = getattr(meta, "mode", None) if meta else None
        m_diff = getattr(meta, "diff_count", 0) if meta else 0

        with self._lock:
            row = self._find_track(t)
            if row:
                tid = row["id"]
                self._conn.execute(
                    """UPDATE tracks SET last_seen_at=?,
                       artist=COALESCE(NULLIF(?,''), NULLIF(artist,''), ?),
                       title=COALESCE(NULLIF(?,''), NULLIF(title,''), ?),
                       display_name=COALESCE(NULLIF(?,''), display_name),
                       creator=COALESCE(creator, ?), source=COALESCE(source, ?),
                       tags=COALESCE(tags, ?), bpm=COALESCE(bpm, ?),
                       length_seconds=COALESCE(length_seconds, ?),
                       mode=COALESCE(mode, ?),
                       diff_count=CASE WHEN ?>0 THEN ? ELSE diff_count END,
                       size_bytes=CASE WHEN ?>0 THEN ? ELSE size_bytes END
                       WHERE id=?""",
                    (seen_at, artist, artist, title, title, display,
                     m_creator, m_source, m_tags, m_bpm, m_len, m_mode,
                     m_diff, m_diff, t.size_bytes, t.size_bytes, tid))
                self._conn.commit()
                self._bump()
                return tid, False
            cur = self._conn.execute(
                """INSERT INTO tracks(beatmapset_id, filename, artist, title,
                   display_name, creator, source, tags, bpm, length_seconds, mode,
                   diff_count, first_seen_at, last_seen_at, copy_attempts,
                   in_library, size_bytes)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,?)""",
                (t.beatmapset_id, t.filename, artist, title, display,
                 m_creator, m_source, m_tags, m_bpm, m_len, m_mode, m_diff,
                 seen_at, seen_at, t.size_bytes))
            self._conn.commit()
            self._bump()
            return cur.lastrowid, True

    def add_track_source(self, track_id: int, pack_id: int | None,
                         subfolder: str | None, seen_at: str) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR IGNORE INTO track_sources(track_id, pack_id,
                   subfolder, seen_at) VALUES(?,?,?,?)""",
                (track_id, pack_id, subfolder, seen_at))
            self._conn.commit()
            self._bump()

    # -- difficulties & metadata (v1.5) --------------------------------------
    def upsert_difficulties(self, track_id: int, diffs: list, stars: dict,
                            when: str) -> None:
        """Replace this track's per-difficulty rows with the freshly parsed set and
        refresh the ``star_min``/``star_max`` rollup on the parent ``tracks`` row.

        ``diffs`` is a list of :class:`~.models.DiffMeta`; ``stars`` maps a diff's
        ``filename`` to its locally-computed star (a float, or ``None`` when
        rosu-pp-py was unavailable/failed — left NULL for the osu! API to fill
        later). A re-parse reconciles: rows whose ``.osu`` no longer exists are
        deleted; a run without a fresh local star never wipes a star already stored
        (so re-running the parser without rosu-pp installed doesn't lose ratings).
        """
        with self._lock:
            present = {d.filename for d in diffs}
            for r in self._conn.execute(
                    "SELECT filename FROM difficulties WHERE track_id=?",
                    (track_id,)).fetchall():
                if r["filename"] not in present:
                    self._conn.execute(
                        "DELETE FROM difficulties WHERE track_id=? AND filename=?",
                        (track_id, r["filename"]))
            for d in diffs:
                star_val = stars.get(d.filename)
                row = self._conn.execute(
                    "SELECT id FROM difficulties WHERE track_id=? AND filename=?",
                    (track_id, d.filename)).fetchone()
                if row:
                    if star_val is not None:
                        self._conn.execute(
                            """UPDATE difficulties SET version=?, mode_int=?, mode=?,
                               keycount=?, cs=?, ar=?, od=?, hp=?, bpm=?,
                               length_seconds=?, checksum=?, star_rating=?,
                               star_source='rosu-pp', star_mods='' WHERE id=?""",
                            (d.version, d.mode_int, d.mode, d.keycount, d.cs, d.ar,
                             d.od, d.hp, d.bpm, d.length_seconds, d.checksum,
                             star_val, row["id"]))
                    else:
                        self._conn.execute(
                            """UPDATE difficulties SET version=?, mode_int=?, mode=?,
                               keycount=?, cs=?, ar=?, od=?, hp=?, bpm=?,
                               length_seconds=?, checksum=? WHERE id=?""",
                            (d.version, d.mode_int, d.mode, d.keycount, d.cs, d.ar,
                             d.od, d.hp, d.bpm, d.length_seconds, d.checksum, row["id"]))
                else:
                    self._conn.execute(
                        """INSERT INTO difficulties(track_id, filename, version,
                           mode_int, mode, keycount, cs, ar, od, hp, bpm,
                           length_seconds, checksum, star_rating, star_source)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (track_id, d.filename, d.version, d.mode_int, d.mode,
                         d.keycount, d.cs, d.ar, d.od, d.hp, d.bpm, d.length_seconds,
                         d.checksum, star_val,
                         "rosu-pp" if star_val is not None else None))
            agg = self._conn.execute(
                "SELECT MIN(star_rating) mn, MAX(star_rating) mx FROM difficulties "
                "WHERE track_id=?", (track_id,)).fetchone()
            self._conn.execute(
                "UPDATE tracks SET star_min=?, star_max=?, diffs_scanned_at=? "
                "WHERE id=?", (agg["mn"], agg["mx"], when, track_id))
            self._conn.commit()
            self._bump()

    def difficulties_for_track(self, track_id: int) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM difficulties WHERE track_id=? "
                "ORDER BY star_rating", (track_id,))
            return [dict(r) for r in cur.fetchall()]

    def mode_set_counts(self) -> dict:
        """How many in-Library sets contain at least one difficulty of each mode —
        so the Search filters panel can disable a mode you own no maps of (v1.6)."""
        with self._lock:
            cur = self._conn.execute(
                """SELECT d.mode AS mode, COUNT(DISTINCT d.track_id) AS n
                   FROM difficulties d JOIN tracks t ON t.id = d.track_id
                   WHERE t.in_library=1 AND d.mode IS NOT NULL
                   GROUP BY d.mode""")
            return {r["mode"]: r["n"] for r in cur.fetchall()}

    def mania_msd_for_pack(self, pack_id: int) -> list[dict]:
        """Every rated mania difficulty (``msd_*`` populated) among a pack's tracks —
        for the Packs-tab skillset summary (v1.6)."""
        with self._lock:
            cur = self._conn.execute(
                """SELECT d.* FROM difficulties d
                   JOIN track_sources ts ON ts.track_id = d.track_id
                   WHERE ts.pack_id=? AND d.mode_int=3 AND d.msd_overall IS NOT NULL""",
                (pack_id,))
            return [dict(r) for r in cur.fetchall()]

    def apply_msd(self, track_id: int, results: dict, when: str) -> None:
        """Write Rosu Skillset Rating values onto this track's mania difficulties.

        ``results`` maps a diff ``filename`` → :class:`~.models.MsdResult`. Non-mania
        diffs and mania diffs with too little data are simply absent from ``results``
        and left untouched. ``msd_scanned_at`` is stamped on the parent track (even
        when ``results`` is empty) so a whole-library backfill treats the set as done
        and never re-scans it — matching the ``diffs_scanned_at``/``api_checked_at``
        idiom.
        """
        with self._lock:
            for fn, res in results.items():
                if res is None:
                    continue
                self._conn.execute(
                    """UPDATE difficulties SET msd_overall=?, msd_stream=?,
                       msd_jumpstream=?, msd_handstream=?, msd_stamina=?,
                       msd_jackspeed=?, msd_chordjack=?, msd_technical=?,
                       msd_source=? WHERE track_id=? AND filename=?""",
                    (res.overall, res.stream, res.jumpstream, res.handstream,
                     res.stamina, res.jackspeed, res.chordjack, res.technical,
                     res.source, track_id, fn))
            self._conn.execute("UPDATE tracks SET msd_scanned_at=? WHERE id=?",
                               (when, track_id))
            self._conn.commit()
            self._bump()

    def apply_api_enrichment(self, beatmapset_id: int, fields: dict,
                             when: str) -> None:
        """Write live osu!-API metadata onto a track and fill any still-missing
        per-diff star from the API's ``difficulty_rating``.

        Unlike :meth:`upsert_track` (COALESCE — never clobber a static local value),
        the fields here (ranked status/dates, play/favourite counts, genre, language)
        are **live and the API is authoritative**, so they use a plain ``SET``: a set
        that goes pending→ranked, or whose play count climbs, must keep updating on
        every enrichment run. A successful fetch also implies the set still exists,
        so ``availability`` is refreshed to 'available'. Per-diff star is matched by
        ``.osu`` MD5 checksum (falling back to version+mode_int) and only written
        where none exists — never overwriting a local rosu-pp rating.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM tracks WHERE beatmapset_id=?",
                (beatmapset_id,)).fetchone()
            if not row:
                return
            tid = row["id"]
            self._conn.execute(
                """UPDATE tracks SET ranked_status=?, ranked_date=?, submitted_date=?,
                   last_updated=?, play_count=?, favourite_count=?, genre=?,
                   language=?, availability='available', api_checked_at=? WHERE id=?""",
                (fields.get("status"), fields.get("ranked_date"),
                 fields.get("submitted_date"), fields.get("last_updated"),
                 fields.get("play_count"), fields.get("favourite_count"),
                 fields.get("genre"), fields.get("language"),
                 when, tid))
            for b in fields.get("beatmaps", []):
                dr = b.get("difficulty_rating")
                if dr is None:
                    continue
                drow = None
                if b.get("checksum"):
                    drow = self._conn.execute(
                        "SELECT id, star_rating FROM difficulties "
                        "WHERE track_id=? AND checksum=?",
                        (tid, b["checksum"])).fetchone()
                if drow is None and b.get("version") is not None:
                    drow = self._conn.execute(
                        "SELECT id, star_rating FROM difficulties "
                        "WHERE track_id=? AND version=? AND mode_int IS ?",
                        (tid, b.get("version"), b.get("mode_int"))).fetchone()
                if drow is not None and drow["star_rating"] is None:
                    self._conn.execute(
                        "UPDATE difficulties SET star_rating=?, star_source='api' "
                        "WHERE id=?", (dr, drow["id"]))
            agg = self._conn.execute(
                "SELECT MIN(star_rating) mn, MAX(star_rating) mx FROM difficulties "
                "WHERE track_id=?", (tid,)).fetchone()
            self._conn.execute(
                "UPDATE tracks SET star_min=COALESCE(?, star_min), "
                "star_max=COALESCE(?, star_max) WHERE id=?",
                (agg["mn"], agg["mx"], tid))
            self._conn.commit()
            self._bump()

    def bump_copy_attempt(self, track_id: int) -> int:
        with self._lock:
            self._conn.execute(
                "UPDATE tracks SET copy_attempts=copy_attempts+1 WHERE id=?",
                (track_id,))
            self._conn.commit()
            r = self._conn.execute(
                "SELECT copy_attempts FROM tracks WHERE id=?", (track_id,)).fetchone()
            return r["copy_attempts"] if r else 0

    def set_library_state(self, track_id: int, in_library: bool,
                          status: str, when: str) -> None:
        with self._lock:
            self._conn.execute(
                """UPDATE tracks SET in_library=?, library_status=?,
                   status_changed_at=? WHERE id=?""",
                (1 if in_library else 0, status, when, track_id))
            self._conn.commit()

    def set_drive_state(self, track_id: int, in_drive: bool,
                        chunk: str | None = None,
                        drive_hash: str | None = None) -> None:
        """Record whether a track is stored in the Drive backup, and if so which
        chunk archive holds it plus its content hash (item 11, v0.8)."""
        with self._lock:
            self._conn.execute(
                """UPDATE tracks SET in_drive=?, drive_chunk=?, drive_hash=?
                   WHERE id=?""",
                (1 if in_drive else 0, chunk, drive_hash, track_id))
            self._conn.commit()

    def set_in_osu(self, beatmapset_id: int, in_osu: bool = True,
                   client: str | None = None) -> None:
        """Flag a beatmapset as present in an osu! client (the Search 'Where'
        markers). ``client`` is ``"stable"`` / ``"lazer"`` / ``None`` — the
        per-client column is set in addition to the legacy ``in_osu`` flag."""
        if beatmapset_id is None:
            return
        cols = ["in_osu=?"]
        vals: list = [1 if in_osu else 0]
        if client == "stable":
            cols.append("in_osu_stable=?"); vals.append(1 if in_osu else 0)
        elif client == "lazer":
            cols.append("in_osu_lazer=?"); vals.append(1 if in_osu else 0)
        vals.append(beatmapset_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE tracks SET {', '.join(cols)} WHERE beatmapset_id=?", vals)
            self._conn.commit()

    def set_availability(self, beatmapset_id: int, status: str) -> None:
        """Record whether a beatmapset still exists on osu! (item F, v1.0):
        'available' / 'gone' / 'unknown'. Keyed by beatmapset id."""
        with self._lock:
            self._conn.execute(
                "UPDATE tracks SET availability=? WHERE beatmapset_id=?",
                (status, beatmapset_id))
            self._conn.commit()

    def lost_map_count(self) -> int:
        """How many owned beatmapsets are flagged as gone from osu! (item F)."""
        with self._lock:
            r = self._conn.execute(
                "SELECT COUNT(*) c FROM tracks WHERE availability='gone'").fetchone()
            return r["c"] if r else 0

    def find_track_row(self, beatmapset_id: int | None,
                       filename: str) -> sqlite3.Row | None:
        with self._lock:
            if beatmapset_id is not None:
                r = self._conn.execute(
                    "SELECT * FROM tracks WHERE beatmapset_id=?",
                    (beatmapset_id,)).fetchone()
                if r:
                    return r
            return self._conn.execute(
                "SELECT * FROM tracks WHERE filename=?", (filename,)).fetchone()

    def mark_library_memory(self, when: str) -> int:
        """After the physical .osz copies are deleted, keep the rows but mark them
        memory-only (item 17). Returns how many rows changed."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE tracks SET in_library=0, library_status='memory', "
                "status_changed_at=? WHERE in_library=1", (when,))
            self._conn.commit()
            return cur.rowcount

    def library_tracks(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM tracks WHERE in_library=1")
            return [dict(r) for r in cur.fetchall()]

    def library_records(self) -> list[dict]:
        """Every track that is part of the Library's *memory* — physically
        present (``in_library=1``) OR intentionally memory-only / already-gone
        (``library_status`` in memory/disappeared). The health scrub (v1.1) uses
        this so a purged-then-re-added file isn't mistaken for an orphan."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM tracks WHERE in_library=1 "
                "OR library_status IN ('memory', 'disappeared')")
            return [dict(r) for r in cur.fetchall()]

    def search_candidates(self, query: str, limit: int = 2000,
                          search_tags: bool = False,
                          filters: list | None = None) -> list[dict]:
        """Token-AND recall over the searchable fields, optionally AND'd with
        structured ``filters`` (query-syntax, v1.5).

        Each query word must appear in some **strong** field (name/artist/title)
        — the old whole-query ``tags LIKE '%…%'`` recall flooded results with maps
        merely tagged with a word (e.g. every Vocaloid map for "Hatsune Miku").
        ``creator``/``tags`` are only recalled when ``search_tags`` is on. A purely
        numeric query also matches on ``beatmapset_id``. ``filters`` (a list of
        :class:`rosu.query.Filter`) are hard constraints applied as SQL — diff-level
        ones collapse into one ``EXISTS`` subquery so ``star>5 mode=mania key=7``
        must be satisfied by the *same* difficulty. This entry point is for queries
        with free text; a filters-only query goes through :meth:`filtered_tracks`.

        Ranking is done in :mod:`rosu.search`. Sources are NOT attached here — that
        would be one JOIN per candidate (an N+1 that froze the UI on common words);
        the caller attaches them in bulk to the *displayed* rows only.
        """
        from .search import tokenize
        raw = query.strip()
        tokens = tokenize(raw)
        fields = ["display_name", "artist", "title"]
        if search_tags:
            fields = fields + ["creator", "tags"]

        clauses: list[str] = []
        params: list = []
        for tok in tokens:
            like = f"%{tok}%"
            ors = " OR ".join(f"{f} LIKE ? COLLATE NOCASE" for f in fields)
            clauses.append(f"({ors})")
            params.extend([like] * len(fields))
        where = " AND ".join(clauses) if clauses else ""

        if raw.isdigit():   # allow an id prefix match regardless of word tokens
            id_clause = "CAST(beatmapset_id AS TEXT) LIKE ?"
            where = f"({where}) OR {id_clause}" if where else id_clause
            params.append(f"{raw}%")

        filter_where, filter_params = self._build_filter_sql(filters or [])
        parts: list[str] = []
        if where:
            parts.append(f"({where})")
        if filter_where:
            parts.append(f"({filter_where})")
        if not parts:
            return []       # nothing searchable (no tokens, no id, no filters)
        params = params + filter_params + [limit]
        final_where = " AND ".join(parts)
        with self._lock:
            cur = self._conn.execute(
                f"SELECT * FROM tracks WHERE {final_where} LIMIT ?", params)
            return [dict(r) for r in cur.fetchall()]

    def _build_filter_sql(self, filters: list) -> tuple[str, list]:
        """Turn structured query filters into (where_fragment, params).

        Track-level fields compare directly against a ``tracks`` column; diff-level
        fields collapse into ONE ``EXISTS`` subquery so several diff constraints must
        hold on the *same* difficulty row (e.g. a 7K chart that is *also* > 5★, not a
        set that merely has some 7K diff and some >5★ diff). ``op`` is validated
        against a whitelist so the field/op strings (never the value) are the only
        thing interpolated into SQL.
        """
        track_cols = {"bpm": "bpm", "status": "ranked_status",
                      "length": "length_seconds"}
        diff_cols = {"star": "star_rating", "mode": "mode", "key": "keycount",
                     "keys": "keycount", "cs": "cs", "ar": "ar", "od": "od", "hp": "hp"}
        text_cols = {"artist": "artist", "creator": "creator", "title": "title",
                     "source": "source", "tags": "tags"}
        cmp_ops = {">", ">=", "<", "<=", "="}
        frags: list[str] = []
        params: list = []
        diff_frags: list[str] = []
        diff_params: list = []
        for f in filters:
            if f.op == "contains" and f.field in text_cols:
                frags.append(f"tracks.{text_cols[f.field]} LIKE ? COLLATE NOCASE")
                params.append(f"%{f.value}%")
            elif f.op not in cmp_ops:
                continue
            elif f.field in track_cols:
                frags.append(f"tracks.{track_cols[f.field]} {f.op} ?")
                params.append(f.value)
            elif f.field in diff_cols:
                diff_frags.append(f"d.{diff_cols[f.field]} {f.op} ?")
                diff_params.append(f.value)
        if diff_frags:
            frags.append("EXISTS (SELECT 1 FROM difficulties d "
                         "WHERE d.track_id = tracks.id AND "
                         + " AND ".join(diff_frags) + ")")
            params.extend(diff_params)
        return (" AND ".join(frags), params)

    def filtered_tracks(self, filters: list, limit: int = 5000) -> list[dict]:
        """Name-sorted rows matching only structured filters (no free text). Used
        for a filters-only query like ``star>5 mode=mania`` — there is nothing to
        rank, so results come back ordered by name directly."""
        where, params = self._build_filter_sql(filters or [])
        if not where:
            return self.all_tracks(limit)
        with self._lock:
            cur = self._conn.execute(
                f"SELECT * FROM tracks WHERE {where} "
                f"ORDER BY display_name COLLATE NOCASE LIMIT ?", params + [limit])
            return [dict(r) for r in cur.fetchall()]

    def all_tracks(self, limit: int = 5000) -> list[dict]:
        """Every track, name-sorted — the default browse listing (item 11)."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM tracks ORDER BY display_name COLLATE NOCASE LIMIT ?",
                (limit,))
            return [dict(r) for r in cur.fetchall()]

    def attach_sources_bulk(self, rows: list[dict]) -> None:
        """Attach source packs to many rows in one pass (no N+1).

        Fetches all their sources with a single (chunked) query and groups them
        in Python, so a 500-row result costs a couple of queries, not 500.
        """
        ids = [r["id"] for r in rows if r.get("id") is not None]
        by_track: dict[int, list] = {}
        with self._lock:
            for i in range(0, len(ids), 900):  # stay under SQLite's variable cap
                chunk = ids[i:i + 900]
                ph = ",".join("?" * len(chunk))
                cur = self._conn.execute(
                    f"""SELECT ts.track_id AS tid, p.code, p.full_name, ts.subfolder
                        FROM track_sources ts LEFT JOIN packs p ON p.id=ts.pack_id
                        WHERE ts.track_id IN ({ph}) ORDER BY p.code""", chunk)
                for r in cur.fetchall():
                    by_track.setdefault(r["tid"], []).append(r)
        for row in rows:
            srcs = by_track.get(row["id"], [])
            row["sources"] = [
                f"{s['code']}/{s['subfolder']}" if s["subfolder"] else (s["code"] or "?")
                for s in srcs]
            row["source_full"] = [(s["full_name"] or s["code"] or "?") for s in srcs]

    def _sources_for(self, track_id: int) -> list[dict]:
        """Return each source pack as {code, full_name, subfolder}."""
        cur = self._conn.execute(
            """SELECT p.code, p.full_name, ts.subfolder FROM track_sources ts
               LEFT JOIN packs p ON p.id=ts.pack_id
               WHERE ts.track_id=? ORDER BY p.code""", (track_id,))
        out = []
        for r in cur.fetchall():
            out.append({
                "code": r["code"] or "?",
                "full_name": r["full_name"] or r["code"] or "?",
                "subfolder": r["subfolder"],
            })
        return out

    def _attach_sources(self, track_row: dict) -> None:
        srcs = self._sources_for(track_row["id"])
        # short label for on-screen display (code + subfolder)
        track_row["sources"] = [
            f"{s['code']}/{s['subfolder']}" if s["subfolder"] else s["code"]
            for s in srcs]
        # full archive names for clipboard copy
        track_row["source_full"] = [s["full_name"] for s in srcs]

    # -- artists -------------------------------------------------------------
    _ARTIST_METRICS = {"count": "song_count", "avg_length": "avg_length",
                       "avg_bpm": "avg_bpm", "avg_star": "avg_star"}

    def artists_ranked(self, metric: str = "count",
                       descending: bool = True) -> list[dict]:
        """Per-artist aggregates ranked by song count, avg length, avg BPM or avg
        star (item 14 / v1.5). Artists with no data for the chosen metric sort last."""
        col = self._ARTIST_METRICS.get(metric, "song_count")
        order = "DESC" if descending else "ASC"
        with self._lock:
            cur = self._conn.execute(
                f"""SELECT artist, COUNT(*) AS song_count,
                           AVG(NULLIF(length_seconds, 0)) AS avg_length,
                           AVG(NULLIF(bpm, 0)) AS avg_bpm,
                           AVG(star_max) AS avg_star
                    FROM tracks WHERE artist IS NOT NULL AND artist <> ''
                    GROUP BY artist
                    ORDER BY ({col} IS NULL), {col} {order}, artist ASC""")
            return [dict(r) for r in cur.fetchall()]

    def attach_difficulties_bulk(self, rows: list[dict]) -> None:
        """Attach each row's per-difficulty records (star/keys/cs/ar/od/hp/version/
        mode) as ``row["difficulties"]`` in one grouped query — only for the
        displayed rows, so the Search list can show each diff's exact star and key
        count without an N+1 (same idea as :meth:`attach_sources_bulk`)."""
        ids = [r["id"] for r in rows if r.get("id") is not None]
        by_track: dict[int, list] = {}
        with self._lock:
            for i in range(0, len(ids), 900):   # stay under SQLite's variable cap
                chunk = ids[i:i + 900]
                ph = ",".join("?" * len(chunk))
                cur = self._conn.execute(
                    f"""SELECT * FROM difficulties WHERE track_id IN ({ph})
                        ORDER BY (star_rating IS NULL), star_rating""", chunk)
                for r in cur.fetchall():
                    by_track.setdefault(r["track_id"], []).append(dict(r))
        for row in rows:
            row["difficulties"] = by_track.get(row["id"], [])

    def artists_by_count(self, descending: bool = True) -> list[dict]:
        return self.artists_ranked("count", descending)

    def tracks_by_artist(self, artist: str) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM tracks WHERE artist=? ORDER BY title", (artist,))
            rows = [dict(r) for r in cur.fetchall()]
            self.attach_sources_bulk(rows)   # RLock re-entrant: keep the read atomic (item 10)
        return rows

    def counts(self) -> dict:
        with self._lock:
            packs = self._conn.execute("SELECT COUNT(*) c FROM packs").fetchone()["c"]
            tracks = self._conn.execute("SELECT COUNT(*) c FROM tracks").fetchone()["c"]
            inlib = self._conn.execute(
                "SELECT COUNT(*) c FROM tracks WHERE in_library=1").fetchone()["c"]
            return {"packs": packs, "tracks": tracks, "in_library": inlib}

    def drive_count(self) -> int:
        """How many beatmap sets are marked as backed up to Drive (in_drive=1)."""
        with self._lock:
            r = self._conn.execute(
                "SELECT COUNT(*) c FROM tracks WHERE in_drive=1").fetchone()
            return r["c"] if r else 0

    def osu_client_ids(self, client: str) -> set[int]:
        """Beatmapset ids Rosu has recorded as present in an osu! client
        (``"stable"`` / ``"lazer"``) — i.e. sets it imported into or sent to it.
        Lets a lazer→ transfer skip re-sending them (lazer's own set list is
        Realm-opaque). An unknown client name yields an empty set."""
        col = {"stable": "in_osu_stable", "lazer": "in_osu_lazer"}.get(client)
        if col is None:
            return set()
        with self._lock:
            cur = self._conn.execute(
                f"SELECT beatmapset_id FROM tracks WHERE {col}=1 "
                "AND beatmapset_id IS NOT NULL")
            return {r["beatmapset_id"] for r in cur.fetchall()}
