#!/usr/bin/env bash
# The repo's checks. Exit 0 only when the branch is fit to review.
#
# The gate runs this script from the main checkout with the job's worktree as
# the working directory. Fast, deterministic and non-interactive: it never
# rewrites files. Mirrors .github/workflows/build.yml (tests) plus the owner's
# hard rules that a script can check.
set -euo pipefail
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1

python3 -c "import PySide6, pytest" 2>/dev/null || python3 -m pip install -q -r requirements-dev.txt

echo "== compile"
python3 -m compileall -q rosu tests run.py >/dev/null

echo "== owner rules"
# No eval/exec, pickle or shell=True; HTTP through the standard library only.
# Parsed, not grepped, so docstrings and Qt's dialog.exec() don't count.
python3 - <<'PY'
import ast, pathlib, sys
BANNED_IMPORTS = {"pickle", "requests", "httpx", "urllib3", "aiohttp"}
bad = []
for path in sorted(pathlib.Path("rosu").rglob("*.py")):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
        where = f"{path}:{getattr(node, 'lineno', 0)}"
        if isinstance(node, ast.Import):
            bad += [f"{where} import {a.name}" for a in node.names if a.name.split(".")[0] in BANNED_IMPORTS]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in BANNED_IMPORTS:
            bad.append(f"{where} from {node.module} import ...")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                bad.append(f"{where} {node.func.id}()")
            bad += [f"{where} shell=True" for k in node.keywords
                    if k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True]
if bad:
    print("owner rule broken (no eval/exec, pickle, shell=True or non-stdlib HTTP):", *bad, sep="\n", file=sys.stderr)
    sys.exit(1)
PY
# Secrets are never tracked.
if git ls-files | grep -E '^config(\..*)?\.json$|(^|/)(oauth_client\.json|report_token\.txt|client_secret[^/]*\.json|\.env[^/]*)$'; then
  echo "a secret file is tracked: see the paths above" >&2; exit 1
fi

echo "== tests"
python3 -m pytest tests/ -q -p no:cacheprovider
