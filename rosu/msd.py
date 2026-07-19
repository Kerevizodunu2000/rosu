# SPDX-License-Identifier: GPL-3.0-or-later
"""Rosu Skillset Rating — an in-house, pure-Python mania skillset heuristic (v1.6).

osu!mania compresses a chart's difficulty into a single opaque star. Players think
in *skillsets* instead — the vocabulary Etterna popularised: can you stream, hit
jumpstream/handstream, sustain jacks, grind stamina, read technical patterns? This
module reads a mania chart's note rows and estimates eight numbers — an ``overall``
plus Etterna's seven skillset names — on a rough 0–10+ scale loosely comparable to
osu! stars.

This is a **heuristic, not an Etterna MSD port** (hence the "Rosu Skillset Rating"
label in the UI and the ``source`` tag on every result). It is deliberately
swappable: a closer algorithm can replace :func:`skillset` later and only the
stored numbers change — no schema migration, because the ``difficulties`` table
already carries an ``msd_source`` column.

Pure and I/O-free: it takes an already-parsed note list (see
:func:`rosu.beatmap.read_mania_notes`) so it stays trivially unit-testable on
synthetic patterns. Never raises; returns ``None`` when there aren't enough notes.

The algorithm, in one paragraph: notes are grouped into *rows* by timestamp; each
row-to-row transition is classified by what the hand does — a single note that
*moves* column is stream, a moving 2-note chord is jumpstream, 3+ is handstream, a
note repeated in the *same* column is a jack, a chord repeated on the same columns
is a chordjack — and each transition contributes its local note-rate to that skill.
Per skill we take a high percentile of the sliding-window intensities (the
"sustained peak", robust to a lone spike); stamina rewards sustained density over
duration; technical rewards irregular spacing. All the magic numbers live in the
one tunable block below and are expected to be calibrated against real charts.
"""
from __future__ import annotations

import math

from .models import MsdResult

# --- tunables (calibrated by eye; adjust against real charts) ----------------
_WIN_MS = 1000.0          # sliding-window width
_STEP_MS = 250.0          # window hop
_MIN_DT_MS = 20.0         # floor on row spacing (caps ~50 rows/s so a 0 ms glitch
                          # can never explode a score)
_PCTL = 0.93              # "sustained peak": high percentile of window intensities
_MIN_ROWS = 8             # too few rows → not enough signal, return None

# Per-skill scale factors turning a rows/sec intensity into a star-like number.
# Jacks/chords are harder per row than streams, so they carry more weight.
_K_STREAM = 0.42
_K_JS = 0.46
_K_HS = 0.55
_K_JACK = 0.54
_K_CJACK = 0.60
_K_TECH = 0.44
_K_STAM = 0.42

_SOURCE = "rosu-heuristic-v1"


def _rows(notes: list[tuple[int, int, int | None]]) -> list[tuple[int, frozenset]]:
    """Group note *heads* into rows keyed by identical timestamp."""
    by_time: dict[int, set] = {}
    for t, col, _end in notes:
        by_time.setdefault(t, set()).add(col)
    return [(t, frozenset(cols)) for t, cols in sorted(by_time.items())]


