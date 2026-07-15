# SPDX-License-Identifier: GPL-3.0-or-later
"""Config hardening: a hand-edited config.json can't crash startup.

json.loads accepts the bare tokens Infinity / NaN (a CPython extension), so a
hand-edited drive_chunk_bytes could arrive as a non-finite float. _fill_defaults
must coerce or reject it, never propagate an uncaught exception up to run().
"""
from rosu import config


def test_fill_defaults_rejects_infinity_chunk_bytes():
    # int(float('inf')) raises OverflowError (not ValueError) — must be caught.
    cfg = config.Config(root="x", drive_chunk_bytes=float("inf"))
    cfg = config._fill_defaults(cfg)
    assert cfg.drive_chunk_bytes == 1073741824
    assert isinstance(cfg.drive_chunk_bytes, int)


def test_fill_defaults_rejects_nan_chunk_bytes():
    cfg = config.Config(root="x", drive_chunk_bytes=float("nan"))
    cfg = config._fill_defaults(cfg)
    assert cfg.drive_chunk_bytes == 1073741824


def test_fill_defaults_floors_tiny_chunk_bytes():
    cfg = config.Config(root="x", drive_chunk_bytes=10)
    cfg = config._fill_defaults(cfg)
    assert cfg.drive_chunk_bytes >= 1024 * 1024   # never below 1 MiB
