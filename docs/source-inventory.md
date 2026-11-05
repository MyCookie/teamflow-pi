# Source inventory: teamflow (Claude Code)

What the port starts from, path by path, sorted by how much each piece
depends on Claude Code. Read from the teamflow repository
(`Ribhu-Labs/teamflow`, local checkout at
`/Users/Ashish/SynologyDrive/Projects/Claude/teamflow`) at commit `423109c`,
plugin version `0.22.2`, on 2026-11-05. Re-check against that repository
before acting on a line here; it keeps moving.

## What teamflow is

A three-team agent pipeline under a manager:

- **research-lead** turns a goal into typed Issues, using `researcher` workers.
- **impl-lead** plans non-overlapping units, gives each an `implementer` in
  its own git worktree, and each opens a PR.
- **review-lead** reviews every PR before it merges with five fresh
  specialist reviewers (architect, security, quality, docs, simplicity),
  records one verdict per head, and is the only actor that merges.
- **manager** routes every handoff, including each PR's review rounds, and
  keeps `.manager-state.json`.

Two invariants: `main` is always green (`scripts/gate.sh` is the one
definition of green), and nothing merges on its author's say-so. Issues and
PRs go only through `bin/tf`, in `local` mode (records under
`.git/teamflow/`) or `github` mode (real Issues/PRs via `gh`).

The rules live once, in `skills/workflow/SKILL.md`; agent prompts point to
it. Read that file first when you need the behaviour, not this summary.

## Tier 1: harness-agnostic, copy as-is

Python and shell with no Claude Code dependency (checked by grep for
`claude`, `CLAUDE_`, `plugin`):

| Path | What it is | Coupling found |
|---|---|---|
| `bin/tf` | Issues and PRs in both forge modes (936 lines) | Reads `.claude/teamflow.json`; `tf setup` adds `.claude/worktrees/` to `.gitignore` (`IGNORES`, line 708) |
| `bin/teamflow-config` | Prints effective config | Reads `.claude/teamflow.json` (line 83) |
| `templates/gate.sh`, `templates/ci.yml`, `templates/branch-ruleset.json`, `templates/pull_request_template.md` | What `tf setup` installs in a target repo | None found |
| `tests/test_tf.py`, `tests/fake_gh.py`, `tests/test_setup.py` | Unit tests for `tf` and `tf setup` (`python3 -m unittest discover -s tests`) | Only through the config path above |

Decision needed: keep the config at `.claude/teamflow.json` (one config
for both harnesses) or move it (for example `.pi/teamflow.json`). See
[porting-plan.md](porting-plan.md), Open decisions.

## Tier 2: rules that carry over, wording that does not

`skills/workflow/SKILL.md` (584 lines) and `skills/setup/SKILL.md`. The
pipeline rules (routing, handoffs, Issue format, branches, gate, red/green,
review and merge, honesty) are harness-agnostic. The Claude Code parts:

- *Teams*: `claude --agent teamflow:manager` as the entry point.
- *Spawn depth*: `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`.
- *Messaging*: `SendMessage(to: "team-lead")`, `SubagentHandback`,
  idle-notification results, `[Subagent hand-back]`, resume by agent ID,
  fork mode, `-p`.
- *Role bounds*: read-only enforced by `disallowedTools`.
- *Release*: version in `.claude-plugin/plugin.json`,
  `claude plugin update teamflow@teamflow --scope project`.
- *Domain language*: `domain-modeling` from the `mattpocock-skills` plugin.

## Tier 3: Claude Code mechanisms, redesign for Pi

### Agents (`agents/*.md`, 11 files)

Frontmatter fields used, and by whom:

