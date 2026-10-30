# SPDX-License-Identifier: GPL-3.0-or-later
"""The profiling tools (tools/make_big_library.py, tools/profile_library.py)."""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from rosu import config, fingerprint
from rosu.beatmap import read_osz_full
from rosu.parsing import parse_pack_name

TOOLS = Path(__file__).resolve().parent.parent / "tools"
PATHS = ["startup", "refresh", "search", "prescan", "extract", "export",
         "read_metadata", "fingerprint"]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load("make_big_library")
prof = _load("profile_library")


def _make(target, n=50, seed=1, *extra):
    return gen.main([str(target), "--n", str(n), "--seed", str(seed), *extra])


def _tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def profiled(tmp_path_factory):
    """A generated N=50 folder, profiled once (no fpcalc), and its JSON report."""
    base = tmp_path_factory.mktemp("profiled")
    target, out = base / "lib", base / "out.json"
    assert _make(target) == 0
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tempfile, "tempdir", None)   # the tool sets it; restored on exit
        mp.setattr(config, "_config_file", lambda: base / "config.json")
        mp.setattr(fingerprint, "fpcalc_path", lambda: None)
        assert prof.main([str(target), "--sample", "10", "--json", str(out)]) == 0
    return target, json.loads(out.read_text(encoding="utf-8"))


def test_generates_library_packs_and_marker(tmp_path):
    assert _make(tmp_path / "lib") == 0
    lib = tmp_path / "lib"
    assert len(list((lib / "Library").glob("*.osz"))) == 50
    packs = list((lib / "Packs").glob("*.zip"))
    assert len(packs) >= 2
    for z in packs:
        parsed = parse_pack_name(z.name)
        assert parsed.series and parsed.number
    assert list((lib / "Output").iterdir()) == []
    assert (lib / ".rosu-perf-library").is_file()
    meta, diffs, _raw = read_osz_full(sorted((lib / "Library").glob("*.osz"))[0])
    assert len(diffs) >= 2 and meta.title and meta.artist


def test_same_seed_gives_identical_bytes(tmp_path):
    assert _make(tmp_path / "a") == 0
    assert _make(tmp_path / "b") == 0
    assert _tree(tmp_path / "a") == _tree(tmp_path / "b")


@pytest.mark.parametrize("extra", [(), ("--force",)])
def test_generator_refuses_folder_without_marker(tmp_path, extra):
    (tmp_path / "keep.txt").write_text("mine")
    assert _make(tmp_path, 5, 0, *extra) != 0
    assert [p.name for p in tmp_path.iterdir()] == ["keep.txt"]


def test_force_regenerates_a_generated_folder(tmp_path):
    assert _make(tmp_path / "lib") == 0
    assert _make(tmp_path / "lib") != 0   # non-empty without --force
    assert _make(tmp_path / "lib", 5, 1, "--force") == 0
    assert len(list((tmp_path / "lib" / "Library").glob("*.osz"))) == 5


def test_profile_reports_every_path(profiled):
    _target, report = profiled
    assert report["n"] == 50 and report["sample"] == 10
    assert [r["name"] for r in report["results"]] == PATHS
    for r in report["results"]:
        if r["name"] == "fingerprint":
            assert r["status"] == "skipped" and r["detail"]
            continue
        assert r["status"] == "ok"
        assert isinstance(r["wall_s"], float) and r["wall_s"] >= 0
        assert isinstance(r["peak_mem_bytes"], int) and r["peak_mem_bytes"] > 0
        assert 1 <= len(r["top"]) <= 10


def test_profile_keeps_everything_in_the_target(profiled):
    target, _report = profiled
    assert len(list((target / "Processed").glob("*.zip"))) >= 2
    assert list((target / "Packs").iterdir()) == []
    assert list((target / "Exports").glob("*.zip"))


def test_profile_refuses_unmarked_and_already_profiled(tmp_path, profiled):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert prof.main([str(plain)]) != 0
    assert list(plain.iterdir()) == []
    target, _report = profiled
    assert prof.main([str(target)]) != 0


def test_profile_never_loads_qt(tmp_path):
    assert _make(tmp_path / "lib", 20) == 0
    code = ("import importlib.util, sys\n"
            "spec = importlib.util.spec_from_file_location('p', sys.argv[1])\n"
            "mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)\n"
            "assert mod.main([sys.argv[2], '--sample', '5']) == 0\n"
            "assert 'PySide6' not in sys.modules\n")
    subprocess.run([sys.executable, "-c", code, str(TOOLS / "profile_library.py"),
                    str(tmp_path / "lib")], check=True, cwd=tmp_path, timeout=120)
