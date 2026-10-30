# SPDX-License-Identifier: GPL-3.0-or-later
"""7z codec check for ``--selftest`` (Qt-free, so it is unit-tested offline).

PyInstaller cannot see the codec modules py7zr imports at runtime, so a frozen
build can be missing one and only fail when a 7z archive is opened. Importing
them by their *import* names (``bcj`` is the module of the ``pybcj`` package) and
round-tripping a tiny BCJ + LZMA2 archive proves they are packaged.
"""
from __future__ import annotations

import importlib
import io
import tempfile
from pathlib import Path

CODEC_MODULES = ("bcj", "pyppmd", "inflate64", "Cryptodome")
_PAYLOAD = b"rosu selftest " * 64


def check_codecs(modules: tuple[str, ...] = CODEC_MODULES) -> str | None:
    """Return None if the 7z codecs work, else a one-line reason."""
    try:
        for name in modules:
            importlib.import_module(name)
        import py7zr
        filters = [{"id": py7zr.FILTER_X86}, {"id": py7zr.FILTER_LZMA2}]
        buf = io.BytesIO()
        with py7zr.SevenZipFile(buf, "w", filters=filters) as z:
            z.writestr(_PAYLOAD, "probe.bin")
        buf.seek(0)
        with tempfile.TemporaryDirectory() as tmp, \
                py7zr.SevenZipFile(buf, "r") as z:
            z.extractall(tmp)
            got = (Path(tmp) / "probe.bin").read_bytes()
        if got != _PAYLOAD:
            return "7z roundtrip returned different bytes"
    except Exception as exc:
        # same shape as rosu.app._error_line (importing app here would be a cycle)
        return " ".join(f"{type(exc).__name__}: {exc}".split())
    return None
