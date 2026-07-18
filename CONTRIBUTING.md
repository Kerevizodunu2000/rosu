# Contributing to Rosu

Thanks for your interest in Rosu! Contributions, bug reports, and feature ideas
are welcome. By taking part you agree to follow our
[Code of Conduct](CODE_OF_CONDUCT.md). For security issues, please see
[SECURITY.md](SECURITY.md) instead of opening a public issue.

## Reporting bugs / requesting features

Open a [GitHub issue](https://github.com/Kerevizodunu2000/rosu/issues) with:

- what you expected versus what actually happened,
- your Windows version and how you launched Rosu (the portable `.exe`, or from source),
- the relevant lines from `logs/app-YYYY-MM-DD.log` if it is a crash or an unexpected result.

## Development setup

```bash
pip install -r requirements-dev.txt
python run.py                 # run from source
python -m pytest tests/ -q    # run the test suite
```

## Guidelines

- **Code, comments, logs, and commit messages are English.** Only the user-facing
  UI is localized (EN/TR — see `rosu/i18n.py`).
- Keep the layered structure: pure logic (`parsing`, `gaps`, `search`, …) stays
  I/O-free and unit-tested; `services.py` orchestrates; the `ui/` layer stays thin
  and runs work off the UI thread via `workers.py`.
- Add or update tests in `tests/` for any logic change, and make sure `pytest` is
  green before opening a pull request.
- Follow [Semantic Versioning](https://semver.org/) and update `CHANGELOG.md`
  ([Keep a Changelog](https://keepachangelog.com/) format) for user-facing changes.

## License

By contributing you agree that your contributions are licensed under the
[GNU General Public License v3.0 or later](LICENSE).
