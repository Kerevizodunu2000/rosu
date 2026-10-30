# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed auto-update for the frozen Windows exe: download, verify, swap, rollback.

The release workflow attaches ``rosu-update.json`` (version, asset name, size,
SHA-256) and ``rosu-update.json.sig`` (an Ed25519 signature over its exact bytes,
see ``tools/update_key.py``). This module downloads the exe only after that
signature verifies with ``UPDATE_PUBLIC_KEY``, stages it as ``<exe>.new`` and,
on restart, renames the running exe to ``<exe>.old`` and the new one into its
place. A new version that fails to come up twice is rolled back and skipped.

Qt-free. Network (``urlopen``), process start (``popen``) and renames
(``replace``) are injectable. Every file it creates, writes, renames or deletes
is one of the update files next to the exe (``_files``); nothing else in the
app folder is touched. Nothing about the user is sent.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import __version__, ed25519
from .update_check import _release_link, is_newer

# Hex Ed25519 public key of the release signing key. Empty = auto-update off.
UPDATE_PUBLIC_KEY = ""

_BASE = "https://github.com/Kerevizodunu2000/rosu/releases/download/{tag}/"
MANIFEST = "rosu-update.json"
SIGNATURE = "rosu-update.json.sig"
STATE = "rosu-update-state.json"
_MANIFEST_CAP = 4 * 1024
_SIG_CAP = 1024
_STATE_CAP = 4 * 1024
_MAX_SIZE = 512 * 1024 * 1024
_CHUNK = 64 * 1024
_TIMEOUT = 30
_KEYS = {"version", "asset", "size", "sha256"}
_TAG = re.compile(r"v\d+\.\d+\.\d+")
_SHA256 = re.compile(r"[0-9a-f]{64}")
# Anything a fetch or a stream can raise: network, HTTP protocol, bad data, disk.
_FAILURES = (urllib.error.URLError, http.client.HTTPException, ValueError, OSError)
# DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, as literals so this imports on Linux.
_CREATION_FLAGS = 0x00000008 | 0x00000200

# Results.
BANNER = "banner"       # fall back to today's "is available" banner
READY = "ready"         # staged; restart to apply
EXIT = "exit"           # a new process was started: this one should quit
KEEP = "keep running"   # nothing was swapped
CONTINUE = "continue"   # start the app normally


class HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to another https:// URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise urllib.error.HTTPError(newurl, code, "refused a non-https redirect",
                                         headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(HttpsOnlyRedirect)


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def can_auto_update(cfg) -> bool:
    return (_frozen() and bool(UPDATE_PUBLIC_KEY)
            and bool(getattr(cfg, "auto_update", False))
            and bool(getattr(cfg, "check_updates", False)))


def _files(exe: Path | None) -> dict[str, Path]:
    e = Path(sys.executable) if exe is None else Path(exe)
    d = e.parent
    return {"exe": e, "part": d / (e.name + ".part"), "new": d / (e.name + ".new"),
            "old": d / (e.name + ".old"), "bad": d / (e.name + ".bad"),
            "manifest": d / MANIFEST, "sig": d / SIGNATURE, "state": d / STATE}


def _unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass   # tried again next time


# -- state file ---------------------------------------------------------------
def _read_capped(path: Path, cap: int) -> bytes | None:
    try:
        with open(path, "rb") as f:
            data = f.read(cap + 1)
    except OSError:
        return None
    return data if len(data) <= cap else None


def _read_state(f: dict) -> dict:
    """``{'from', 'to', 'boots', 'skip'}``; a missing, oversize or bad file is empty."""
    raw = _read_capped(f["state"], _STATE_CAP)
    try:
        st = json.loads(raw) if raw is not None else {}
    except (ValueError, RecursionError):
        st = {}
    if not isinstance(st, dict):
        st = {}
    skip = st.get("skip")
    boots = st.get("boots")
    return {"from": st.get("from") if isinstance(st.get("from"), str) else None,
            "to": st.get("to") if isinstance(st.get("to"), str) else None,
            "boots": boots if type(boots) is int else None,
            "skip": [s for s in skip if isinstance(s, str)] if isinstance(skip, list) else []}


