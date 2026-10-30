# SPDX-License-Identifier: GPL-3.0-or-later
"""tools/update_key.py: the signed update manifest the release workflow writes."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from rosu import ed25519, updater

TOOLS = Path(__file__).resolve().parent.parent / "tools"
SEED = bytes(range(32))
TAG = "v9.9.9"


def _load():
    spec = importlib.util.spec_from_file_location("update_key", TOOLS / "update_key.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


uk = _load()


@pytest.fixture
def exe(tmp_path):
    p = tmp_path / f"rosu-{TAG}-win64.exe"
    p.write_bytes(b"MZ" + b"x" * 5000)
    out = tmp_path / "out"
    out.mkdir()
    return p, out


def _run(exe, out, tag=TAG):
    return uk.main(["manifest", str(exe), tag, str(out)])


def test_manifest_writes_a_verifiable_signed_manifest(exe, monkeypatch, capsys):
    p, out = exe
    monkeypatch.setenv("ROSU_UPDATE_SIGNING_KEY", SEED.hex())
    monkeypatch.setattr(updater, "UPDATE_PUBLIC_KEY", ed25519.public_key(SEED).hex())
    assert _run(p, out) == 0
    body = (out / "rosu-update.json").read_bytes()
    m = json.loads(body)
    assert m == {"version": TAG, "asset": p.name, "size": p.stat().st_size,
                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    sig = bytes.fromhex((out / "rosu-update.json.sig").read_text())
    assert ed25519.verify(ed25519.public_key(SEED), body, sig)
    captured = capsys.readouterr()
    assert SEED.hex() not in captured.out + captured.err
    assert SEED.hex().upper() not in captured.out + captured.err


def test_missing_key_exits_nonzero_and_writes_nothing(exe, monkeypatch, capsys):
    p, out = exe
    monkeypatch.delenv("ROSU_UPDATE_SIGNING_KEY", raising=False)
    monkeypatch.setattr(updater, "UPDATE_PUBLIC_KEY", ed25519.public_key(SEED).hex())
    assert _run(p, out) != 0
    assert list(out.iterdir()) == []


def test_malformed_key_exits_nonzero_without_echoing_it(exe, monkeypatch, capsys):
    p, out = exe
    monkeypatch.setenv("ROSU_UPDATE_SIGNING_KEY", "zz" + SEED.hex()[2:])
    monkeypatch.setattr(updater, "UPDATE_PUBLIC_KEY", ed25519.public_key(SEED).hex())
    assert _run(p, out) != 0
    captured = capsys.readouterr()
    assert SEED.hex()[2:] not in captured.out + captured.err
    assert list(out.iterdir()) == []


def test_mismatched_public_key_exits_nonzero(exe, monkeypatch):
    p, out = exe
    monkeypatch.setenv("ROSU_UPDATE_SIGNING_KEY", SEED.hex())
    monkeypatch.setattr(updater, "UPDATE_PUBLIC_KEY", ed25519.public_key(b"\1" * 32).hex())
    assert _run(p, out) != 0
    assert list(out.iterdir()) == []


def test_empty_public_key_exits_nonzero(exe, monkeypatch):
    p, out = exe
    monkeypatch.setenv("ROSU_UPDATE_SIGNING_KEY", SEED.hex())
    monkeypatch.setattr(updater, "UPDATE_PUBLIC_KEY", "")
    assert _run(p, out) != 0


@pytest.mark.parametrize("tag,name", [("9.9.9", "rosu-9.9.9-win64.exe"),
                                      ("v9.9", "rosu-v9.9-win64.exe"),
                                      (TAG, "rosu.exe"),
                                      (TAG, "rosu-v9.9.8-win64.exe")])
def test_refuses_a_bad_tag_or_exe_name(tmp_path, monkeypatch, tag, name):
    monkeypatch.setenv("ROSU_UPDATE_SIGNING_KEY", SEED.hex())
    monkeypatch.setattr(updater, "UPDATE_PUBLIC_KEY", ed25519.public_key(SEED).hex())
    p = tmp_path / name
    p.write_bytes(b"MZ")
    out = tmp_path / "out"
    out.mkdir()
    assert _run(p, out, tag) != 0
    assert list(out.iterdir()) == []


def test_keygen_prints_a_matching_pair(capsys):
    assert uk.main(["keygen"]) == 0
    lines = capsys.readouterr().out.splitlines()
    seed = bytes.fromhex(lines[0].rsplit(" ", 1)[1])
    pub = lines[1].rsplit(" ", 1)[1]
    assert len(seed) == 32 and ed25519.public_key(seed).hex() == pub
