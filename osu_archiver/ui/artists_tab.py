"""Artists tab: artists ranked by song count; click one to see their songs."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QSplitter, QVBoxLayout, QWidget,
)

from ..i18n import human_duration
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
        top.addWidget(self.sort_label)
        top.addWidget(self.sort)
        top.addStretch(1)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        self.artists = CopyTable(name_column=0)
        self.artists.setColumnCount(2)
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

    def retranslate(self) -> None:
        t = self.ctx.t
        self.sort_label.setText(t("sort_by"))
        cur = self.sort.currentIndex()
        self.sort.blockSignals(True)
        self.sort.clear()
        self.sort.addItem(t("sort_most"), True)
        self.sort.addItem(t("sort_least"), False)
        self.sort.setCurrentIndex(cur if cur >= 0 else 0)
        self.sort.blockSignals(False)
        self.artists.setHorizontalHeaderLabels([t("col_artist"), t("col_songs")])
        self.songs.setHorizontalHeaderLabels([t(k) for k in self._SONG_KEYS])

    def on_shown(self) -> None:
        self.reload()

    def reload(self) -> None:
        descending = self.sort.currentData()
        if descending is None:
            descending = True
        rows = self.ctx.services.artists(descending)
        self.artists.setSortingEnabled(False)
        self.artists.setRowCount(len(rows))
        for r, a in enumerate(rows):
            self.artists.setItem(r, 0, SortItem(a["artist"]))
            self.artists.setItem(r, 1, SortItem(str(a["song_count"]), a["song_count"]))
        self.artists.setSortingEnabled(True)
        self.artists.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.songs.setRowCount(0)
        self.selected.setText("")

    def _on_artist(self, row: int, _col: int) -> None:
        item = self.artists.item(row, 0)
        if item is None:
            return
        artist = item.text()
        tracks = self.ctx.services.tracks_by_artist(artist)
        self.selected.setText(self.ctx.t("artist_songs", artist=artist, n=len(tracks)))
        self._populate_songs(tracks)

    def _populate_songs(self, tracks: list[dict]) -> None:
        self.songs.setSortingEnabled(False)
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
                if c in (1, 2, 3):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.songs.setItem(r, c, item)
            self.songs.set_clean_name(r, row.get("display_name", ""))
            full = row.get("source_full") or []
            if full:
                self.songs.set_copy_value(r, 6, "; ".join(full))
        self.songs.setSortingEnabled(True)
        self.songs.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
