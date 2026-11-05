# Claude Code → Pi mapping

For each Claude Code mechanism teamflow uses: what Pi offers, where that is
documented, and what is missing. Read on 2026-11-05 from Pi 1.5.0 and the
pi-subagents package 0.84.0. **Nothing here has been run**; every row is from
docs or source, and rows marked *inferred* are a reading, not a quote.

Path keys used in citations:

- `PD/` = `/opt/homebrew/Cellar/pi-coding-agent/1.5.0/libexec/lib/node_modules/@earendil-works/pi-coding-agent/`
- `PS/` = `~/.pi/agent/npm/node_modules/pi-subagents/` (installed as `npm:pi-subagents` in `~/.pi/agent/settings.json`)

Core Pi has no subagents (`PD/examples/extensions/subagent/` is only an
example). The port depends on **pi-subagents** for everything agent-shaped.

## Summary

| teamflow uses (Claude Code) | Pi equivalent | Fit |
|---|---|---|
| Plugin + marketplace (`.claude-plugin/`) | Pi package: `package.json` with a `pi` key, installed by `pi install npm:…`/`git:…` | Good |
| Plugin dependencies (ponytail, mattpocock-skills) | None; bundle into the tarball | **Gap**; D6: ponytail installed separately (it is a Pi package), mattpocock dropped |
| `agents/*.md` subagents | pi-subagents agent files | Good, fields differ |
| `Agent(subagent_type)` tool | `subagent({agent, task, …})` tool | Good |
| `Agent(…)` lists + `hooks/check-spawn` spawn table | `allowedAgents` frontmatter, intersected down the tree | Good, replaces the hook |
| Caller identity in a `PreToolUse` hook | Not exposed to third-party extensions | **Gap** (moot if `allowedAgents` is used) |
| `isolation: worktree` | `worktree: true` per call | Good |
| `skills:` preload (full text) | `skills:` in agent frontmatter, lazy (list + path) | Partial |
| Plugin `bin/` on `PATH` (how agents find `tf`) | None; bash `spawnHook` extension or absolute path | **Gap** |
| `claude --agent teamflow:manager` | None; `--append-system-prompt`, prompt template, or extension | **Gap**; see [research/manager-startup.md](research/manager-startup.md) |
| `SendMessage` resume of a live child by agent ID | `subagent({action:"resume", id, message})`: new child from stored session | Changed semantics |
| `SubagentHandback` / completion notice | async completion message triggers a parent turn | Good |
| `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` | `PI_SUBAGENT_MAX_DEPTH` (default 2) | Good |
| Permissions (`Bash(tf *)`, permission modes) | None; Pi asks for nothing | Moot |
| `disallowedTools: Edit, Write` | `tools` allowlist / `excludeTools` | Good |
| `${CLAUDE_PLUGIN_ROOT}` | `import.meta.url` in an extension; paths relative to skill/agent file | Partial |
| `CLAUDE.md` project instructions | Pi reads `AGENTS.md` and `CLAUDE.md`; children only with `inheritProjectContext: true` | Good |
| `claude plugin validate --strict` in the gate | No validate command in `pi --help` | **Gap** |
| `claude -p` headless | `pi -p`, `--mode json`, `--mode rpc` | Good |

## Packaging

- A package is a directory or npm package using conventional dirs
  (`extensions/ skills/ prompts/ themes/`) or explicit `pi.extensions`,
  `pi.skills`, `pi.prompts` in `package.json` (`PD/docs/packages.md:48-76`).
- pi-subagents agents ship from a package through
  `{"pi":{"subagents":{"agents":["./agents"]}}}` (`PS/docs/agents.md:22,32`),
  and frontmatter `package:` namespaces an agent as `pkg.name`
  (`PS/docs/agents.md:398-477`). So `teamflow:manager` becomes something like
  `teamflow.manager` (*inferred* from the field description).
- Install: `pi install npm:pkg@ver | git:github.com/o/r@ref | <path>`; `-l`
  writes the project's `.pi/settings.json` (`PD/docs/packages.md:11-40`).
  One-run trial without installing: `pi -e <source>` (`packages.md:25-31`).
  Update: `pi update <source>` (`PD/docs/cli.md:262-279`). This replaces
  `claude plugin update teamflow@teamflow --scope project`.
