# SPDX-License-Identifier: GPL-3.0-or-later
"""Real progress for the osu!lazer export (v1.9)."""
import sys

import pytest

from rosu import config
from rosu.db import Database
from rosu.services import Services
from rosu.services.import_svc import _export_line


class DummyLog:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


def test_export_lines_count_sets_and_read_the_total():
    assert _export_line("TOTAL 12\n") == (0, 12)
    assert _export_line("EXPORT 5\t5 A - B.osz\n") == (1, None)
    assert _export_line("EXPORT 5\n") == (1, None)          # an older helper
    assert _export_line("done exported=3") == (0, None)
    assert _export_line("TOTAL x") == (0, None)


@pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX shell script as the helper")
def test_run_lazer_export_reports_done_of_total(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "save_config", lambda cfg: None)
    cfg = config._fill_defaults(config.Config(root=str(tmp_path)))
    cfg.ensure_dirs()
    db = Database(cfg.db_path)
    svc = Services(cfg, db, DummyLog())
    helper = tmp_path / "helper.sh"
    helper.write_text("#!/bin/sh\necho TOTAL 3\n"
                      "for i in 1 2 3; do echo \"EXPORT $i\t$i x.osz\"; sleep 0.25; done\n")
    helper.chmod(0o755)
    monkeypatch.setattr(type(svc), "_lazer_helper", lambda self: helper)
    seen = []
    ok, detail = svc._run_lazer_export(tmp_path, tmp_path / "out", seen.append)
    assert ok and detail == ""
    bars = [(m["done"], m["total"]) for m in seen if m.get("kind") == "export"]
    assert bars and all(t == 3 for _d, t in bars)
    assert [d for d, _t in bars] == sorted(d for d, _t in bars)   # only moves forward
    db.close()
