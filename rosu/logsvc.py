# SPDX-License-Identifier: GPL-3.0-or-later
"""Structured, parseable logging for every user action and system event.

Log lines are English and follow one fixed, machine-parseable shape so they can
later be inspected by a human or an AI. Format:

    <ISO8601> | <LEVEL> | <ACTION_CODE> | <key=value ...> | <human message>

The list of action codes and their fields is documented in
``logs/log_formats.md`` (written by :func:`write_log_formats_doc`) so the format
file always matches the code.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

FIELD_SEP = " | "


# --- Action codes -----------------------------------------------------------
# Each entry: code -> (fields, description). Buttons/actions the user can
# trigger and the system events they cause. Keep in sync with the doc writer.
ACTIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "APP_START":     (("version", "root"), "Application launched"),
    "APP_STOP":      (("reason",), "Application closed"),
    "PATH_HEAL":     (("status", "root"), "Re-pointed working folders after the app folder moved"),
    "SCAN_PACKS":    (("count", "source"), "Scanned the Packs/ folder for .zip archives"),
    "READD_PROMPT":  (("code", "kind", "missing"), "Asked the user about re-adding an already-known pack"),
    "READD_SKIP":    (("code",), "User skipped extracting an already-known pack"),
    "READD_EXTRACT": (("code",), "User chose to extract an already-known pack anyway"),
    "EXTRACT_START": (("pack_count", "source"), "Button: Extract & Process started"),
    "EXTRACT_PACK":  (("code", "tracks", "subfolders"), "Extracted one pack into Output/"),
    "EXTRACT_DONE":  (("packs", "tracks", "duration_s"), "Extract & Process finished"),
    "ZIP_TRASHED":   (("file",), "Moved a processed .zip to the Recycle Bin"),
    "ZIP_MOVED":     (("file", "dest"), "Moved a processed .zip to the Processed/ folder"),
    "ZIP_DELETED":   (("file",), "Permanently deleted a processed .zip"),
    "LIBRARY_COPY":  (("new", "duplicates", "dup_ids"), "Button: Copy to Library finished"),
    "LIBRARY_PURGE": (("deleted",), "Deleted the Library's physical .osz copies (kept metadata)"),
    "OSU_IMPORT":    (("batch", "files"), "Button: Import to osu! sent a batch to osu!lazer"),
    "OSU_IMPORT_DONE": (("files", "batches"), "Import to osu! finished dispatching"),
    "REFRESH":       (("added", "disappeared", "present"), "Button: Refresh Library Data finished"),
    "CLIENT_IMPORT": (("client", "added", "made"), "Auto-imported songs from an installed osu! client"),
    "REFERENCE_SYNC": (("packs",), "Fetched the authoritative pack list from the osu! API"),
    "OSU_IMPORT_CANCEL": (("sent", "total"), "User cancelled osu! import dispatch"),
    "GAP_DETECT":    (("summary",), "Recomputed missing/red rows across all series"),
    "EXCEL_WRITE":   (("path", "sheets"), "Regenerated the Excel tracking report"),
    "SEARCH":        (("query", "results"), "User searched the music memory"),
    "SETTINGS_SAVE": (("changed",), "User saved settings"),
    "AUDIO_FINGERPRINT": (("computed", "cached", "failed", "cancelled"), "Fingerprinted Library audio for same-song detection"),
    "STAGE_OUTPUT":  (("copied", "already", "skipped"), "Copied chosen Library sets into Output for Import to osu!"),
    "WATCH_IMPORT":  (("files", "new"), "Added new .osz files from the watched folder to the Library"),
    "LIBRARY_MOVE":  (("old", "new", "files", "bytes"), "Moved the Library to another folder (copied, verified, switched)"),
    "ERROR":         (("where", "detail"), "An error occurred"),
}


class LogService:
    """Appends structured lines to a per-day log file under ``logs/``."""

    def __init__(self, logs_dir: Path, app_version: str = ""):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.app_version = app_version
        # Optional UI sink (set by the GUI to mirror lines into a live view).
        self.ui_sink = None

    def _log_file(self) -> Path:
        day = _dt.date.today().isoformat()
        return self.logs_dir / f"app-{day}.log"

    def log(self, action: str, level: str = "INFO", message: str = "",
            **fields: Any) -> str:
        ts = _dt.datetime.now().replace(microsecond=0).isoformat()
        field_str = " ".join(f"{k}={_fmt(v)}" for k, v in fields.items())
        if not message and action in ACTIONS:
            message = ACTIONS[action][1]
        line = FIELD_SEP.join([ts, level, action, field_str, message])
        try:
            with self._log_file().open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass
        if self.ui_sink is not None:
            try:
                self.ui_sink(line)
            except Exception:
                pass
        return line

    def info(self, action: str, message: str = "", **fields: Any) -> str:
        return self.log(action, "INFO", message, **fields)

    def error(self, where: str, detail: str) -> str:
        return self.log("ERROR", "ERROR", "", where=where, detail=detail)


# --- Reading logs back (Logs tab, v1.9) ---------------------------------------
_LOG_NAME = "app-"
_ERROR_LEVELS = ("ERROR", "WARN")


def parse_line(line: str) -> dict:
    """One log line → ``{"time","level","action","fields","message","raw"}``.

    Timestamp, level and action never contain the separator; a field value may
    (it is quoted), so the message is taken from the LAST separator. A line that
    does not have the shape (a stray traceback line) keeps its text as the
    message with empty columns, so nothing in the file is ever hidden."""
    raw = line.rstrip("\r\n")
    head = raw.split(FIELD_SEP, 3)
    if len(head) == 4 and head[0][:4].isdigit():
        fields, _sep, message = head[3].rpartition(FIELD_SEP)
        if not _sep:
            fields, message = head[3], ""
        return {"time": head[0], "level": head[1].strip(), "action": head[2].strip(),
                "fields": fields, "message": message, "raw": raw}
    return {"time": "", "level": "", "action": "", "fields": "", "message": raw, "raw": raw}


def entry_matches(entry: dict, words: list[str], errors_only: bool = False) -> bool:
    """Every word (lowercase) appears somewhere in the line; ``errors_only``
    keeps ERROR/WARN lines only."""
    if errors_only and entry.get("level") not in _ERROR_LEVELS:
        return False
    hay = entry.get("raw", "").lower()
    return all(w in hay for w in words)


def log_days(logs_dir: Path, limit: int = 60) -> list[str]:
    """The days (``YYYY-MM-DD``) that have a log file, newest first."""
    days = []
    try:
        for f in Path(logs_dir).glob(f"{_LOG_NAME}*.log"):
            day = f.stem[len(_LOG_NAME):]
            if len(day) == 10 and day[4] == "-" and day[7] == "-" and \
                    day.replace("-", "").isdigit():
                days.append(day)
    except OSError:
        return []
    return sorted(days, reverse=True)[:limit]


def read_day(logs_dir: Path, day: str, max_lines: int = 5000) -> list[dict]:
    """The last ``max_lines`` entries of one day's log (empty when missing)."""
    path = Path(logs_dir) / f"{_LOG_NAME}{day}.log"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [parse_line(ln) for ln in lines[-max_lines:] if ln.strip()]


