# SPDX-License-Identifier: GPL-3.0-or-later
"""Search tab: relevance-ranked query over the music memory, with metadata.

Search runs off the UI thread and is debounced, so typing never freezes the app
even on a large library (item 10). An empty box lists everything so the library
is browsable (item 11).
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
    QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from .. import presets, query, table_export
from ..columns import has_library_copy, library_status_text, mode_text, where_marks
from ..i18n import human_duration
from ..workers import Worker
from .copy_table import CopyTable, SortItem
from .cover_gallery import GALLERY_CAP, CoverGallery
from .filters_panel import FiltersPanel
from .histogram import Histogram
from .reveal import reveal_in_explorer

_DATA_ROW_ROLE = Qt.UserRole + 40   # maps a (sortable) view row back to _last_rows

# The query fields the visual Filters panel OWNS (see filters_panel.filter_tokens).
# When the panel changes we replace only these tokens in the box and preserve every
# other token — free text AND hand-typed filters like status=/mapper=/cs= .
_PANEL_FILTER_FIELDS = {"mode", "star", "key", "keys", "bpm", "length", "ar", "od"}


def _pruned_where(row: dict, t) -> str:
    """Which copies of this set have been pruned, translated — "" when none.

    Prune is per-location. ``tracks.is_pruned`` means only "the Library copy is
    stripped"; ``pruned_sources`` records every place a prune ran. A set can be
    pruned in the Library and in osu!(stable) while its osu!lazer copy is whole,
    so a bare "pruned" badge claimed more than was true.
    """
    sources = [s for s in (row.get("pruned_sources") or "").split(",") if s]
    if not sources and row.get("is_pruned"):
        sources = ["library"]      # rows written before pruned_sources existed
    return ", ".join(t(f"prune_source_{s}") for s in sources)


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


_SKILL_ABBR = {"stream": "STR", "jumpstream": "JS", "handstream": "HS",
               "stamina": "STM", "jackspeed": "JCK", "chordjack": "CJ",
               "technical": "TCH"}


def _skill_cell(diffs: list[dict]) -> tuple[str, float, str]:
    """(text, sort, tooltip) for the Skill column — the set's hardest mania
    difficulty's Rosu Skillset overall + its dominant skill (e.g. "5.42 CJ"), with
    a per-diff breakdown on hover. Blank for sets with no rated mania chart."""
    from ..models import MsdResult
    rated = [d for d in diffs if d.get("mode_int") == 3
             and d.get("msd_overall") is not None]
    if not rated:
        return "", 0.0, ""
    best = max(rated, key=lambda d: d["msd_overall"])
    skills = {k: best.get(f"msd_{k}") or 0.0 for k in MsdResult.SKILLS}
    dom = max(skills, key=skills.get)
    text = f"{best['msd_overall']:.2f} {_SKILL_ABBR[dom]}"
    tip_lines = []
    for d in rated:
        vals = " ".join(f"{_SKILL_ABBR[k]}{(d.get(f'msd_{k}') or 0.0):.1f}"
                        for k in MsdResult.SKILLS)
        tip_lines.append(f"{d.get('version') or '?'}  {d['msd_overall']:.2f}★  [{vals}]")
    return text, best["msd_overall"], "\n".join(tip_lines)


class SearchTab(QWidget):
    _KEYS = ("col_name", "col_artist", "col_id", "col_bpm", "col_length",
             "col_mapper", "col_mode", "col_star", "col_keys", "col_skill",
             "col_sources", "col_first_seen", "col_attempts", "col_lib_status",
             "col_location")

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.ctx = main_window.ctx
        self._threads: list[Worker] = []
        self._search_seq = 0        # ignore results from superseded searches
        self._loaded_once = False
        self._last_rows: list[dict] = []   # current results (row → Map Details)
        self._last_truncated = False       # the results are a capped page
        self._pending_histogram = False    # open the histogram once results refresh
        self._hist_mode = "auto"           # star-histogram binning, remembered
        self._hist_pairs: list = []        # (track_id, star) behind the bars

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        row = QHBoxLayout()
        # v1.9: back/forward through the last 16 searches (Alt+←/→).
        self._history = presets.History()
        self._navigating = False
        self.btn_back = QToolButton(objectName="secondary", text="◀")
        self.btn_back.clicked.connect(lambda: self._go_history(-1))
        self.btn_fwd = QToolButton(objectName="secondary", text="▶")
        self.btn_fwd.clicked.connect(lambda: self._go_history(1))
        QShortcut(QKeySequence("Alt+Left"), self, activated=lambda: self._go_history(-1))
        QShortcut(QKeySequence("Alt+Right"), self, activated=lambda: self._go_history(1))
        row.addWidget(self.btn_back)
        row.addWidget(self.btn_fwd)
        self.box = QLineEdit()
        self.box.returnPressed.connect(self.do_search)          # Enter = search now
        self.btn = QPushButton()
        self.btn.clicked.connect(self.do_search)
        self.btn_reload = QPushButton(objectName="secondary")
        self.btn_reload.clicked.connect(self.refresh_now)       # visible re-pull
        self.btn_hist = QPushButton(objectName="secondary")
        self.btn_hist.clicked.connect(self._show_histogram)     # star distribution
        # v1.9: saved searches (a menu rebuilt on open) and CSV/JSON export.
        self.btn_saved = QToolButton(objectName="secondary")
        self.btn_saved.setPopupMode(QToolButton.InstantPopup)
        self.saved_menu = QMenu(self.btn_saved)
        self.saved_menu.aboutToShow.connect(self._fill_saved_menu)
        self.btn_saved.setMenu(self.saved_menu)
        self.btn_export = QPushButton(objectName="secondary")
        self.btn_export.clicked.connect(self._export_results)
        self.btn_gallery = QPushButton(objectName="secondary")
        self.btn_gallery.setCheckable(True)
        self.btn_gallery.setChecked(self.ctx.cfg.search_view == "gallery")
        self.btn_gallery.toggled.connect(self._set_gallery)
        row.addWidget(self.box, 1)
        row.addWidget(self.btn)
        row.addWidget(self.btn_reload)
        row.addWidget(self.btn_saved)
        row.addWidget(self.btn_hist)
        row.addWidget(self.btn_gallery)
        row.addWidget(self.btn_export)
        root.addLayout(row)

        # Visual filters panel (v1.6) — composes the same query syntax into the box.
        self.filters = FiltersPanel(self.ctx)
        self.filters.filtersChanged.connect(self._apply_filters_from_panel)
        self._mode_counts_loaded = False
        root.addWidget(self.filters)

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
        self.table.repairRequested.connect(self._repair_map)
        self.table.stageRequested.connect(self._stage_to_output)
        self.table.rowActivated.connect(self._show_map_details)   # dbl-click → details
        # v1.9: right-click a column header to hide/show columns (remembered).
        header = self.table.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._column_menu)
        self._apply_hidden_columns()
        # v1.9: the same results as a grid of cover art.
        self.gallery = CoverGallery(self.ctx)
        self.gallery.rowActivated.connect(self._show_details_for)
        self._gallery_stale = True
        self.views = QStackedWidget()
        self.views.addWidget(self.table)
        self.views.addWidget(self.gallery)
        self.views.setCurrentWidget(self.gallery if self.btn_gallery.isChecked() else self.table)
        root.addWidget(self.views, 1)

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
        self.filters.retranslate()
        self.hint.setText(t("copy_hint"))
        self.box.setToolTip(t("tip_search_box"))
        self.btn.setToolTip(t("tip_search_btn"))
        self.btn_reload.setToolTip(t("tip_reload"))
        self.btn_saved.setText(t("saved_searches"))
        self.btn_saved.setToolTip(t("tip_saved_searches"))
        self.btn_export.setText(t("btn_export_results"))
        self.btn_export.setToolTip(t("tip_export_results"))
        self.btn_back.setToolTip(t("tip_history_back"))
        self.btn_fwd.setToolTip(t("tip_history_forward"))
        self.btn_gallery.setText(t("btn_gallery"))
        self.btn_gallery.setToolTip(t("tip_gallery", n=GALLERY_CAP))
        self.table.setHorizontalHeaderLabels([t(k) for k in self._KEYS])
        self.table.horizontalHeader().setToolTip(t("tip_column_menu"))
        self.table.set_menu_labels(t("copy_names_action"), t("copy_table_action"))
        self.table._menu_open_location = t("menu_open_location")
        self.table._menu_repair = t("menu_repair")
        self.table._menu_stage = t("menu_stage_output")

    def on_shown(self) -> None:
        # First time the tab is opened, show the full library so it's browsable.
        self._refresh_mode_counts()
        if not self._loaded_once:
            self._loaded_once = True
            self.do_search()

    def reload(self) -> None:
        """Re-run the current query after the library changed elsewhere (item 7)."""
        self._refresh_mode_counts()
        if self._loaded_once:
            self.do_search()

    def _refresh_mode_counts(self) -> None:
        """Tell the filters panel which ruleset toggles the Library can offer."""
        try:
            self.filters.set_mode_counts(self.ctx.services.mode_counts())
            self._mode_counts_loaded = True
        except Exception:
            pass   # a mode-count hiccup must never block search

    def _apply_filters_from_panel(self) -> None:
        """A filters-panel change → replace only the filter tokens the panel OWNS
        (mode/star/key/bpm/length/ar/od), preserving free text AND any other filter
        the user typed by hand (status=, mapper=, cs=, …), then re-run the search."""
        kept = []
        for tok in self.box.text().split():
            m = query._FILTER_RE.fullmatch(tok)
            if m and m.group("key").lower() in _PANEL_FILTER_FIELDS:
                continue   # panel owns this field — it will re-emit it below
            kept.append(tok)
        new = " ".join(kept + self.filters.filter_tokens()).strip()
        self.box.blockSignals(True)     # avoid a second (debounced) search
        self.box.setText(new)
        self.box.blockSignals(False)
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
        w = Worker(self.ctx.services.search_page, query,
                   search_tags=self.chk_tags.isChecked())
        self._threads.append(w)
        w.succeeded.connect(lambda res, s=seq, q=query: self._on_results(res, s, q))
        w.failed.connect(self._on_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _on_failed(self, msg: str) -> None:
        self.result.setText(msg)

    def _on_results(self, res: dict, seq: int, query: str) -> None:
        if seq != self._search_seq:
            return  # a newer search already ran; drop this stale result
        rows = res["rows"]
        total = res["total"]
        self._last_truncated = bool(res["truncated"])
        if not self._navigating:
            self._history.push((query, self.chk_tags.isChecked()), time.monotonic())
        self._navigating = False
        self._sync_history_buttons()
        self._populate(rows)
        t = self.ctx.t
        if res["truncated"]:
            # Never present the cap as if it were the whole answer — the silent
            # 500-row cut is exactly what made a 1600-set range look like 500.
            self.result.setText(t("search_truncated", n=len(rows), total=total))
        elif not query:
            self.result.setText(t("browse_all", n=len(rows)))
        else:
            self.result.setText(t("search_have", n=len(rows)) if rows
                                else t("search_none"))
        if self._pending_histogram:   # a compute-ratings run just refreshed us
            self._pending_histogram = False
            self._open_histogram()

    def _populate(self, rows: list[dict]) -> None:
        self._last_rows = rows
        self._gallery_stale = True
        if self.btn_gallery.isChecked():
            self._fill_gallery()
        self.table.setUpdatesEnabled(False)   # coalesce paints while filling (item 10)
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                status = library_status_text(row, self.ctx.t)
                # `is_pruned` used to exist ONLY to decide whether the row got a
                # repair context-menu entry — invisible otherwise. And it is
                # per-LOCATION: a set can be stripped in the Library and/or in
                # osu!(stable) while its osu!lazer copy is untouched, so the badge
                # has to name where, or it over-claims.
                where = _pruned_where(row, self.ctx.t)
                if where:
                    status = f"{status} · {self.ctx.t('lib_status_pruned')} ({where})"
                bpm = row.get("bpm")
                length = row.get("length_seconds")
                attempts = row.get("copy_attempts", 0)
                bid = row.get("beatmapset_id")
                loc_marks, loc_weight = where_marks(row)
                diffs = row.get("difficulties") or []
                star_text, star_sort, star_tip = _star_cell(diffs)
                key_text, key_sort = _key_cell(diffs)
                skill_text, skill_sort, skill_tip = _skill_cell(diffs)
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
                    (mode_text(diffs, row.get("mode")), None),  # every diff's mode
                    (star_text, star_sort),    # each diff's exact star; sort on hardest
                    (key_text, key_sort),      # mania key counts (blank for other modes)
                    (skill_text, skill_sort),  # mania Rosu Skillset overall + dominant
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
                    if c == 9 and skill_tip:
                        item.setToolTip(skill_tip)  # per-diff Rosu Skillset breakdown
                    if c == 13 and where:
                        item.setToolTip(self.ctx.t("pruned_tip", where=where))
                    if c == 14:
                        item.setToolTip(self.ctx.t("where_legend"))  # explain the icons
                    if c in (2, 3, 4, 7, 8, 9, 12):
                        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                    self.table.setItem(r, c, item)
                self.table.set_clean_name(r, row.get("display_name", ""))
                # remember which _last_rows entry this row is, so a double-click
                # opens the right map even after the user re-sorts a column
                self.table.item(r, 0).setData(_DATA_ROW_ROLE, r)
                full = row.get("source_full") or []
                if full:
                    self.table.set_copy_value(r, 10, "; ".join(full))
                
                # Expose 'Open location' / 'Repair'
                is_missing = not row.get("in_library")
                is_pruned = row.get("is_pruned")
                if row.get("filename"):
                    if has_library_copy(row):   # never point at a memory-only set
                        self.table.set_row_path(r, self.ctx.cfg.library_path / row["filename"])
                    if is_missing or is_pruned:
                        self.table.set_repair_filename(r, row["filename"])
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)
        self.table.seed_widths_once(name_min=260)   # title-only name column

    def _open_location(self, path: str) -> None:
        reveal_in_explorer(self, self.ctx, path)

    def _stage_to_output(self, paths: list) -> None:
        """Library → Output staging (v1.9): pick sets here, then "Import to
        osu!" on the Dashboard sends exactly those."""
        w = Worker(self.ctx.services.stage_to_output, paths)
        self._threads.append(w)
        w.succeeded.connect(self._staged)
        w.failed.connect(self._on_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _staged(self, res: dict) -> None:
        self.result.setText(self.ctx.t("stage_output_done", n=res.get("copied", 0),
                                       already=res.get("already", 0),
                                       skipped=res.get("skipped", 0)))
        self.mw.dashboard.refresh_scan()

    # -- columns (v1.9) ----------------------------------------------------------
    def _apply_hidden_columns(self) -> None:
        hidden = set(self.ctx.cfg.search_hidden_columns)
        for c, key in enumerate(self._KEYS):
            # The name column carries copy/open/details: it never hides.
            self.table.setColumnHidden(c, c != 0 and key in hidden)

    def _column_menu(self, pos) -> None:
        t = self.ctx.t
        menu = QMenu(self)
        for c, key in enumerate(self._KEYS):
            act = menu.addAction(t(key))
            act.setCheckable(True)
            act.setChecked(not self.table.isColumnHidden(c))
            act.setEnabled(c != 0)
            act.toggled.connect(lambda on, k=key: self._set_column_visible(k, on))
        menu.addSeparator()
        menu.addAction(t("columns_show_all"), lambda: self._set_hidden_columns([]))
        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    def _set_column_visible(self, key: str, visible: bool) -> None:
        hidden = [k for k in self.ctx.cfg.search_hidden_columns if k != key]
        if not visible:
            hidden.append(key)
        self._set_hidden_columns(hidden)

    def _set_hidden_columns(self, hidden: list[str]) -> None:
        self.ctx.cfg.search_hidden_columns = [k for k in self._KEYS[1:] if k in hidden]
        self._apply_hidden_columns()
        self.ctx.save_config()   # UI state: saved at once in either Settings mode

    # -- saved searches (v1.9) ---------------------------------------------------
    def _fill_saved_menu(self) -> None:
        t = self.ctx.t
        menu = self.saved_menu
        menu.clear()
        save = menu.addAction(t("saved_search_save"), self._save_current_search)
        save.setEnabled(bool(self.box.text().strip()))
        saved = self.ctx.cfg.saved_searches
        if saved:
            menu.addSeparator()
            for e in saved:
                act = menu.addAction(e["name"], lambda e=e: self.apply_saved_search(e))
                act.setToolTip(e["query"])
            menu.setToolTipsVisible(True)
            menu.addSeparator()
            delete = menu.addMenu(t("saved_search_delete"))
            for e in saved:
                delete.addAction(e["name"], lambda n=e["name"]: self._delete_saved_search(n))
        else:
            menu.addSeparator()
            menu.addAction(t("saved_search_none")).setEnabled(False)

    def _save_current_search(self) -> None:
        t = self.ctx.t
        text = self.box.text().strip()
        if not text:
            return
        name, ok = QInputDialog.getText(self, t("saved_searches"), t("saved_search_name"),
                                        text=text[:presets.NAME_MAX])
        if not ok or not name.strip():
            return
        self.ctx.cfg.saved_searches = presets.save(
            self.ctx.cfg.saved_searches, name, text, self.chk_tags.isChecked())
        self.ctx.save_config()
        self.result.setText(t("saved_search_saved", name=" ".join(name.split())))

    def _sync_history_buttons(self) -> None:
        self.btn_back.setEnabled(self._history.can_back())
        self.btn_fwd.setEnabled(self._history.can_forward())

    def _go_history(self, step: int) -> None:
        entry = self._history.back() if step < 0 else self._history.forward()
        if entry is None:
            return
        self._navigating = True
        self.apply_saved_search({"query": entry[0], "tags": entry[1]})

    def apply_saved_search(self, entry: dict) -> None:
        """Put a saved search back in the box (and the tags toggle) and run it."""
        self.filters.blockSignals(True)   # reset the panel without it rewriting the box
        self.filters.clear()
        self.filters.blockSignals(False)
        self.chk_tags.blockSignals(True)
        self.chk_tags.setChecked(bool(entry.get("tags")))
        self.chk_tags.blockSignals(False)
        self.box.blockSignals(True)
        self.box.setText(entry.get("query", ""))
        self.box.blockSignals(False)
        self.do_search()

    def _delete_saved_search(self, name: str) -> None:
        self.ctx.cfg.saved_searches = presets.remove(self.ctx.cfg.saved_searches, name)
        self.ctx.save_config()

    # -- export (v1.9) -------------------------------------------------------------
    def _export_results(self) -> None:
        t = self.ctx.t
        if not self._last_rows:
            self.result.setText(t("export_results_none"))
            return
        path, _flt = QFileDialog.getSaveFileName(
            self, t("btn_export_results"), str(self.ctx.cfg.data_path / "rosu-search.csv"),
            "CSV (*.csv);;JSON (*.json)")
        if not path:
            return
        if not path.lower().endswith((".csv", ".json")):
            path += ".json" if "json" in _flt.lower() else ".csv"
        try:
            n = table_export.write(path, self._last_rows, self.box.text().strip())
        except OSError as exc:
            QMessageBox.warning(self, t("app_title"), t("export_results_failed", error=str(exc)))
            return
        self.result.setText(t("export_results_done_shown" if self._last_truncated
                              else "export_results_done", n=n))

    def _repair_map(self, filename: str) -> None:
        t = self.ctx.t
        reply = QMessageBox.question(
            self, t("repair_confirm_title"),
            t("repair_confirm_body", filename=filename),
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        w = Worker(lambda progress=None:
                  self.ctx.services.repair_maps([filename], progress))
        self._threads.append(w)
        w.succeeded.connect(self._repair_done)
        w.failed.connect(self._repair_failed)
        w.finished.connect(lambda: self._threads.remove(w) if w in self._threads else None)
        w.start()

    def _repair_done(self, res) -> None:
        t = self.ctx.t
        repaired = res.get("repaired", 0)
        failed = len(res.get("failed", []))
        if repaired and not failed:
            self.result.setText(t("repair_done", repaired=repaired))
        elif repaired:
            self.result.setText(t("repair_partial", repaired=repaired, failed=failed))
        else:
            self.result.setText(t("repair_none"))
        if repaired:
            self.reload()

    def _repair_failed(self, msg) -> None:
        QMessageBox.critical(self, self.ctx.t("app_title"), msg)

    def _show_map_details(self, view_row: int) -> None:
        """Double-click a result → full per-difficulty details + enriched metadata."""
        item = self.table.item(view_row, 0)
        if item is None:
            return
        self._show_details_for(item.data(_DATA_ROW_ROLE))

    def _show_details_for(self, idx) -> None:
        if idx is None or not 0 <= idx < len(self._last_rows):
            return
        from .map_details_dialog import MapDetailsDialog
        MapDetailsDialog(self.ctx, self._last_rows[idx], self,
                         on_restore=self._repair_map).exec()

    # -- gallery (v1.9) ------------------------------------------------------------
    def _set_gallery(self, on: bool) -> None:
        self.views.setCurrentWidget(self.gallery if on else self.table)
        self.ctx.cfg.search_view = "gallery" if on else "table"
        self.ctx.save_config()   # UI state: saved at once in either Settings mode
        if on:
            self._fill_gallery()
        else:
            self.gallery.stop()

    def _fill_gallery(self) -> None:
        if self._gallery_stale:
            self._gallery_stale = False
            self.gallery.set_rows(self._last_rows)

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
        """The whole Library's star distribution, binned per DIFFICULTY.

        Both halves of this used to lie: the bars came from ``self._last_rows``
        (one capped page of search results, not the library) and they binned each
        set's ``star_max`` (its hardest diff) while clicking a bar searched
        ``star>=lo star<hi``, which matches *any* difficulty — so a 2★+5★ set was
        drawn in the 5★ bar yet turned up in the 2★ search. The service now bins
        difficulties, which is the same unit the ``star>=`` filter already used.
        """
        t = self.ctx.t
        data = self.ctx.services.star_histogram_data(mode=self._hist_mode)
        self._hist_pairs = data["pairs"]   # (track_id, star) — for the set count
        if not data["bins"]:
            QMessageBox.information(self, t("app_title"), t("star_dist_empty"))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(t("star_dist_title"))
        dlg.setMinimumSize(520, 380)
        lay = QVBoxLayout(dlg)
        head = QLabel(objectName="status")
        head.setText(t("star_dist_head", n=data["difficulties"], sets=data["sets"]))
        lay.addWidget(head)

        # Bin mode: the data-driven split gives edges like 3.94–4.55, which is
        # unreadable as "how many 5★ maps do I have"; plain 1★ buckets answer that.
        mode_row = QHBoxLayout()
        mode_lbl = QLabel(t("star_dist_bins"))
        mode_lbl.setToolTip(t("star_dist_bins_tip"))
        mode_row.addWidget(mode_lbl)
        mode_box = QComboBox()
        mode_box.setToolTip(t("star_dist_bins_tip"))
        mode_box.addItem(t("star_dist_bins_auto"), "auto")
        mode_box.setItemData(0, t("star_dist_bins_auto_tip"), Qt.ToolTipRole)
        mode_box.addItem(t("star_dist_bins_integer"), "integer")
        mode_box.setItemData(1, t("star_dist_bins_integer_tip"), Qt.ToolTipRole)
        idx = mode_box.findData(self._hist_mode)
        mode_box.setCurrentIndex(idx if idx >= 0 else 0)
        mode_row.addWidget(mode_box)
        mode_row.addStretch(1)
        lay.addLayout(mode_row)

        hist = Histogram()
        hist.set_bins(data["bins"])
        lay.addWidget(hist, 1)
        sel = QLabel(objectName="status")
        sel.setWordWrap(True)
        sel.setText(t("star_dist_hint"))
        lay.addWidget(sel)

        bar = QHBoxLayout()
        btn_search = QPushButton(t("star_dist_search"))
        btn_search.setVisible(False)   # only after a bar is clicked/selected
        btn_export = QPushButton(t("star_dist_export"), objectName="secondary")
        btn_export.setVisible(False)
        bar.addStretch(1)
        bar.addWidget(btn_export)
        bar.addWidget(btn_search)
        lay.addLayout(bar)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        lay.addWidget(buttons)

        def on_sel(lo, hi, count, pct):
            # Say the SET count too, and say it before the user clicks Search.
            # The bar counts difficulties; the search lists the sets holding them,
            # so "2727 difficulties" followed by "1509 matches" looked like a bug.
            sets = len({tid for tid, star in self._hist_pairs if lo <= star < hi})
            sel.setText(t("star_dist_selected", lo=f"{lo:.2f}", hi=f"{hi:.2f}",
                          count=count, pct=f"{pct:.1f}", sets=sets))
            btn_search.setVisible(True)
            btn_export.setVisible(True)

        def do_range():
            rng = hist.selection_range()
            if rng:
                dlg.accept()
                self._search_star_range(rng[0], rng[1])

        def do_export():
            rng = hist.selection_range()
            if rng:
                dlg.accept()
                self._export_star_range(rng[0], rng[1])

        def on_activated(lo, hi):
            dlg.accept()
            self._search_star_range(lo, hi)   # double-click a bar → jump to Search

        def on_mode(_i=None):
            self._hist_mode = mode_box.currentData() or "auto"
            fresh = self.ctx.services.star_histogram_data(mode=self._hist_mode)
            self._hist_pairs = fresh["pairs"]
            hist.set_bins(fresh["bins"])      # also clears the selection
            head.setText(t("star_dist_head", n=fresh["difficulties"],
                           sets=fresh["sets"]))
            sel.setText(t("star_dist_hint"))
            btn_search.setVisible(False)
            btn_export.setVisible(False)

        mode_box.currentIndexChanged.connect(on_mode)
        hist.barSelected.connect(on_sel)
        hist.barActivated.connect(on_activated)
        btn_search.clicked.connect(do_range)
        btn_export.clicked.connect(do_export)
        dlg.exec()

    def _search_star_range(self, lo: float, hi: float) -> None:
        """Put a star-range query in the box and run it (from the histogram)."""
        self.box.setText(f"star>={lo:.2f} star<{hi:.2f}")
        self.do_search()

    def _export_star_range(self, lo: float, hi: float) -> None:
        """Hand a star range to the Shortcuts export flow (from the histogram)."""
        self.mw.shortcuts.prefill_star_range(lo, hi)
        self.mw.tabs.setCurrentWidget(self.mw.shortcuts)
