# SPDX-License-Identifier: GPL-3.0-or-later
"""Parity: ``rosu_native_osu_core.parse_batch`` against the Python parser.

Every input goes through ``beatmap.parse_osu_sections``, ``beatmap.read_mania_notes``
and ``msd.skillset`` and through ``parse_batch``, and every field must be equal, with
the same types (the reprs are compared). The MSD values are compared exactly: both
sides round them to two decimals. A 1e-9 relative tolerance on unrounded values is
allowed only if a libm difference between the two sides is ever traced; none is used.

The native tests skip when the wheel is not installed, and fail instead when
``ROSU_REQUIRE_NATIVE=1`` (as in CI). The import-guard test always runs.
"""
import importlib.util
import io
import os
import random
import subprocess
import sys
import unicodedata
import zipfile
from pathlib import Path

import pytest

from rosu import beatmap, msd
from rosu.models import DiffMeta

try:
    import rosu_native_osu_core as _native
except ImportError:
    _native = None

ROOT = Path(__file__).resolve().parent.parent
META_KEYS = ("Version", "Artist", "Title", "Creator", "Source", "Tags")
DIFF_KEYS = ("CircleSize", "ApproachRate", "OverallDifficulty", "HPDrainRate")
MSD_FIELDS = ("overall", "stream", "jumpstream", "handstream", "stamina", "jackspeed",
              "chordjack", "technical")
MAX_BYTES = 16 * 1024 * 1024


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load("make_big_library")


@pytest.fixture
def native():
    if _native is None:
        if os.environ.get("ROSU_REQUIRE_NATIVE") == "1":
            pytest.fail("ROSU_REQUIRE_NATIVE=1 but rosu_native_osu_core is not installed")
        pytest.skip("rosu_native_osu_core is not installed")
    return _native


def python_result(data: bytes, keycount):
    """What parse_batch must return for one item, computed by the Python code."""
    p = beatmap.parse_osu_sections(data.decode("utf-8", errors="replace"))
    out = {"meta": {k: v for k, v in p["meta"].items() if k in META_KEYS},
           "mode_int": p["mode_int"],
           "difficulty": {k: v for k, v in p["difficulty"].items() if k in DIFF_KEYS},
           "bpm": p["bpm"], "length_seconds": p["length_seconds"], "msd": None}
    if keycount is not None:
        r = msd.skillset(beatmap.read_mania_notes(data, keycount), keycount)
        out["msd"] = None if r is None else tuple(getattr(r, f) for f in MSD_FIELDS)
    return out


def check(native, items):
    """``items``: ``[(data, keycount), ...]``, sent as one batch."""
    got = native.parse_batch([(f"{i}.osu", d, k) for i, (d, k) in enumerate(items)])
    assert len(got) == len(items)
    for (data, keycount), g in zip(items, got):
        want = python_result(data, keycount)
        assert repr(g) == repr(want), (data[:300], keycount)


def osu(*lines: str, sep: str = "\n") -> bytes:
    return sep.join(lines).encode("utf-8")


def mania_text(notes, keys=4, extra=()):
    """A mania .osu: ``notes`` are (x, time) or full hit-object lines."""
    objs = [n if isinstance(n, str) else f"{n[0]},192,{n[1]},1,0,0:0:0:0:" for n in notes]
    return osu("osu file format v14", "[General]", "Mode: 3", "[Difficulty]",
               f"CircleSize:{keys}", *extra, "[HitObjects]", *objs)


def stream(n=64, keys=4, dt=125, start=1000):
    return [(int((i % keys) * 512 / keys) + 1, start + i * dt) for i in range(n)]


def _generated_sets(count, seed=11):
    tones = gen._tones(random.Random(seed), 2)
    for index in range(count):
        _name, data = gen.make_set(seed, index, 100000 + index, tones)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            yield [zf.read(n) for n in zf.namelist() if n.endswith(".osu")]


def _keycount(data):
    return beatmap.read_osu_diff(data, "x.osu").keycount


# --- generated library -------------------------------------------------------

def test_generated_sets_match(native):
    items, mania = [], 0
    for files in _generated_sets(240):
        items += [(d, None) for d in files]
        for d in files:
            k = _keycount(d)
            if k:
                items.append((d, k))
                mania += 1
        if len(items) > 500:
            check(native, items)
            items = []
    check(native, items)
    assert mania > 100   # the MSD side was really exercised


