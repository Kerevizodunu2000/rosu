# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for rosu.pathheal — folder self-heal after a move (item 20)."""
from rosu.config import Config
from rosu.pathheal import diagnose, apply_fix, CANONICAL_DIRS


def _cfg(root, **over):
    """A Config whose 5 working dirs default to <root>/<Canonical>."""
    from pathlib import Path
    p = Path(root)
    c = Config(
        root=str(p),
        packs_dir=over.get("packs_dir", str(p / "Packs")),
        output_dir=over.get("output_dir", str(p / "Output")),
        library_dir=over.get("library_dir", str(p / "Library")),
        data_dir=over.get("data_dir", str(p / "data")),
        logs_dir=over.get("logs_dir", str(p / "logs")),
    )
    return c


def _make_dirs(base, names, with_data=()):
    for n in names:
        d = base / n
        d.mkdir(parents=True, exist_ok=True)
        if n in with_data:
            (d / "sample.osz").write_text("x", encoding="utf-8")


def test_healthy_when_all_dirs_exist(tmp_path):
    base = tmp_path / "app"
    base.mkdir()
    _make_dirs(base, ["Packs", "Output", "Library", "data", "logs"])
    cfg = _cfg(base)
    diag = diagnose(cfg, base)
    assert diag.status == "healthy"
    assert not diag.has_changes()
    assert diag.fixes == []


def test_relocated_detects_data_next_to_exe(tmp_path):
    # Config points at an OLD location that no longer exists; the app now lives
    # in `base`, which already holds the real folders (Library has data).
    old = tmp_path / "Old"          # never created -> stale
    base = tmp_path / "rosu"
    base.mkdir()
    _make_dirs(base, ["Packs", "Output", "Library", "data", "logs"],
               with_data=["Library", "data"])
    cfg = _cfg(old)
    diag = diagnose(cfg, base)
    assert diag.status == "relocated"
    assert diag.has_changes()
    assert diag.root_new == str(base)
    # every dir is re-pointed to the exe-adjacent folder
    by_attr = {f.attr: f for f in diag.fixes}
    assert set(by_attr) == {a for a, _ in CANONICAL_DIRS}
    assert by_attr["library_dir"].new == str(base / "Library")
    assert by_attr["library_dir"].new_has_data is True
    assert by_attr["output_dir"].new_has_data is False


def test_relocated_when_stale_dirs_are_empty_junk(tmp_path):
    # The REAL bug: config still points at an old location whose folders were
    # recreated EMPTY (e.g. the app polluted an unrelated folder), while the real
    # data now sits next to the exe. Existence alone must not read as "healthy".
    old = tmp_path / "Osu"          # unrelated folder; archiver left empty dirs here
    _make_dirs(old, ["Packs", "Output", "Library", "data", "logs"])
    (old / "data" / "memory.db").write_text("tiny", encoding="utf-8")  # near-empty db
    base = tmp_path / "rosu"
    base.mkdir()
    _make_dirs(base, ["Packs", "Output", "Library", "data", "logs"])
    for i in range(20):             # real Library has many .osz
        (base / "Library" / f"{i}.osz").write_text("data" * 100, encoding="utf-8")
    (base / "data" / "memory.db").write_text("x" * 5000, encoding="utf-8")  # real db
    cfg = _cfg(old)
    diag = diagnose(cfg, base)
    assert diag.status == "relocated"
    changed = {f.attr for f in diag.fixes}
    assert "library_dir" in changed     # empty junk Library -> real one
    assert "data_dir" in changed        # tiny db -> real db
    apply_fix(cfg, diag)
    assert cfg.library_dir == str(base / "Library")
    assert cfg.data_dir == str(base / "data")


def test_fresh_when_nothing_exists_anywhere(tmp_path):
    old = tmp_path / "Old"          # stale
    base = tmp_path / "empty_app"
    base.mkdir()                    # base has no working folders yet
    cfg = _cfg(old)
    diag = diagnose(cfg, base)
    assert diag.status == "fresh"   # first-run: just create structure, no scary dialog


def test_partial_leaves_valid_custom_paths(tmp_path):
    # The app moved (old root gone) and most folders are now next to the exe,
    # but the user keeps Library on another drive at a path that STILL exists.
    old = tmp_path / "Old"                      # stale root, never created
    base = tmp_path / "rosu"
    base.mkdir()
    _make_dirs(base, ["Packs", "Output", "data", "logs"], with_data=["data"])
    bigdrive = tmp_path / "BigDrive"
    _make_dirs(bigdrive, ["Library"], with_data=["Library"])
    cfg = _cfg(old, library_dir=str(bigdrive / "Library"))
    diag = diagnose(cfg, base)
    assert diag.status == "relocated"
    changed = {f.attr for f in diag.fixes}
    # the valid custom Library is preserved; everything else re-points to base
    assert "library_dir" not in changed
    assert changed == {"packs_dir", "output_dir", "data_dir", "logs_dir"}
    apply_fix(cfg, diag)
    assert cfg.library_dir == str(bigdrive / "Library")   # untouched
    assert cfg.packs_dir == str(base / "Packs")


def test_apply_fix_mutates_config(tmp_path):
    old = tmp_path / "Old"
    base = tmp_path / "rosu"
    base.mkdir()
    _make_dirs(base, ["Packs", "Output", "Library", "data", "logs"],
               with_data=["Library"])
    cfg = _cfg(old)
    diag = diagnose(cfg, base)
    apply_fix(cfg, diag)
    assert cfg.root == str(base)
    assert cfg.library_dir == str(base / "Library")
    assert cfg.data_dir == str(base / "data")
    # derived paths follow automatically
    assert cfg.db_path == base / "data" / "memory.db"
    assert cfg.excel_path == base / "data" / "tracking.xlsx"
