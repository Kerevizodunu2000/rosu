## Summary

<!-- What does this PR change, and why? -->

## Related issue

<!-- e.g. Closes #123 — or "n/a" -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / cleanup
- [ ] Documentation

## Checklist

- [ ] `python -m pytest -q` passes
- [ ] `python run.py --selftest` exits 0
- [ ] Added or updated tests for any logic change
- [ ] Kept the layered structure (pure logic stays I/O-free and unit-tested · `services.py` orchestrates · `ui/` stays thin and runs off-thread via `workers.py`)
- [ ] Code, comments, and commit messages are in English; any new user-facing string lives in `rosu/i18n.py` (EN + TR)
- [ ] Updated `CHANGELOG.md` for user-facing changes
