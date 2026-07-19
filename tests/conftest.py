# SPDX-License-Identifier: GPL-3.0-or-later
"""Global test configuration (v1.6.3).

Two safety nets applied to every test automatically:

* ``QT_QPA_PLATFORM=offscreen`` — Qt code never needs a real display.
* Config-file isolation — ``config._config_file`` is monkeypatched to a
  per-test temp path, so ``save_config``/``load_config`` can never touch the
  developer's real ``config.json``. The v1.4.1 creds-wipe incident was exactly
  this failure mode: an offscreen UI harness built ``Config(root=tmp)`` without
  patching ``_config_file`` and clobbered the real config (see the warning in
  ``config.save_config``). Tests that patch ``_config_file`` themselves keep
  working — their patch is applied later and simply wins.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rosu import config


@pytest.fixture(autouse=True)
def _isolate_config_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_config_file",
                        lambda: tmp_path / "config.json")
