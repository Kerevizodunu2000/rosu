# SPDX-License-Identifier: GPL-3.0-or-later
"""Signing key and signed manifest for Rosu's auto-update.

    python tools/update_key.py keygen
    ROSU_UPDATE_SIGNING_KEY=<64 hex> python tools/update_key.py manifest EXE TAG OUTDIR

``keygen`` prints a new seed (store it as the ``ROSU_UPDATE_SIGNING_KEY`` GitHub
secret) and its public key (``UPDATE_PUBLIC_KEY`` in ``rosu/updater.py``); it
writes no files. ``manifest`` writes ``rosu-update.json`` and its Ed25519
signature ``rosu-update.json.sig`` into OUTDIR, after checking the signature
against ``UPDATE_PUBLIC_KEY``. The seed is read only from the environment and
is never printed or written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rosu import ed25519, updater  # noqa: E402


def keygen() -> int:
    seed = os.urandom(32)
    print(f"seed (secret, ROSU_UPDATE_SIGNING_KEY): {seed.hex()}")
    print(f"public key (UPDATE_PUBLIC_KEY): {ed25519.public_key(seed).hex()}")
    return 0


def _fail(msg: str) -> int:
    print(f"update_key: {msg}", file=sys.stderr)
    return 1


def manifest(exe: str, tag: str, outdir: str) -> int:
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        return _fail("the tag must look like v1.2.3")
    exe_path = Path(exe)
    if exe_path.name != f"rosu-{tag}-win64.exe":
        return _fail(f"the exe must be named rosu-{tag}-win64.exe")
    raw = os.environ.get("ROSU_UPDATE_SIGNING_KEY", "")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", raw):
        return _fail("ROSU_UPDATE_SIGNING_KEY is missing or not 64 hex characters")
    seed = bytes.fromhex(raw)
    try:
        public = bytes.fromhex(updater.UPDATE_PUBLIC_KEY)
    except ValueError:
        public = b""
    if not public:
        return _fail("UPDATE_PUBLIC_KEY in rosu/updater.py is empty or not hex")
    h, size = hashlib.sha256(), 0
    with open(exe_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            size += len(chunk)
            h.update(chunk)
    body = json.dumps({"version": tag, "asset": exe_path.name, "size": size,
                       "sha256": h.hexdigest()}).encode("utf-8")
    sig = ed25519.sign(seed, body)
    if not ed25519.verify(public, body, sig):
        return _fail("the signature does not verify with UPDATE_PUBLIC_KEY (wrong key?)")
    out = Path(outdir)
    (out / updater.MANIFEST).write_bytes(body)
    (out / updater.SIGNATURE).write_text(sig.hex(), encoding="ascii")
    print(f"Wrote {updater.MANIFEST} ({size} bytes, sha256 {h.hexdigest()}) and its signature.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen", help="print a new seed and its public key")
    m = sub.add_parser("manifest", help="write the signed update manifest")
    m.add_argument("exe")
    m.add_argument("tag")
    m.add_argument("outdir")
    args = ap.parse_args(argv)
    if args.cmd == "keygen":
        return keygen()
    return manifest(args.exe, args.tag, args.outdir)


if __name__ == "__main__":
    sys.exit(main())
