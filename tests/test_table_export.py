# SPDX-License-Identifier: GPL-3.0-or-later
"""CSV/JSON export of search results (v1.9)."""
import csv
import io
import json

from rosu import table_export


def _row(**over):
    row = {"beatmapset_id": 123, "artist": "Camellia", "title": "=HYPERLINK(\"x\")",
           "creator": "Mapper", "bpm": 180.0, "length_seconds": 95, "mode": "osu!mania",
           "difficulties": [{"mode": "osu!mania", "star_rating": 5.4321, "keycount": 7},
                            {"mode": "osu!mania", "star_rating": 3.1, "keycount": 4}],
           "sources": ["Pack 1"], "in_library": 1, "library_status": "memory",
           "in_osu_stable": 1, "in_osu_lazer": 0, "filename": "123 C - T.osz",
           "first_seen_at": "2026-10-20T10:00:00"}
    row.update(over)
    return row


def test_record_collects_the_shown_facts():
    rec = table_export.record(_row())
    assert rec["stars"] == [3.1, 5.43] and rec["keys"] == [4, 7]
    assert rec["modes"] == ["osu!mania"]
    assert rec["in_library"] is True and rec["library_file"] is False   # memory-only
    assert rec["in_osu_stable"] is True and rec["in_osu_lazer"] is False


def test_csv_neutralises_formulas_and_keeps_numbers():
    text = table_export.to_csv([_row(), _row(title="-5", artist="+cool")])
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows[0]["title"] == "'=HYPERLINK(\"x\")"
    assert rows[1]["title"] == "-5" and rows[1]["artist"] == "'+cool"
    assert rows[0]["stars"] == "3.1; 5.43" and rows[0]["in_osu_stable"] == "yes"


def test_json_keeps_types_and_the_query():
    data = json.loads(table_export.to_json([_row()], "mode=mania"))
    assert data["query"] == "mode=mania" and data["count"] == 1
    assert data["sets"][0]["bpm"] == 180.0 and data["sets"][0]["keys"] == [4, 7]


def test_write_picks_the_format_from_the_suffix(tmp_path):
    assert table_export.write(tmp_path / "a.csv", [_row()]) == 1
    assert (tmp_path / "a.csv").read_bytes().startswith(b"\xef\xbb\xbf")   # Excel reads UTF-8
    table_export.write(tmp_path / "a.json", [_row()], "q")
    assert json.loads((tmp_path / "a.json").read_text(encoding="utf-8"))["query"] == "q"
