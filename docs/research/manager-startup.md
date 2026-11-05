# Research: how the manager starts (D3)

**Question.** teamflow starts with `claude --agent teamflow:manager`: the
session's own agent is the manager, with its prompt, its tools, and a spawn
list limited to the three leads. Pi has no `--agent` flag (`pi --help`).
What should replace it?

Read on 2026-11-05 from Pi 1.5.0 and pi-subagents 0.84.0 (path keys `PD/`
and `PS/` as in [pi-mapping.md](../pi-mapping.md)). Nothing here was run.

## What the replacement has to do

1. Give the main session the manager's prompt, kept for the whole session
   (the manager runs for hours, across many review rounds).
2. Keep the manager the **main session**. pi-subagents' default depth is 2,
   main → sub → sub-sub (`PS/docs/workflows.md:555`), and manager → lead →
   worker uses all of it.
3. Limit the main session's spawns to the three leads, while still letting
   the leads spawn their workers (teamflow's `hooks/check-spawn` table).
4. Let the human talk to the manager directly: it asks for plan approval.

## Options

| | Option | 1. Prompt kept | 2. Main session | 3. Spawn limit | 4. Human talks to it | Code |
|---|---|---|---|---|---|---|
| A | `pi --append-system-prompt <path>/manager.md` | yes (system prompt, `PD/docs/cli.md:229-232`) | yes | no | yes | none, but the human types the install path |
| B | Prompt template `/teamflow <goal>` | **no**: expands into a user message (`PD/docs/prompt-templates.md`, "Use a template"), which compaction can summarise (*inferred*) | yes | no | yes | none |
| C | Extension flag `pi --teamflow` (and `/teamflow` command) | yes (`before_agent_start` system prompt, `PD/docs/extensions.md:615-657`) | yes | yes, see below | yes | small; same extension as D4 |
| D | Manager as a pi-subagents agent, launched from a plain session | yes | **no**: depth 3, needs `PI_SUBAGENT_MAX_DEPTH=3` | yes (`allowedAgents`) | **no**: the human talks to the parent, which relays | none |

Pi's own `preset` example does what C needs: a `pi.registerFlag("preset")`
read with `pi.getFlag`, and a `before_agent_start` handler that appends
instructions to `event.systemPrompt`; it also sets model and tools
(`PD/examples/extensions/preset.ts:1-40,114,388-402`). Tool selection can
change in the same handler or through `pi.setActiveTools()`
(`PD/docs/extensions.md:657,1586`).

### The spawn limit in option C

Two pieces, because one limit must apply only to the main session:

- **Ceiling for the whole tree.** `registerSubagentCapabilityCeiling`
  restricts `allowedAgents` for a session; the snapshot "is propagated
  monotonically to nested and async children" (`PS/docs/extension-api.md:413-445`).
  Because it propagates, it cannot be the three leads alone: that would also
  stop impl-lead spawning implementer. It can be the ten teamflow agents,
  which keeps every non-teamflow agent out. This is the same reason
  teamflow's manager frontmatter lists every type today (teamflow
  `agents/manager.md:106-109`, "Spawning leads").
- **Main session to three leads.** The leads' own `allowedAgents` cover
  depth 1 and 2. For the main session, a `tool_call` handler that blocks a
  `subagent` call whose `agent` is not a lead (`PD/docs/extensions.md:971-1011`).
  It must act only in the main session: background children load ambient
  extensions (`PS/docs/agents.md:553`), and they carry `PI_SUBAGENT_CHILD=1`
  (`PS/src/runs/shared/child-runtime-config.d.ts:15-23`), so the handler can
  skip itself there. That the handler sees `event.input.agent` is read from
  the tool schema (`PS/docs/tool-reference.md:70`), not run.

## Recommendation

**Option C.** It is the only option that meets all four needs, and teamflow-pi
needs an extension for D4 (`spawnHook`) anyway, so it adds a flag and two
handlers to code that will exist regardless. A is the fallback if the
extension approach fails a spike: it needs no code but gives up the spawn
limit for the main session (a prompt rule only, as Claude Code's frontmatter
list is today without the hook).

## To verify (spike before building)

1. `pi --teamflow` appends the manager prompt, and it is still there after
   a `/compact`.
2. The ceiling's agent names: plain `impl-lead` or the package-namespaced
   form (`package:` field, `PS/docs/agents.md:398-477`). Unknown.
3. The main-session `tool_call` handler blocks `subagent({agent: "implementer"})`
   and allows `impl-lead`; the same extension, loaded in a background
   child, does nothing.
4. A foreground child, which loads no ambient extensions
   (`PS/docs/agents.md:553`), still gets the ceiling (it is propagated by
   pi-subagents, not by the extension).
