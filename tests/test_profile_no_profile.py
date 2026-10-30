# SPDX-License-Identifier: GPL-3.0-or-later
"""tools/profile_library.py --no-profile: wall times only, no profiler."""
import cProfile
import importlib.util
import json
import tempfile
import tracemalloc
from pathlib import Path

import pytest

from rosu import config, fingerprint

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load("make_big_library")
prof = _load("profile_library")


def test_no_profile_times_every_path_without_profiler(tmp_path, monkeypatch, capsys):
    target, out = tmp_path / "lib", tmp_path / "out.json"
    assert gen.main([str(target), "--n", "20", "--seed", "3"]) == 0

    def boom(*_a, **_k):
        raise AssertionError("profiler used with --no-profile")
    monkeypatch.setattr(tempfile, "tempdir", None)
    monkeypatch.setattr(config, "_config_file", lambda: tmp_path / "config.json")
    monkeypatch.setattr(fingerprint, "fpcalc_path", lambda: None)
    monkeypatch.setattr(cProfile, "Profile", boom)
    monkeypatch.setattr(tracemalloc, "start", boom)
    assert prof.main([str(target), "--no-profile", "--sample", "10", "--json", str(out)]) == 0

    table = capsys.readouterr().out
    report = json.loads(out.read_text(encoding="utf-8"))
    assert [r["name"] for r in report["results"]] == list(prof.NAMES)
    for r in report["results"]:
        if r["name"] == "fingerprint":
            assert r["status"] == "skipped"
            continue
        assert r["status"] == "ok"
        assert isinstance(r["wall_s"], float) and r["wall_s"] >= 0
        assert r["peak_mem_bytes"] is None and r["top"] == []
        assert r["name"] in table
    assert report["results"][prof.NAMES.index("read_metadata")]["detail"]["sets"] == 10


@pytest.mark.parametrize("profile", [True, False])
def test_measure_returns_the_value(profile):
    entry, value = prof.measure("x", lambda: 42, profile)
    assert value == 42 and entry["status"] == "ok"
    assert (entry["peak_mem_bytes"] is None) is (not profile)
