# AGENTS.md

Instructions for coding agents (Claude Code, the software factory's agents, and
others) working in this repo. Humans: see `CONTRIBUTING.md`.

## What Rosu is

A free, open-source (GPL-3.0-or-later) Windows desktop companion app for osu!
(stable and lazer), in Python 3.13 and PySide6. It imports and archives
beatmaps into a deduplicated Library, finds missing packs and lost maps,
backs up to Google Drive, syncs collections, rates difficulties, and removes
maps recoverably. It is an unofficial fan tool, not affiliated with ppy. Its
website and bug-report backend live in the separate `rosu-web` repo.

## Setup (fresh checkout)

```bash
pip install -r requirements-dev.txt   # Python 3.13
python run.py                         # run from source (Windows; Qt needs a display)
```

Secrets are never in the repo. `config.json`, `rosu/drive/oauth_client.json`
and `rosu/report_token.txt` are written by CI or the user and are gitignored.
The app and the tests run without them.

## Validation

`factory/checks.sh` is the source of truth; it runs, from the repo root:

```bash
QT_QPA_PLATFORM=offscreen python3 -m compileall -q rosu tests run.py
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q
```

plus the owner-rule checks below. CI (`.github/workflows/build.yml`) runs the
tests on Windows and builds the exe with PyInstaller (`rosu.spec`).

To look at a widget without a display, build it with
`QT_QPA_PLATFORM=offscreen` and save `widget.grab()` to a PNG.

## Layout

- `rosu/` pure logic (`parsing.py`, `gaps.py`, `query.py`, `search.py`,
  `msd.py`, …): I/O-free and unit-tested.
- `rosu/services/`: orchestration. **Qt-free.**
- `rosu/db.py`: `Database`. All database access goes through its methods,
  which take the lock.
- `rosu/ui/`: thin Qt layer. Long work runs through `rosu/workers.py`
  (`Worker`), never on the UI thread.
- `rosu/i18n.py`: every user-facing string, in English and Turkish.
- `rosu/theming.py`: palettes (light and dark).
- `rosu/drive/`: Google Drive backup (scope `drive.file`).
- `tests/`: pytest; `conftest.py` sets up fixtures.

## Owner's rules (binding)

- **Language:** code, comments, logs, commit messages, `CHANGELOG.md` and
  `README.md` are English. The UI is bilingual (English + Turkish) through
  `rosu/i18n.py`, used as `t(key)` with no `default=` fallback.
- **Commits:** authored as the repo's configured git user (the owner). Never
  add `Co-Authored-By` or other trailers, and never put a model name in a
  commit, PR, comment or file.
- **Architecture:** services stay Qt-free; the database only through locked
  `Database` methods; UI calls services through `workers.Worker`.
- **Tests:** every logic change gets a test.
- **Destructive operations** are recoverable (Recycle Bin or backup), with a
  preview and a countdown confirm. Never delete osu!lazer files directly.
- **Banned:** non-stdlib HTTP (only the standard library, plus `keyring`);
  `eval`, `exec`, `pickle`, `shell=True`; UnRAR; the ppy osu! logo; a
  `mailto:` bug report; storing raw IP addresses.
- **Drive** uses the `drive.file` scope only; tokens live in the OS keyring.
- **Never commit:** `config.json`, `rosu/drive/oauth_client.json`,
  `docs/client_secret_*.json`, `rosu/report_token.txt`, `.env*`.
- **Money:** Rosu takes no money and spends none. No sales, donations,
  supporter tiers, paywalls, paid services or paid infrastructure; only free
  tiers.
- **Security:** the repo is public. Nothing may leak the owner's personal
  data or let anyone use the owner's keys or accounts. Any local server binds
  to `127.0.0.1` and is off by default. Any LAN feature listens on the LAN
  only while the user has turned it on, and only for paired devices.
- **Rust:** the app stays Python + PySide6; there is no full rewrite. Move an
  existing function to Rust (a PyO3 module, as `rosu-pp-py` already is) only
  after a profile on a large library shows it is a bottleneck. For a new
  feature, decide at intake whether its heavy core (hashing or scanning large
  data, audio or image processing, a long-running engine) is better written
  in Rust; the UI, services and tests stay in Python. Rust modules follow the
  same rules: GPL-3.0-or-later, tested, built with free tools, and CI builds
  the Windows wheel.
- **Releases:** each version passes a review gate (Sonnet finders → Opus
  verification → fixes) before it ships. Agents never tag or publish a
  release.
- **License:** GPL-3.0-or-later. Third-party code keeps its notices;
  `THIRD-PARTY-LICENSES.md` lists dependencies.
- **Versioning:** Semantic Versioning; user-facing changes go in
  `CHANGELOG.md` under `[Unreleased]` (Keep a Changelog).

## Software factory

`/factory run` builds every open GitHub issue labeled `factory` through
intake → spec → build → gate → review → approve, one PR per issue. State is in
`factory/jobs/` (gitignored); `factory/bin/job` is its only writer. Checks:
`factory/checks.sh`. Dashboard: `cd factory && python3 -m http.server`, then
open http://localhost:8000/dashboard.html. In sessions without the `gh` CLI,
run the scripts with `FACTORY_GITHUB=mcp` (see `.claude/skills/factory/SKILL.md`).
