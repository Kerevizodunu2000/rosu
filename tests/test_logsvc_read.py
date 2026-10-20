# SPDX-License-Identifier: GPL-3.0-or-later
"""Reading logs back for the Logs table (v1.9)."""
from rosu import logsvc


def test_parse_line_splits_columns_and_keeps_quoted_separators():
    svc_line = ('2026-10-20T10:00:00 | INFO | SEARCH | query="a | b" results=3 | '
                'User searched the music memory')
    e = logsvc.parse_line(svc_line + "\n")
    assert (e["time"], e["level"], e["action"]) == ("2026-10-20T10:00:00", "INFO", "SEARCH")
    assert e["fields"] == 'query="a | b" results=3'
    assert e["message"] == "User searched the music memory"
    odd = logsvc.parse_line("Traceback (most recent call last):")
    assert odd["message"] == "Traceback (most recent call last):" and odd["level"] == ""


def test_round_trip_through_the_log_service(tmp_path):
    svc = logsvc.LogService(tmp_path)
    svc.info("SEARCH", query="x y", results=2)
    svc.error("drive:restore", "boom | bad")
    day = logsvc.log_days(tmp_path)[0]
    entries = logsvc.read_day(tmp_path, day)
    assert [e["action"] for e in entries] == ["SEARCH", "ERROR"]
    assert entries[1]["level"] == "ERROR" and 'detail="boom | bad"' in entries[1]["fields"]
    assert [e["action"] for e in entries if logsvc.entry_matches(e, [], True)] == ["ERROR"]
    assert [e["action"] for e in entries if logsvc.entry_matches(e, ["x", "y"])] == ["SEARCH"]
    assert logsvc.read_day(tmp_path, "1999-01-01") == []


def test_log_days_lists_only_dated_files_newest_first(tmp_path):
    for name in ("app-2026-10-19.log", "app-2026-10-20.log", "app-notes.log", "other.log"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    assert logsvc.log_days(tmp_path) == ["2026-10-20", "2026-10-19"]
