// SPDX-License-Identifier: GPL-3.0-or-later
//! `rosu_native_osu_core`: Rosu's native `.osu` parser and mania skillset rating.
//!
//! One entry point, `parse_batch(items)`, called by `rosu/beatmap.py` and
//! `rosu/msd.py` once per beatmap set. It mirrors `beatmap.parse_osu_sections`
//! (restricted to the fields Rosu reads) plus `msd.skillset`; the dataclasses and
//! the `source` tag stay in Python. The module needs no file, network or thread.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::pybacked::PyBackedBytes;
use pyo3::types::{PyDict, PyList, PyTuple};

mod msd;
mod parse;
mod pysem;

/// Most items one call takes: far above any real beatmap set.
const MAX_ITEMS: usize = 65_536;
/// Largest `.osu` accepted, the same as `beatmap._MAX_OSU_BYTES`.
const MAX_BYTES: usize = 16 * 1024 * 1024;

/// Parse a list of `(name: str, data: bytes, keycount: int | None)` items.
///
/// Returns one dict per item, in order, with the keys `meta`, `mode_int`,
/// `difficulty`, `bpm`, `length_seconds` and `msd` (the eight skillset values in
/// `MsdResult` field order, or `None`; always `None` when `keycount` is `None`).
/// Raises `ValueError` for more than 65,536 items or an item over 16 MiB.
#[pyfunction]
fn parse_batch<'py>(py: Python<'py>, items: &Bound<'py, PyList>) -> PyResult<Bound<'py, PyList>> {
    if items.len() > MAX_ITEMS {
        return Err(PyValueError::new_err(format!(
            "parse_batch takes at most {MAX_ITEMS} items, got {}",
            items.len()
        )));
    }
    let mut input: Vec<(PyBackedBytes, Option<i64>)> = Vec::with_capacity(items.len());
    for item in items.iter() {
        let (name, data, keycount): (String, PyBackedBytes, Option<i64>) = item.extract()?;
        if data.len() > MAX_BYTES {
            return Err(PyValueError::new_err(format!(
                "{name}: {} bytes is over the {MAX_BYTES}-byte limit for one .osu file",
                data.len()
            )));
        }
        input.push((data, keycount));
    }
    let parsed: Vec<parse::Parsed> = py.detach(|| {
        input
            .iter()
            .map(|(data, keycount)| parse::parse(data, *keycount))
            .collect()
    });
    let out = PyList::empty(py);
    for p in parsed {
        let d = PyDict::new(py);
        let meta = PyDict::new(py);
        for (k, v) in &p.meta {
            meta.set_item(k, v)?;
        }
        let difficulty = PyDict::new(py);
        for (k, v) in &p.difficulty {
            difficulty.set_item(k, v)?;
        }
        d.set_item("meta", meta)?;
        d.set_item("mode_int", p.mode_int)?;
        d.set_item("difficulty", difficulty)?;
        d.set_item("bpm", p.bpm)?;
        d.set_item("length_seconds", p.length_seconds)?;
        match p.msd {
            Some(values) => d.set_item("msd", PyTuple::new(py, values)?)?,
            None => d.set_item("msd", py.None())?,
        }
        out.append(d)?;
    }
    Ok(out)
}

#[pymodule]
fn rosu_native_osu_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_batch, m)?)
}