def test_generated_set_mutations_match(native):
    """Seeded mutations of generated files: flipped bytes, hostile tokens, cut lines."""
    rnd = random.Random(7)
    tokens = [b"inf", b"-inf", b"nan", b"1e400", b"1e300", b"9" * 30, b"\x1c", b"\x1f", b"_",
              b"\xd9\xa2", b"\xef\xbc\x95", b"\r", b"\x85", b"\xe2\x80\xa8", b"\xff", b"-0",
              b"0.5", b"2.5", b"+", b".", b"e", b",", b":", b"[", b"]", b"\n[HitObjects]\n"]
    items = []
    for files in _generated_sets(60, seed=5):
        for data in files:
            b = bytearray(data)
            for _ in range(rnd.randint(1, 25)):
                pos = rnd.randrange(len(b))
                op = rnd.random()
                if op < 0.4:
                    b[pos:pos] = rnd.choice(tokens)
                elif op < 0.7:
                    b[pos] = rnd.randrange(256)
                else:
                    del b[pos:pos + rnd.randint(1, 40)]
            items.append((bytes(b), rnd.choice([None, 4, 7, _keycount(bytes(b))])))
    check(native, items)


# --- edge inputs --------------------------------------------------------------

def test_empty_malformed_and_garbage(native):
    check(native, [
        (b"", None), (b"", 4), (b"\n\n\r\n", 4), (b"[General]", None), (b"[]\n[", None),
        (b"\x00\x01 not a beatmap \xff", 7), (bytes(range(256)) * 8, 4),
        (osu("[General]", "Mode:", "Mode: x", "[Metadata]", ":", "Title:", ":v"), None),
        (osu("[Difficulty]", "CircleSize", "CircleSize:", ":5"), None),
        (osu("[TimingPoints]", "500", ",", "0,", "0,abc", "0,-5", "0,0"), None),
        (osu("[HitObjects]", "1,2", "1,2,", "1,2,x,1", "1,2,3"), 4),
        (b"[HitObjects]\n" + b"64,192,1,1\n" * 20, 4),   # one row only
    ])


def test_random_bytes(native):
    rnd = random.Random(1234)
    alphabet = b"[]:,.-+_0123456789eEinfaINFAMode \r\n\x0b\x1c\x1f\xc2\x85\xe2\x80\xa8\xff"
    heads = [b"[General]\n", b"[Metadata]\n", b"[Difficulty]\n", b"[TimingPoints]\n",
             b"[HitObjects]\n", b"Mode:3\n", b"CircleSize:", b"Title:"]
    items = []
    for _ in range(400):
        out = bytearray()
        for _ in range(rnd.randint(0, 1500)):
            r = rnd.random()
            if r < 0.05:
                out += rnd.choice(heads)
            elif r < 0.3:
                out.append(rnd.randrange(256))
            else:
                out.append(rnd.choice(alphabet))
        items.append((bytes(out), rnd.choice([None, 1, 4, 7, 64, 100])))
    check(native, items)


def test_near_16_mib_file_with_many_notes(native):
    pad = "0:0:0:0:" + "x" * 180
    lines = [f"{(i % 7) * 73 + 5},192,{1000 + (i // 3) * 40},{128 if i % 5 == 0 else 1},0,"
             f"{1000 + (i // 3) * 40 + 200}:{pad}" for i in range(76_000)]
    data = mania_text(lines, keys=7)
    data += b"\n" + b" " * (MAX_BYTES - len(data) - 1)
    assert len(data) == MAX_BYTES
    check(native, [(data, 7)])


def test_unicode_metadata(native):
    data = osu("[Metadata]", "Title:もっともっと",
               "Artist:　 العربية  ",
               "Creator:é́", "Source:\U0001f3b5​", "Tags:\x1fTag\x1f",
               "Version:﻿V", "TitleUnicode: ")
    check(native, [(data, None)])
    got = native.parse_batch([("u.osu", data, None)])[0]["meta"]
    assert got["Title"] == "もっともっと"
    assert got["Tags"] == "Tag"


def test_invalid_utf8_like_decode_replace(native):
    check(native, [
        (b"[Metadata]\nTitle:a\xed\xa0\x80b", None),         # surrogate
        (b"[Metadata]\nTitle:a\xf0\x9f\x98", None),           # truncated
        (b"[Metadata]\nTitle:\xc0\x80\xf4\x90\x80\x80", None),  # overlong, above U+10FFFF
        (b"\xef\xbb\xbf[General]\nMode: 3", None),            # a leading BOM is kept
        (b"[Metadata]\nTitle:\xe2\x82", None),
    ])


