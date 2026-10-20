# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded reads of zip members (v1.9 review).

``ZipFile.read`` trusts the size a member *declares*: a forged header can claim
1 KB and inflate to gigabytes before the length check ever runs. These helpers
read through the decompressor in bounded steps and stop past ``cap``.
"""
from __future__ import annotations

import zipfile

_CHUNK = 1024 * 1024


class TooBig(ValueError):
    """A member holds more than its cap."""


def read_capped(zf: zipfile.ZipFile, info, cap: int) -> bytes:
    """The member's bytes; raises :class:`TooBig` past ``cap`` (whatever its
    header says) and the usual zipfile errors for a corrupt member."""
    if getattr(info, "file_size", 0) > cap:
        raise TooBig(str(getattr(info, "filename", info)))
    out = bytearray()
    with zf.open(info) as fh:
        while True:
            block = fh.read(min(_CHUNK, cap + 1 - len(out)))
            if not block:
                return bytes(out)
            out += block
            if len(out) > cap:
                raise TooBig(str(getattr(info, "filename", info)))


def copy_capped(zf: zipfile.ZipFile, info, dest, cap: int) -> int:
    """Stream the member into the open binary file ``dest``; raises
    :class:`TooBig` past ``cap``. Returns the bytes written."""
    if getattr(info, "file_size", 0) > cap:
        raise TooBig(str(getattr(info, "filename", info)))
    written = 0
    with zf.open(info) as fh:
        while True:
            block = fh.read(_CHUNK)
            if not block:
                return written
            written += len(block)
            if written > cap:
                raise TooBig(str(getattr(info, "filename", info)))
            dest.write(block)
