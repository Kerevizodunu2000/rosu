# SPDX-License-Identifier: GPL-3.0-or-later
"""Application bootstrap: build the context, apply the theme, show the window."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen

from . import __version__, config, logsvc, pathheal, theming
from .db import Database
from .i18n import I18N
from .services import Services
from .ui.main_window import MainWindow


def asset_path(name: str) -> str:
    return str(Path(__file__).resolve().parent / "assets" / name)


def load_stylesheet(theme: str) -> str:
    return theming.stylesheet_for(theme)


class AppContext:
    """Shared, long-lived services handed to every tab."""

    def __init__(self, cfg: config.Config | None = None):
        self.cfg = cfg if cfg is not None else config.load_config()
        self.cfg.ensure_dirs()
        # auto-detect the osu! clients once if not configured (import targets)
        changed = False
        if not self.cfg.osu_lazer_exe:
            found = config.detect_osu_exe()
            if found:
                self.cfg.osu_lazer_exe = found
                changed = True
        if not self.cfg.osu_stable_exe:
            found = config.detect_stable_exe()
            if found:
                self.cfg.osu_stable_exe = found
                changed = True
        if changed:
            self.cfg.osu_exe = self.cfg.osu_lazer_exe or self.cfg.osu_exe
            config.save_config(self.cfg)
        # give this install a stable id for its Drive manifest shard (item 11)
        if not self.cfg.device_id:
            self.cfg.device_id = uuid.uuid4().hex
            config.save_config(self.cfg)
        logsvc.write_log_formats_doc(self.cfg.logs_path)
        self.log = logsvc.LogService(self.cfg.logs_path, __version__)
        self.db = Database(self.cfg.db_path)
        self.i18n = I18N(self.cfg.language)
        self.services = Services(self.cfg, self.db, self.log)

    def t(self, key: str, **kwargs) -> str:
        return self.i18n.t(key, **kwargs)

    def save_config(self) -> None:
        config.save_config(self.cfg)


def _heal_paths(cfg: config.Config, headless: bool) -> pathheal.Diagnosis | None:
    """Self-heal working-folder paths if the app folder moved (item 20).

    ``relocated`` in an interactive run asks the user to confirm before re-pointing;
    a ``fresh`` diagnosis (or any headless run) applies silently so the folder
    structure lands next to the exe. Returns the applied Diagnosis, or None.
    """
    diag = pathheal.diagnose(cfg, config.app_root())
    if not diag.has_changes():
        return None
    if not headless and diag.status == "relocated":
        i18n = I18N(cfg.language)
        changes = "\n".join(pathheal.summary_lines(diag))
        box = QMessageBox()
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(i18n.t("path_heal_title"))
        box.setText(i18n.t("path_heal_body", base=diag.base, changes=changes))
        apply_btn = box.addButton(i18n.t("path_heal_apply"), QMessageBox.AcceptRole)
        box.addButton(i18n.t("path_heal_keep"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not apply_btn:
            return None
    pathheal.apply_fix(cfg, diag)
    config.save_config(cfg)
    return diag


def run() -> int:
    argv = sys.argv[1:]
    if "--version" in argv:
        print(__version__)
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("Rosu")
    app.setWindowIcon(QIcon(asset_path("icon.png")))

    cfg = config.load_config()
    healed = _heal_paths(cfg, headless="--selftest" in argv)
    ctx = AppContext(cfg)
    qss = load_stylesheet(ctx.cfg.theme)

    if "--selftest" in argv:
        # Verify a packaged build boots: theme, icon, db and dirs are available.
        ok = bool(qss) and ctx.cfg.data_path.exists() and Path(asset_path("icon.png")).exists()
        print("selftest OK" if ok else "selftest FAIL")
        ctx.db.close()
        return 0 if ok else 1

    app.setStyleSheet(qss)
    ctx.log.info("APP_START", version=__version__, root=str(ctx.cfg.root))
    if healed is not None:
        ctx.log.info("PATH_HEAL", status=healed.status, root=str(ctx.cfg.root))

    splash_pix = QPixmap(asset_path("splash.png"))
    splash = QSplashScreen(splash_pix) if not splash_pix.isNull() else None
    if splash:
        splash.show()
        app.processEvents()

    win = MainWindow(ctx, app)
    win.setWindowIcon(QIcon(asset_path("icon.png")))
    win.show()
    if splash:
        splash.finish(win)
    code = app.exec()

    ctx.log.info("APP_STOP", reason="window closed")
    ctx.db.close()
    return code
