---
name: rust
description: Use when deciding whether Rosu code should be written in Rust, when profiling a slow path, or when writing, building, testing or shipping a Rust (PyO3) module for Rosu. Covers the measure-then-Rust rule, the PyO3/maturin boundary, parity tests against the Python version, Windows wheels in CI and supply-chain checks.
---

<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Rust in Rosu

Rosu stays Python + PySide6. Rust is for hot paths only, as PyO3 extension
modules called from the Qt-free services (the way `rosu-pp-py` already is).
AGENTS.md has the binding rule; this skill is the how.

## 1. Decide: measure first

- Existing code moves to Rust only after a profile on a large library
  (100k sets) names it. Profile with `cProfile`/`pstats` or `py-spy`, record
  wall time and peak memory, and write the numbers into the PR.
- Try the cheap Python fixes first: a better algorithm, fewer filesystem
  calls, batching DB writes, `hashlib`/`zlib` (already C), moving work to a
  `Worker`. Port only what is still slow.
- Port a whole loop, not the body of a Python loop. Each Python→Rust call
  costs roughly a microsecond; a function called per file from Python gains
  little. Pass a list of paths or a buffer, get a list back.
- Good candidates: hashing and scanning many files, parsing large `.osu` or
  `.osr` batches, audio fingerprinting, Map Lab audio work, replay analysis,
  the streamer-mode engine. Poor candidates: UI, DB access (it goes through
  locked `Database` methods), network code (stdlib HTTP rule), glue.
- New features: decide at intake. If the core is heavy (large data, audio
  or image processing, a long-running engine), write that core in Rust from
  the start and keep its API small.

## 2. Layout

- One crate per module under `native/<name>/` (`Cargo.toml`, `src/lib.rs`,
  `pyproject.toml` with `build-backend = "maturin"`), importable as
  `rosu_native_<name>`.
- The Python side wraps it in `rosu/` with a pure-Python fallback, selected
  at import time:
  `try: from rosu_native_x import f` / `except ImportError: f = _py_f`.
  The app must run (slower) without the wheel, and the tests run both.
- Every source file starts with the SPDX line
  (`// SPDX-License-Identifier: GPL-3.0-or-later`); `Cargo.toml` says
  `license = "GPL-3.0-or-later"`.

## 3. The PyO3 boundary

Check the current PyO3 and maturin docs for exact names; the API changes
between releases (for example `allow_threads` became `Python::detach`).

- Build abi3 wheels (`pyo3` feature `abi3-py3XX` for the lowest Python Rosu
  supports) so one wheel serves 3.14 and later. Confirm the PyO3 release
  supports the Python version CI uses.
- Release the GIL around long work (`py.detach(|| ...)`), so the Qt UI and
  other workers keep running. Never touch Python objects inside it.
- Inputs: take plain types (`&str`, `Vec<String>`, `&[u8]`, `PathBuf`).
  Validate at the boundary: path length, sizes, counts.
- Errors: return `PyResult`; map each Rust error to a specific Python
  exception (`OSError` for I/O, `ValueError` for bad input) with the path in
  the message. No `unwrap()`/`expect()` on input-dependent values; a panic
  becomes `PanicException` and must never be the error path.
- Cancellation: long calls take a chunk size or return partial results so
  the service can check its cancel token between chunks.
- No network, no `unsafe` unless a dependency requires it and a comment
  says why, no global state, no threads that outlive the call (use `rayon`
  inside the call if parallelism pays).
- Same rules as Python: never delete files (return paths; the service sends
  them to the Recycle Bin), never write to osu!lazer's store.

## 4. Tests

- Rust unit tests: `cargo test` in the crate.
- Parity tests in `tests/` (pytest): the same inputs through the Python
  fallback and the Rust module must give identical results, including edge
  cases (empty input, unicode and long Windows paths, corrupt archives,
  huge files). Watch the semantic traps: integer width and overflow, `//`
  and `%` on negatives, `str` vs `bytes`, float formatting, sort stability.
- A benchmark in `tools/` records Python vs Rust timings on the same data;
  the PR quotes them. If Rust is not clearly faster, do not merge it.

## 5. Build and CI

- Local: `maturin develop --release` inside the crate.
- CI (`windows-latest`): install the Rust toolchain, build the wheel with
  `PyO3/maturin-action` (pin it to a commit SHA like every action), run
  `cargo test`, `cargo clippy -- -D warnings`, `cargo fmt --check`, then
  pytest with the wheel installed. PyInstaller must bundle the module
  (add it to `rosu.spec` hidden imports, as for `rosu_pp_py`).
- Supply chain: `Cargo.lock` committed; `cargo deny check` for licenses
  (GPL-3.0-compatible only), advisories and sources (crates.io only); add
  each crate to `THIRD-PARTY-LICENSES.md`. Few dependencies, well known
  ones. Dependabot covers `cargo`.
- Free tools only: rustup, cargo, maturin, GitHub-hosted runners.

## 6. Done checklist

- [ ] Profile numbers before and after, on the same 100k-set data
- [ ] Python fallback kept; parity tests pass on both
- [ ] GIL released for long work; errors mapped; no panics on bad input
- [ ] Windows wheel built in CI; PyInstaller bundles it; exe smoke test
- [ ] `cargo deny`, clippy and fmt clean; licenses listed
- [ ] CHANGELOG entry if users notice the speed-up