| Field | Values in use | Meaning in Claude Code |
|---|---|---|
| `model` | `claude-opus-5-5` (manager, three leads), `claude-sonnet-5-5` (workers) | Model per agent |
| `effort` | `high` everywhere | Reasoning effort |
| `tools` | allowlists; leads add `Agent(teamflow:<type>, ...)` | Tools, and which subagent types it may spawn |
| `disallowedTools` | `Edit, Write, MultiEdit` on read-only agents; `Agent` on implementer; `mcp__github` on researcher | Denylist |
| `isolation` | `worktree` on the five reviewers, researcher, review-lead | Harness creates a git worktree per spawn |
| `skills` | `teamflow:workflow` everywhere; simplicity-reviewer adds three `ponytail:*` skills | Skills preloaded into the subagent |
| `maxTurns` | 60 to 300 | Turn cap |

Spawn table (what each agent may spawn):

| Caller | May spawn |
|---|---|
| manager | research-lead, impl-lead, review-lead |
| research-lead | researcher |
| impl-lead | implementer |
| review-lead | architect-, security-, quality-, docs-, simplicity-reviewer |
| workers | nothing |

Prompt bodies that name Claude Code mechanisms (from grep):

| Mechanism | Files |
|---|---|
| `Agent(subagent_type: ...)` calls | manager, research-lead, impl-lead, review-lead |
| `SendMessage` (mid-task message; resume by agent ID) | all 11 |
| `SubagentHandback` (final report on async spawns) | all workers, review-lead |
| `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` startup check | manager, research-lead, impl-lead, review-lead |
| `claude --agent teamflow:<lead>` (running a lead alone) | research-lead, impl-lead, review-lead |
| `claude plugin update` (release step) | manager |
| `/ponytail ultra`, `/ponytail-audit`, `/ponytail-debt` | simplicity-reviewer |

Behaviour the pipeline depends on:

- **Nesting depth 2**: manager, lead, worker. No third layer.
- **Parallel spawns**: review-lead runs five reviewers at once; impl-lead
  runs one implementer per independent unit.
- **Wait for children**: a lead returns only after its workers report.
- **Resume a child**: the manager resumes the same impl-lead after every
  review round, by agent ID, within one process. A restart loses it.
- **Fresh context per spawn**: each review round uses a fresh review-lead and
  five fresh reviewers, briefed with only PR number, branch, Issue, head SHA.
- **Worktrees**: impl-lead creates implementer worktrees itself
  (`git worktree add`); reviewers and researchers get one from
  `isolation: worktree`.

### Spawn hook (`hooks/check-spawn`, `hooks/hooks.json`)

A `PreToolUse` hook on the `Agent` tool. It reads the caller's
`agent_type` and `tool_input.subagent_type` and denies any pair outside the
spawn table above, at every depth (frontmatter `Agent(...)` lists bind only
the main thread). Unparseable input blocks (exit 2); a non-teamflow caller
gets no decision. Tested by `tests/test_hooks.py`.

### Packaging (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`)

`version` lives only in `plugin.json`. Dependencies: `ponytail@ponytail` (the
simplicity-reviewer's engine) and `mattpocock-skills@mattpocock`. Plugin
`bin/` is put on `PATH` for the session and every subagent; that is how
agents find `tf`.

### Repo tooling

- `scripts/gate.sh`: runs the tests and `claude plugin validate --strict` on
  the plugin and marketplace.
- `tests/test_agents.py`: checks agent frontmatter (Bash kept in `tools`,
  Write implies Read, safe `tf` command lines in prompts).
- `tests/test_hooks.py`: the spawn table.
- `.claude/settings.json`: `permissions.allow: ["Bash(tf *)"]`.

### Docs (`docs/*.md`, `README.md`)

`running.md`, `setup.md`, `release.md`, `forge-modes.md`,
`plugin-contents.md`. Mostly Claude Code specific; `forge-modes.md` is
mostly about `tf` and carries over.

## What was observed live in teamflow

From `docs/running.md`: one interactive run (Claude Code 2.1.308) went from
goal to a merged PR using the older single code-reviewer. A per-PR round
with review-lead and its five specialists has **not** been run live, and
neither has a post-merge review. A port should not assume those paths are
proven on Claude Code either.
