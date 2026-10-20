# SPDX-License-Identifier: GPL-3.0-or-later
"""Saved searches (v1.9): validation of hand-editable config data."""
from rosu import config, presets


def test_normalize_keeps_valid_unique_entries_only():
    raw = [{"name": " Hard  mania ", "query": "mode=mania star>5", "tags": 1},
           {"name": "hard MANIA", "query": "dupe"},            # same name, case-folded
           {"name": "", "query": "x"}, {"name": "n"}, "junk", None,
           {"name": 5, "query": "x"}]
    assert presets.normalize(raw) == [
        {"name": "Hard mania", "query": "mode=mania star>5", "tags": True}]
    assert presets.normalize("not a list") == []


def test_save_replaces_by_name_and_caps():
    saved = presets.save([], "Jumps", "pattern=jump")
    saved = presets.save(saved, "jumps", "pattern=jump star>6", tags=True)
    assert saved == [{"name": "jumps", "query": "pattern=jump star>6", "tags": True}]
    for i in range(presets.MAX_SAVED + 3):
        saved = presets.save(saved, f"s{i}", "q")
    assert len(saved) == presets.MAX_SAVED
    assert saved[-1]["name"] == f"s{presets.MAX_SAVED + 2}"      # oldest made room
    assert presets.save(saved, "   ", "q") == saved                # blank name ignored


def test_remove_by_name():
    saved = presets.save(presets.save([], "A", "a"), "B", "b")
    assert [e["name"] for e in presets.remove(saved, " a ")] == ["B"]


def test_config_coerces_hand_edited_ui_state(tmp_path):
    cfg = config.Config(root=str(tmp_path), search_hidden_columns="col_bpm",
                        saved_searches=[{"name": "ok", "query": "x"}, 3])
    cfg = config._fill_defaults(cfg)
    assert cfg.search_hidden_columns == []
    assert cfg.saved_searches == [{"name": "ok", "query": "x", "tags": False}]


def test_history_steps_back_and_forward_and_coalesces_typing():
    h = presets.History(size=3)
    h.push(("ca", False), now=0.0)
    h.push(("cam", False), now=0.5)            # same burst of typing: one step
    h.push(("camellia", False), now=1.0)
    h.push(("star>5", False), now=10.0)
    assert h.back() == ("camellia", False) and not h.can_back()
    assert h.forward() == ("star>5", False) and not h.can_forward()
    h.back()
    h.push(("mode=mania", True), now=20.0)     # a new step drops the forward ones
    assert not h.can_forward() and h.back() == ("camellia", False)
    for i in range(5):
        h.push((f"q{i}", False), now=100.0 + 10 * i)
    assert len(h._items) == 3                  # capped
    h.push(("q4", False), now=200.0)           # repeating the current entry: no step
    assert len(h._items) == 3 and h._items[-1] == ("q4", False)
