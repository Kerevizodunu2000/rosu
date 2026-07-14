# SPDX-License-Identifier: GPL-3.0-or-later
"""Artists tab: artists ranked by song count; click one to see their songs."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget,
)

from ..i18n import human_duration
from . import wheel_guard
from .copy_table import CopyTable, SortItem


class ArtistsTab(QWidget):
    _SONG_KEYS = ("col_name", "col_id", "col_bpm", "col_length", "col_mapper",
                  "col_mode", "col_sources")

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.ctx = main_window.ctx

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.sort_label = QLabel(objectName="status")
        self.sort = QComboBox()
        self.sort.currentIndexChanged.connect(self.reload)
        wheel_guard.guard(self.sort)   # no accidental change on scroll (item 16)
        top.addWidget(self.sort_label)
        top.addWidget(self.sort)
        top.addStretch(1)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        self.artists = CopyTable(name_column=0)
        self.artists.setColumnCount(4)  # Artist, Songs, Avg length, Avg BPM
        self.artists.cellClicked.connect(self._on_artist)
        self.songs = CopyTable(name_column=0)
        self.songs.setColumnCount(len(self._SONG_KEYS))
        splitter.addWidget(self.artists)
        splitter.addWidget(self.songs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        self.selected = QLabel(objectName="status")
        root.addWidget(self.selected)
        # (data_generation, metric, descending) of the last build — lets on_shown
        # skip a full rebuild when nothing changed (item 10).
        self._built_key = None

    _SORTS = (
        ("sort_most", ("count", True)),
        ("sort_least", ("count", False)),
        ("sort_len_long", ("avg_length", True)),
        ("sort_len_short", ("avg_length", False)),
        ("sort_bpm_high", ("avg_bpm", True)),
        ("sort_bpm_low", ("avg_bpm", False)),
    )

    def retranslate(self) -> None:
        t = self.ctx.t
        self.sort_label.setText(t("sort_by"))
        cur = self.sort.currentIndex()
        self.sort.blockSignals(True)
        self.sort.clear()
        for key, data in self._SORTS:
            self.sort.addItem(t(key), data)
        self.sort.setCurrentIndex(cur if cur >= 0 else 0)
        self.sort.blockSignals(False)
        self.sort.setToolTip(t("tip_artists_sort"))
        self.artists.setHorizontalHeaderLabels(
            [t("col_artist"), t("col_songs"), t("col_avg_length"), t("col_avg_bpm")])
        self.artists.set_menu_labels(t("copy_names_action"), t("copy_table_action"))
        self.songs.setHorizontalHeaderLabels([t(k) for k in self._SONG_KEYS])
        self.songs.set_menu_labels(t("copy_names_action"), t("copy_table_action"))

    def on_shown(self) -> None:
        # Rebuilding the (up to ~1000-row) artists table is expensive and used to run
        # synchronously on EVERY tab focus, freezing the app (item 10). Skip it when
        # neither the data nor the chosen sort changed since the last build.
        metric, descending = self.sort.currentData() or ("count", True)
        key = (self.ctx.services.data_generation(), metric, descending)
        if key != self._built_key:
            self.reload()

    def reload(self) -> None:
        metric, descending = self.sort.currentData() or ("count", True)
        gen = self.ctx.services.data_generation()
        rows = self.ctx.services.artists(metric, descending)
        self.artists.setUpdatesEnabled(False)   # coalesce paints during the build
        self.artists.setSortingEnabled(False)
        try:
            self.artists.setRowCount(len(rows))
            for r, a in enumerate(rows):
                avg_len = a.get("avg_length")
                avg_bpm = a.get("avg_bpm")
                name_item = SortItem(a["artist"])
                name_item.setToolTip(a["artist"] or "")   # full artist on hover (item 15)
                self.artists.setItem(r, 0, name_item)
                self.artists.setItem(r, 1, SortItem(str(a["song_count"]), a["song_count"]))
                self.artists.setItem(r, 2, SortItem(
                    human_duration(int(avg_len)) if avg_len else "", avg_len or 0))
                self.artists.setItem(r, 3, SortItem(
                    f"{avg_bpm:.0f}" if avg_bpm else "", avg_bpm or 0.0))
                for c in (1, 2, 3):
                    self.artists.item(r, c).setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        finally:
            self.artists.setSortingEnabled(True)
            self.artists.setUpdatesEnabled(True)
        self.artists.seed_widths_once(name_min=220)
        self.songs.setRowCount(0)
        self.selected.setText("")
        self._built_key = (gen, metric, descending)

    def _on_artist(self, row: int, _col: int) -> None:
        item = self.artists.item(row, 0)
        if item is None:
            return
        artist = item.text()
        tracks = self.ctx.services.tracks_by_artist(artist)
        self.selected.setText(self.ctx.t("artist_songs", artist=artist, n=len(tracks)))
        self._populate_songs(tracks)

    def _populate_songs(self, tracks: list[dict]) -> None:
        self.songs.setUpdatesEnabled(False)
        self.songs.setSortingEnabled(False)
        try:
            self.songs.setRowCount(len(tracks))
            for r, row in enumerate(tracks):
                bpm = row.get("bpm")
                length = row.get("length_seconds")
                bid = row.get("beatmapset_id")
                cells = [
                    (row.get("title") or row.get("display_name", ""), None),
                    (str(bid) if bid is not None else "-", bid or 0),
                    (f"{bpm:g}" if bpm else "", bpm or 0.0),
                    (human_duration(length), length or 0),
                    (row.get("creator") or "", None),
                    (row.get("mode") or "", None),
                    (", ".join(row.get("sources", [])), None),
                ]
                for c, (text, sort_val) in enumerate(cells):
                    item = SortItem(text, sort_val)
                    if c == 0 and text:
                        item.setToolTip(text)      # full title on hover (item 15)
                    if c in (1, 2, 3):
                        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                    self.songs.setItem(r, c, item)
                self.songs.set_clean_name(r, row.get("display_name", ""))
                full = row.get("source_full") or []
                if full:
                    self.songs.set_copy_value(r, 6, "; ".join(full))
        finally:
            self.songs.setSortingEnabled(True)
            self.songs.setUpdatesEnabled(True)
        self.songs.seed_widths_once(name_min=240)
