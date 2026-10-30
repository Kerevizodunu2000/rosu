// SPDX-License-Identifier: GPL-3.0-or-later
//! One `.osu` file: the port of `beatmap.parse_osu_sections` (restricted to the
//! fields Rosu uses) and of `beatmap.read_mania_notes` (time and column only: the
//! hold-note end never changes a rating), in a single pass over the lines.

use std::collections::HashMap;

use crate::msd;
use crate::pysem::{
    is_line_break, py_float, py_int, py_round, py_round_int, py_strip, true_div_1000, trunc_i64,
};

/// beatmap._MAX_NOTE_TIME_MS: a note outside 0..=2 h is hostile or broken (DoS guard).
pub const MAX_NOTE_TIME_MS: i64 = 2 * 60 * 60 * 1000;

/// The `[Metadata]` keys Rosu reads (TrackMeta fields plus the diff name).
const META_KEYS: [&str; 6] = ["Version", "Artist", "Title", "Creator", "Source", "Tags"];
/// The `[Difficulty]` keys Rosu reads.
const DIFF_KEYS: [&str; 4] = [
    "CircleSize",
    "ApproachRate",
    "OverallDifficulty",
    "HPDrainRate",
];

#[derive(Debug, Default, PartialEq)]
pub struct Parsed {
    pub meta: Vec<(&'static str, String)>,
    pub mode_int: Option<i64>,
    pub difficulty: Vec<(&'static str, f64)>,
    pub bpm: Option<f64>,
    pub length_seconds: Option<i64>,
    pub msd: Option<[f64; 8]>,
}

fn known(keys: &[&'static str], key: &str) -> Option<&'static str> {
    keys.iter().copied().find(|k| *k == key)
}

/// `_dominant_bpm`: the most common `round(b, 3)` (first seen wins a tie, as
/// `Counter.most_common(1)`), as `round(60000 / dominant, 1)`.
fn dominant_bpm(beat_lengths: &[f64]) -> Option<f64> {
    // Keys are rounded positive floats (never NaN or -0.0), so bit equality is float equality.
    let mut index: HashMap<u64, usize> = HashMap::new();
    let mut counts: Vec<(f64, usize)> = Vec::new();
    for &b in beat_lengths {
        let key = py_round(b, 3);
        match index.get(&key.to_bits()).and_then(|&i| counts.get_mut(i)) {
            Some(entry) => entry.1 = entry.1.saturating_add(1),
            None => {
                index.insert(key.to_bits(), counts.len());
                counts.push((key, 1));
            }
        }
    }
    let mut best: Option<(f64, usize)> = None;
    for &(key, n) in &counts {
        if best.is_none_or(|(_, m)| n > m) {
            best = Some((key, n));
        }
    }
    let (dominant, _) = best?;
    if dominant > 0.0 {
        Some(py_round(60000.0 / dominant, 1))
    } else {
        None
    }
}

/// `read_mania_notes`' column: `int(x * keycount / 512)` clamped to `0..keycount`.
/// The product is exact in i128 and the i128 → f64 cast rounds once, like Python's
/// int true division by a power of two.
fn column(x: i64, keycount: i64) -> i64 {
    const TWO_63: f64 = 9_223_372_036_854_775_808.0;
    let col = ((i128::from(x).saturating_mul(i128::from(keycount))) as f64 / 512.0).trunc();
    if col < 0.0 {
        0
    } else if col >= TWO_63 || (col as i64) >= keycount {
        keycount.saturating_sub(1)
    } else {
        col as i64
    }
}

/// Parse one `.osu` file. With `keycount`, also rate it as `skillset(read_mania_notes(
/// data, keycount), keycount)` would.
pub fn parse(data: &[u8], keycount: Option<i64>) -> Parsed {
    let text = String::from_utf8_lossy(data); // bytes.decode("utf-8", "replace")
    let notes_keycount = keycount.filter(|&k| k >= 1);
    let mut out = Parsed::default();
    let mut beat_lengths: Vec<f64> = Vec::new();
    let mut notes: Vec<(i64, i64)> = Vec::new();
    let mut last_time: i64 = 0;
    let mut section = "";
    for raw in text.split(is_line_break) {
        let line = py_strip(raw);
        if line.is_empty() {
            continue;
        }
        if let Some(name) = line.strip_prefix('[').and_then(|l| l.strip_suffix(']')) {
            section = name;
            continue;
        }
        match section {
            "General" => {
                if let Some(rest) = line.strip_prefix("Mode:")
                    && let Some(mode) = py_int(py_strip(rest))
                {
                    out.mode_int = Some(mode);
                }
            }
            "Metadata" => {
                if let Some((key, value)) = line.split_once(':') {
                    let (key, value) = (py_strip(key), py_strip(value));
                    if let Some(k) = known(&META_KEYS, key) {
                        // first non-empty value wins
                        if !value.is_empty() && !out.meta.iter().any(|(m, _)| *m == k) {
                            out.meta.push((k, value.to_owned()));
                        }
                    }
                }
            }
            "Difficulty" => {
                if let Some((key, value)) = line.split_once(':')
                    && let Some(k) = known(&DIFF_KEYS, py_strip(key))
                {
                    // A non-finite value is unparseable (inf, nan, 1e400); a later
                    // valid line overwrites.
                    if let Some(v) = py_float(py_strip(value)).filter(|v| v.is_finite()) {
                        match out.difficulty.iter_mut().find(|(d, _)| *d == k) {
                            Some(entry) => entry.1 = v,
                            None => out.difficulty.push((k, v)),
                        }
                    }
                }
            }
            "TimingPoints" => {
                if let Some(beat) = line.split(',').nth(1).and_then(py_float)
                    && beat > 0.0
                {
                    beat_lengths.push(beat); // uninherited (a real BPM point)
                }
            }
            "HitObjects" => {
                let mut parts = line.split(',');
                let (p0, _, p2, p3) = (parts.next(), parts.next(), parts.next(), parts.next());
                if let Some(t) = p2.and_then(py_int) {
                    last_time = last_time.max(t);
                }
                if let (Some(k), Some(p0), Some(p2), Some(p3)) = (notes_keycount, p0, p2, p3) {
                    let x = py_float(p0).and_then(trunc_i64);
                    let time = py_float(p2).and_then(trunc_i64);
                    if let (Some(x), Some(time), Some(_type)) = (x, time, py_int(p3))
                        && (0..=MAX_NOTE_TIME_MS).contains(&time)
                    {
                        notes.push((time, column(x, k)));
                    }
                }
            }
            _ => {}
        }
    }
    out.bpm = dominant_bpm(&beat_lengths);
    if last_time > 0 {
        out.length_seconds = py_round_int(true_div_1000(last_time));
    }
    if let Some(k) = keycount {
        out.msd = if k >= 1 {
            msd::skillset(notes, k)
        } else {
            None
        };
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mania(objects: &str) -> String {
        format!("[General]\nMode: 3\n[Difficulty]\nCircleSize:4\n[HitObjects]\n{objects}")
    }

    #[test]
    fn sections_and_fields() {
        let text = "osu file format v14\r\n[General]\r\nMode: 3\r\n[Metadata]\r\nTitle:\r\n\
                    Title: Song \r\nTitle:Later\r\nArtist:A:B\r\nTitleUnicode:x\r\n[Difficulty]\r\n\
                    CircleSize:7\r\nCircleSize:inf\r\nApproachRate:1e400\r\nHPDrainRate:nan\r\n\
                    OverallDifficulty:8\r\nOverallDifficulty:8.5\r\n[TimingPoints]\r\n0,300,4\r\n\
                    10,-100,4\r\n[HitObjects]\r\n64,192,1000,1\r\n64,192,2500,1\r\n";
        let p = parse(text.as_bytes(), None);
        assert_eq!(p.mode_int, Some(3));
        assert_eq!(
            p.meta,
            vec![("Title", "Song".to_owned()), ("Artist", "A:B".to_owned())]
        );
        assert_eq!(
            p.difficulty,
            vec![("CircleSize", 7.0), ("OverallDifficulty", 8.5)]
        );
        assert_eq!(p.bpm, Some(200.0));
        assert_eq!(p.length_seconds, Some(2)); // round(2.5) ties to even
        assert_eq!(p.msd, None);
    }

    #[test]
    fn every_line_break_splits() {
        for sep in [
            "\n", "\r", "\r\n", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\u{85}", "\u{2028}",
            "\u{2029}",
        ] {
            let text = ["[General]", "Mode: 1", "[Metadata]", "Version:V"].join(sep);
            let p = parse(text.as_bytes(), None);
            assert_eq!(p.mode_int, Some(1), "{sep:?}");
            assert_eq!(p.meta, vec![("Version", "V".to_owned())], "{sep:?}");
        }
        // \x1f is stripped but does not end a line.
        let p = parse(b"[General]\x1fMode: 1", None);
        assert_eq!(p.mode_int, None);
    }

    #[test]
    fn strip_then_int() {
        // strip() removes \x1c..\x1f around the value first, so Mode reads.
        assert_eq!(parse(b"[General]\nMode:\x1f2\x1f", None).mode_int, Some(2));
        // int() alone does not: a hit-object time "\x1f5" is rejected.
        assert_eq!(
            parse(b"[HitObjects]\n1,1,\x1f5000", None).length_seconds,
            None
        );
        assert_eq!(
            parse(b"[HitObjects]\n1,1, 5000 ", None).length_seconds,
            Some(5)
        );
    }

    #[test]
    fn decode_like_python_replace() {
        // Lone surrogate, truncated sequence and overlong form each become U+FFFD; a BOM stays.
        let p = parse(
            b"[Metadata]\nTitle:a\xed\xa0\x80b\xf0\x9f\x98c\xc0\x80\nArtist:\xef\xbb\xbfx",
            None,
        );
        assert_eq!(
            p.meta,
            vec![
                (
                    "Title",
                    "a\u{fffd}\u{fffd}\u{fffd}b\u{fffd}c\u{fffd}\u{fffd}".to_owned()
                ),
                ("Artist", "\u{feff}x".to_owned())
            ]
        );
        let p = parse(b"\xef\xbb\xbf[General]\nMode: 3", None);
        assert_eq!(p.mode_int, None); // the BOM keeps the header from matching
    }

    #[test]
    fn out_of_range_integers_are_malformed() {
        let thirty = "9".repeat(30);
        let p = parse(
            format!("[General]\nMode: {thirty}\n[HitObjects]\n1,1,{thirty}\n1,1,7000").as_bytes(),
            None,
        );
        assert_eq!(p.mode_int, None);
        assert_eq!(p.length_seconds, Some(7));
        let p = parse(format!("[HitObjects]\n1,1,{}", i64::MAX).as_bytes(), None);
        assert_eq!(p.length_seconds, Some(9_223_372_036_854_776));
    }

    #[test]
    fn dominant_bpm_first_seen_wins_tie() {
        let p = parse(b"[TimingPoints]\n0,500\n1,300\n2,300.0001\n3,500\n", None);
        assert_eq!(p.bpm, Some(120.0)); // 500 and 300 both seen twice; 500 came first
        let p = parse(b"[TimingPoints]\n0,1e-300\n", None);
        assert_eq!(p.bpm, None); // round(1e-300, 3) == 0.0
        let p = parse(b"[TimingPoints]\n0,inf\n", None);
        assert_eq!(p.bpm, Some(0.0));
    }

    #[test]
    fn columns_match_python() {
        assert_eq!(column(64, 4), 0);
        assert_eq!(column(448, 4), 3);
        assert_eq!(column(-5, 4), 0);
        assert_eq!(column(5000, 4), 3);
        assert_eq!(column(i64::MAX, i64::MAX), i64::MAX - 1);
        assert_eq!(column(i64::MIN, i64::MAX), 0);
        assert_eq!(column(100, 100), 19); // keycounts above 64 work
        assert_eq!(column(511, 1000), 998);
    }

    #[test]
    fn mania_notes_guards() {
        let mut rows = String::new();
        for i in 0..40 {
            rows.push_str(&format!(
                "{},192,{},1,0,0:0:0:0:\n",
                (i % 4) * 128 + 64,
                1000 + i * 100
            ));
        }
        let base = parse(mania(&rows).as_bytes(), Some(4)).msd;
        assert!(base.is_some());
        // Hostile lines are skipped: overflowing x/time, huge type, out-of-range time,
        // and an overflowing hold-note end keeps the note.
        let hostile = "1e400,192,1500,1\n64,192,1e400,1\n64,192,1500,99999999999999999999\n\
                       64,192,-1,1\n64,192,7200001,1\nnan,192,1500,1\n";
        let with = parse(mania(&format!("{rows}{hostile}")).as_bytes(), Some(4)).msd;
        assert_eq!(with, base);
        assert_eq!(parse(mania(&rows).as_bytes(), Some(0)).msd, None);
        assert_eq!(parse(mania(&rows).as_bytes(), Some(-3)).msd, None);
        assert!(parse(mania(&rows).as_bytes(), Some(200)).msd.is_some());
    }

    /// xorshift64*: a seeded generator for the no-panic loop (no extra crate).
    struct Rng(u64);
    impl Rng {
        fn next(&mut self) -> u64 {
            self.0 ^= self.0 >> 12;
            self.0 ^= self.0 << 25;
            self.0 ^= self.0 >> 27;
            self.0.wrapping_mul(0x2545_f491_4f6c_dd1d)
        }
    }

    #[test]
    fn random_bytes_never_panic() {
        let mut rng = Rng(0x5eed_1234_abcd_ef01);
        let alphabet = b"[]:,.-+_0123456789eEinfaINFA \r\n\x0b\x1c\xc2\x85\xe2\x80\xa8\xff";
        let headers = [
            "[General]\n",
            "[Difficulty]\n",
            "[TimingPoints]\n",
            "[HitObjects]\n",
            "Mode:3\n",
        ];
        for round in 0..3000 {
            let len = (rng.next() % 2048) as usize;
            let mut data = Vec::with_capacity(len);
            while data.len() < len {
                let r = rng.next();
                match r % 8 {
                    0 => data
                        .extend_from_slice(headers[(r >> 8) as usize % headers.len()].as_bytes()),
                    1 | 2 => data.push((r >> 8) as u8),
                    _ => data.push(alphabet[(r >> 8) as usize % alphabet.len()]),
                }
            }
            let k = [
                None,
                Some(0),
                Some(1),
                Some(4),
                Some(7),
                Some(i64::MAX),
                Some(i64::MIN),
            ][round % 7];
            let _ = parse(&data, k);
        }
    }
}