# --- parity traps (requirements 11 to 20) ---------------------------------------

@pytest.mark.parametrize("sep", ["\n", "\r", "\r\n", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e",
                                 "\x85", " ", " ", "\x1f"])
def test_every_line_ending(native, sep):
    data = osu("[General]", "Mode: 3", "[Metadata]", "Title:T", "[Difficulty]",
               "CircleSize:4", "[TimingPoints]", "0,500,4", "[HitObjects]",
               *(f"{x},192,{t},1,0,0:0:0:0:" for x, t in stream(40)), sep=sep)
    check(native, [(data, 4), (data, None)])


def test_strip_versus_int_and_float_whitespace(native):
    check(native, [
        (osu("[General]", "Mode:\x1c3\x1f"), None),           # strip() removes \x1c..\x1f
        (osu("[General]", "Mode:　3 "), None),
        (osu("[HitObjects]", "1,1,\x1c5000"), None),          # int() does not
        (osu("[HitObjects]", "1,1, 5000　"), None),  # but takes Unicode spaces
        (osu("[TimingPoints]", "0,\x1f500"), None),            # nor does float()
        (osu("[TimingPoints]", "0, 500\x0b"), None),
        (mania_text([f"\x1c{x},192,{t},1" for x, t in stream(20)]), 4),
        (mania_text([f"{x},192,{t},\x1f1" for x, t in stream(20)]), 4),
    ])


def test_int_and_float_acceptance(native):
    times = ["+5000", "-5000", "5_000", "5__000", "_5000", "5000_", "٥٠٠٠",
             "５０００", "5000.0", "0x1388", "5e3", "0" * 4296 + "5000",
             "0" * 4297 + "5000", "0_" * 4296 + "5000", " 7000 ", ""]
    floats = ["300", "+300", "3_0_0", "3__00", "1e1_0", "1_e10", "inf", "-INF", "Infinity",
              "nAn", "1e400", "-1e400", ".5", "5.", ".", "e5", "1e", "٣٠٠",
              "３００.5", "333.3335", "0x10", "1e-400"]
    items = [(osu("[HitObjects]", f"1,1,{t}"), None) for t in times]
    items += [(osu("[TimingPoints]", f"0,{f}"), None) for f in floats]
    items += [(osu("[Difficulty]", f"CircleSize:{f}", f"HPDrainRate:{f}"), None) for f in floats]
    items += [(osu("[General]", f"Mode: {t}"), None) for t in times]
    items += [(mania_text([f"{f},192,{t},1" for _, t in stream(20)]), 4) for f in floats]
    items += [(mania_text([f"64,192,{t}.9,1" for _, t in stream(20)]), 4)]
    check(native, items)


def test_every_unicode_digit_run(native):
    """Each run of decimal digits this Python knows parses the same natively (the
    module's table follows Python 3.14, Unicode 16.0)."""
    zeros = [c for c in range(0x110000) if unicodedata.decimal(chr(c), -1) == 0]
    assert len(zeros) >= 68
    items = []
    for z in zeros:
        digits = "".join(chr(z + int(d)) for d in "7250")
        items.append((osu("[HitObjects]", f"1,1,{digits}"), None))
        items.append((osu("[TimingPoints]", f"0,{chr(z + 3)}{chr(z)}{chr(z)}.5"), None))
    check(native, items)


def test_truncation_and_round_ties(native):
    check(native, [
        (osu("[HitObjects]", "1,1,2500"), None),   # round(2.5) == 2
        (osu("[HitObjects]", "1,1,3500"), None),   # round(3.5) == 4
        (osu("[HitObjects]", "1,1,500"), None),    # round(0.5) == 0
        (osu("[TimingPoints]", "0,333.3335"), None),
        (osu("[TimingPoints]", "0,0.0005"), None),  # rounds to 0.0: no bpm
        (osu("[TimingPoints]", "0,0.0015"), None),
        (osu("[TimingPoints]", "0,1e-300"), None),
        (osu("[TimingPoints]", "0,inf"), None),
        (mania_text([f"-0.9,192,{t},1" for _, t in stream(20)]), 4),
        (mania_text([f"{x}.99,192,{t}.99,1" for x, t in stream(20)]), 4),
    ])


def test_length_of_64_bit_times(native):
    times = [2**53 + 1, 5258986265376043509, 6000012885340954297, 2**63 - 1, 2**63, -(2**63),
             10**30, 999]
    check(native, [(osu("[HitObjects]", f"1,1,{t}"), None) for t in times])