def _percentile(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(pos)
    frac = pos - lo
    if lo + 1 < len(s):
        return s[lo] * (1.0 - frac) + s[lo + 1] * frac
    return s[lo]


def _score_window(win: list[tuple[int, frozenset]]) -> tuple:
    """One window → (stream, js, hs, jack, chordjack, tech, nps) intensities.

    Each transition contributes its instantaneous row-rate to exactly one hand
    skill (stream/js/hs when the hand moves, jack/chordjack when it repeats a
    column); the skill value is the mean contributed rate across the window.
    """
    nrows = len(win)
    if nrows < 2:
        return (0.0,) * 7
    stream = js = hs = jack = cj = 0.0
    notes = 0
    intervals: list[float] = []
    for k in range(1, nrows):
        prev, cur = win[k - 1][1], win[k][1]
        dt = max(float(win[k][0] - win[k - 1][0]), _MIN_DT_MS)
        intervals.append(dt)
        rate = 1000.0 / dt
        size = len(cur)
        notes += size
        if prev & cur:                 # shares a column with the previous row → jack
            if size == 1:
                jack += rate
            else:
                cj += rate
        elif size == 1:
            stream += rate
        elif size == 2:
            js += rate
        else:
            hs += rate
    notes += len(win[0][1])            # first row's notes (loop starts at k=1)
    trans = nrows - 1
    stream /= trans
    js /= trans
    hs /= trans
    jack /= trans
    cj /= trans
    nps = notes / (_WIN_MS / 1000.0)
    mean = sum(intervals) / len(intervals)
    var = sum((x - mean) ** 2 for x in intervals) / len(intervals)
    cv = (var ** 0.5) / mean if mean else 0.0
    tech = nps * min(cv, 1.5) / 1.5
    return (stream, js, hs, jack, cj, tech, nps)


def skillset(notes: list[tuple[int, int, int | None]],
             keycount: int) -> MsdResult | None:
    """Estimate a mania difficulty's skillset ratings from its note rows.

    ``notes`` is ``[(time_ms, column, end_time|None), ...]`` (from
    :func:`rosu.beatmap.read_mania_notes`); ``keycount`` is the chart's key count.
    Returns a :class:`~.models.MsdResult`, or ``None`` when there is too little to
    rate (fewer than a handful of rows, or zero duration). Never raises.
    """
    if not notes or not keycount or keycount < 1:
        return None
    rows = _rows(notes)
    if len(rows) < _MIN_ROWS:
        return None
    first, last = rows[0][0], rows[-1][0]
    duration_s = (last - first) / 1000.0
    if duration_s <= 0:
        return None

    cols = [[] for _ in range(7)]      # stream, js, hs, jack, cj, tech, nps
    n = len(rows)
    start = float(first)
    i0 = 0
    while start < last:
        end = start + _WIN_MS
        while i0 < n and rows[i0][0] < start:
            i0 += 1
        j = i0
        win = []
        while j < n and rows[j][0] < end:
            win.append(rows[j])
            j += 1
        scores = _score_window(win) if len(win) >= 2 else (0.0,) * 7
        for c, v in zip(cols, scores):
            c.append(v)
        start += _STEP_MS

    stream = _percentile(cols[0], _PCTL) * _K_STREAM
    js = _percentile(cols[1], _PCTL) * _K_JS
    hs = _percentile(cols[2], _PCTL) * _K_HS
    jack = _percentile(cols[3], _PCTL) * _K_JACK
    cj = _percentile(cols[4], _PCTL) * _K_CJACK
    tech = _percentile(cols[5], _PCTL) * _K_TECH
    # Stamina = how consistently the map holds near its peak pattern intensity,
    # rewarded for lasting a long time. It is built from the same rows/sec pattern
    # scale (the per-window *peak* pattern intensity), NOT raw note density — so a
    # dense chordjack doesn't masquerade as stamina — and its length bonus only
    # exceeds 1.0 on genuinely long files, so a short stream stays stream-dominant
    # while a 3-minute grind can legitimately become stamina-dominant.
    peak_per_win = [max(cols[0][w], cols[1][w], cols[2][w], cols[3][w], cols[4][w])
                    for w in range(len(cols[0]))]
    stamina_base = _percentile(peak_per_win, 0.60)
    length_factor = 0.75 + 0.30 * math.log2(1.0 + duration_s / 25.0)
    stamina = stamina_base * _K_STAM * length_factor

    skills = [stream, js, hs, stamina, jack, cj, tech]
    overall = 0.6 * max(skills) + 0.4 * (sum(skills) / len(skills))

    def r(v: float) -> float:
        return round(max(0.0, v), 2)

    return MsdResult(
        overall=r(overall), stream=r(stream), jumpstream=r(js), handstream=r(hs),
        stamina=r(stamina), jackspeed=r(jack), chordjack=r(cj), technical=r(tech),
        source=_SOURCE)


def msd_for_diffs(diffs: list, raw_by_name: dict) -> dict:
    """Map each **mania** diff's ``filename`` → its :class:`~.models.MsdResult`.

    Non-mania diffs, and mania diffs with too little data, are simply absent from
    the result (never keyed to ``None``) so a caller writes only real ratings.
    Mirrors :func:`rosu.ratings.stars_for_diffs` and is shared by the ingest hooks
    and the whole-library ``compute_msd`` scan. Reads note rows from the raw ``.osu``
    bytes already in hand (via :func:`rosu.beatmap.read_mania_notes`) — no disk I/O.
    """
    from .beatmap import read_mania_notes
    out: dict = {}
    for d in diffs:
        if getattr(d, "mode_int", None) != 3 or not getattr(d, "keycount", None):
            continue
        raw = raw_by_name.get(d.filename)
        if raw is None:
            continue
        res = skillset(read_mania_notes(raw, d.keycount), d.keycount)
        if res is not None:
            out[d.filename] = res
    return out
