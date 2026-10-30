// SPDX-License-Identifier: GPL-3.0-or-later
//! The port of `rosu/msd.py`'s `skillset`: same algorithm, tunables, guards and
//! float operations in the same order (Python's `sum()` is Neumaier summation).

use crate::pysem::{py_max, py_round, py_sum};

const WIN_MS: f64 = 1000.0; // _WIN_MS
const STEP_MS: f64 = 250.0; // _STEP_MS
const MIN_DT_MS: f64 = 20.0; // _MIN_DT_MS
const PCTL: f64 = 0.93; // _PCTL
const MIN_ROWS: usize = 8; // _MIN_ROWS
const MAX_WINDOWS: f64 = 200_000.0; // _MAX_WINDOWS
const K_STREAM: f64 = 0.42; // _K_STREAM
const K_JS: f64 = 0.46; // _K_JS
const K_HS: f64 = 0.55; // _K_HS
const K_JACK: f64 = 0.54; // _K_JACK
const K_CJACK: f64 = 0.60; // _K_CJACK
const K_TECH: f64 = 0.44; // _K_TECH
const K_STAM: f64 = 0.42; // _K_STAM

/// One row: a timestamp and its distinct columns (sorted), as `_rows` builds them.
struct Row<'a> {
    time: i64,
    cols: &'a [i64],
}

/// True when two sorted column lists share a column (`prev & cur`).
fn shares_column(a: &[i64], b: &[i64]) -> bool {
    let (mut i, mut j) = (a.iter().peekable(), b.iter().peekable());
    while let (Some(&&x), Some(&&y)) = (i.peek(), j.peek()) {
        if x == y {
            return true;
        }
        if x < y {
            i.next();
        } else {
            j.next();
        }
    }
    false
}

/// `_percentile`: linear interpolation on the sorted values.
fn percentile(vals: &[f64], q: f64) -> f64 {
    let mut s = vals.to_vec();
    // Stable and NaN-free like `sorted()`; the values are never NaN.
    s.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    match s.len() {
        0 => 0.0,
        1 => s.first().copied().unwrap_or(0.0),
        n => {
            let pos = q * (n - 1) as f64;
            let lo = pos as usize; // int(pos): pos >= 0
            let frac = pos - lo as f64;
            match (s.get(lo), s.get(lo.saturating_add(1))) {
                (Some(&a), Some(&b)) => a * (1.0 - frac) + b * frac,
                (Some(&a), None) => a,
                _ => 0.0,
            }
        }
    }
}

/// `_score_window`: (stream, js, hs, jack, chordjack, tech, nps) for >= 2 rows.
fn score_window(win: &[Row]) -> [f64; 7] {
    let nrows = win.len();
    if nrows < 2 {
        return [0.0; 7];
    }
    let (mut stream, mut js, mut hs, mut jack, mut cj) = (0.0, 0.0, 0.0, 0.0, 0.0);
    let mut notes: usize = 0;
    let mut intervals: Vec<f64> = Vec::with_capacity(nrows);
    for pair in win.windows(2) {
        let [prev, cur] = pair else { continue };
        let dt = py_max([cur.time.saturating_sub(prev.time) as f64, MIN_DT_MS]);
        intervals.push(dt);
        let rate = 1000.0 / dt;
        let size = cur.cols.len();
        notes = notes.saturating_add(size);
        if shares_column(prev.cols, cur.cols) {
            // shares a column with the previous row → jack
            if size == 1 {
                jack += rate;
            } else {
                cj += rate;
            }
        } else if size == 1 {
            stream += rate;
        } else if size == 2 {
            js += rate;
        } else {
            hs += rate;
        }
    }
    notes = notes.saturating_add(win.first().map_or(0, |r| r.cols.len()));
    let trans = (nrows - 1) as f64;
    stream /= trans;
    js /= trans;
    hs /= trans;
    jack /= trans;
    cj /= trans;
    let nps = notes as f64 / (WIN_MS / 1000.0);
    let count = intervals.len() as f64;
    let mean = py_sum(intervals.iter().copied()) / count;
    let var = py_sum(intervals.iter().map(|x| (x - mean).powf(2.0))) / count;
    let cv = if mean != 0.0 {
        var.powf(0.5) / mean
    } else {
        0.0
    };
    let capped = if 1.5 < cv { 1.5 } else { cv }; // min(cv, 1.5)
    let tech = nps * capped / 1.5;
    [stream, js, hs, jack, cj, tech, nps]
}

