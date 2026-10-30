# SPDX-License-Identifier: GPL-3.0-or-later
"""rosu.updater: signed download, staging, swap, rollback and file scope.

No network and no real process start: ``urlopen``, ``popen`` and ``replace``
are fakes, ``sys.frozen`` is monkeypatched and the exe folder is ``tmp_path``.
"""
import hashlib
import io
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from rosu import __version__, ed25519, updater

SEED = bytes(range(1, 33))
TAG = "v9.9.9"
NEW_EXE = b"MZ-new-rosu" * 1000
OLD_EXE = b"MZ-old-rosu" * 700
BASE = f"https://github.com/Kerevizodunu2000/rosu/releases/download/{TAG}/"
UPDATE_NAMES = {"rosu.exe", "rosu.exe.part", "rosu.exe.new", "rosu.exe.old",
                "rosu.exe.bad", "rosu-update.json", "rosu-update.json.sig",
                "rosu-update-state.json"}


# -- fakes and helpers ----------------------------------------------------------
class Resp:
    def __init__(self, data: bytes):
        self.data, self.pos = data, 0

    def read(self, n=-1):
        end = len(self.data) if n is None or n < 0 else self.pos + n
        chunk = self.data[self.pos:end]
        self.pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Net:
    """Fake ``urlopen``: serves ``files`` by URL; a missing URL is a 404."""

    def __init__(self, files):
        self.files, self.calls, self.responses = files, [], {}

    def __call__(self, req, timeout=None):
        assert timeout, "every request needs an explicit timeout"
        assert req.get_header("User-agent") == f"Rosu/{__version__}"
        self.calls.append(req.full_url)
        if req.full_url not in self.files:
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
        resp = Resp(self.files[req.full_url])
        self.responses[req.full_url] = resp
        return resp


def manifest(**over):
    m = {"version": TAG, "asset": f"rosu-{TAG}-win64.exe", "size": len(NEW_EXE),
         "sha256": hashlib.sha256(NEW_EXE).hexdigest()}
    m.update(over)
    for k in [k for k, v in m.items() if v is _DROP]:
        del m[k]
    return json.dumps(m).encode()


_DROP = object()


def sign(body: bytes) -> bytes:
    return ed25519.sign(SEED, body).hex().encode()


def release(body=None, sig=None, exe=NEW_EXE):
    body = manifest() if body is None else body
    files = {BASE + "rosu-update.json": body,
             BASE + "rosu-update.json.sig": sign(body) if sig is None else sig,
             BASE + f"rosu-{TAG}-win64.exe": exe}
    return {k: v for k, v in files.items() if v is not _DROP}


