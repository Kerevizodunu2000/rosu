# SPDX-License-Identifier: GPL-3.0-or-later
"""Map (beatmapset) details dialog (v1.5).

The one place with the full, precise per-map info: every difficulty's exact star,
key count and CS/AR/OD/HP, plus the osu!-API metadata that enrichment adds
(ranked status, official dates, play/favourite counts, genre, language) — so it's
obvious what the API enrichment buys you over the locally-parsed data.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHeaderView, QLabel, QTableWidget, QVBoxLayout,
)

from .copy_table import SortItem


def _num(v) -> str:
    return f"{v:g}" if v is not None else ""


class MapDetailsDialog(QDialog):
    # (i18n column key, tooltip key, value fn, numeric?) — Keys is dropped when the
    # set has no mania difficulty (key count is a mania-only concept).
    pass

    def __init__(self, ctx, row: dict, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        t = ctx.t
        self.setWindowTitle(t("map_details_title"))
        self.setMinimumSize(640, 440)
        root = QVBoxLayout(self)
        root.setSpacing(8)

        head = QLabel(objectName="h1")
        head.setWordWrap(True)
        head.setText(row.get("display_name") or row.get("title") or "?")
        root.addWidget(head)

        bits = []
        if row.get("creator"):
            bits.append(t("map_details_mapper", mapper=row["creator"]))
        if row.get("beatmapset_id"):
            bits.append(f"#{row['beatmapset_id']}")
        if row.get("bpm"):
            bits.append(f"{row['bpm']:g} BPM")
        if bits:
            sub = QLabel(objectName="status")
            sub.setWordWrap(True)
            sub.setText("   ·   ".join(bits))
            root.addWidget(sub)

        # osu!-API enrichment block — what the API adds beyond the local parse.
        meta_bits = []
        if row.get("ranked_status"):
            meta_bits.append(t("map_details_status", status=row["ranked_status"]))
        if row.get("play_count") is not None:
            meta_bits.append(t("map_details_plays", n=f"{row['play_count']:,}"))
        if row.get("favourite_count") is not None:
            meta_bits.append(t("map_details_favs", n=f"{row['favourite_count']:,}"))
        if row.get("genre"):
            meta_bits.append(str(row["genre"]))
        if row.get("language"):
            meta_bits.append(str(row["language"]))
        if row.get("ranked_date"):
            meta_bits.append(t("map_details_ranked_on", d=str(row["ranked_date"])[:10]))
        info = QLabel(objectName="status")
        info.setWordWrap(True)
        info.setText("   ·   ".join(meta_bits) if meta_bits
                     else t("map_details_no_enrich"))
        root.addWidget(info)

        diffs = sorted(
            row.get("difficulties") or [],
            key=lambda d: (d.get("star_rating") is None, d.get("star_rating") or 0.0))
        has_keys = any(d.get("keycount") for d in diffs)   # mania-only column

        # (i18n col key, tooltip key, cell (text, sort) builder). Keys is included
        # only for sets that actually have a mania difficulty.
        columns = [
            ("col_version", "tip_col_version",
             lambda d: (d.get("version") or "?", None)),
            ("col_mode", "tip_col_mode", lambda d: (d.get("mode") or "", None)),
        ]
        if has_keys:
            columns.append(("col_keys", "tip_col_keys",
                            lambda d: (f"{d['keycount']}K" if d.get("keycount") else "",
                                       d.get("keycount") or 0)))
        columns += [
            ("col_star", "tip_col_star",
             lambda d: (f"{d['star_rating']:.2f}" if d.get("star_rating") is not None
                        else "—", d.get("star_rating") or 0.0)),
            ("col_cs", "tip_col_cs", lambda d: (_num(d.get("cs")), d.get("cs") or 0.0)),
            ("col_ar", "tip_col_ar", lambda d: (_num(d.get("ar")), d.get("ar") or 0.0)),
            ("col_od", "tip_col_od", lambda d: (_num(d.get("od")), d.get("od") or 0.0)),
            ("col_hp", "tip_col_hp", lambda d: (_num(d.get("hp")), d.get("hp") or 0.0)),
        ]

        table = QTableWidget(0, len(columns))
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setHorizontalHeaderLabels([t(c[0]) for c in columns])
        for c, (_key, tip_key, _fn) in enumerate(columns):
            hdr = table.horizontalHeaderItem(c)
            if hdr is not None:
                hdr.setToolTip(t(tip_key))   # explain CS/AR/OD/HP/etc. on hover
        table.setSortingEnabled(False)
        table.setRowCount(len(diffs))
        for r, d in enumerate(diffs):
            for c, (_key, _tip, fn) in enumerate(columns):
                text, sort_val = fn(d)
                item = SortItem(str(text), sort_val)   # numeric-aware header sorting
                if c != 0:
                    item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                table.setItem(r, c, item)
        table.setSortingEnabled(True)   # click a header to sort (numeric where apt)
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        root.addWidget(table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)