def test_counter_tie_first_seen(native):
    check(native, [
        (osu("[TimingPoints]", "0,500", "1,300", "2,300.0001", "3,500"), None),
        (osu("[TimingPoints]", "0,300", "1,500", "2,500", "3,300.0004"), None),
        (osu("[TimingPoints]", "0,300", "1,-1", "2,500"), None),
    ])


def test_keycounts_above_64_and_wide_columns(native):
    xs = [0, 1, 511, 512, 4000, -1, 2**62, -(2**62), 2**63 - 1, -(2**63)]
    items = []
    for k in (1, 4, 65, 100, 1000, 2**31, 2**62, 2**63 - 1):
        notes = [(xs[i % len(xs)] if i % 3 else (i * 37) % 512, t)
                 for i, (_, t) in enumerate(stream(60))]
        items.append((mania_text(notes, keys=k), k))
    items.append((mania_text([(x, 1000 + i * 10) for i, x in enumerate(xs * 3)]), 2**63 - 1))
    check(native, items)


def test_neumaier_sums_and_window_edges(native):
    """Python 3.12+ sum() is compensated; a plain sum differs by an ulp or so, which
    the two-decimal outputs almost never show (20,000 random charts showed none), so
    the summation itself is pinned bit-for-bit by the crate's cargo tests."""
    rnd = random.Random(3)
    items = []
    for _ in range(40):
        t, notes = 1000, []
        for _ in range(rnd.randint(8, 300)):
            t += rnd.choice([0, 1, 7, 19, 20, 21, 33, 125, 250, 251, 999, 1000, 1001, 3000])
            for _ in range(rnd.randint(1, 3)):
                notes.append((rnd.randrange(512), t))
        k = rnd.choice([4, 7, 10])
        items.append((mania_text(notes, keys=k), k))
    # windows that start exactly on a row and rows exactly on a window end
    items.append((mania_text([(64, 1000 + i * 250) for i in range(30)]), 4))
    items.append((mania_text([(64 + (i % 4) * 128, i * 1000) for i in range(30)]), 4))
    items.append((mania_text([(64, 0)] * 10 + [(192, 7_200_000)] * 10), 4))
    check(native, items)


def test_hostile_values(native):
    big = "9" * 30
    items = [
        (osu("[General]", f"Mode: {big}", "Mode: 3"), None),
        (osu("[General]", "Mode: 3", f"Mode: {big}"), None),
        (osu("[General]", "Mode: 9223372036854775807"), None),
        (osu("[General]", "Mode: -9223372036854775809"), None),
        (osu("[HitObjects]", f"1,1,{big}", "1,1,7000"), None),
    ]
    for cs in ("inf", "-inf", "1e400", "nan", "1e300", "-1e300", "4.5", "5.5", "0"):
        items.append((mania_text(stream(30), extra=(f"OverallDifficulty:{cs}",)), 4))
        items.append((osu("[General]", "Mode: 3", "[Difficulty]", f"CircleSize:{cs}"), None))
    hostile = ["1e400,192,1500,1", "64,192,1e400,1", "64,192,1500,1e400",
               f"64,192,1500,{big}", f"{big},192,1500,1", "64,192,-1,1", "64,192,7200001,1",
               "64,192,7200000,1", "nan,192,1500,1", "64,192,1500,128,0,1e400:0:0:0:0:",
               "64,192,1500,128,0,nan:0", "64,192,1500,128", f"64,192,{big},1"]
    for h in hostile:
        items.append((mania_text([*stream(30), h]), 4))
    check(native, items)


# --- the Python wiring ----------------------------------------------------------------

def _write_sets(tmp_path, count, seed=21):
    tones = gen._tones(random.Random(seed), 2)
    paths = []
    for index in range(count):
        name, data = gen.make_set(seed, index, 200000 + index, tones)
        p = tmp_path / name
        p.write_bytes(data)
        paths.append(p)
    return paths


def _read_both(monkeypatch, path):
    monkeypatch.setattr(beatmap, "_parse_batch", None)
    py = beatmap.read_osz_full(path)
    py_msd = msd.msd_for_diffs(py[1], py[2])
    monkeypatch.undo()
    nat = beatmap.read_osz_full(path)
    return py, py_msd, nat, msd.msd_for_diffs(nat[1], nat[2])