/// `skillset(notes, keycount)` → the eight values in `MsdResult` field order
/// (overall, stream, jumpstream, handstream, stamina, jackspeed, chordjack,
/// technical), or `None` where Python returns `None`. `notes` are (time, column)
/// heads with times inside `0..=MAX_NOTE_TIME_MS`, so every time is exact as a float.
pub fn skillset(mut notes: Vec<(i64, i64)>, keycount: i64) -> Option<[f64; 8]> {
    if notes.is_empty() || keycount < 1 {
        return None;
    }
    // _rows: group heads by timestamp into sets of columns.
    notes.sort_unstable();
    notes.dedup();
    let cols: Vec<i64> = notes.iter().map(|&(_, c)| c).collect();
    let mut rows: Vec<Row> = Vec::new();
    let mut start_idx = 0;
    for (i, pair) in notes.iter().enumerate() {
        let next_time = notes.get(i.saturating_add(1)).map(|&(t, _)| t);
        if next_time != Some(pair.0) {
            let end_idx = i.saturating_add(1);
            rows.push(Row {
                time: pair.0,
                cols: cols.get(start_idx..end_idx).unwrap_or(&[]),
            });
            start_idx = end_idx;
        }
    }
    if rows.len() < MIN_ROWS {
        return None;
    }
    let first = rows.first()?.time;
    let last = rows.last()?.time;
    let duration_s = last.saturating_sub(first) as f64 / 1000.0;
    if duration_s <= 0.0 {
        return None;
    }
    if last.saturating_sub(first) as f64 / STEP_MS > MAX_WINDOWS {
        return None; // implausibly long span → refuse (DoS guard)
    }

    let mut series: [Vec<f64>; 7] = Default::default(); // stream, js, hs, jack, cj, tech, nps
    let n = rows.len();
    let mut start = first as f64;
    let mut i0 = 0;
    while start < last as f64 {
        let end = start + WIN_MS;
        while rows.get(i0).is_some_and(|r| (r.time as f64) < start) {
            i0 += 1;
        }
        let mut j = i0;
        while rows.get(j).is_some_and(|r| (r.time as f64) < end) {
            j += 1;
        }
        let win = rows.get(i0..j.min(n)).unwrap_or(&[]);
        let scores = if win.len() >= 2 {
            score_window(win)
        } else {
            [0.0; 7]
        };
        for (s, v) in series.iter_mut().zip(scores) {
            s.push(v);
        }
        start += STEP_MS;
    }

    let [s_stream, s_js, s_hs, s_jack, s_cj, s_tech, _nps] = &series;
    let stream = percentile(s_stream, PCTL) * K_STREAM;
    let js = percentile(s_js, PCTL) * K_JS;
    let hs = percentile(s_hs, PCTL) * K_HS;
    let jack = percentile(s_jack, PCTL) * K_JACK;
    let cj = percentile(s_cj, PCTL) * K_CJACK;
    let tech = percentile(s_tech, PCTL) * K_TECH;
    let peak_per_win: Vec<f64> = (0..s_stream.len())
        .map(|w| {
            py_max(
                [s_stream, s_js, s_hs, s_jack, s_cj]
                    .iter()
                    .map(|s| s.get(w).copied().unwrap_or(0.0)),
            )
        })
        .collect();
    let stamina_base = percentile(&peak_per_win, 0.60);
    let length_factor = 0.75 + 0.30 * (1.0 + duration_s / 25.0).log2();
    let stamina = stamina_base * K_STAM * length_factor;

    let skills = [stream, js, hs, stamina, jack, cj, tech];
    let overall = 0.6 * py_max(skills) + 0.4 * (py_sum(skills) / skills.len() as f64);

    // round(max(0.0, v), 2)
    let r = |v: f64| py_round(if v > 0.0 { v } else { 0.0 }, 2);
    Some([
        r(overall),
        r(stream),
        r(js),
        r(hs),
        r(stamina),
        r(jack),
        r(cj),
        r(tech),
    ])
}

#[cfg(test)]
mod tests {
    use super::*;

    fn stream(n: i64, keys: i64) -> Vec<(i64, i64)> {
        (0..n).map(|i| (i * 125, i % keys)).collect()
    }

    #[test]
    fn too_little_to_rate() {
        assert_eq!(skillset(vec![], 4), None);
        assert_eq!(skillset(stream(7, 4), 4), None); // fewer than _MIN_ROWS rows
        assert_eq!(skillset(stream(64, 4), 0), None);
        assert_eq!(skillset((0..10).map(|c| (500, c)).collect(), 10), None); // zero duration
    }

    #[test]
    fn stream_scores_stream_highest() {
        let v = skillset(stream(64, 7), 7).unwrap();
        assert!(v[1] > v[5] && v[1] > v[6], "{v:?}");
        assert!(v[0] > 0.0);
    }

    #[test]
    fn jack_scores_jackspeed_highest() {
        let v = skillset((0..64).map(|i| (i * 125, 3)).collect(), 7).unwrap();
        assert!(v[5] > v[1] && v[5] > v[6], "{v:?}");
    }

    #[test]
    fn wide_keycounts_have_no_column_limit() {
        let wide: Vec<(i64, i64)> = (0..64).map(|i| (i * 125, 100 + i * 3)).collect();
        assert!(skillset(wide, 1000).is_some());
    }

    #[test]
    fn rows_group_and_dedup_columns() {
        let mut notes = stream(16, 4);
        notes.push((0, 0)); // duplicate head: same row, same column
        notes.push((0, 2));
        assert_eq!(
            skillset(notes.clone(), 4),
            skillset(notes.into_iter().rev().collect(), 4)
        );
    }

    #[test]
    fn shares_column_merges_sorted_lists() {
        assert!(shares_column(&[1, 3, 5], &[2, 5]));
        assert!(!shares_column(&[1, 3], &[2, 4]));
        assert!(!shares_column(&[], &[1]));
    }

    #[test]
    fn percentile_interpolates() {
        assert_eq!(percentile(&[], 0.5), 0.0);
        assert_eq!(percentile(&[3.0], 0.93), 3.0);
        assert_eq!(percentile(&[4.0, 0.0, 2.0], 0.5), 2.0);
        assert_eq!(
            percentile(&[0.0, 10.0], 0.93),
            0.0 * (1.0 - 0.93) + 10.0 * 0.93
        );
    }
}
