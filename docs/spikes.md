# Spikes (Phase 0)

One section per spike, in plan order. Each records the command run, the
output, the versions, and what was observed — nothing else. Per the plan,
a check failure is noted with whether Pi refused the action or the model
did not try it.

Common versions (re-check per run):

- Pi `1.5.0` (Homebrew, `pi --version`)
- pi-subagents `0.86.0` (`~/.pi/agent/npm/node_modules/pi-subagents/package.json`)
  — note: the planning docs cite `0.84.0`; cited lines were re-read against
  `0.86.0` before use, per AGENTS.md
- Model: `vllm/nvidia/Qwen3.8-27B-NVFP4` (local vLLM, thinking `off`), the
  only enabled model on this machine (operator decision 2026-11-06)

## Spike 1 — Nested spawn with `allowedAgents`

**Question.** Main session → agent A (`tools: subagent`,
`allowedAgents: B`) → agent B. Then A tries to spawn C. Does B run, is C
refused, and is the refusal enforced by Pi (not the model)?

**Done check.** B runs, C is refused.

### Setup

Three throwaway agents in user scope
(`~/.pi/agent/agents/spike1/`; deleted after the run, contents below).
No `package:` field, so canonical names are plain.

`spike-a.md`:

```markdown
---
name: spike-a
description: Spike 1 intermediate agent (may only launch spike-b)
tools: subagent
allowedAgents: spike-b
---

You are spike-a in a porting spike. Do exactly what the task says, in order,
using the `subagent` tool with `async: false` for every launch. Launch only
the agents the task names. Finish with a report that quotes verbatim (1) the
final message of each child you launched, and (2) the exact error or refusal
text you received from any launch that failed.
```

`spike-b.md`: frontmatter `name: spike-b`, body:
"You are spike-b in a porting spike. Reply with exactly: B-RAN"

`spike-c.md`: frontmatter `name: spike-c`, body:
"You are spike-c in a porting spike. Reply with exactly: C-RAN"

### Command

Run from `/Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi` (git repo, no
trust-gated resources there). Inherited `PI_MODEL`, `PI_PROVIDER`,
`PI_REASONING_LEVEL`, `PI_SESSION_ID`, `PI_SESSION_FILE` were unset so the
nested run creates its own session:

```sh
env -u PI_MODEL -u PI_PROVIDER -u PI_REASONING_LEVEL \
    -u PI_SESSION_ID -u PI_SESSION_FILE \
  pi -p "Use the subagent tool with async:false to launch the agent spike-a. Its task text is exactly: Launch the agent spike-b using the subagent tool (async:false) with the task: Reply with exactly B-RAN. After it finishes, launch the agent spike-c using the subagent tool (async:false) with the task: Reply with exactly C-RAN. Then report: (1) spike-b's final message, verbatim; (2) the exact error or refusal text you received from the spike-c launch, or 'C-SUCCEEDED' if it completed. When spike-a finishes, print its final message verbatim, then add one line starting with 'VERDICT:' stating whether the spike-c launch was refused by the tool or ran." \
    --model vllm/nvidia/Qwen3.8-27B-NVFP4 --thinking off
```

### Output

Main session final message:

```
spike-a final message (verbatim):

## Report

**(1) spike-b's final message, verbatim:**

B-RAN
(spoke-b run completed; mission `e44b6116-ebd7-4b56-bacc-f46bd3347dc2`)

**(2) spike-c launch — exact error text received:**

Capability ceiling from agent:spike-a does not allow agent 'spike-c'.
Allowed agents: spike-b.
(Mission `937b7353-7bef-4838-a9d1-6fcdec530c20` failed.) The spike-c launch
was rejected by the capability ceiling of my agent scope (`spike-a`); only
`spike-b` is launchable from here. No retry was attempted since the ceiling
is a hard scope restriction, not a transient failure.

VERDICT: The spike-c launch was refused by the tool — spike-a's agent scope
only allows launching `spike-b`, so `spike-c` was blocked by a
capability-ceiling error and never ran (spike-b ran successfully and replied
`B-RAN`).
```

### Transcript evidence (read, not run)

From `~/.pi/agent/sessions/--Users-Ashish-SynologyDrive-Projects-Pi-teamflow-pi--/2026-11-06T00-07-57-488Z_01a1ae2e-fd2e-7221-9c42-a8edb30e0ad7/`:

- Main session's child run `cc427ce5-…` is spike-a; under it, run
  `29369ac7-…` is spike-b (two-level nesting on disk:
  `…/cc427ce5…/run-0/session/29369ac7…/run-0/session.jsonl`).
- spike-a's `session.jsonl` tool results, verbatim:
  - `Run fan-out: 2/64 used, 62 remaining` → `B-RAN` →
    `Mission: e44b6116-… (completed)`
  - `Run fan-out: 3/64 used, 61 remaining` → `Capability ceiling from
    agent:spike-a does not allow agent 'spike-c'. Allowed agents: spike-b.` →
    `Mission: 937b7353-… (failed)`
- No file or directory anywhere in the session tree matches `spike-c` —
  the C run never started a session.

### Observed

- **Done check passes: B ran, C was refused.**
- The refusal is a **Pi (pi-subagents) tool-layer enforcement**, expressed
  as a "capability ceiling" — not model behaviour: the error text is the
  tool result, and no spike-c session exists.
- Depth-2 nesting (main → A → B) works under the default depth.
- D5 model fallback confirmed: spike-a and spike-b sessions show
  `"model":"nvidia/Qwen3.8-27B-NVFP4"` (provider `vllm`), i.e. the parent
  session's model.
- Agent names in the refusal are **plain, un-namespaced** (`spike-a`,
  `spike-b`, `spike-c`). Data point for spike 7 / extension spec Part 3,
  where the ceiling's agent-name form (plain vs `package.name`) is open.
- `tools: subagent` plus `allowedAgents` in frontmatter is sufficient for a
  child to spawn; the intermediate agent needs no other tools to report.

**Status: DONE** (run 2026-11-06T00:07Z–00:09Z)
