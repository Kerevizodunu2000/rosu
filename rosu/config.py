# SPDX-License-Identifier: GPL-3.0-or-later
"""Application configuration: paths, language, theme and toggles.

The config is a small JSON file (``config.json``) that lives next to the
application. All working folders (Packs/Output/Library/data/logs) default to
being siblings of the app root, but every path is overridable so the user can
point the tool at any location from the Settings tab.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# --- Enumerated option values (stored in config, compared in code) ----------
LANGUAGES = ("en", "tr")
THEMES = (
    "dark", "white", "pink", "pink-white", "pink-dark", "pink-darker",
    "nord", "dracula", "catppuccin-mocha", "catppuccin-latte",
    "solarized-dark", "solarized-light",
)
# What to do with a .zip once its contents have been extracted to Output.
ZIP_DISPOSAL = ("recycle", "move", "delete")  # Recycle Bin / move to Processed / permanent


def app_root() -> Path:
    """Directory the app treats as its working root.

    When frozen by PyInstaller we use the folder that holds the .exe, otherwise
    the repository root (parent of this package). This keeps Packs/Output/etc.
    next to the executable the user double-clicks.
    """
    if getattr(sys, "frozen", False):  # PyInstaller onefile/onedir
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


@dataclass
class Config:
    # Working folders
    root: str = ""
    packs_dir: str = ""
    output_dir: str = ""
    library_dir: str = ""
    data_dir: str = ""
    logs_dir: str = ""

    # osu!lazer executable (auto-detected on first run if empty)
    osu_exe: str = ""

    # UI preferences
    language: str = "en"      # default English per spec
    theme: str = "dark"       # default Dark Mode per spec

    # osu! API (optional) for the authoritative pack reference
    osu_client_id: str = ""
    osu_client_secret: str = ""

    # Behaviour toggles
    library_physical_copy: bool = True   # keep real .osz backups in Library
    clear_output_before_extract: bool = True  # Output only holds the current batch
    auto_backup_after_extract: bool = False   # auto-run Copy to Library after extract
    zip_disposal: str = "recycle"

    # Bookkeeping
    schema_note: str = "paths are absolute; edit from Settings tab"
    _extra: dict = field(default_factory=dict)

    # -- derived path helpers -------------------------------------------------
    @property
    def root_path(self) -> Path:
        return Path(self.root)

    @property
    def packs_path(self) -> Path:
        return Path(self.packs_dir)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)

    @property
    def library_path(self) -> Path:
        return Path(self.library_dir)

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def logs_path(self) -> Path:
        return Path(self.logs_dir)

    @property
    def db_path(self) -> Path:
        return self.data_path / "memory.db"

    @property
    def excel_path(self) -> Path:
        return self.data_path / "tracking.xlsx"

    @property
    def reference_path(self) -> Path:
        return self.data_path / "reference.json"

    def ensure_dirs(self) -> None:
        for p in (self.packs_path, self.output_path, self.library_path,
                  self.data_path, self.logs_path):
            p.mkdir(parents=True, exist_ok=True)


def _config_file() -> Path:
    return app_root() / "config.json"


def _fill_defaults(cfg: Config) -> Config:
    root = Path(cfg.root) if cfg.root else app_root()
    cfg.root = str(root)
    cfg.packs_dir = cfg.packs_dir or str(root / "Packs")
    cfg.output_dir = cfg.output_dir or str(root / "Output")
    cfg.library_dir = cfg.library_dir or str(root / "Library")
    cfg.data_dir = cfg.data_dir or str(root / "data")
    cfg.logs_dir = cfg.logs_dir or str(root / "logs")
    if cfg.language not in LANGUAGES:
        cfg.language = "en"
    if cfg.theme not in THEMES:
        cfg.theme = "dark"
    if cfg.zip_disposal not in ZIP_DISPOSAL:
        cfg.zip_disposal = "recycle"
    return cfg


def load_config() -> Config:
    """Load config.json, filling in any missing values with defaults."""
    path = _config_file()
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    known = {f for f in Config.__dataclass_fields__ if not f.startswith("_")}
    extra = {k: v for k, v in data.items() if k not in known}
    cfg = Config(**{k: v for k, v in data.items() if k in known})
    cfg._extra = extra
    cfg = _fill_defaults(cfg)
    return cfg


def save_config(cfg: Config) -> None:
    path = _config_file()
    payload = asdict(cfg)
    payload.pop("_extra", None)
    payload.update(cfg._extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                    encoding="utf-8")


def detect_osu_exe() -> str:
    """Best-effort auto-detection of the osu!lazer executable on Windows."""
    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "osulazer" / "current" / "osu!.exe")
        candidates.append(Path(local) / "osulazer" / "osu!.exe")
    for c in candidates:
        if c.exists():
            return str(c)
    return ""
