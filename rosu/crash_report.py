# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in crash reports (v1.8) — OFF unless the user ticks it in Settings.

When enabled, an unexpected exception (an uncaught one, or one a background
worker caught and turned into an error dialog) sends a small fingerprint to
``rosu-web`` ``POST /api/crash``: the exception type, a short message with file
paths, quoted text and e-mail addresses removed, and the stack as ``module:function`` names
(``rosu/services/library_svc.py:copy_to_library``) — no line contents, no
files, no library data, no usernames. The server scrubs again and groups
identical crashes so the maintainer sees "this crash hit N users".

Expected failures are not crashes and are never sent: disk/network errors
(``OSError`` and its subclasses), cancellations, Ctrl+C / exit.

Stdlib only; sending happens on a daemon thread and never raises.
"""
from __future__ import annotations

import json
import os
import platform
import re
import sys
import threading
import traceback
import urllib.error
import urllib.request
from typing import Callable

from . import __version__

CRASH_ENDPOINT = "https://rosu-web.vercel.app/api/crash"
_MAX_FRAMES = 30
_MAX_MESSAGE = 300

_enabled: Callable[[], bool] = lambda: False
_seen: set = set()
_seen_lock = threading.Lock()
_installed = False

_EMAIL = re.compile(r"[^\s@<>\"']+@[^\s@<>\"']+\.[A-Za-z]{2,}")
# Quoted text is usually a name from the user's library or disk ('Artist -
# Title', a file name), so it goes whole. A Windows path may contain spaces
# ("C:\\Users\\John Smith\\…"), so from a drive letter or a UNC prefix the
# rest of the line goes; elsewhere everything from the first slashed token to
# the last one on a line is a (relative, maybe spaced) path too.
_QUOTED = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")
_LINE_PATHS = (re.compile(r"[A-Za-z]:[\\/].*"), re.compile(r"\\\\.*"))
_SLASHY = re.compile(r"\S*[\\/](?:.*[\\/])?\S*")


def scrub(text: str) -> str:
    """Remove anything that could carry a name: e-mail addresses, quoted text
    and paths (a message must not carry a username or a library entry)."""
    text = _EMAIL.sub("<email>", text)
    text = _QUOTED.sub("'<str>'", text)
    for pat in _LINE_PATHS:
        text = pat.sub("<path>", text)
    text = _SLASHY.sub("<path>", text)
    return re.sub(r"[\x00-\x1f\x7f]", " ", text)


def module_path(filename: str) -> str:
    """``C:\\...\\_MEI123\\rosu\\db.py`` → ``rosu/db.py``; anything outside the
    package → its bare file name (``zipfile.py``)."""
    f = (filename or "").replace("\\", "/")
    idx = f.rfind("/rosu/")
    if idx >= 0:
        return f[idx + 1:]
    if f.startswith("rosu/"):
        return f
    return f.rsplit("/", 1)[-1] or "?"


def exc_type_name(exc: BaseException) -> str:
    t = type(exc)
    mod = getattr(t, "__module__", "") or ""
    name = t.__qualname__.replace("<", "").replace(">", "")
    full = name if mod in ("builtins", "") else f"{mod}.{name}"
    return re.sub(r"[^\w.]", "_", full)[:120] or "Exception"


# Rosu's own "this went wrong out there" errors (Drive/osu! API/HTTP replies, a
# hostile archive refused, osu! not installed): handled conditions, not bugs.
_EXPECTED = frozenset({"DriveError", "ReportError", "UnsafeArchive", "OsuApiError",
                       "OsuNotFoundError", "_CancelledWrite"})


def is_reportable(exc: BaseException) -> bool:
    """Bugs only: not disk/network trouble, not a cancel, not an exit, not one
    of Rosu's own handled error types."""
    if isinstance(exc, (KeyboardInterrupt, SystemExit, OSError)):
        return False
    names = {c.__name__ for c in type(exc).__mro__}
    if names & _EXPECTED:
        return False
    return not type(exc).__name__.endswith("Cancelled")


def build_payload(exc: BaseException) -> dict | None:
    tb = exc.__traceback__
    if tb is None:
        return None
    frames = [f"{module_path(fs.filename)}:{fs.name}"
              for fs in traceback.extract_tb(tb)[-_MAX_FRAMES:]]
    if not frames:
        return None
    try:
        os_name = f"{platform.system()} {platform.release()}".strip()
    except Exception:
        os_name = "unknown"
    return {
        "exc_type": exc_type_name(exc),
        "message": scrub(str(exc))[:_MAX_MESSAGE],
        "frames": frames,
        "app_version": __version__,
        "os": os_name,
    }


def send(payload: dict, endpoint: str | None = None, timeout: int = 10) -> dict:
    """POST one fingerprint. Never raises; https only."""
    from .report import _resolve_token
    url = endpoint or os.environ.get("ROSU_CRASH_ENDPOINT") or CRASH_ENDPOINT
    if not url.lower().startswith("https://"):
        return {"ok": False, "error": "bad_endpoint"}
    body = json.dumps({**payload, "token": _resolve_token()}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": f"Rosu/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read(64 * 1024) or b"{}")
    except (urllib.error.URLError, OSError, ValueError):
        return {"ok": False, "error": "offline"}


def capture(exc: BaseException, sender: Callable[[dict], object] | None = None,
            background: bool = True) -> bool:
    """Report ``exc`` if crash reports are on and this crash was not already sent
    in this session. Returns True when a report was dispatched."""
    try:
        if not _enabled() or not is_reportable(exc):
            return False
        payload = build_payload(exc)
        if payload is None:
            return False
        key = (payload["exc_type"], tuple(payload["frames"]))
        with _seen_lock:
            if key in _seen:
                return False
            _seen.add(key)
        fn = sender or send
        if background:
            threading.Thread(target=fn, args=(payload,), daemon=True,
                             name="rosu-crash-report").start()
        else:
            fn(payload)
        return True
    except Exception:
        return False   # reporting a crash must never cause one


def install(is_enabled: Callable[[], bool]) -> None:
    """Hook uncaught exceptions (main thread + threads). ``is_enabled`` is read at
    crash time, so toggling the Settings checkbox takes effect immediately."""
    global _enabled, _installed
    _enabled = is_enabled
    if _installed:
        return
    _installed = True
    prev_sys = sys.excepthook
    prev_thread = threading.excepthook

    def _sys_hook(etype, value, tb):
        if value is not None:
            capture(value)
        prev_sys(etype, value, tb)

    def _thread_hook(args):
        if args.exc_value is not None:
            capture(args.exc_value)
        prev_thread(args)

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook
