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


def test_auto_refresh_on_tab_defaults_on_and_round_trips(tmp_path, monkeypatch):
    # v1.3: the "auto-refresh a tab on switch" toggle defaults ON and persists.
    monkeypatch.setattr(config, "_config_file", lambda: tmp_path / "config.json")
    assert config.Config(root="x").auto_refresh_on_tab is True
    cfg = config.load_config()                         # no file yet → default
    assert cfg.auto_refresh_on_tab is True
    cfg.auto_refresh_on_tab = False
    config.save_config(cfg)
    assert config.load_config().auto_refresh_on_tab is False


def test_v14_client_and_autosave_defaults_round_trip(tmp_path, monkeypatch):
    # v1.4: lazer on, stable off, settings auto-save on — defaults + persistence.
    monkeypatch.setattr(config, "_config_file", lambda: tmp_path / "config.json")
    c = config.Config(root="x")
    assert c.lazer_enabled is True
    assert c.stable_enabled is False
    assert c.settings_autosave is True
    cfg = config.load_config()                         # no file yet → defaults
    assert (cfg.lazer_enabled, cfg.stable_enabled, cfg.settings_autosave) == \
        (True, False, True)
    cfg.lazer_enabled = False
    cfg.stable_enabled = True
    cfg.settings_autosave = False
    config.save_config(cfg)
    r = config.load_config()
    assert (r.lazer_enabled, r.stable_enabled, r.settings_autosave) == \
        (False, True, False)