@pytest.fixture
def app(tmp_path, monkeypatch):
    """A frozen app folder: the exe, the user's folders and config.json."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(updater, "UPDATE_PUBLIC_KEY", ed25519.public_key(SEED).hex())
    d = tmp_path / "Rosu"
    d.mkdir()
    for sub in ("Packs", "Library", "Output", "data", "logs"):
        (d / sub).mkdir()
        (d / sub / "keep.bin").write_bytes(sub.encode() * 10)
    (d / "config.json").write_text('{"language": "en"}')
    exe = d / "rosu.exe"
    exe.write_bytes(OLD_EXE)
    return SimpleNamespace(dir=d, exe=exe, cfg=SimpleNamespace(auto_update=True,
                                                               check_updates=True))


def p(app, suffix):
    return app.dir / ("rosu.exe" + suffix)


def state(app):
    return json.loads((app.dir / "rosu-update-state.json").read_text())


def write_state(app, **st):
    (app.dir / "rosu-update-state.json").write_text(json.dumps(st))


def nothing_staged(app):
    return not any((p(app, ".part").exists(), p(app, ".new").exists(),
                    (app.dir / "rosu-update.json").exists(),
                    (app.dir / "rosu-update.json.sig").exists()))


def download(app, net, **kw):
    return updater.download(app.cfg, kw.pop("tag", TAG), exe=app.exe, urlopen=net, **kw)


def stage(app, exe=NEW_EXE, body=None):
    body = manifest() if body is None else body
    p(app, ".new").write_bytes(exe)
    (app.dir / "rosu-update.json").write_bytes(body)
    (app.dir / "rosu-update.json.sig").write_bytes(sign(body))


class Popen:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.fail:
            raise OSError("cannot start")


class Replace:
    def __init__(self, fail_on=None):
        self.calls, self.fail_on = [], fail_on

    def __call__(self, src, dst):
        self.calls.append((Path(src).name, Path(dst).name))
        if len(self.calls) == self.fail_on:
            raise PermissionError("in use")
        os.replace(src, dst)


# -- download and staging --------------------------------------------------------
def test_valid_release_is_staged(app):
    net = Net(release())
    seen = []
    res = download(app, net, progress=seen.append)
    assert res == {"status": updater.READY, "tag": TAG}
    assert p(app, ".new").read_bytes() == NEW_EXE
    assert (app.dir / "rosu-update.json").read_bytes() == manifest()
    assert (app.dir / "rosu-update.json.sig").read_bytes() == sign(manifest())
    assert not p(app, ".part").exists()
    assert app.exe.read_bytes() == OLD_EXE
    assert seen and seen[-1] == {"percent": 100}


def _tampered():
    body = manifest()
    return {"body": body.replace(b"9.9.9", b"9.9.8", 1), "sig": sign(body)}


def _padded(n):
    body = manifest()[:-1] + b" " * n + b"}"
    return {"body": body}


REJECTIONS = {
    "manifest changed after signing": _tampered,
    "bad sig": lambda: {"sig": b"00" * 64},
    "sig not hex": lambda: {"sig": b"not hex"},
    "missing sig": lambda: {"sig": _DROP},
    "extra key": lambda: {"body": manifest(channel="beta")},
    "missing key": lambda: {"body": manifest(sha256=_DROP)},
    "size as string": lambda: {"body": manifest(size=str(len(NEW_EXE)))},
    "size as True": lambda: {"body": manifest(size=True)},
    "version differs from tag": lambda: {"body": manifest(
        version="v9.9.8", asset="rosu-v9.9.8-win64.exe")},
    "same version": lambda: {"body": manifest(
        version=f"v{__version__}", asset=f"rosu-v{__version__}-win64.exe")},
    "older version": lambda: {"body": manifest(
        version="v0.1.0", asset="rosu-v0.1.0-win64.exe")},
    "asset name": lambda: {"body": manifest(asset="rosu.exe")},
    "asset path": lambda: {"body": manifest(asset="../v9.9.9/rosu-v9.9.9-win64.exe")},
    "size 0": lambda: {"body": manifest(size=0)},
    "size over 512 MiB": lambda: {"body": manifest(size=512 * 1024 * 1024 + 1)},
    "sha256 not hex": lambda: {"body": manifest(sha256="z" * 64)},
    "sha256 upper case": lambda: {"body": manifest(
        sha256=hashlib.sha256(NEW_EXE).hexdigest().upper())},
    "sha256 short": lambda: {"body": manifest(sha256="a" * 63)},
    "manifest over cap": lambda: _padded(4096),
    "sig over cap": lambda: {"sig": sign(manifest()) + b" " * 1024},
    "exe bytes differ": lambda: {"exe": NEW_EXE[:-1] + b"!"},
    "exe stream shorter": lambda: {"exe": NEW_EXE[:-1]},
}


@pytest.mark.parametrize("case", REJECTIONS)
def test_rejection_stages_nothing(app, case):
    net = Net(release(**REJECTIONS[case]()))
    assert download(app, net) == {"status": updater.BANNER}
    assert nothing_staged(app)
    assert app.exe.read_bytes() == OLD_EXE


def test_version_in_skip_is_rejected(app):
    write_state(app, skip=["9.9.9"])
    net = Net(release())
    assert download(app, net) == {"status": updater.BANNER}
    assert nothing_staged(app)
    assert BASE + f"rosu-{TAG}-win64.exe" not in net.calls


def test_padded_manifest_under_the_cap_is_accepted(app):
    net = Net(release(**_padded(3000)))
    assert download(app, net)["status"] == updater.READY


def test_exe_stream_longer_than_size_stops_within_a_chunk(app):
    url = BASE + f"rosu-{TAG}-win64.exe"
    net = Net(release(exe=NEW_EXE + b"\0" * (updater._CHUNK * 20)))
    assert download(app, net) == {"status": updater.BANNER}
    assert nothing_staged(app)
    assert net.responses[url].pos <= len(NEW_EXE) + updater._CHUNK


def test_big_exe_streams_in_chunks(app, monkeypatch):
    big = os.urandom(updater._CHUNK * 3 + 17)
    body = manifest(size=len(big), sha256=hashlib.sha256(big).hexdigest())
    net = Net(release(body=body, exe=big))
    seen = []
    assert download(app, net, progress=seen.append)["status"] == updater.READY
    assert p(app, ".new").read_bytes() == big
    assert len(seen) == 4


# -- URLs ---------------------------------------------------------------------------
@pytest.mark.parametrize("tag", ["v9.9", "9.9.9/../../evil", "v9.9.9/x", "", "v9.9.9?x=1"])
def test_tag_failing_release_link_makes_no_request(app, tag):
    net = Net({})
    assert download(app, net, tag=tag) == {"status": updater.BANNER}
    assert net.calls == []
    assert nothing_staged(app)


def test_redirect_handler_allows_only_https():
    h = updater.HttpsOnlyRedirect()
    req = urllib.request.Request(BASE + "rosu-update.json")
    with pytest.raises(urllib.error.HTTPError):
        h.redirect_request(req, io.BytesIO(), 302, "Found", {}, "http://example.com/x")
    with pytest.raises(urllib.error.HTTPError):
        h.redirect_request(req, io.BytesIO(), 302, "Found", {}, "file:///etc/passwd")
    nxt = h.redirect_request(req, io.BytesIO(), 302, "Found", {},
                             "https://objects.githubusercontent.com/x")
    assert nxt.full_url == "https://objects.githubusercontent.com/x"


def test_default_opener_uses_the_https_only_handler():
    assert any(isinstance(h, updater.HttpsOnlyRedirect) for h in updater._OPENER.handlers)
    assert not any(type(h) is urllib.request.HTTPRedirectHandler
                   for h in updater._OPENER.handlers)


# -- fallbacks ------------------------------------------------------------------------
def test_part_permission_error_falls_back_to_banner(app, monkeypatch):
    real_open = open

    def fake_open(path, *a, **kw):
        if str(path).endswith(".part"):
            raise PermissionError("read-only folder")
        return real_open(path, *a, **kw)

    monkeypatch.setattr(updater, "open", fake_open, raising=False)
    assert download(app, Net(release())) == {"status": updater.BANNER}
    assert nothing_staged(app)


@pytest.mark.parametrize("off", ["not frozen", "empty key", "auto_update", "check_updates"])
def test_ineligible_touches_no_network_or_disk(app, monkeypatch, off):
    if off == "not frozen":
        monkeypatch.setattr(sys, "frozen", False)
    elif off == "empty key":
        monkeypatch.setattr(updater, "UPDATE_PUBLIC_KEY", "")
    else:
        setattr(app.cfg, off, False)
    assert updater.can_auto_update(app.cfg) is False
    before = sorted(x.name for x in app.dir.iterdir())
    net = Net(release())
    assert download(app, net) == {"status": updater.BANNER}
    assert updater.on_startup(app.cfg, exe=app.exe, popen=Popen()) == updater.CONTINUE
    assert net.calls == []
    assert sorted(x.name for x in app.dir.iterdir()) == before


def test_eligible_when_everything_is_on(app):
    assert updater.can_auto_update(app.cfg) is True


def test_cancel_mid_download_deletes_part(app):
    big = os.urandom(updater._CHUNK * 4)
    body = manifest(size=len(big), sha256=hashlib.sha256(big).hexdigest())
    cancel = threading.Event()
    res = download(app, Net(release(body=body, exe=big)), cancel=cancel,
                   progress=lambda _p: cancel.set())
    assert res == {"status": updater.BANNER}
    assert nothing_staged(app)


# -- swap -------------------------------------------------------------------------------
def test_swap_order_state_and_launch(app):
    stage(app)
    rep, pop = Replace(), Popen()
    assert updater.apply_staged(exe=app.exe, replace=rep, popen=pop) == updater.EXIT
    assert rep.calls == [("rosu.exe", "rosu.exe.old"), ("rosu.exe.new", "rosu.exe")]
    assert app.exe.read_bytes() == NEW_EXE
    assert p(app, ".old").read_bytes() == OLD_EXE
    st = state(app)
    assert st["from"] == __version__ and st["to"] == "9.9.9" and st["boots"] == 0
    assert len(pop.calls) == 1
    args, kwargs = pop.calls[0]
    assert args[0] == [str(app.exe)]
    assert not kwargs.get("shell", False)
    assert kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert kwargs["creationflags"] == 0x208


def _assert_undone(app, res):
    assert res == updater.KEEP
    assert app.exe.read_bytes() == OLD_EXE
    assert not p(app, ".old").exists()
    st = state(app)
    assert "from" not in st and "to" not in st and "boots" not in st


def test_swap_undone_when_second_rename_fails(app):
    stage(app)
    rep = Replace(fail_on=2)
    _assert_undone(app, updater.apply_staged(exe=app.exe, replace=rep, popen=Popen()))
    assert rep.calls[-1] == ("rosu.exe.old", "rosu.exe")


def test_swap_undone_when_popen_fails(app):
    stage(app)
    _assert_undone(app, updater.apply_staged(exe=app.exe, popen=Popen(fail=True)))
    assert p(app, ".new").read_bytes() == NEW_EXE   # still staged for the next start


def test_tampered_staged_exe_is_deleted_not_swapped(app):
    stage(app)
    p(app, ".new").write_bytes(NEW_EXE[:-1] + b"!")
    pop = Popen()
    assert updater.apply_staged(exe=app.exe, popen=pop) == updater.KEEP
    assert app.exe.read_bytes() == OLD_EXE
    assert not p(app, ".old").exists()
    assert nothing_staged(app)
    assert pop.calls == []


def test_tampered_staged_manifest_is_deleted_not_swapped(app):
    stage(app)
    (app.dir / "rosu-update.json").write_bytes(manifest(size=len(NEW_EXE) - 1))
    assert updater.apply_staged(exe=app.exe, popen=Popen()) == updater.KEEP
    assert nothing_staged(app) and app.exe.read_bytes() == OLD_EXE


def test_apply_staged_is_off_when_not_frozen(app, monkeypatch):
    stage(app)
    monkeypatch.setattr(sys, "frozen", False)
    pop = Popen()
    assert updater.apply_staged(exe=app.exe, popen=pop) == updater.KEEP
    assert app.exe.read_bytes() == OLD_EXE and pop.calls == []


# -- startup, rollback, healthy ----------------------------------------------------------
def test_first_boot_counts(app):
    write_state(app, **{"from": "1.0.0", "to": __version__, "boots": 0, "skip": []})
    assert updater.on_startup(app.cfg, exe=app.exe, popen=Popen()) == updater.CONTINUE
    assert state(app)["boots"] == 1


def test_second_boot_rolls_back(app):
    # The running exe is the new version that never reached mark_healthy.
    app.exe.write_bytes(NEW_EXE)
    p(app, ".old").write_bytes(OLD_EXE)
    write_state(app, **{"from": "1.0.0", "to": __version__, "boots": 1, "skip": ["2.0.0"]})
    pop = Popen()
    assert updater.on_startup(app.cfg, exe=app.exe, popen=pop) == updater.EXIT
    assert app.exe.read_bytes() == OLD_EXE
    assert p(app, ".bad").read_bytes() == NEW_EXE
    assert not p(app, ".old").exists()
    st = state(app)
    assert st["skip"] == ["2.0.0", __version__]
    assert "to" not in st and "boots" not in st
    assert len(pop.calls) == 1
    assert pop.calls[0][0][0] == [str(app.exe)]
    assert pop.calls[0][1]["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_rollback_without_old_clears_state_and_continues(app):
    write_state(app, **{"from": "1.0.0", "to": __version__, "boots": 1, "skip": []})
    pop = Popen()
    assert updater.on_startup(app.cfg, exe=app.exe, popen=pop) == updater.CONTINUE
    assert state(app) == {"skip": []} and pop.calls == []


def test_mark_healthy_clears_and_deletes(app):
    p(app, ".old").write_bytes(OLD_EXE)
    p(app, ".bad").write_bytes(b"bad")
    write_state(app, **{"from": "1.0.0", "to": __version__, "boots": 1, "skip": ["2.0.0"]})
    updater.mark_healthy(exe=app.exe)
    assert not p(app, ".old").exists() and not p(app, ".bad").exists()
    assert state(app) == {"skip": ["2.0.0"]}
    assert app.exe.read_bytes() == OLD_EXE


def test_mark_healthy_ignores_a_failed_delete(app, monkeypatch):
    p(app, ".old").write_bytes(OLD_EXE)

    def deny(self, missing_ok=False):
        raise PermissionError("in use")

    monkeypatch.setattr(Path, "unlink", deny)
    updater.mark_healthy(exe=app.exe)   # does not raise
    assert p(app, ".old").exists()


def test_mark_healthy_writes_nothing_without_a_swap(app):
    before = sorted(x.name for x in app.dir.iterdir())
    updater.mark_healthy(exe=app.exe)
    assert sorted(x.name for x in app.dir.iterdir()) == before


@pytest.mark.parametrize("raw", [b"{not json", b"[1, 2]", b"\xff\xfe", b"[" * 3000,
                                 json.dumps({"to": __version__, "boots": 1,
                                             "pad": "x" * 5000}).encode()])
def test_corrupt_or_oversize_state_counts_as_empty(app, raw):
    (app.dir / "rosu-update-state.json").write_bytes(raw)
    p(app, ".old").write_bytes(b"keep")
    pop = Popen()
    assert updater.on_startup(app.cfg, exe=app.exe, popen=pop) == updater.CONTINUE
    assert pop.calls == [] and app.exe.read_bytes() == OLD_EXE
    assert download(app, Net(release()))["status"] == updater.READY   # skip is empty


def test_on_startup_applies_a_staged_update(app):
    stage(app)
    pop = Popen()
    assert updater.on_startup(app.cfg, exe=app.exe, popen=pop) == updater.EXIT
    assert app.exe.read_bytes() == NEW_EXE and len(pop.calls) == 1


def test_on_startup_keeps_running_when_the_swap_fails(app):
    stage(app)
    assert updater.on_startup(app.cfg, exe=app.exe, popen=Popen(fail=True)) \
        == updater.CONTINUE
    assert app.exe.read_bytes() == OLD_EXE


# -- file scope ----------------------------------------------------------------------------
def _snapshot(root: Path) -> dict:
    return {str(x.relative_to(root)): x.read_bytes()
            for x in root.rglob("*") if x.is_file()}


def test_whole_flow_touches_only_update_files(app, monkeypatch):
    before = _snapshot(app.dir)
    assert download(app, Net(release()))["status"] == updater.READY
    assert updater.apply_staged(exe=app.exe, popen=Popen()) == updater.EXIT
    monkeypatch.setattr(updater, "__version__", "9.9.9")   # now the new exe runs
    assert updater.on_startup(app.cfg, exe=app.exe, popen=Popen()) == updater.CONTINUE
    assert updater.on_startup(app.cfg, exe=app.exe, popen=Popen()) == updater.EXIT
    monkeypatch.setattr(updater, "__version__", __version__)   # rolled back
    updater.mark_healthy(exe=app.exe)
    after = _snapshot(app.dir)
    assert app.exe.read_bytes() == OLD_EXE
    changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
    assert changed and changed <= UPDATE_NAMES
    for k, v in before.items():
        if k not in UPDATE_NAMES:
            assert after[k] == v
    assert sorted(x.name for x in app.dir.iterdir() if x.is_dir()) == \
        ["Library", "Output", "Packs", "data", "logs"]


# -- app.run wiring -------------------------------------------------------------------------
def test_app_source_order():
    src = (Path(__file__).resolve().parent.parent / "rosu" / "app.py").read_text()
    load, start = src.index("cfg = config.load_config()"), src.index("updater.on_startup(cfg)")
    assert load < start < src.index("ctx = AppContext(cfg)")
    assert '"--selftest" not in argv and updater.on_startup' in src
    assert src.index("win.showMaximized()") < src.index("updater.mark_healthy")
    assert src.index("    ctx.db.close()\n    if win.restart_for_update") \
        < src.index("updater.apply_staged()")


def test_run_version_and_selftest_skip_on_startup(tmp_path, monkeypatch, capsys):
    from PySide6.QtWidgets import QApplication
    from rosu import app as app_mod, config
    qapp = QApplication.instance() or QApplication([])
    calls = []
    monkeypatch.setattr(updater, "on_startup", lambda *a, **k: calls.append(a) or "exit")
    monkeypatch.setattr(sys, "argv", ["rosu", "--version"])
    assert app_mod.run() == 0
    assert capsys.readouterr().out.strip() == __version__
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    monkeypatch.setattr(config, "load_config", lambda: cfg)
    monkeypatch.setattr(config, "save_config", lambda c: None)
    monkeypatch.setattr(app_mod, "_heal_paths", lambda c, headless: None)
    monkeypatch.setattr(app_mod, "QApplication", lambda argv: qapp)
    monkeypatch.setattr(sys, "argv", ["rosu", "--selftest"])
    assert app_mod.run() == 0
    assert "selftest OK" in capsys.readouterr().out
    assert calls == []
