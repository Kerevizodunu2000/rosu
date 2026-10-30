# SPDX-License-Identifier: GPL-3.0-or-later
""".github/workflows/build.yml: build secrets reach the runner on tag runs only.

Read as text (no YAML library in requirements-dev.txt), so this guards the
layout the workflow uses: two-space indents, jobs at 2, steps at 6.
"""
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "build.yml"
SECRETS = ("secrets.ROSU_OAUTH_CLIENT_JSON", "secrets.ROSU_REPORT_TOKEN")
TAG_IF = "if: startsWith(github.ref, 'refs/tags/')"


def sections(lines, indent):
    """Group (number, line) pairs by the keys at `indent`; each group starts with its key line."""
    out, key = {}, None
    for n, line in lines:
        body = line.lstrip(" ")
        if not body or body.startswith("#"):
            continue
        depth = len(line) - len(body)
        if depth == indent:
            key = body.split(":", 1)[0]
            out[key] = [(n, line)]
        elif depth > indent and key is not None:
            out[key].append((n, line))
        else:
            key = None
    return out


def jobs(text):
    top = sections(enumerate(text.splitlines(), 1), 0)
    return {name: sections(lines[1:], 4) for name, lines in sections(top["jobs"][1:], 2).items()}


def steps(job):
    """Split a job's `steps:` list into steps, each as sections() of its keys."""
    items = []
    for n, line in job.get("steps", [])[1:]:
        if line.startswith(" " * 6 + "- "):
            items.append([])
            line = " " * 8 + line[8:]
        if items:
            items[-1].append((n, line))
    return [sections(item, 8) for item in items]


def secret_violations(text):
    """Line numbers holding a build secret outside the env: of a tag-only step."""
    allowed = set()
    for job in jobs(text).values():
        for step in steps(job):
            if step.get("if", [(0, "")])[0][1].strip() == TAG_IF:
                allowed |= {n for n, _ in step.get("env", [])[1:]}
    return [n for n, line in enumerate(text.splitlines(), 1)
            if any(s in line for s in SECRETS) and n not in allowed]


TEXT = WORKFLOW.read_text(encoding="utf-8")


def test_secrets_only_in_tag_only_step_env():
    assert all(s in TEXT for s in SECRETS)
    assert secret_violations(TEXT) == []


SECRET_ENV = "        env:\n          T: ${{ secrets.ROSU_REPORT_TOKEN }}\n"


@pytest.mark.parametrize("workflow", [
    # Secret in a step without the tag if:.
    "jobs:\n  windows:\n    steps:\n      - name: Embed\n" + SECRET_ENV,
    # Secret at job level, next to a tag-only step.
    "jobs:\n  windows:\n    env:\n      T: ${{ secrets.ROSU_REPORT_TOKEN }}\n    steps:\n"
    "      - name: Embed\n        " + TAG_IF + "\n",
    # Secret in the run: of a tag-only step, not its env:.
    "jobs:\n  windows:\n    steps:\n      - name: Embed\n        " + TAG_IF + "\n"
    "        run: echo ${{ secrets.ROSU_OAUTH_CLIENT_JSON }}\n",
])
def test_helper_reports_violations(workflow):
    assert secret_violations(workflow)
    # The same step with the tag if: is accepted, so the check is not vacuous.
    ok = "jobs:\n  windows:\n    steps:\n      - name: Embed\n        " + TAG_IF + "\n" + SECRET_ENV
    assert secret_violations(ok) == []


def test_both_jobs_have_timeouts():
    found = jobs(TEXT)
    assert {"windows", "release"} <= found.keys()
    for name in ("windows", "release"):
        assert "timeout-minutes" in found[name], name


def test_windows_checkout_drops_credentials():
    checkout = [s for s in steps(jobs(TEXT)["windows"])
                if "uses" in s and "actions/checkout@" in s["uses"][0][1]]
    assert len(checkout) == 1
    assert any(line.strip() == "persist-credentials: false" for _, line in checkout[0].get("with", []))


def test_concurrency_never_cancels_tag_runs():
    block = sections(enumerate(TEXT.splitlines(), 1), 0)["concurrency"]
    lines = [line.strip() for _, line in block]
    assert "group: build-${{ github.ref }}" in lines
    assert "cancel-in-progress: ${{ !startsWith(github.ref, 'refs/tags/') }}" in lines


def test_two_space_indentation():
    assert "\t" not in TEXT
    prev = 0
    for n, line in enumerate(TEXT.splitlines(), 1):
        body = line.lstrip(" ")
        if not body or body.startswith("#"):
            continue
        depth = len(line) - len(body)
        assert depth % 2 == 0 and depth <= prev + 2, f"line {n}: bad indent"
        prev = depth
