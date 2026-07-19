# SPDX-License-Identifier: GPL-3.0-or-later
"""Visual Filters panel for the Search tab (v1.6, deferred from v1.5).

A collapsible panel that composes the SAME query-syntax the Search box already
understands (see :mod:`rosu.query` + ``db._build_filter_sql``) — it is purely a UX
layer over that backend. Changing a control rewrites the Search box's *filter*
tokens (preserving any free text the user typed) and re-runs the search, so the box
always shows the equivalent syntax (which quietly teaches it).

Mode toggles use OUR OWN neutral glyphs — ppy's osu! ruleset icons are trademarked,
so they are deliberately NOT used — and a mode you own no maps of is disabled with a
"no <mode> maps" hint. A blank/neutral control contributes no filter.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from ..query import _parse_length
from .range_slider import RangeSlider

_STAR_CAP = 12.0

# (mode display name, our own glyph). NOT ppy's ruleset icons (trademark).
_MODES = [("osu!", "●"), ("osu!taiko", "◎"), ("osu!catch", "◆"), ("osu!mania", "▤")]
_MODE_ALIAS = {"osu!": "osu", "osu!taiko": "taiko",
               "osu!catch": "catch", "osu!mania": "mania"}


def _spin(maximum: float, decimals: int = 0, step: float = 1.0) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(0.0, maximum)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setSpecialValueText("—")   # 0 shows as "—" = off
    return s


class FiltersPanel(QWidget):
    filtersChanged = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._selected_mode: str | None = None
        self._suspend = False    # block signal storms while resetting

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        head = QHBoxLayout()
        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.RightArrow)
        self.toggle.toggled.connect(self._on_toggle)
        self.btn_clear = QPushButton(objectName="secondary")
        self.btn_clear.clicked.connect(self.clear)
        head.addWidget(self.toggle)
        head.addStretch(1)
        head.addWidget(self.btn_clear)
        root.addLayout(head)

        self.body = QFrame()
        self.body.setVisible(False)
        grid = QGridLayout(self.body)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        # -- mode toggles ----------------------------------------------------
        self.lbl_mode = QLabel()
        mode_row = QHBoxLayout()
        self.mode_btns: dict = {}
        for disp, glyph in _MODES:
            b = QPushButton(f"{glyph}")
            b.setCheckable(True)
            b.setObjectName("secondary")
            b.setMaximumWidth(64)
            b.clicked.connect(lambda _=False, d=disp: self._on_mode_clicked(d))
            self.mode_btns[disp] = b
            mode_row.addWidget(b)
        mode_row.addStretch(1)
        grid.addWidget(self.lbl_mode, 0, 0)
        grid.addLayout(mode_row, 0, 1)

        # -- star range (dual slider + min/max boxes) ------------------------
        self.lbl_star = QLabel()
        self.star = RangeSlider(0.0, _STAR_CAP, 0.1)
        self.star.rangeChanged.connect(self._on_star_slider)
        self.star_lo = _spin(_STAR_CAP, decimals=1, step=0.1)
        self.star_hi = _spin(_STAR_CAP, decimals=1, step=0.1)
        self.star_hi.setValue(_STAR_CAP)          # max = cap = "off"
        self.star_lo.valueChanged.connect(self._on_star_spin)
        self.star_hi.valueChanged.connect(self._on_star_spin)
        star_box = QHBoxLayout()
        star_box.addWidget(self.star_lo)
        star_box.addWidget(self.star, 1)
        star_box.addWidget(self.star_hi)
        grid.addWidget(self.lbl_star, 1, 0)
        grid.addLayout(star_box, 1, 1)

        # -- keys (mania) ----------------------------------------------------
        self.lbl_keys = QLabel()
        self.keys = QComboBox()
        self.keys.addItem("—", 0)
        for k in range(1, 11):
            self.keys.addItem(f"{k}K", k)
        self.keys.currentIndexChanged.connect(lambda _=0: self._emit())
        grid.addWidget(self.lbl_keys, 2, 0)
        grid.addWidget(self.keys, 2, 1)

        # -- BPM range -------------------------------------------------------
        self.lbl_bpm = QLabel()
        self.bpm_lo = _spin(1000, decimals=0, step=5)
        self.bpm_hi = _spin(1000, decimals=0, step=5)
        self.bpm_lo.valueChanged.connect(lambda _=0: self._emit())
        self.bpm_hi.valueChanged.connect(lambda _=0: self._emit())
        bpm_box = QHBoxLayout()
        bpm_box.addWidget(self.bpm_lo)
        bpm_box.addWidget(QLabel("–"))
        bpm_box.addWidget(self.bpm_hi)
        bpm_box.addStretch(1)
        grid.addWidget(self.lbl_bpm, 3, 0)
        grid.addLayout(bpm_box, 3, 1)

        # -- length range (mm:ss or seconds) ---------------------------------
        self.lbl_length = QLabel()
        self.len_lo = QLineEdit()
        self.len_hi = QLineEdit()
        self.len_lo.setMaximumWidth(80)
        self.len_hi.setMaximumWidth(80)
        self.len_lo.editingFinished.connect(self._emit)
        self.len_hi.editingFinished.connect(self._emit)
        len_box = QHBoxLayout()
        len_box.addWidget(self.len_lo)
        len_box.addWidget(QLabel("–"))
        len_box.addWidget(self.len_hi)
        len_box.addStretch(1)
        grid.addWidget(self.lbl_length, 4, 0)
        grid.addLayout(len_box, 4, 1)

        # -- AR / OD minimums ------------------------------------------------
        self.lbl_arod = QLabel()
        self.ar = _spin(10, decimals=1, step=0.5)
        self.od = _spin(10, decimals=1, step=0.5)
        self.ar.valueChanged.connect(lambda _=0: self._emit())
        self.od.valueChanged.connect(lambda _=0: self._emit())
        self.lbl_ar = QLabel("AR ≥")
        self.lbl_od = QLabel("OD ≥")
        arod_box = QHBoxLayout()
        arod_box.addWidget(self.lbl_ar)
        arod_box.addWidget(self.ar)
        arod_box.addSpacing(10)
        arod_box.addWidget(self.lbl_od)
        arod_box.addWidget(self.od)
        arod_box.addStretch(1)
        grid.addWidget(self.lbl_arod, 5, 0)
        grid.addLayout(arod_box, 5, 1)

        root.addWidget(self.body)
        self._update_mode_relevant()

    # -- translation ---------------------------------------------------------
    def retranslate(self) -> None:
        t = self.ctx.t
        self.toggle.setText(t("filters_panel"))
        self.btn_clear.setText(t("filters_clear"))
        self.lbl_mode.setText(t("filters_mode"))
        self.lbl_star.setText(t("filters_star"))
        self.lbl_keys.setText(t("filters_keys"))
        self.lbl_bpm.setText(t("filters_bpm"))
        self.lbl_length.setText(t("filters_length"))
        self.lbl_arod.setText(t("filters_arod"))
        self.len_lo.setPlaceholderText(t("filters_min"))
        self.len_hi.setPlaceholderText(t("filters_max"))
        for disp, _glyph in _MODES:
            self.mode_btns[disp].setToolTip(disp)

    # -- external: which modes the Library actually owns ---------------------
    def set_mode_counts(self, counts: dict) -> None:
        """Disable a mode the Library has no maps of, with an explanatory hint."""
        t = self.ctx.t
        for disp, _glyph in _MODES:
            n = counts.get(disp, 0)
            b = self.mode_btns[disp]
            b.setEnabled(n > 0)
            if n > 0:
                b.setToolTip(t("filters_mode_have", mode=disp, n=n))
            else:
                b.setToolTip(t("filters_mode_none", mode=disp))
                if b.isChecked():
                    b.setChecked(False)
                    if self._selected_mode == disp:
                        self._selected_mode = None

    # -- collapse / expand ---------------------------------------------------
    def _on_toggle(self, on: bool) -> None:
        self.body.setVisible(on)
        self.toggle.setArrowType(Qt.DownArrow if on else Qt.RightArrow)

    # -- mode single-select --------------------------------------------------
    def _on_mode_clicked(self, disp: str) -> None:
        if self._selected_mode == disp:      # clicking the active mode clears it
            self._selected_mode = None
            self.mode_btns[disp].setChecked(False)
        else:
            self._selected_mode = disp
            for d, b in self.mode_btns.items():
                b.setChecked(d == disp)
        self._update_mode_relevant()
        self._emit()

    def _keys_applicable(self) -> bool:
        """Keys is a mania-only concept — offer it for mania (or no chosen mode)."""
        return self._selected_mode in (None, "osu!mania")

    def _update_mode_relevant(self) -> None:
        mania = self._keys_applicable()
        self.lbl_keys.setVisible(mania)
        self.keys.setVisible(mania)

    # -- keep slider and spin boxes in sync ----------------------------------
    def _on_star_slider(self, lo: float, hi: float) -> None:
        if self._suspend:
            return
        self._suspend = True
        self.star_lo.setValue(lo)
        self.star_hi.setValue(hi)
        self._suspend = False
        self._emit()

    def _on_star_spin(self, _v=0.0) -> None:
        if self._suspend:
            return
        self._suspend = True
        self.star.set_values(self.star_lo.value(), self.star_hi.value())
        lo, hi = self.star.values()            # snapped + swapped if lo>hi
        self.star_lo.setValue(lo)
        self.star_hi.setValue(hi)
        self._suspend = False
        self._emit()

    # -- compose query tokens ------------------------------------------------
    def filter_tokens(self) -> list[str]:
        toks: list[str] = []
        if self._selected_mode:
            toks.append(f"mode={_MODE_ALIAS[self._selected_mode]}")
        lo, hi = self.star.values()
        if lo > 0.0:
            toks.append(f"star>={lo:g}")
        if hi < _STAR_CAP:
            toks.append(f"star<={hi:g}")
        k = self.keys.currentData()
        if k and self._keys_applicable():
            toks.append(f"key={k}")
        if self.bpm_lo.value() > 0:
            toks.append(f"bpm>={self.bpm_lo.value():g}")
        if self.bpm_hi.value() > 0:
            toks.append(f"bpm<={self.bpm_hi.value():g}")
        # Only emit a length token if it actually parses (mm:ss or seconds) — an
        # unparseable box would otherwise leak "length>=abc" into the free text.
        lo_txt = self.len_lo.text().strip()
        hi_txt = self.len_hi.text().strip()
        if lo_txt and _parse_length(lo_txt) is not None:
            toks.append(f"length>={lo_txt}")
        if hi_txt and _parse_length(hi_txt) is not None:
            toks.append(f"length<={hi_txt}")
        if self.ar.value() > 0:
            toks.append(f"ar>={self.ar.value():g}")
        if self.od.value() > 0:
            toks.append(f"od>={self.od.value():g}")
        return toks

    def clear(self) -> None:
        self._suspend = True
        self._selected_mode = None
        for b in self.mode_btns.values():
            b.setChecked(False)
        self.star.set_values(0.0, _STAR_CAP)
        self.star_lo.setValue(0.0)
        self.star_hi.setValue(_STAR_CAP)
        self.keys.setCurrentIndex(0)
        for s in (self.bpm_lo, self.bpm_hi, self.ar, self.od):
            s.setValue(0.0)
        self.len_lo.clear()
        self.len_hi.clear()
        self._suspend = False
        self._update_mode_relevant()
        self._emit()

    def _emit(self) -> None:
        if not self._suspend:
            self.filtersChanged.emit()
