# Software factory

`/factory run` builds every open GitHub issue labeled `factory` through
intake → spec → build → gate → review → approve, one pull request per issue.
How it works: `.claude/skills/factory/SKILL.md` (the orchestrator) and
`.claude/agents/` (one file per role).

| File | Job |
|---|---|
| `config.json` | concurrency, rounds, labels, risk routing, protected paths, prices |
| `checks.sh` | this repo's checks; the gate runs the base branch's copy |
| `bin/job` | the only writer of `jobs/<id>/job.json`; refuses illegal moves; merges |
| `bin/gate` | runs `checks.sh` in a job's worktree → `round-N/checks.md` |
| `bin/route` | intake's risk + surfaces → the job's reviewers and models |
| `dashboard.html` | the board: `cd factory && python3 -m http.server`, open `/dashboard.html` |

`jobs/` and `.github-cache/` are runtime state and are gitignored.

Sessions without the `gh` CLI (Claude Code on the web) run the scripts with
`FACTORY_GITHUB=mcp`: `bin/job` reads GitHub data from `.github-cache/` and
queues its GitHub writes in `.github-cache/outbox.jsonl`, and the orchestrator
does the GitHub side through the GitHub MCP tools.

## Origin and license

Adapted from ZazenCodes' Software Factory for Claude Code
([v1](https://github.com/zazencodes/zazencodes-season-3/tree/main/src/software-factory-claude-code),
[v2](https://github.com/zazencodes/zazencodes-season-3/tree/main/src/software-factory-claude-code-v2)),
which is licensed under the GNU GPL v3. The files in `factory/` and
`.claude/` derived from it are distributed under the GPL v3 as well. Changes
for this repo: the MCP GitHub mode, intake on Opus instead of Fable (the
project spends no money), Windows-safe locking, cost read across project
folders, and agents tailored to this repo and its owner's rules.
