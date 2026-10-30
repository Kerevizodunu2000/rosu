// SPDX-License-Identifier: GPL-3.0-or-later
//! Python's text and number rules, reproduced exactly so the native parser gives
//! the same answers as `rosu/beatmap.py` and `rosu/msd.py`.

use std::borrow::Cow;

/// `str.splitlines()` line boundaries.
pub fn is_line_break(c: char) -> bool {
    matches!(
        c,
        '\n' | '\r'
            | '\x0b'
            | '\x0c'
            | '\x1c'
            | '\x1d'
            | '\x1e'
            | '\u{85}'
            | '\u{2028}'
            | '\u{2029}'
    )
}

/// `str.isspace()`, which `str.strip()` removes: Unicode White_Space plus `\x1c`..`\x1f`.
pub fn is_py_space(c: char) -> bool {
    matches!(
        c,
        '\t'..='\r'
            | '\x1c'..='\x1f'
            | ' '
            | '\u{85}'
            | '\u{a0}'
            | '\u{1680}'
            | '\u{2000}'..='\u{200a}'
            | '\u{2028}'
            | '\u{2029}'
            | '\u{202f}'
            | '\u{205f}'
            | '\u{3000}'
    )
}

/// `str.strip()`.
pub fn py_strip(s: &str) -> &str {
    s.trim_matches(is_py_space)
}

/// The C-locale `isspace` that `int()` and `float()` strip after mapping non-ASCII
/// whitespace to `' '`. ASCII `\x1c`..`\x1f` are not in it, so `int("\x1c5")` fails.
fn is_c_space(c: char) -> bool {
    matches!(c, '\t'..='\r' | ' ')
}

/// First code point of every run of ten Unicode decimal digits (category Nd), as in
/// Python 3.14's `unicodedata` (Unicode 16.0), the Python the release exe ships.
/// Python 3.13 (Unicode 15.1) lacks 0x10d40, 0x116d0, 0x116da, 0x11bf0, 0x16130,
/// 0x16d70, 0x1ccf0 and 0x1e5f1.
const DIGIT_ZEROS: [u32; 76] = [
    0x30, 0x660, 0x6f0, 0x7c0, 0x966, 0x9e6, 0xa66, 0xae6, 0xb66, 0xbe6, 0xc66, 0xce6, 0xd66,
    0xde6, 0xe50, 0xed0, 0xf20, 0x1040, 0x1090, 0x17e0, 0x1810, 0x1946, 0x19d0, 0x1a80, 0x1a90,
    0x1b50, 0x1bb0, 0x1c40, 0x1c50, 0xa620, 0xa8d0, 0xa900, 0xa9d0, 0xa9f0, 0xaa50, 0xabf0, 0xff10,
    0x104a0, 0x10d30, 0x10d40, 0x11066, 0x110f0, 0x11136, 0x111d0, 0x112f0, 0x11450, 0x114d0,
    0x11650, 0x116c0, 0x116d0, 0x116da, 0x11730, 0x118e0, 0x11950, 0x11bf0, 0x11c50, 0x11d50,
    0x11da0, 0x11f50, 0x16130, 0x16a60, 0x16ac0, 0x16b50, 0x16d70, 0x1ccf0, 0x1d7ce, 0x1d7d8,
    0x1d7e2, 0x1d7ec, 0x1d7f6, 0x1e140, 0x1e2f0, 0x1e4f0, 0x1e5f1, 0x1e950, 0x1fbf0,
];

/// The ASCII digit for a Unicode decimal digit.
fn decimal_digit(c: char) -> Option<char> {
    let cp = u32::from(c);
    let i = DIGIT_ZEROS.partition_point(|&z| z <= cp).checked_sub(1)?;
    let offset = cp.checked_sub(*DIGIT_ZEROS.get(i)?)?;
    if offset < 10 {
        char::from_digit(offset, 10)
    } else {
        None
    }
}

/// What `int()` and `float()` parse: non-ASCII digits and whitespace mapped to ASCII
/// (any other non-ASCII character makes the string invalid), C-space stripped, and
/// underscores removed when each one sits between two digits.
fn numeric_ascii(s: &str) -> Option<Cow<'_, str>> {
    if s.is_ascii() {
        let t = s.trim_matches(is_c_space);
        if !t.contains('_') {
            return Some(Cow::Borrowed(t));
        }
        return drop_underscores(t).map(Cow::Owned);
    }
    let mut mapped = String::with_capacity(s.len());
    for c in s.chars() {
        if c.is_ascii() {
            mapped.push(c);
        } else if is_py_space(c) {
            mapped.push(' ');
        } else {
            mapped.push(decimal_digit(c)?);
        }
    }
    drop_underscores(mapped.trim_matches(is_c_space)).map(Cow::Owned)
}

fn drop_underscores(t: &str) -> Option<String> {
    let b = t.as_bytes();
    let mut out = String::with_capacity(t.len());
    for (i, &c) in b.iter().enumerate() {
        if c == b'_' {
            let before = i
                .checked_sub(1)
                .and_then(|j| b.get(j))
                .is_some_and(u8::is_ascii_digit);
            let after = b.get(i.saturating_add(1)).is_some_and(u8::is_ascii_digit);
            if !(before && after) {
                return None;
            }
        } else {
            out.push(char::from(c));
        }
    }
    Some(out)
}