def _write_state(f: dict, skip: list, **swap) -> None:
    """Write the state; without ``swap`` (from/to/boots) those keys are cleared."""
    f["state"].write_text(json.dumps({**swap, "skip": skip}), encoding="utf-8")


# -- manifest -------------------------------------------------------------------
def _accept(manifest: bytes, sig: bytes, tag: str | None, skip: list) -> dict | None:
    """The manifest dict when it passes every check, else None. ``tag`` None
    (a staged manifest) skips only the tag comparison."""
    try:
        if not ed25519.verify(bytes.fromhex(UPDATE_PUBLIC_KEY), manifest,
                              bytes.fromhex(sig.decode("ascii").strip())):
            return None
        m = json.loads(manifest)
    except (ValueError, RecursionError):
        return None
    if not isinstance(m, dict) or set(m) != _KEYS:
        return None
    version, size, sha = m["version"], m["size"], m["sha256"]
    if not (isinstance(version, str) and _TAG.fullmatch(version)
            and (tag is None or version == tag)
            and is_newer(version, __version__)
            and version[1:] not in skip
            and m["asset"] == f"rosu-{version}-win64.exe"
            and type(size) is int and 1 <= size <= _MAX_SIZE
            and isinstance(sha, str) and _SHA256.fullmatch(sha)):
        return None
    return m


def _fetch(url: str, cap: int, urlopen) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": f"Rosu/{__version__}"})
    with urlopen(req, timeout=_TIMEOUT) as resp:
        data = resp.read(cap + 1)
    if len(data) > cap:
        raise ValueError("over the read cap")
    return data