def test_read_osz_full_and_msd_for_diffs_match(native, tmp_path, monkeypatch):
    assert beatmap._parse_batch is native.parse_batch
    rated = 0
    for path in _write_sets(tmp_path, 40):
        py, py_msd, nat, nat_msd = _read_both(monkeypatch, path)
        assert nat == py
        assert nat_msd == py_msd
        rated += len(nat_msd)
    assert rated > 5


@pytest.mark.filterwarnings("ignore:Duplicate name")
def test_read_osz_full_with_hostile_members(native, tmp_path, monkeypatch):
    osz = tmp_path / "h.osz"
    with zipfile.ZipFile(osz, "w") as zf:
        zf.writestr("b [inf].osu", mania_text(stream(30), extra=("OverallDifficulty:inf",)))
        zf.writestr("a [cs].osu", osu("[General]", "Mode: 3", "[Metadata]", "Title:T",
                                      "[Difficulty]", "CircleSize:1e300"))
        zf.writestr("c [garbage].osu", b"\xff\x00garbage")
        zf.writestr("c [garbage].osu", mania_text(stream(40)))   # a duplicate member name
    py, py_msd, nat, nat_msd = _read_both(monkeypatch, osz)
    assert nat == py and nat_msd == py_msd
    assert len(nat[1]) == 4 and nat[0].title == "T"


def test_boundary_too_many_items(native):
    with pytest.raises(ValueError, match="65536"):
        native.parse_batch([("x.osu", b"", None)] * 65537)
    assert len(native.parse_batch([("x.osu", b"", None)] * 65536)) == 65536


def test_boundary_item_over_16_mib(native):
    with pytest.raises(ValueError, match=r"big\.osu.*16777216"):
        native.parse_batch([("ok.osu", b"", None), ("big.osu", b" " * (MAX_BYTES + 1), None)])
    assert native.parse_batch([("ok.osu", b" " * MAX_BYTES, 4)])[0]["msd"] is None


def test_boundary_wrong_types(native):
    for bad in [("x.osu", "text", None), (1, b"", None), ("x.osu", b"", "4")]:
        with pytest.raises(TypeError):
            native.parse_batch([bad])
    with pytest.raises(TypeError):
        native.parse_batch((("x.osu", b"", None),))


def test_boundary_error_falls_back_to_python(native, tmp_path, monkeypatch):
    """A ValueError or OverflowError from parse_batch uses the Python loop for that set,
    never the outer 'bad zip' empties."""
    path = _write_sets(tmp_path, 12, seed=4)
    monkeypatch.setattr(beatmap, "_parse_batch", None)
    want = [beatmap.read_osz_full(p) for p in path]
    want_msd = [msd.msd_for_diffs(w[1], w[2]) for w in want]
    for exc in (ValueError, OverflowError):
        def refuse(items, exc=exc):
            raise exc("refused")
        monkeypatch.setattr(beatmap, "_parse_batch", refuse)
        got = [beatmap.read_osz_full(p) for p in path]
        assert got == want
        assert [msd.msd_for_diffs(g[1], g[2]) for g in got] == want_msd
    assert any(want_msd)


def test_key_count_beyond_64_bits_falls_back(native, monkeypatch):
    """The module raises OverflowError for a key count it can't take; msd_for_diffs
    then rates that set in Python."""
    raw = mania_text(stream(40))
    diffs = [DiffMeta(filename="m.osu", mode_int=3, keycount=2**70)]
    with pytest.raises(OverflowError):
        native.parse_batch([("m.osu", raw, 2**70)])
    got = msd.msd_for_diffs(diffs, {"m.osu": raw})
    monkeypatch.setattr(beatmap, "_parse_batch", None)
    assert got == msd.msd_for_diffs(diffs, {"m.osu": raw})


def test_package_imports_without_the_module():
    """Always runs: with the module blocked, rosu still imports and uses Python."""
    code = ("import sys\n"
            "sys.modules['rosu_native_osu_core'] = None\n"
            "from rosu import beatmap, msd\n"
            "from rosu.models import DiffMeta\n"
            "assert beatmap._parse_batch is None\n"
            "raw = b'[General]\\nMode: 3\\n[HitObjects]\\n' + b''.join(\n"
            "    b'%d,192,%d,1\\n' % (64 + (i % 4) * 128, 1000 + i * 125) for i in range(40))\n"
            "d = beatmap.read_osu_diff(raw, 'm.osu')\n"
            "assert msd.msd_for_diffs([DiffMeta('m.osu', mode_int=3, keycount=4)], {'m.osu': raw})\n")
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True, timeout=60)
