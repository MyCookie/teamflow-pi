# Extension spec (Phase 3)

The one Pi extension teamflow-pi ships. Written for the agent that builds
it. Build it in the order below; each part ends on a check you run.

Path key: `PD/` = `/opt/homebrew/Cellar/pi-coding-agent/1.5.0/libexec/lib/node_modules/@earendil-works/pi-coding-agent/`,
`PS/` = `~/.pi/agent/npm/node_modules/pi-subagents/`. Every API below was
read in those files on 2026-11-05; none of this code has been run.

## Rules for building it

- **Copy the pattern from the cited example.** Each part names a Pi example
  file. Read it first, and write your code in the same shape.
- **Use only APIs cited here or in `PD/docs/extensions.md`.** If you need
  one that isn't, stop and write down what you needed and why.
- **Pure logic goes in `extensions/teamflow-lib.ts`** as small exported
  functions, each with a test in `extensions/teamflow-lib.test.ts`. Write the
  test first and see it fail. Run the tests with
  `node --test extensions/teamflow-lib.test.ts` (Node 26.13.0 runs `.ts` test
  files directly: checked with a one-test file on 2026-11-05). Import the
  lib with its extension: `import { ... } from "./teamflow-lib.ts"`; Node
  needs it (*from Node's docs, not tried here*).
- **`extensions/teamflow.ts` only wires the pieces to Pi:** the default
  export, `pi.on(...)`, `pi.register...(...)`. Keep it short.

## Files

| Path | What |
|---|---|
| `extensions/teamflow.ts` | The extension (default export `function (pi: ExtensionAPI)`) |
| `extensions/teamflow-lib.ts` | Pure functions, no Pi imports |
| `extensions/teamflow-lib.test.ts` | `node:test` tests for the lib |
| `manager.md` | The manager's prompt. A placeholder line is enough for Phase 3; Phase 4 writes it |
| `bin/tf` | From Phase 2 |

Find the package root from the extension file:
`join(dirname(fileURLToPath(import.meta.url)), "..")` (pattern from
`PD/examples/extensions/doom-overlay/wad-finder.ts:7`).

## Part 1: `tf` on PATH (D4)

**What.** Replace the `bash` tool with one whose commands run with
`<package root>/bin` first on `PATH`.

**Example to copy.** `PD/examples/extensions/bash-spawn-hook.ts` (whole
file, 30 lines): `createBashTool(cwd, { spawnHook })`, then
`pi.registerTool({ ...bashTool, execute })`. The hook gets
`{ command, cwd, env }` and returns them changed.

**Lib function.** `pathWithBin(path: string | undefined, bin: string): string`
returns `bin` followed by `:` and the old `PATH`, or just `bin` when the old
one is empty or undefined. Tests: both cases.

**Check.** `pi -e ./extensions/teamflow.ts -p "Run: command -v tf"` prints
a path ending in `bin/tf`.

## Part 2: the `--teamflow` flag and the manager prompt (D3)

**What.** `pi --teamflow` makes the main session the manager: the content of
`manager.md` is appended to the system prompt on every run. Without the flag
the extension changes nothing.

**Examples to copy.**

- Flag: `pi.registerFlag("teamflow", { description, type: "boolean", default: false })`;
  read it with `pi.getFlag("teamflow")` inside an event, not in the factory,
  where it still returns the default (`PD/docs/extensions.md:1862-1880`).
- Prompt: `pi.on("before_agent_start", (event) => ({ systemPrompt: event.systemPrompt + ... }))`
  (`PD/docs/extensions.md:615-657`; `PD/examples/extensions/preset.ts:388-402`
  does the same with a flag).

**Lib function.** `appendManagerPrompt(systemPrompt: string, manager: string): string`
returns the system prompt, two newlines, then the manager text. Tests: the
result starts with the original and ends with the manager text.

**Check.** Put `Your name is teamflow-manager.` in `manager.md`. Then
`pi -e ./extensions/teamflow.ts --teamflow -p "What is your name?"` answers
with it, and the same command without `--teamflow` does not.

## Part 3: spawn limits (D3)

Two pieces, both only when the flag is on. Why there are two:
[research/manager-startup.md](research/manager-startup.md), "The spawn limit
in option C".

**3a. Ceiling for the whole agent tree.** In `session_start`, register a
ceiling with the ten teamflow subagent names:

```ts
import { registerSubagentCapabilityCeiling } from "pi-subagents/capability-ceiling";

registerSubagentCapabilityCeiling({
  sessionId: ctx.sessionManager.getSessionId(),
  source: "teamflow",
  ceiling: { allowedAgents: TEAMFLOW_AGENTS },
});
```

(`PS/docs/extension-api.md:413-445`.) Keep the returned handle and call its
`dispose()` in `session_shutdown`.

Two things are unknown. Find them out before you write this part, and record
them in `docs/spikes.md`:

- **The agent names.** Plain (`impl-lead`) or package-namespaced. Phase 0
  spike 7 finds out.
- **How to import it.** pi-subagents is a separate Pi package, and Pi loads
  each installed package with its own module root (`PD/docs/packages.md:116`).
  Its ceiling registry is kept on `Symbol.for("pi-subagents.capability-ceiling.v1")`
  (`PS/bundle/chunk-QXASAHIA.js:4-6`), which suggests a second copy of the
  module would share it. That is inferred, not run. Try `pi-subagents` as
  an npm `dependency` of teamflow-pi and check the ceiling takes effect.

**3b. Main session spawns only the three leads.** A `tool_call` handler
(`PD/docs/extensions.md:971-1011`). Copy its shape from
`PD/examples/extensions/permission-gate.ts:13-33`: return
`{ block: true, reason }` to refuse, `undefined` to allow.

**Lib function.** `spawnDecision(input: Record<string, unknown>, isChild: boolean): string | undefined`
returns a refusal reason, or `undefined` to allow:

- `isChild` true: allow. (Background children load this extension too,
  `PS/docs/agents.md:553`. They carry `PI_SUBAGENT_CHILD=1`,
  `PS/src/runs/shared/child-runtime-config.d.ts:15-23`. The leads' own
  `allowedAgents` limit them.)
- `input.agent` is `research-lead`, `impl-lead` or `review-lead`, and there
  is no `tasks` or `chain` field: allow.
- `input.action` is `resume`: allow (the manager resumes impl-lead).
- Anything else: refuse, with a reason naming the three leads.

This fails closed: other `subagent` forms (parallel `tasks`, workflows,
other actions) are refused in the main session until a spike shows the
manager needs one. Tests: one per rule, plus a non-lead `agent`, a lead
inside `tasks`, and a missing `agent`.

The handler calls `spawnDecision(event.input, process.env.PI_SUBAGENT_CHILD === "1")`
when `event.toolName === "subagent"` and the flag is on.

**Check.** With `--teamflow`, asking the session to launch `implementer`
is refused with the reason, and asking it to launch `impl-lead` is not.
Without `--teamflow`, neither is refused.

## Done

All three checks pass, `node --test extensions/teamflow-lib.test.ts`
passes, and `docs/spikes.md` records each check's command and output, with
the Pi, pi-subagents and model versions.