# -- download -------------------------------------------------------------------
def download(cfg, tag: str, cancel=None, progress=None, *, exe: Path | None = None,
             urlopen=None, replace=os.replace) -> dict:
    """Fetch, verify and stage the release ``tag``. Returns ``{'status': READY,
    'tag': tag}`` or ``{'status': BANNER}`` (on any failure, fall back to the banner)."""
    banner = {"status": BANNER}
    if not can_auto_update(cfg):
        return banner
    urlopen = urlopen or _OPENER.open
    base = _BASE.format(tag=tag)
    if not (_release_link(base + MANIFEST) and _release_link(base + SIGNATURE)):
        return banner
    f = _files(exe)
    try:
        manifest = _fetch(base + MANIFEST, _MANIFEST_CAP, urlopen)
        sig = _fetch(base + SIGNATURE, _SIG_CAP, urlopen)
    except _FAILURES:
        return banner
    m = _accept(manifest, sig, tag, _read_state(f)["skip"])
    if m is None or not _release_link(base + m["asset"]):
        return banner
    try:
        out = open(f["part"], "wb")
    except OSError:
        return banner
    size, h, n, ok, staged = m["size"], hashlib.sha256(), 0, False, False
    try:
        with out:
            req = urllib.request.Request(base + m["asset"],
                                         headers={"User-Agent": f"Rosu/{__version__}"})
            with urlopen(req, timeout=_TIMEOUT) as resp:
                while not (cancel is not None and cancel.is_set()):
                    chunk = resp.read(_CHUNK)
                    if not chunk:
                        ok = n == size and h.hexdigest() == m["sha256"]
                        break
                    n += len(chunk)
                    if n > size:
                        break
                    h.update(chunk)
                    out.write(chunk)
                    if progress:
                        progress({"percent": n * 100 // size})
        if ok:
            f["manifest"].write_bytes(manifest)
            f["sig"].write_bytes(sig)
            replace(f["part"], f["new"])
            staged = True
            return {"status": READY, "tag": tag}
    except _FAILURES:
        pass
    finally:
        if not staged:   # any failure, cancel or unexpected error: leave nothing half-staged
            for key in ("part", "manifest", "sig") if ok else ("part",):
                _unlink(f[key])
    return banner


# -- swap -------------------------------------------------------------------------
def _hash_file(path: Path) -> tuple[int, str] | None:
    h, n = hashlib.sha256(), 0
    try:
        with open(path, "rb") as fh:
            while chunk := fh.read(_CHUNK):
                n += len(chunk)
                if n > _MAX_SIZE:
                    return None
                h.update(chunk)
    except OSError:
        return None
    return n, h.hexdigest()


def _launch(exe: Path, popen) -> None:
    # A child at the parent's path would reuse (and lose) the parent's _MEI folder.
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    popen([str(exe)], creationflags=_CREATION_FLAGS, env=env)


def apply_staged(*, exe: Path | None = None, replace=os.replace,
                 popen=subprocess.Popen, log=None) -> str:
    """Swap a verified ``<exe>.new`` in and start it. Returns EXIT or KEEP;
    on KEEP, ``log`` (if given) gets one line saying why."""
    log = log or (lambda _why: None)
    if not _frozen():
        log("not running as the frozen exe")
        return KEEP
    f = _files(exe)
    st = _read_state(f)
    manifest = _read_capped(f["manifest"], _MANIFEST_CAP)
    sig = _read_capped(f["sig"], _SIG_CAP)
    m = (_accept(manifest, sig, None, st["skip"])
         if manifest is not None and sig is not None else None)
    if m is None or _hash_file(f["new"]) != (m["size"], m["sha256"]):
        for key in ("new", "manifest", "sig"):
            _unlink(f[key])
        log("the staged update failed verification and was deleted")
        return KEEP
    try:
        _write_state(f, st["skip"], **{"from": __version__, "to": m["version"][1:],
                                       "boots": 0})
    except OSError as exc:
        log(f"could not write {STATE}: {type(exc).__name__}")
        return KEEP
    done = []
    try:
        for src, dst in ((f["exe"], f["old"]), (f["new"], f["exe"])):
            replace(src, dst)
            done.append((src, dst))
        _launch(f["exe"], popen)
        return EXIT
    except Exception as exc:
        log(f"the swap failed and was undone: {type(exc).__name__}")
        for src, dst in reversed(done):
            try:
                replace(dst, src)
            except OSError:
                pass
        try:
            _write_state(f, st["skip"])
        except OSError:
            pass
        return KEEP


def relaunch(*, exe: Path | None = None, popen=subprocess.Popen) -> bool:
    """Start the current exe again (after a failed swap); True if it started."""
    if not _frozen():
        return False
    try:
        _launch(_files(exe)["exe"], popen)
    except Exception:
        return False
    return True


# -- startup ----------------------------------------------------------------------
def on_startup(cfg, *, exe: Path | None = None, replace=os.replace,
               popen=subprocess.Popen) -> str:
    """Roll back a version that failed to start, count a first boot, or apply a
    staged update. Returns EXIT (quit now) or CONTINUE."""
    if not _frozen():
        return CONTINUE
    f = _files(exe)
    st = _read_state(f)
    if st["to"] == __version__ and st["boots"] is not None and st["boots"] >= 1:
        # The new version was started before and never reached mark_healthy.
        try:
            if not f["old"].exists():
                _write_state(f, st["skip"])
                return CONTINUE
            replace(f["exe"], f["bad"])
            try:
                replace(f["old"], f["exe"])
            except OSError:
                replace(f["bad"], f["exe"])
                raise
            _write_state(f, st["skip"] + [st["to"]])
            _launch(f["exe"], popen)
            return EXIT
        except Exception:
            return CONTINUE
    if st["to"] == __version__ and st["boots"] == 0:
        try:
            _write_state(f, st["skip"], **{"from": st["from"], "to": st["to"], "boots": 1})
        except OSError:
            pass
        return CONTINUE
    if can_auto_update(cfg) and f["new"].exists():
        return EXIT if apply_staged(exe=f["exe"], replace=replace, popen=popen) == EXIT \
            else CONTINUE
    return CONTINUE


def mark_healthy(*, exe: Path | None = None) -> None:
    """The window came up: forget the swap, keep ``skip``, drop ``.old``/``.bad``."""
    if not _frozen():
        return
    f = _files(exe)
    st = _read_state(f)
    if st["from"] is not None or st["to"] is not None or st["boots"] is not None:
        try:
            _write_state(f, st["skip"])
        except OSError:
            pass
    for key in ("old", "bad"):
        _unlink(f[key])