- Version: `version` in `package.json`; pinned specs stay pinned
  (`packages.md:42`). That replaces the version in `.claude-plugin/plugin.json`.
- **Dependencies:** "Other Pi packages used as dependencies must be included
  in the published tarball and referenced through their `node_modules`
  resource paths" (`packages.md:100-116`). There is no cross-package
  dependency or marketplace like Claude's.

## Agents (pi-subagents)

Format: Markdown with YAML frontmatter; the body is the system prompt
(`PS/docs/agents.md:3-13`). Discovery, lowest to highest priority: builtin,
installed package, `~/.pi/agent/agents/**/*.md`, project `.pi/agents/**/*.md`
(`agents.md:17-34`).

Field mapping (Pi fields from `PS/docs/agents.md:398-477`):

| teamflow field | Pi field | Note |
|---|---|---|
| `name`, `description` | `name`, `description` | Same; add `package: teamflow` |
| `model: claude-opus-5-5` | `model` | Omitted under D5: falls back to `subagents.defaultModel`, then the parent's model; `subagents.agentOverrides.<name>.model` pins one (`PS/docs/models.md:5-14`) |
| `effort: high` | `thinking` | *inferred* equivalent |
| `tools` | `tools` (strict allowlist) | Pi built-ins: `read bash edit write grep find ls` (`pi --help`) |
| `disallowedTools` | `excludeTools` | |
| `Agent(teamflow:x, …)` in `tools` | `tools: subagent` (or `allowNestedSubagents: true`) **plus** `allowedAgents: x, …` | Nesting needs both |
| `disallowedTools: Agent` (implementer) | omit `subagent` from `tools`, or `allowedAgents:` empty | Empty list denies all launches (`agents.md:453`) |
| `isolation: worktree` | `worktree: true` on the `subagent` call (`PS/docs/tool-reference.md:106`) | Per call, not per agent (*check for a frontmatter default*) |
| `skills: teamflow:workflow` | `skills:`, `skillPath:` (`agents.md:463-464`) | Lazy, see Skills |
| `maxTurns` | not found | `timeoutMs` exists; no turn cap found |
| (implicit) project CLAUDE.md | `inheritProjectContext: true` | Custom agents start clean (`agents.md:378-390`) |

### Spawning, waiting, resuming

- Tool: `subagent({agent, task, async, model, cwd, worktree, output, action, id, message, options})`
  (`PS/docs/tool-reference.md:70`).
- `async` is on by default; `async:false` blocks the parent
  (`tool-reference.md:104`). A finished background run sends a message with
  `triggerTurn:true`, which starts a parent turn when the parent is idle
  (`PS/docs/extension-api.md:647-649`). Close completions can be batched into
  one notice (`PS/docs/configuration.md:731-751`). This fits teamflow's "end
  your turn and continue on the completion notice; never poll".
- Depth: default 2, main → sub → sub-sub; `PI_SUBAGENT_MAX_DEPTH`,
  `config.maxSubagentDepth`, or frontmatter `maxSubagentDepth` (tighten only)
  (`PS/docs/workflows.md:555-569`). manager → lead → worker fits **only if the
  manager is the main session**.
- **Resume differs.** `resume` "starts a new child session from the old
  session context; it does not resume the live session", needs a persisted
  `.jsonl`, and stopped runs cannot be resumed (`tool-reference.md:374-383`).
  teamflow's manager resumes the same impl-lead after every review round.
  Under Pi, impl-lead's conversation would carry over through the session
  file (*inferred*), but each resume is a new process. Must be tested.
- Children of a foreground child never load the parent's ambient
  extensions; background children do unless the agent sets `extensions`
  (`PS/docs/tool-reference.md:104`, `PS/docs/agents.md:553`). This matters
  for any extension teamflow ships (the `tf` PATH hook below).

### Spawn table

`allowedAgents` "restricts which canonical, case-sensitive agent names this
agent may launch … only narrows an existing nesting grant … intersected and
cannot be widened" (`PS/docs/agents.md:453`). That expresses
`hooks/check-spawn`'s table in frontmatter, at every depth. A session-wide
ceiling is also available (`registerSubagentCapabilityCeiling`,
`PS/docs/extension-api.md:413-445`).