/// `int(s)` when it is a signed 64-bit value; `None` where Python raises
/// `ValueError` (including the 4300-digit limit, leading zeros counted) or the value
/// is outside the 64-bit range (Rosu treats that as malformed).
pub fn py_int(s: &str) -> Option<i64> {
    const MAX_STR_DIGITS: usize = 4300; // sys.get_int_max_str_digits() default
    let t = numeric_ascii(s)?;
    let b = t.as_bytes();
    let (negative, digits) = match b.split_first() {
        Some((b'-', rest)) => (true, rest),
        Some((b'+', rest)) => (false, rest),
        _ => (false, b),
    };
    if digits.is_empty() || digits.len() > MAX_STR_DIGITS {
        return None;
    }
    let mut value: i128 = 0;
    for &d in digits {
        if !d.is_ascii_digit() {
            return None;
        }
        // Saturates far above the i64 range, so an overlong value stays out of range.
        value = value
            .saturating_mul(10)
            .saturating_add(i128::from(d - b'0'));
    }
    i64::try_from(if negative { -value } else { value }).ok()
}

/// `float(s)`, or `None` where Python raises `ValueError`. Python and Rust accept the
/// same ASCII grammar (sign, digits, point, exponent, `inf`/`infinity`/`nan` in any
/// case); the underscores and Unicode are handled by [`numeric_ascii`].
pub fn py_float(s: &str) -> Option<f64> {
    numeric_ascii(s)?.parse::<f64>().ok()
}

/// `int(x)` for a float (truncation toward zero), when finite and inside the signed
/// 64-bit range.
pub fn trunc_i64(x: f64) -> Option<i64> {
    const TWO_63: f64 = 9_223_372_036_854_775_808.0;
    let t = x.trunc();
    if (-TWO_63..TWO_63).contains(&t) {
        Some(t as i64)
    } else {
        None
    }
}

/// `round(x)` for a float (ties to even), when finite and inside the signed 64-bit range.
pub fn py_round_int(x: f64) -> Option<i64> {
    trunc_i64(x.round_ties_even())
}

/// `round(x, ndigits)` for a float: the exact decimal value rounded half to even at
/// `ndigits` places, read back as the nearest float (CPython's dtoa path). Rust's
/// fixed-precision formatting is exact and rounds ties to even.
pub fn py_round(x: f64, ndigits: usize) -> f64 {
    if !x.is_finite() {
        return x; // nans and infinities round to themselves
    }
    format!("{x:.ndigits$}").parse().unwrap_or(x)
}

/// `t / 1000` for an int, correctly rounded like Python's int true division for
/// every 64-bit `t` (an `i64` → `f64` cast would round once too often above 2^53).
pub fn true_div_1000(t: i64) -> f64 {
    let (q, r) = (t / 1000, (t % 1000).unsigned_abs());
    let sign = if t < 0 { "-" } else { "" };
    format!("{sign}{}.{r:03}", q.unsigned_abs())
        .parse()
        .unwrap_or(f64::NAN)
}

/// `sum()` of floats as Python 3.12+ computes it: Neumaier compensated summation
/// starting from the first item, the compensation added at the end when finite.
pub fn py_sum(values: impl IntoIterator<Item = f64>) -> f64 {
    let mut it = values.into_iter();
    let Some(mut total) = it.next() else {
        return 0.0;
    };
    let mut c = 0.0;
    for x in it {
        let t = total + x;
        if total.abs() >= x.abs() {
            c += (total - t) + x;
        } else {
            c += (x - t) + total;
        }
        total = t;
    }
    if c != 0.0 && c.is_finite() {
        total += c;
    }
    total
}

