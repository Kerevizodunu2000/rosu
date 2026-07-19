# SPDX-License-Identifier: GPL-3.0-or-later
"""Pack skillset summary dialog (v1.6).

Double-click a present pack in the Packs tab → the AVERAGE Rosu Skillset profile of
its mania sets on a radar, so you can see at a glance what kind of pack it is
(jack-heavy, stream-heavy, technical…). Sets with no mania chart just say so.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from ..models import MsdResult
from .radar_widget import RadarChart

_ABBR = {"stream": "Stream", "jumpstream": "JS", "handstream": "HS",
         "stamina": "Stamina", "jackspeed": "Jack", "chordjack": "CJ",
         "technical": "Tech"}


class PackSkillsetDialog(QDialog):
    def __init__(self, ctx, code: str, summary: dict, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        t = ctx.t
        self.setWindowTitle(t("pack_skill_title", code=code))
        self.setMinimumSize(420, 420)
        root = QVBoxLayout(self)
        root.setSpacing(8)

        head = QLabel(objectName="h1")
        head.setText(t("pack_skill_title", code=code))
        root.addWidget(head)

        if not summary or summary.get("n", 0) == 0:
            msg = QLabel(objectName="status")
            msg.setWordWrap(True)
            msg.setText(t("pack_skill_none"))
            root.addWidget(msg, 1)
        else:
            sub = QLabel(objectName="status")
            sub.setWordWrap(True)
            sub.setText(t("pack_skill_sub", n=summary["n"],
                          overall=f"{summary['overall']:.2f}",
                          peak=f"{summary['peak']:.2f}"))
            root.addWidget(sub)
            radar = RadarChart()
            radar.set_values(summary["skills"])
            root.addWidget(radar, 1)
            vals = QLabel(objectName="status")
            vals.setWordWrap(True)
            vals.setAlignment(Qt.AlignHCenter)
            skills = summary["skills"]
            vals.setText("   ".join(f"{_ABBR[k]} {skills[k]:.2f}"
                                    for k in MsdResult.SKILLS))
            root.addWidget(vals)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)
