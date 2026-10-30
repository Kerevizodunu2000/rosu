# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in crash reports (v1.8): what is built, what is never sent."""

import pytest

from rosu import crash_report


@pytest.fixture(autouse=True)
def _reset():
    crash_report._seen.clear()
    prev = crash_report._enabled
    yield
    crash_report._enabled = prev
    crash_report._seen.clear()


def _raise(exc):
    try:
        raise exc
    except BaseException as e:   # noqa: BLE001 - we want the traceback attached
        return e


def test_scrub_and_module_paths():
    assert crash_report.scrub(r"cannot open C:\Users\you\osu!\Songs\x.osz") == "cannot open <path>"
    assert crash_report.scrub("mail me@example.com") == "mail <email>"
    # Spaces inside a path, quoted library names and relative paths all go.
    spaced = r"bad C:\Users\John Smith\Documents\osu!\Songs\123 Artist - Title\a.osu"
    assert crash_report.scrub(spaced) == "bad <path>"
    assert crash_report.scrub("x /home/jane doe/x") == "x <path>"
    assert crash_report.scrub("Songs/123 A - B/x.osu missing") == "<path> missing"
    assert crash_report.scrub("'Artist - Title'") == "'<str>'"
    assert crash_report.scrub(r"\\server\share\John Doe\f") == "<path>"
    assert crash_report.scrub("invalid literal for int() with base 10: 12") == \
        "invalid literal for int() with base 10: 12"
    assert crash_report.module_path(r"C:\x\_MEI1\rosu\services\library_svc.py") == "rosu/services/library_svc.py"
    assert crash_report.module_path("/usr/lib/python3.13/zipfile.py") == "zipfile.py"


def test_type_names_match_the_server_contract():
    assert crash_report.exc_type_name(ValueError("x")) == "ValueError"
    import zipfile
    assert crash_report.exc_type_name(zipfile.BadZipFile("x")) == "zipfile.BadZipFile"


def test_expected_failures_are_never_reported():
    from rosu.drive.auth import DriveError, DriveCancelled
    for exc in (OSError("disk"), ConnectionError("net"), KeyboardInterrupt(),
                DriveError("http"), DriveCancelled("stop")):
        assert crash_report.is_reportable(exc) is False, exc
    assert crash_report.is_reportable(ValueError("bug")) is True


def test_payload_is_frames_and_scrubbed_message_only():
    exc = _raise(KeyError(r"C:\Users\me\secret.osz"))
    p = crash_report.build_payload(exc)
    assert p["exc_type"] == "KeyError"
    assert "Users" not in p["message"] and p["message"] == "'<str>'"
    assert all(":" in f and "\\" not in f for f in p["frames"])
    assert p["frames"][-1].endswith(":_raise")
    assert set(p) == {"exc_type", "message", "frames", "app_version", "os"}


def test_capture_is_off_by_default_and_deduplicates_when_on():
    sent = []
    crash_report._enabled = lambda: False
    assert crash_report.capture(_raise(ValueError("a")), sender=sent.append, background=False) is False
    crash_report._enabled = lambda: True
    e1 = _raise(ValueError("a"))
    assert crash_report.capture(e1, sender=sent.append, background=False) is True
    assert crash_report.capture(e1, sender=sent.append, background=False) is False   # same crash
    assert crash_report.capture(_raise(OSError("disk")), sender=sent.append, background=False) is False
    assert len(sent) == 1


def test_capture_never_raises_even_if_sending_does():
    crash_report._enabled = lambda: True
    def boom(_p):
        raise RuntimeError("network stack exploded")
    assert crash_report.capture(_raise(ValueError("z")), sender=boom, background=False) is False


def test_send_refuses_plain_http():
    assert crash_report.send({}, endpoint="http://example.com/api/crash") == {"ok": False, "error": "bad_endpoint"}


def test_worker_failure_is_captured(monkeypatch):
    from rosu import workers
    got = []
    monkeypatch.setattr(crash_report, "capture", lambda exc, **k: got.append(exc))
    w = workers.Worker(lambda progress=None: 1 / 0)
    w.run()   # run synchronously on this thread
    assert len(got) == 1 and isinstance(got[0], ZeroDivisionError)