/// `max(a, b, ...)` of floats: the first item no later item is greater than.
pub fn py_max(values: impl IntoIterator<Item = f64>) -> f64 {
    let mut it = values.into_iter();
    let mut best = it.next().unwrap_or(f64::NAN);
    for v in it {
        if v > best {
            best = v;
        }
    }
    best
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splitlines_and_strip_sets() {
        let text = "a\nb\rc\r\nd\x0be\x0cf\x1cg\x1dh\x1ei\u{85}j\u{2028}k\u{2029}l";
        let lines: Vec<&str> = text
            .split(is_line_break)
            .filter(|l| !l.is_empty())
            .collect();
        assert_eq!(
            lines,
            ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"]
        );
        assert!(!"a\x1fb".contains(is_line_break)); // \x1f strips but does not split
        assert_eq!(py_strip("\x1c\x1f \u{3000}x\u{a0}\x1d"), "x");
        assert_eq!(py_strip("\u{feff}x"), "\u{feff}x"); // a BOM is not whitespace
    }

    #[test]
    fn int_rules() {
        assert_eq!(py_int(" 5 "), Some(5));
        assert_eq!(py_int("+5"), Some(5));
        assert_eq!(py_int("-5"), Some(-5));
        assert_eq!(py_int("1_0"), Some(10));
        assert_eq!(py_int("0_5"), Some(5));
        for bad in [
            "1__0", "_1", "1_", "+_1", "", " ", "+", "1.0", "0x10", "\x1c5", "5\x1f", "1 2",
        ] {
            assert_eq!(py_int(bad), None, "{bad:?}");
        }
        assert_eq!(py_int("\u{662}"), Some(2)); // Arabic-Indic two
        assert_eq!(py_int("\u{ff15}"), Some(5)); // fullwidth five
        assert_eq!(py_int("\u{85}7\u{3000}"), Some(7));
        assert_eq!(py_int("\u{e9}"), None);
        assert_eq!(py_int("9223372036854775807"), Some(i64::MAX));
        assert_eq!(py_int("-9223372036854775808"), Some(i64::MIN));
        assert_eq!(py_int("9223372036854775808"), None);
        assert_eq!(py_int(&"9".repeat(30)), None);
        let ok = format!("{}5", "0".repeat(4299));
        let over = format!("{}5", "0".repeat(4300));
        assert_eq!(py_int(&ok), Some(5));
        assert_eq!(py_int(&over), None); // leading zeros count toward the limit
        assert_eq!(py_int(&format!("{}5", "0_".repeat(4300))), None);
    }

    #[test]
    fn float_rules() {
        assert_eq!(py_float(" 1_000.5 "), Some(1000.5));
        assert_eq!(py_float("1e1_0"), Some(1e10));
        assert_eq!(py_float("\u{661}.\u{665}"), Some(1.5));
        assert_eq!(py_float("1_\u{662}"), Some(12.0));
        assert_eq!(py_float("-Infinity"), Some(f64::NEG_INFINITY));
        assert_eq!(py_float("iNf"), Some(f64::INFINITY));
        assert!(py_float("+nan").is_some_and(f64::is_nan));
        assert_eq!(py_float("1e400"), Some(f64::INFINITY));
        assert_eq!(py_float("1."), Some(1.0));
        assert_eq!(py_float(".5"), Some(0.5));
        for bad in [
            "1_.5", "1._5", "1e_10", "in_f", "infinit", ".", "e5", "1e", "1e+", "0x10", "\x1c5",
            "nan(1)",
        ] {
            assert_eq!(py_float(bad), None, "{bad:?}");
        }
    }

    #[test]
    fn truncation_and_rounding() {
        assert_eq!(trunc_i64(-2.7), Some(-2));
        assert_eq!(trunc_i64(2.7), Some(2));
        assert_eq!(trunc_i64(f64::INFINITY), None);
        assert_eq!(trunc_i64(f64::NAN), None);
        assert_eq!(trunc_i64(1e30), None);
        assert_eq!(trunc_i64(-9_223_372_036_854_775_808.0), Some(i64::MIN));
        assert_eq!(trunc_i64(9_223_372_036_854_775_808.0), None);
        assert_eq!(py_round_int(2.5), Some(2));
        assert_eq!(py_round_int(3.5), Some(4));
        assert_eq!(py_round_int(-2.5), Some(-2));
        assert_eq!(py_round_int(1e300), None);
        assert_eq!(py_round(0.125, 2), 0.12);
        assert_eq!(py_round(0.375, 2), 0.38);
        assert_eq!(py_round(2.675, 2), 2.67); // 2.675 is just below the tie
        assert_eq!(py_round(1e-300, 3), 0.0);
        assert_eq!(py_round(f64::INFINITY, 3), f64::INFINITY);
        assert!(py_round(-1e-300, 3).is_sign_negative());
    }

    #[test]
    fn int_division_is_correctly_rounded() {
        // Casting first would round twice: these give ...043.0 and ...955.0.
        assert_eq!(
            true_div_1000(5_258_986_265_376_043_509),
            5_258_986_265_376_044.0
        );
        assert_eq!(
            true_div_1000(6_000_012_885_340_954_297),
            6_000_012_885_340_954.0
        );
        assert_eq!(
            py_round_int(true_div_1000(5_258_986_265_376_043_509)),
            Some(5_258_986_265_376_044)
        );
        assert_eq!(true_div_1000(i64::MAX), 9_223_372_036_854_776.0);
        assert_eq!(true_div_1000(i64::MIN), -9_223_372_036_854_776.0);
        assert_eq!(true_div_1000(2500), 2.5);
        assert_eq!(py_round_int(true_div_1000(2500)), Some(2));
        assert_eq!(py_round_int(true_div_1000(3500)), Some(4));
    }

    #[test]
    fn neumaier_sum_and_max() {
        assert_eq!(py_sum([0.1; 10]), 1.0); // naive summation gives 0.9999999999999999
        assert_eq!(py_sum([1e100, 1.0, -1e100]), 1.0);
        assert_eq!(py_sum([f64::INFINITY, 1.0]), f64::INFINITY);
        assert_eq!(py_sum(std::iter::empty()), 0.0);
        assert_eq!(py_max([1.0, 3.0, 2.0]), 3.0);
    }
}