def _fmt(value: Any) -> str:
    """Render a field value; quote strings that contain spaces."""
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(str(v) for v in value) + "]"
    s = str(value)
    if " " in s or "|" in s:
        return f'"{s}"'
    return s


def write_log_formats_doc(logs_dir: Path) -> Path:
    """Write ``logs/log_formats.md`` documenting every log line format."""
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Log Formats",
        "",
        "Every log line in `app-YYYY-MM-DD.log` has this shape "
        "(fields separated by ` | `):",
        "",
        "```",
        "<ISO8601 timestamp> | <LEVEL> | <ACTION_CODE> | <key=value ...> | <human message>",
        "```",
        "",
        "- **timestamp** — local time, `YYYY-MM-DDTHH:MM:SS`.",
        "- **LEVEL** — `INFO`, `WARN` or `ERROR`.",
        "- **ACTION_CODE** — which button/event produced the line (table below).",
        "- **key=value** — space-separated fields; list values look like `[a,b,c]`; "
        "values with spaces are quoted.",
        "- **message** — short human-readable English description.",
        "",
        "## Action codes",
        "",
        "| ACTION_CODE | Fields | Meaning |",
        "|-------------|--------|---------|",
    ]
    for code, (fields, desc) in ACTIONS.items():
        field_txt = ", ".join(f"`{f}`" for f in fields) if fields else "—"
        lines.append(f"| `{code}` | {field_txt} | {desc} |")
    lines += [
        "",
        "## Examples",
        "",
        "```",
        "2026-07-12T20:15:03 | INFO | EXTRACT_START | pack_count=59 source=Packs/ | "
        "Button: Extract & Process started",
        "2026-07-12T20:16:41 | INFO | ZIP_TRASHED | file=\"S1819 - osu! Beatmap Pack #1819.zip\" | "
        "Moved a processed .zip to the Recycle Bin",
        "2026-07-12T20:20:10 | INFO | LIBRARY_COPY | new=2137 duplicates=3 dup_ids=[2419051,...] | "
        "Button: Copy to Library finished",
        "```",
        "",
    ]
    path = logs_dir / "log_formats.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
