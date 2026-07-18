# SPDX-License-Identifier: GPL-3.0-or-later
"""Search tab: relevance-ranked query over the music memory, with metadata.

Search runs off the UI thread and is debounced, so typing never freezes the app
even on a large library (item 10). An empty box lists everything so the library
is browsable (item 11).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ..i18n import human_duration
from ..workers import Worker
from .copy_table import CopyTable, SortItem
from .histogram import Histogram
from .reveal import reveal_in_explorer

_DATA_ROW_ROLE = Qt.UserRole + 40   # maps a (sortable) view row back to _last_rows


def _star_cell(diffs: list[dict]) -> tuple[str, float, str]:
    """(text, sort, tooltip) for the Star column from a set's per-diff rows.

    Shows EACH difficulty's exact star ("1.61, 4.30, 5.42") — not a lossy min–max
    range — and a per-diff breakdown (mode / keys / CS·AR·OD·HP) on hover.
    """
    stars = sorted({round(d["star_rating"], 2) for d in diffs
                    if d.get("star_rating") is not None})
    if not stars:
        return "—", 0.0, ""
    text = ", ".join(f"{s:.2f}" for s in stars)
    tip_lines = []
    for d in diffs:
        parts = [d.get("version") or "?"]
        if d.get("mode"):
            parts.append(d["mode"])
        if d.get("keycount"):
            parts.append(f"{d['keycount']}K")
        sr = d.get("star_rating")
        parts.append(f"{sr:.2f}★" if sr is not None else "—★")
        attrs = [f"{lbl}{d[key]:g}" for lbl, key in
                 (("CS", "cs"), ("AR", "ar"), ("OD", "od"), ("HP", "hp"))
                 if d.get(key) is not None]
        line = "  ".join(parts)
        if attrs:
            line += "   [" + " ".join(attrs) + "]"
        tip_lines.append(line)
    return text, max(stars), "\n".join(tip_lines)


def _key_cell(diffs: list[dict]) -> tuple[str, int]:
    """(text, sort) for the Keys column — distinct mania key counts, e.g. "4K, 7K"."""
    keys = sorted({d["keycount"] for d in diffs if d.get("keycount")})
    if not keys:
        return "", 0
    return ", ".join(f"{k}K" for k in keys), max(keys)


class SearchTab(QWidget):
    _KEYS = ("col_name", "col_artist", "col_id", "col_bpm", "col_length",
             "col_mapper", "col_mode", "col_star", "col_keys", "col_sources",
             "col_first_seen", "col_attempts", "col_lib_status", "col_location")

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.ctx = main_window.ctx
        self._threads: list[Worker] = []
        self._search_seq = 0        # ignore results from superseded searches
        self._loaded_once = False
        self._last_rows: list[dict] = []   # current results, for the star histogram
        self._pending_histogram = False    # open the histogram once results refresh

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        row = QHBoxLayout()
        self.box = QLineEdit()
        self.box.returnPressed.connect(self.do_search)          # Enter = search now
        self.btn = QPushButton()
        self.btn.clicked.connect(self.do_search)
        self.btn_reload = QPushButton(objectName="secondary")
        self.btn_reload.clicked.connect(self.refresh_now)       # visible re-pull
        self.btn_hist = QPushButton(objectName="secondary")
        self.btn_hist.clicked.connect(self._show_histogram)     # star distribution
        row.addWidget(self.box, 1)
        row.addWidget(self.btn)
        row.addWidget(self.btn_reload)
        row.addWidget(self.btn_hist)
        root.addLayout(row)

        # Opt-in: also match creator/tags. Off by default — tag matching used to
        # flood results (e.g. every Vocaloid map for "Hatsune Miku").
        self.chk_tags = QCheckBox()
        self.chk_tags.toggled.connect(lambda _=None: self.do_search())
        root.addWidget(self.chk_tags)

        self.result = QLabel(objectName="status")
        root.addWidget(self.result)
        self.hint = QLabel(objectName="status")
        root.addWidget(self.hint)

        self.table = CopyTable(name_column=0, activate_details=True)
        self.table.setColumnCount(len(self._KEYS))
        self.table.openLocationRequested.connect(self._open_location)
        self.table.rowActivated.connect(self._show_map_details)   # dbl-click → details
        root.addWidget(self.table, 1)

        # Debounced live search: wait until typing pauses (~250 ms) before running.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self.do_search)
        self.box.textChanged.connect(lambda _=None: self._debounce.start())

    def retranslate(self) -> None:
        t = self.ctx.t
        self.box.setPlaceholderText(t("search_placeholder"))
        self.btn.setText(t("tab_search"))
        self.btn_reload.setText(t("btn_reload"))
        self.btn_hist.setText(t("btn_star_dist"))
        self.btn_hist.setToolTip(t("tip_star_dist"))
        self.chk_tags.setText(t("search_tags_toggle"))
        self.chk_tags.setToolTip(t("tip_search_tags"))
        self.hint.setText(t("copy_hint"))
        self.box.setToolTip(t("tip_search_box"))
        self.btn.setToolTip(t("tip_search_btn"))
        self.btn_reload.setToolTip(t("tip_reload"))
        self.table.setHorizontalHeaderLabels([t(k) for k in self._KEYS])
        self.table.set_menu_labels(t("copy_names_action"), t("copy_table_action"))
        self.table._menu_open_location = t("menu_open_location")

    def on_shown(self) -> None:
        # First time the tab is opened, show the full library so it's browsable.
        if not self._loaded_once:
            self._loaded_once = True
            self.do_search()

    def reload(self) -> None:
        """Re-run the current query after the library changed elsewhere (item 7)."""
        if self._loaded_once:
            self.do_search()

    def refresh_now(self) -> None:
        """Explicit ⟳: clear the table first so the list visibly re-loads from
        scratch — a refresh the eye can register even when the re-query is
        near-instant (the fill itself is the 'animation')."""
        self.table.setRowCount(0)
        self.result.setText(self.ctx.t("refreshing"))
        self.do_search()

    def do_search(self) -> None:
        self._debounce.stop()
        query = self.box.text().strip()
        self._search_seq += 1
        seq = self._search_seq
        self.result.setText(self.ctx.t("working"))
        w = Worker(self.ctx.services.search, query,
                   search_tags=self.chk_tags.isChecked())
        self._threads.append(w)
        w.succeeded.connect(lambda rows, s=seq, q=query: self._on_results(rows, s, q))
        w.failed.connect(self._on_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_failed(self, msg: str) -> None:
        self.result.setText(msg)

    def _on_results(self, rows: list[dict], seq: int, query: str) -> None:
        if seq != self._search_seq:
            return  # a newer search already ran; drop this stale result
        self._populate(rows)
        if not query:
            self.result.setText(self.ctx.t("browse_all", n=len(rows)))
        else:
            self.result.setText(self.ctx.t("search_have", n=len(rows)) if rows
                                else self.ctx.t("search_none"))
        if self._pending_histogram:   # a compute-ratings run just refreshed us
            self._pending_histogram = False
            self._open_histogram()

    def _populate(self, rows: list[dict]) -> None:
        self._last_rows = rows
        self.table.setUpdatesEnabled(False)   # coalesce paints while filling (item 10)
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                status = row.get("library_status") or "-"
                if status == "disappeared" and row.get("status_changed_at"):
                    status = f"disappeared @ {row['status_changed_at']}"
                bpm = row.get("bpm")
                length = row.get("length_seconds")
                attempts = row.get("copy_attempts", 0)
                bid = row.get("beatmapset_id")
                loc_marks = []
                in_lazer = row.get("in_osu_lazer")
                in_stable = row.get("in_osu_stable")
                if in_lazer:
                    loc_marks.append("🎮")           # osu!lazer
                if in_stable:
                    loc_marks.append("🕹️")           # osu!(stable)
                if not in_lazer and not in_stable and row.get("in_osu"):
                    loc_marks.append("🎮")           # legacy flag, client unknown
                if row.get("in_library"):
                    loc_marks.append("💾")           # Library
                if row.get("in_drive"):
                    loc_marks.append("☁️")           # Drive backup
                loc_weight = ((4 if row.get("in_osu") else 0)
                              + (2 if row.get("in_library") else 0)
                              + (1 if row.get("in_drive") else 0))
                diffs = row.get("difficulties") or []
                star_text, star_sort, star_tip = _star_cell(diffs)
                key_text, key_sort = _key_cell(diffs)
                cells = [
                    # Show the title only — the artist is its own column, so
                    # "Artist - Title" here was redundant and ate width. The full
                    # "Artist - Title" is still what a click/Ctrl+C copies (below).
                    (row.get("title") or row.get("display_name", ""), None),
                    (row.get("artist", ""), None),
                    (str(bid) if bid is not None else "-", bid or 0),
                    (f"{bpm:g}" if bpm else "", bpm or 0.0),
                    (human_duration(length), length or 0),
                    (row.get("creator") or "", None),
                    (row.get("mode") or "", None),
                    (star_text, star_sort),    # each diff's exact star; sort on hardest
                    (key_text, key_sort),      # mania key counts (blank for other modes)
                    (", ".join(row.get("sources", [])), None),
                    (row.get("first_seen_at", ""), None),
                    (str(attempts), attempts),
                    (status, None),
                    (" ".join(loc_marks) if loc_marks else "-", loc_weight),
                ]
                for c, (text, sort_val) in enumerate(cells):
                    item = SortItem(text, sort_val)
                    if c in (0, 1) and text:
                        item.setToolTip(text)      # full name/artist on hover (item 15)
                    if c == 7 and star_tip:
                        item.setToolTip(star_tip)  # per-diff star + CS/AR/OD/HP
                    if c == 13:
                        item.setToolTip(self.ctx.t("where_legend"))  # explain the icons
                    if c in (2, 3, 4, 7, 8, 11):
                        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                    self.table.setItem(r, c, item)
                self.table.set_clean_name(r, row.get("display_name", ""))
                # remember which _last_rows entry this row is, so a double-click
                # opens the right map even after the user re-sorts a column
                self.table.item(r, 0).setData(_DATA_ROW_ROLE, r)
                full = row.get("source_full") or []
                if full:
                    self.table.set_copy_value(r, 9, "; ".join(full))
                if row.get("in_library") and row.get("filename"):
                    self.table.set_row_path(
                        r, self.ctx.cfg.library_path / row["filename"])
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)
        self.table.seed_widths_once(name_min=260)   # title-only name column

    def _open_location(self, path: str) -> None:
        reveal_in_explorer(self, self.ctx, path)

    def _show_map_details(self, view_row: int) -> None:
        """Double-click a result → full per-difficulty details + enriched metadata."""
        item = self.table.item(view_row, 0)
        if item is None:
            return
        idx = item.data(_DATA_ROW_ROLE)
        if idx is None or idx >= len(self._last_rows):
            return
        from .map_details_dialog import MapDetailsDialog
        MapDetailsDialog(self.ctx, self._last_rows[idx], self).exec()

    def _show_histogram(self) -> None:
        """Star distribution. If the Library has sets without a star yet, offer to
        scan them first (this is now the only place ratings are computed — the
        Dashboard button is gone). Empty Library → tell the user to add music."""
        t = self.ctx.t
        status = self.ctx.services.rating_status()
        if status["in_library"] == 0:
            QMessageBox.information(self, t("app_title"), t("star_dist_no_library"))
            return
        if status["unrated"] > 0 and status["engine"]:
            reply = QMessageBox.question(
                self, t("app_title"),
                t("star_dist_scan_prompt", n=status["unrated"]),
                QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Ok)
            if reply == QMessageBox.Ok:
                self._compute_then_histogram()
                return
        self._open_histogram()

    def _compute_then_histogram(self) -> None:
        self.result.setText(self.ctx.t("ratings_scanning"))
        self.btn_hist.setEnabled(False)
        w = Worker(self.ctx.services.compute_ratings)
        self._threads.append(w)
        w.progressed.connect(self._on_compute_progress)
        w.succeeded.connect(self._on_computed)
        w.failed.connect(self._on_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_compute_progress(self, msg) -> None:
        if isinstance(msg, dict) and msg.get("kind") == "ratings":
            self.result.setText(self.ctx.t(
                "ratings_progress", done=msg.get("done", 0), total=msg.get("total", 0)))

    def _on_computed(self, res) -> None:
        self.btn_hist.setEnabled(True)
        if isinstance(res, dict) and res.get("error") == "no_rosu_pp":
            QMessageBox.information(self, self.ctx.t("app_title"),
                                    self.ctx.t("ratings_no_engine_msg"))
            return
        # Re-run the current query so the Star column + histogram reflect the new
        # ratings, then open the histogram once those results arrive.
        self._pending_histogram = True
        self.do_search()

    def _open_histogram(self) -> None:
        t = self.ctx.t
        values = [r["star_max"] for r in self._last_rows
                  if r.get("star_max") is not None]
        if not values:
            QMessageBox.information(self, t("app_title"), t("star_dist_empty"))
            return
        from ..stats import histogram_bins
        dlg = QDialog(self)
        dlg.setWindowTitle(t("star_dist_title"))
        dlg.setMinimumSize(520, 380)
        lay = QVBoxLayout(dlg)
        head = QLabel(objectName="status")
        head.setText(t("star_dist_head", n=len(values)))
        lay.addWidget(head)
        hist = Histogram()
        hist.set_bins(histogram_bins(values))
        lay.addWidget(hist, 1)
        sel = QLabel(objectName="status")
        sel.setWordWrap(True)
        sel.setText(t("star_dist_hint"))
        lay.addWidget(sel)

        bar = QHBoxLayout()
        btn_search = QPushButton(t("star_dist_search"))
        btn_search.setVisible(False)   # only after a bar is clicked/selected
        bar.addStretch(1)
        bar.addWidget(btn_search)
        lay.addLayout(bar)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        lay.addWidget(buttons)

        def on_sel(lo, hi, count, pct):
            sel.setText(t("star_dist_selected", lo=f"{lo:.2f}", hi=f"{hi:.2f}",
                          count=count, pct=f"{pct:.1f}"))
            btn_search.setVisible(True)

        def do_range():
            rng = hist.selection_range()
            if rng:
                dlg.accept()
                self._search_star_range(rng[0], rng[1])

        def on_activated(lo, hi):
            dlg.accept()
            self._search_star_range(lo, hi)   # double-click a bar → jump to Search

        hist.barSelected.connect(on_sel)
        hist.barActivated.connect(on_activated)
        btn_search.clicked.connect(do_range)
        dlg.exec()

    def _search_star_range(self, lo: float, hi: float) -> None:
        """Put a star-range query in the box and run it (from the histogram)."""
        self.box.setText(f"star>={lo:.2f} star<{hi:.2f}")
        self.do_search()
