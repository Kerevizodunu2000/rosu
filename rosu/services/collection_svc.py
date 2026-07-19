# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations
from pathlib import Path
from ..collections import read_collection_db

class CollectionMixin:
    def locate_stable_collection_db(self) -> Path | None:
        """Find osu!(stable)'s collection.db from the configured/detected install
        dir, or ``None`` if stable isn't installed/found."""
        from .. import client_import
        install_dir = client_import.stable_install_dir()
        if not install_dir:
            return None
        p = install_dir / "collection.db"
        return p if p.exists() else None

    def sync_collections(self, db_path: Path | str) -> dict:
        """Reads collection.db and tags tracks in the library with Collection names."""
        p = Path(db_path)
        if not p.exists():
            return {"found": False}

        version, collections = read_collection_db(p)
        if not collections:
            return {"found": True, "collections": 0, "tagged": 0}

        md5_to_colls = {}
        for coll in collections:
            # We sanitize the name slightly so it forms a nice tag
            tag_name = f"Collection:{coll.name.replace(' ', '_')}"
            for md5 in coll.md5s:
                md5_to_colls.setdefault(md5, []).append(tag_name)

        # Map checksum -> track_id through the properly-locked accessor (this
        # method may run off the UI thread via Worker, same as everything else
        # in services/ — raw self.db._conn access here would bypass the DB lock).
        track_to_new_tags = {}
        for checksum, track_id in self.db.checksum_to_track_id().items():
            if checksum in md5_to_colls:
                track_to_new_tags.setdefault(track_id, set()).update(md5_to_colls[checksum])

        if not track_to_new_tags:
            return {"found": True, "collections": len(collections), "tagged": 0}

        # Update tracks. bulk() holds the DB lock for the whole block, so the
        # raw cursor use below is safe (same pattern the contextmanager is for).
        tagged_count = 0
        with self.db.bulk():
            cursor = self.db._conn.cursor()
            for track_id, new_tags in track_to_new_tags.items():
                cursor.execute("SELECT tags FROM tracks WHERE id = ?", (track_id,))
                row = cursor.fetchone()
                if not row:
                    continue

                current_tags = row[0] or ""
                # We append missing tags
                existing_tags = set(current_tags.split())
                added = False
                for t in new_tags:
                    if t not in existing_tags:
                        existing_tags.add(t)
                        current_tags += f" {t}"
                        added = True

                if added:
                    cursor.execute("UPDATE tracks SET tags = ? WHERE id = ?", (current_tags.strip(), track_id))
                    tagged_count += 1

        if tagged_count > 0:
            self.db._bump()
        return {"found": True, "collections": len(collections), "tagged": tagged_count}
