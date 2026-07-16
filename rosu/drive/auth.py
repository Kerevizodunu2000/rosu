# SPDX-License-Identifier: GPL-3.0-or-later
"""Google OAuth for the Drive backup — Desktop-app loopback flow + PKCE (v0.8).

Stdlib only (urllib + http.server), mirroring osu_api.py's "no extra HTTP
dependency, bundles cleanly" policy. The only third-party piece is ``keyring``,
used to keep the long-lived refresh token in the OS credential store (Windows
Credential Manager) rather than in the plaintext config.json.

Flow (RFC 8252 native app):
  1. generate a PKCE verifier/challenge and a random state,
  2. spin up a throwaway HTTP server on 127.0.0.1:<ephemeral port>,
  3. open the system browser to Google's consent screen,
  4. receive the ?code=... redirect on the loopback server,
  5. exchange code -> {access, refresh} at the token endpoint (with the verifier),
  6. stash the refresh token in keyring.

Only the non-sensitive ``drive.file`` scope is requested, so Google needs no app
verification and the app can only see files it created.

The online pieces are injectable (token store + HTTP poster) so the token-refresh
logic is unit-testable without a browser, network, or keyring.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/drive.file"

_KEYRING_SERVICE = "rosu-drive"
_KEYRING_USER = "refresh-token"
_CLIENT_FILE = "oauth_client.json"     # gitignored; local dev + CI-injected


class DriveError(Exception):
    """Base class for Drive errors surfaced to the UI."""


class DriveNotConfigured(DriveError):
    """No embedded OAuth client (client_id/secret) is available."""


class DriveAuthError(DriveError):
    """Login failed/was cancelled, or the stored token is no longer valid."""


class DriveCancelled(DriveError):
    """The user cancelled an in-progress Drive operation (upload/backup)."""


@dataclass(frozen=True)
class ClientConfig:
    client_id: str
    client_secret: str


def load_client_config() -> ClientConfig:
    """Resolve the embedded OAuth client (client_id/secret).

    Order: ``ROSU_OAUTH_CLIENT_JSON`` env var (raw JSON) -> ``oauth_client.json``
    next to this module (dev tree) -> the same file bundled in a frozen build
    (``sys._MEIPASS/rosu/drive/oauth_client.json``). The file is the exact JSON
    Google hands out (``{"installed": {...}}``). Raises DriveNotConfigured when
    none is present — the app still runs; only Drive login is unavailable.
    """
    raw = os.environ.get("ROSU_OAUTH_CLIENT_JSON")
    if raw:
        return _parse_client(raw)
    candidates = [Path(__file__).resolve().parent / _CLIENT_FILE]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "rosu" / "drive" / _CLIENT_FILE)
    for path in candidates:
        if path.exists():
            return _parse_client(path.read_text(encoding="utf-8"))
    raise DriveNotConfigured(
        "No OAuth client found (set ROSU_OAUTH_CLIENT_JSON or add "
        f"rosu/drive/{_CLIENT_FILE}).")


def _parse_client(text: str) -> ClientConfig:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise DriveNotConfigured(f"invalid OAuth client JSON: {exc}") from exc
    node = data.get("installed") or data.get("web") or data
    cid = node.get("client_id")
    secret = node.get("client_secret")
    if not cid or not secret:
        raise DriveNotConfigured("OAuth client JSON missing client_id/secret")
    return ClientConfig(cid, secret)


# --- PKCE helpers -----------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) per RFC 7636 (S256)."""
    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _post_form(url: str, fields: dict) -> dict:
    """POST application/x-www-form-urlencoded, return the JSON body as a dict."""
    body = urllib.parse.urlencode(fields).encode("ascii")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Google returns a JSON error body (e.g. invalid_grant) — surface it.
        try:
            return json.loads(exc.read().decode("utf-8"))
        except (ValueError, OSError):
            raise DriveAuthError(f"token endpoint HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise DriveAuthError(f"network error: {exc.reason}") from exc


def _keyring():
    """Import keyring lazily; a missing backend is a clean auth error, not a crash."""
    try:
        import keyring
        return keyring
    except ImportError as exc:  # declared dependency, absent in this env
        raise DriveAuthError(
            "keyring is not installed (run: pip install -r requirements.txt)"
        ) from exc


def keyring_available() -> bool:
    """Whether the OS keyring backend is importable, i.e. whether the refresh token
    can actually be persisted. A cheap import probe kept off the startup path (called
    only from ``drive_status``), so a user without keyring is warned BEFORE running
    the whole OAuth browser flow instead of failing at the final store step (item 1b)."""
    try:
        import keyring  # noqa: F401
        return True
    except Exception:
        return False


class _KeyringStore:
    """Refresh-token storage backed by the OS credential store."""

    def get(self) -> str | None:
        return _keyring().get_password(_KEYRING_SERVICE, _KEYRING_USER)

    def set(self, token: str) -> None:
        _keyring().set_password(_KEYRING_SERVICE, _KEYRING_USER, token)

    def delete(self) -> None:
        try:
            _keyring().delete_password(_KEYRING_SERVICE, _KEYRING_USER)
        except Exception:
            pass   # not present / already gone — logout is best-effort


def _result_page(status: str | None) -> str:
    """A polished, self-contained branded page for the loopback redirect (item 5).

    No external assets (served by the stdlib loopback server); adapts to the OS
    light/dark theme; styled on Rosu's pink brand with a drawn-in success tick.
    ``status`` is ``"ok"`` (consent granted), ``"error"`` (denied / state
    mismatch), or ``None`` (an unrelated request such as favicon)."""
    if status == "error":
        accent, accent2, rgb = "#ff6b81", "#e0405e", "224,64,94"
        title = "Sign-in didn't complete"
        msg = "Something went wrong. Close this tab and try Connect again in Rosu."
        badge = '<div class="glyph">&#10007;</div>'   # ✗
    elif status == "ok":
        accent, accent2, rgb = "#ff66aa", "#ff2e97", "255,102,170"
        title = "Connected to Google Drive"
        msg = ("You're all set — Rosu can now back up and share your beatmaps. "
               "Rosu is back in focus; you can close this tab whenever you like.")
        badge = ('<svg class="tick" viewBox="0 0 52 52" aria-hidden="true">'
                 '<circle class="tick-c" cx="26" cy="26" r="23" fill="none"/>'
                 '<path class="tick-p" fill="none" d="M15 27l7.5 7.5L37.5 19"/></svg>')
    else:
        accent, accent2, rgb = "#ff66aa", "#ff2e97", "255,102,170"
        title = "Rosu — Google Drive"
        msg = "You can close this tab and return to Rosu."
        badge = '<div class="glyph">&#9679;</div>'      # ●
    # Best-effort tab close after a couple of seconds. Browsers BLOCK window.close()
    # for a tab the user navigated to themselves (only script-opened tabs may be
    # closed), so this only succeeds where the browser allows it — it never blanks
    # the tab where it doesn't. Rosu itself raises its window on connect, so the
    # user returns to the app regardless; the page copy doesn't promise a close.
    script = ("<script>setTimeout(function(){try{window.close();}catch(e){}},2500);</script>"
              if status == "ok" else "")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rosu — Google Drive</title>
<style>
  :root {{ color-scheme: light dark; --accent:{accent}; --accent2:{accent2}; }}
  * {{ box-sizing:border-box; }}
  html,body {{ height:100%; }}
  body {{ margin:0; display:flex; align-items:center; justify-content:center; padding:24px;
    font-family:"Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,Roboto,sans-serif;
    color:#211f2b;
    background:radial-gradient(130% 100% at 50% -20%, rgba({rgb},.20), transparent 62%), #f4f3f9; }}
  .card {{ position:relative; background:#fff; border-radius:24px; padding:48px 44px 32px;
    max-width:460px; width:100%; text-align:center; border:1px solid rgba(0,0,0,.05);
    box-shadow:0 26px 80px -24px rgba({rgb},.55), 0 8px 24px -12px rgba(0,0,0,.2);
    animation:rise .55s cubic-bezier(.2,.9,.25,1) both; }}
  .badge {{ width:92px; height:92px; border-radius:50%; margin:0 auto 24px; display:flex;
    align-items:center; justify-content:center;
    background:linear-gradient(135deg, var(--accent), var(--accent2));
    box-shadow:0 14px 34px -8px rgba({rgb},.7);
    animation:pop .6s .08s cubic-bezier(.2,1.35,.35,1) both; }}
  .glyph {{ font-size:44px; color:#fff; line-height:1; }}
  .tick {{ width:56px; height:56px; }}
  .tick-c {{ stroke:rgba(255,255,255,.5); stroke-width:2.5;
    stroke-dasharray:145; stroke-dashoffset:145; animation:draw .6s .2s ease forwards; }}
  .tick-p {{ stroke:#fff; stroke-width:5.5; stroke-linecap:round; stroke-linejoin:round;
    stroke-dasharray:44; stroke-dashoffset:44; animation:draw .5s .5s ease forwards; }}
  h1 {{ font-size:23px; font-weight:750; margin:0 0 12px; letter-spacing:-.3px; }}
  p {{ margin:0 auto; max-width:36ch; color:#6a6a80; line-height:1.6; font-size:15px; }}
  .brand {{ margin-top:26px; font-weight:800; letter-spacing:4px; font-size:12px;
    text-transform:uppercase; color:var(--accent); opacity:.85;
    cursor:default; user-select:none; }}
  @keyframes rise {{ from{{opacity:0; transform:translateY(16px) scale(.97);}} to{{opacity:1; transform:none;}} }}
  @keyframes pop {{ from{{opacity:0; transform:scale(.35);}} to{{opacity:1; transform:scale(1);}} }}
  @keyframes draw {{ to{{stroke-dashoffset:0;}} }}
  @media (prefers-color-scheme: dark) {{
    body {{ color:#ecebf5;
      background:radial-gradient(130% 100% at 50% -20%, rgba({rgb},.26), transparent 62%), #121019; }}
    .card {{ background:#1b1926; border-color:rgba(255,255,255,.06);
      box-shadow:0 26px 80px -24px rgba({rgb},.5), 0 8px 24px -12px rgba(0,0,0,.6); }}
    p {{ color:#a6a5c0; }}
  }}
  @media (prefers-reduced-motion: reduce) {{
    * {{ animation:none !important; }} .tick-c,.tick-p {{ stroke-dashoffset:0; }} }}
</style></head>
<body><main class="card">
  <div class="badge">{badge}</div>
  <h1>{title}</h1>
  <p>{msg}</p>
  <div class="brand">Rosu</div>
</main>{script}</body></html>"""


def _make_handler(expected_state: str, sink: dict):
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler API)
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            status = None   # "ok" / "error" for THIS request (drives the shown page)
            # Only the real OAuth redirect carries code/error; ignore favicon etc.
            if "code" in qs or "error" in qs:
                if qs.get("state", [None])[0] == expected_state:
                    if "code" in qs:
                        sink["code"] = qs["code"][0]
                        status = "ok"
                    else:
                        sink["error"] = qs["error"][0]
                        status = "error"
                else:
                    sink["error"] = "state mismatch"
                    status = "error"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_result_page(status).encode("utf-8"))

        def log_message(self, *args):  # silence: GUI app, no console
            pass

    return _Handler


class DriveAuth:
    """Owns the OAuth client + a short-lived access-token cache.

    ``token_store`` and ``http_post`` are injectable so refresh logic can be
    unit-tested without keyring or the network.
    """

    def __init__(self, client: ClientConfig | None = None, token_store=None,
                 http_post: Callable[[str, dict], dict] | None = None):
        self._client = client
        self._store = token_store if token_store is not None else _KeyringStore()
        self._post = http_post if http_post is not None else _post_form
        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    def _config(self) -> ClientConfig:
        if self._client is None:
            self._client = load_client_config()
        return self._client

    def is_configured(self) -> bool:
        try:
            self._config()
            return True
        except DriveNotConfigured:
            return False

    def is_connected(self) -> bool:
        try:
            return bool(self._store.get())
        except Exception:
            return False

    def can_store_token(self) -> bool:
        """Whether a refresh token can be persisted (keyring backend present).
        The Connect button is disabled when this is False (item 1b)."""
        return keyring_available()

    def logout(self) -> None:
        with self._lock:
            self._access_token = None
            self._expires_at = 0.0
        try:
            self._store.delete()
        except Exception:
            pass

    def get_access_token(self, now: float | None = None) -> str:
        """Return a valid access token, refreshing via the stored refresh token."""
        now = time.time() if now is None else now
        with self._lock:
            if self._access_token and now < self._expires_at - 60:
                return self._access_token
        refresh = self._store.get()
        if not refresh:
            raise DriveAuthError("not connected to Google Drive")
        cfg = self._config()
        data = self._post(TOKEN_URI, {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
        })
        token = data.get("access_token")
        if not token:
            if data.get("error") in ("invalid_grant", "invalid_token"):
                self.logout()   # revoked/expired: force a fresh login
            raise DriveAuthError(
                f"token refresh failed: {data.get('error', 'no access_token')}")
        with self._lock:
            self._access_token = token
            self._expires_at = now + int(data.get("expires_in", 3600))
        return token

    def login(self, timeout: float = 180.0, open_browser: bool = True,
              cancel: Callable[[], bool] | None = None) -> None:
        """Run the loopback + PKCE consent flow and store the refresh token."""
        cfg = self._config()
        verifier, challenge = make_pkce()
        state = secrets.token_urlsafe(24)
        sink: dict = {}
        server = HTTPServer(("127.0.0.1", 0), _make_handler(state, sink))
        server.timeout = 0.5
        port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/"
        params = {
            "client_id": cfg.client_id, "redirect_uri": redirect_uri,
            "response_type": "code", "scope": SCOPE, "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256",
            "access_type": "offline", "prompt": "consent",
        }
        url = AUTH_URI + "?" + urllib.parse.urlencode(params)
        if open_browser:
            webbrowser.open(url)
        deadline = time.time() + timeout
        try:
            while not sink and time.time() < deadline:
                if cancel and cancel():
                    raise DriveAuthError("login cancelled")
                server.handle_request()   # blocks up to server.timeout
        finally:
            server.server_close()
        if "code" not in sink:
            raise DriveAuthError(sink.get("error") or "login timed out")

        tokens = self._post(TOKEN_URI, {
            "grant_type": "authorization_code",
            "code": sink["code"], "redirect_uri": redirect_uri,
            "client_id": cfg.client_id, "client_secret": cfg.client_secret,
            "code_verifier": verifier,
        })
        refresh = tokens.get("refresh_token")
        if not refresh:
            raise DriveAuthError(
                tokens.get("error")
                or "no refresh token returned (revoke prior access and retry)")
        self._store.set(refresh)
        access = tokens.get("access_token")
        if access:
            with self._lock:
                self._access_token = access
                self._expires_at = time.time() + int(tokens.get("expires_in", 3600))