Porting `check-spawn` itself as a Pi `tool_call` handler
(`PD/docs/extensions.md:971-1011`) is blocked: no documented API tells a
third-party handler which agent is calling in a child session. The child
markers are only `PI_SUBAGENT_CHILD`, `PI_SUBAGENT_RUNNER_PID`,
`PI_SUBAGENT_PARENT_SESSION` (`PS/src/runs/shared/child-runtime-config.d.ts:15-23`).
Whether a parent's `tool_call` gate sees launches made inside workflow
scripts (`runs.run`) is unverified.

## Skills

Agent Skills format: `skills/<name>/SKILL.md` with `name`, `description`
(`PD/docs/skills.md:7-35`). Only name, description and path enter the
prompt; the body is read on demand; `/skill:name` forces one
(`skills.md:43-53`). An agent's `skills:` field gives the child the
`<available_skills>` list, and `read` is added when `tools` is an allowlist
(`PS/docs/agents.md:601-641`). **The full text is not injected**, unlike
Claude's `skills:` preload. teamflow's leads already load the workflow skill
as their first step; under Pi every agent should be told to `read` it first.

## `tf` on PATH

No documented package mechanism puts a `bin/` on `PATH`. Options:

1. An extension that overrides `bash` with
   `createBashTool(cwd, {spawnHook})` to prepend the package's `bin/` to
   `PATH` (`PD/docs/extensions.md:2407-2429`, example
   `PD/examples/extensions/bash-spawn-hook.ts`). The package dir comes from
   `dirname(fileURLToPath(import.meta.url))`
   (`PD/examples/extensions/doom-overlay/wad-finder.ts:7`). Foreground
   children need it listed in their `extensions` (see above).
2. Register a `tf` tool (`pi.registerTool`, `pi.exec`;
   `extensions.md:1580-1600,1881-1890`). Breaks the prompts' heredoc-on-stdin
   convention; more change.
3. The `shellCommandPrefix` setting, prepended to every built-in `bash`
   command, for example `export PATH=…/bin:$PATH` (`PD/docs/settings.md:143`,
   `PD/docs/shell-aliases.md:40`). A user or project setting, so the human
   sets it; whether children inherit it is unverified.
4. Ask the human to put `bin/` on `PATH` themselves (no code; setup burden).

## Starting the manager

No `--agent` flag (`pi --help`). Options: `--system-prompt` /
`--append-system-prompt <file>` (`PD/docs/cli.md:229-232`), `.pi/SYSTEM.md`
or `.pi/APPEND_SYSTEM.md` (`PD/docs/configuration.md:19-20`), a prompt
template run as `/name` (`PD/docs/prompt-templates.md:9-19`), or an extension
that sets the prompt in `before_agent_start` and registers a flag
(`PD/docs/extensions.md:615-657,1862`). Launching the manager itself as a
subagent would make the chain main → manager → lead → worker, depth 3, over
the default of 2. The options compared, and a recommendation:
[research/manager-startup.md](research/manager-startup.md).

## Permissions and headless

Pi "does not ask for approval before every tool call"; safety comes from OS
or container isolation (`PD/docs/security.md:3-7`). So teamflow's
`Bash(tf *)` allowlist and the auto-mode refusals in its `docs/setup.md` have
no Pi counterpart. Read-only agents stay a guard rail, as today: `bash` can
still write, and pi-subagents' child permissions pass `bash` through
(`PS/docs/watchdog.md:168-187`). Headless: `-p`, `--mode json`,
`--mode rpc` (`PD/docs/cli.md:41-51`); pi-subagents does not auto-resume async
workflows after `pi -p` (`PS/docs/configuration.md:264`).

## Context files

Pi loads `AGENTS.override.md`, `AGENTS.md` and `CLAUDE.md` from the agent
dir, the cwd and its parents, without needing project trust
(`PD/docs/configuration.md:41-47`). A target repo's existing `CLAUDE.md`
therefore still reaches the main session; children get it only with
`inheritProjectContext: true` (`PS/docs/agents.md:378-390`).

## Not found

- An agent turn cap (`maxTurns`).
- A frontmatter default for worktree isolation (only the per-call flag was read).
- A package validation command for the gate.
- ponytail is not installed for Pi on this machine. It is a Pi package
  (`pi install git:github.com/DietrichGebert/ponytail`, its README.md:177;
  read in the local Claude plugin copy), so this is an install step, not a gap.
