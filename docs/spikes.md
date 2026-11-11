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

## Spike 2 — Parallel and wait

**Question.** A spawns five children at once and reports only after all five
finish. Mechanism used: the built-in `parallel` workflow resource,
`subagent({ workflow: "parallel", async: false, args: { tasks: [{agent, task}, …] } })`
(`PS/docs/workflows.md:143,167`, re-read on 0.86.0): "the children run in one
`runs.all` batch, and the result lists each child's output in order. A failed
child fails the workflow."

**Done check.** One report naming all five results.

### Setup

Six throwaway agents in user scope (`~/.pi/agent/agents/spike2/`, deleted
after the run).

`spike2-a.md`:

```markdown
---
name: spike2-a
description: Spike 2 intermediate agent (may launch the five workers only)
tools: subagent
allowedAgents: spike2-w1, spike2-w2, spike2-w3, spike2-w4, spike2-w5
---

You are spike2-a in a porting spike. Do exactly what the task says. Finish
with one report: a single message that names, in order, the exact output of
every child.
```

`spike2-w1.md` … `spike2-w5.md`: frontmatter `name: spike2-w<n>`, body:
"You are spike2-w<n> in a porting spike. Reply with exactly: W<n>-RAN"

### Command

Same environment as spike 1 (from
`/Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi`):

```sh
env -u PI_MODEL -u PI_PROVIDER -u PI_REASONING_LEVEL \
    -u PI_SESSION_ID -u PI_SESSION_FILE \
  pi -p "Use the subagent tool with async:false to launch the agent spike2-a. Its task text is exactly: Call the subagent tool exactly once with workflow 'parallel' and async false. Its args must be { tasks: [ {agent: spike2-w1, task: Reply with exactly W1-RAN}, {agent: spike2-w2, task: Reply with exactly W2-RAN}, {agent: spike2-w3, task: Reply with exactly W3-RAN}, {agent: spike2-w4, task: Reply with exactly W4-RAN}, {agent: spike2-w5, task: Reply with exactly W5-RAN} ] }. After that call returns, your final message must be one report listing, in order, the exact output of each of the five children. Do not launch anything else. When spike2-a finishes, print its final message verbatim, then add one line starting with 'VERDICT:' stating how many distinct worker results appear in it." \
    --model vllm/nvidia/Qwen3.8-27B-NVFP4 --thinking off
```

### Output

Main session final message:

```
spike2-a final message (verbatim):

## Report: parallel workflow fan-out — exact child outputs (in order)

1. **spike2-w1**: "\n\nW1-RAN" (two leading newlines, then W1-RAN)
2. **spike2-w2**: "\n\nW2-RAN" (two leading newlines, then W2-RAN)
3. **spike2-w3**: "\n\nW3-RAN" (two leading newlines, then W3-RAN)
4. **spike2-w4**: "\n\nW4-RAN" (two leading newlines, then W4-RAN)
5. **spike2-w5**: "\n\nW5-RAN" (two leading newlines, then W5-RAN)

All 5 children completed ok=true; mission `dae42e2b-66e9-4d8d-8d0a-03c6992bcc08`
completed. The subagent tool was called exactly once (workflow `parallel`,
async=false); nothing else was launched.
Mission: 66d2bfbf-93e0-4667-853b-0e14c7461551 (completed)

VERDICT: 5 distinct worker results (W1-RAN through W5-RAN, all unique).
```

### Transcript evidence (read, not run)

Session tree under
`~/.pi/agent/sessions/--Users-Ashish-SynologyDrive-Projects-Pi-teamflow-pi--/2026-11-06T18-29-41-784Z_01a1b21f-a916-76d2-8e2b-92c0738a1d5c/`:

- Main session's child run `453729e6-…` (spike2-a, started 18:30:04.395Z);
  under it, exactly five worker runs:
  - `ed685fce-…` start 18:30:20.104Z
  - `8419bd7c-…` start 18:30:20.119Z
  - `74654a99-…` start 18:30:20.127Z
  - `df142fc2-…` start 18:30:20.148Z
  - `67ba12ca-…` start 18:30:20.150Z
  — all five started within a 46 ms window, i.e. one concurrent batch.
- spike2-a's `session.jsonl` has one `subagent` tool result, verbatim
  (abridged):

  ```
  Run fan-out: 6/64 used, 58 remaining
  Workflow completed.
  Return: {
    "ok": true,
    "children": [
      { "key": "task-1", "agent": "spike2-w1", "ok": true, "output": "\n\nW1-RAN" },
      { "key": "task-2", "agent": "spike2-w2", "ok": true, "output": "\n\nW2-RAN" },
      { "key": "task-3", "agent": "spike2-w3", "ok": true, "output": "\n\nW3-RAN" },
      { "key": "task-4", "agent": "spike2-w4", "ok": true, "output": "\n\nW4-RAN" },
      { "key": "task-5", "agent": "spike2-w5", "ok": true, "output": "\n\nW5-RAN" }
    ]
  ```

### Observed

- **Done check passes: one report naming all five results**, produced after
  all five finished (`async: false` blocked spike2-a until the batch settled).
- The built-in `parallel` resource works from a **child agent** that has
  only `tools: subagent` plus `allowedAgents`; the capability ceiling did
  not block any of the five (all five are in the allowlist).
- Results come back **ordered by task order** with `ok` and `output` per
  child; child `output` values carry two leading newlines (message framing
  around the child's text) — a formatting detail to expect when parsing
  child outputs.
- Fan-out counter: `6/64` after the batch (the parent run plus five).
- The whole chain (main → spike2-a → five workers) completed inside one
  headless `pi -p` process.

**Status: DONE** (run 2026-11-06T18:29Z–18:31Z)

## Spike 3 — Resume

**Question.** Main spawns A, A returns, main runs `resume` on A with a
message. Does the revived A remember its first task? Mechanism facts
re-read on 0.86.0: a top-level `{action:"resume"}` is detached and returns
a background-run receipt (`PS/docs/tool-reference.md:195`); it revives
"paused, completed, or failed async/foreground child" by starting a new
child from the stored session file, which requires a persisted `.jsonl`
(`tool-reference.md:376,381`).

**Done check.** A's reply shows it remembers its first task.

### Setup

One throwaway agent in user scope (`~/.pi/agent/agents/spike3/`, deleted
after the run):

```markdown
---
name: spike3-a
description: Spike 3 memory agent (to be resumed after it finishes)
---

You are spike3-a in a porting spike. Remember everything the user tells you
in this conversation, especially any code word. If asked for the code word,
answer with exactly: CODE-<the code word>
```

### Command

Same environment as spike 1 (from
`/Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi`). The main prompt
drives three steps: (1) spawn `spike3-a` with `async:false`, task "Remember
the code word ALPHA-7 for the rest of this conversation. Reply with exactly:
FIRST-TURN"; (2) from the result's id, call `subagent({action:"resume", id,
message})` with message "What was the code word I told you to remember on
your first turn? Reply with exactly: CODE-<the code word>"; (3) end the turn
right after step 2; when the completion notice arrives, quote the revived
child's exact reply and add a `VERDICT:` line.

```sh
env -u PI_MODEL -u PI_PROVIDER -u PI_REASONING_LEVEL \
    -u PI_SESSION_ID -u PI_SESSION_FILE \
  pi -p "Step 1: Use the subagent tool with async:false to launch the agent spike3-a with the task: Remember the code word ALPHA-7 for the rest of this conversation. Reply with exactly: FIRST-TURN
Step 2: From the step 1 result, find the run id (the id after 'Mission:'). Then call the subagent tool with action 'resume', that id, and the message: What was the code word I told you to remember on your first turn? Reply with exactly: CODE-<the code word>
Step 3: The resume runs in the background and returns a receipt immediately. Right after step 2, end your turn with the single line: RESUME-SENT <the run id>. When the completion notice for that resumed run arrives, your final message must contain: (a) the revived child's exact reply, quoted; (b) one line starting with 'VERDICT:' stating whether it remembered the code word ALPHA-7. If the notice does not include the child's reply, first call the subagent tool with action 'status', that id, and options {view: 'transcript'}, then quote its final reply." \
    --model vllm/nvidia/Qwen3.8-27B-NVFP4 --thinking off
```

### Output

Main session final message:

```
Spike 3 result — the resume worked and the revived child remembered.

(a) The revived child's exact reply, quoted:

> CODE-ALPHA-7
>
> Confirmed from the first turn of this conversation: the code word you asked
> me to remember was ALPHA-7.

(b) VERDICT: YES — spike3-a remembered the code word ALPHA-7 across the
resume; it answered `CODE-ALPHA-7` exactly as the protocol required.

Notes for the record: the id after `Mission:` in the synchronous result is
the **mission** id, which `resume` rejects ("Async run not found"); the
resumable target is the run id inside the mission record
(`86906f5e-924a-4778-ba7b-de294316b748`). Reviving it produced a new
background run `fafa4813-d587-4eac-8ba1-6f3f6248b33e`, and its completion
notice included the child's final reply directly.
```

### Transcript evidence (read, not run)

Main session file
`~/.pi/agent/sessions/--Users-Ashish-SynologyDrive-Projects-Pi-teamflow-pi--/2026-11-06T20-43-09-228Z_01a1b299-d82b-70c6-8aed-763268f65f51.jsonl`
and its child run `86906f5e-…/run-0/session.jsonl`:

1. Blocking spawn result, verbatim (abridged):
   `Run fan-out: 1/64 used, 63 remaining` → `FIRST-TURN\n\nI've stored the
   code word (ALPHA-7) for the rest of this conversation. …` → `Mission:
   c96aed16-f8a3-40cb-8854-e84da1870e38 (completed)`.
2. `resume` with the mission id: `Async run not found for
   'c96aed16-f8a3-40cb-8854-e84da1870e38'.` The model then read the mission
   file `~/.pi/agent/missions/projects/9dfda7a7…/c96aed16-….json` and took
   `runs[0].runId = 86906f5e-…`.
3. `resume` with the run id — detached receipt, verbatim (abridged):
   `Revived foreground subagent from 86906f5e-…. Revived run:
   fafa4813-d587-4eac-8ba1-6f3f6248b33e. Agent: spike3-a. Session:
   …/86906f5e-…/run-0/session.jsonl. Async dir: /var/folders/…`
4. The main model ended its turn. A `custom_message` entry with
   `customType: "subagent-notify"` then arrived, verbatim:

   ```
   Background task completed: **spike3-a**

   spike3-a:


   CODE-ALPHA-7

   Confirmed from the first turn of this conversation: the code word you
   asked me to remember was ALPHA-7.

   Retention-managed async directory: /var/folders/…/async-subagent-runs/fafa4813-…

   Session file: …/86906f5e-…/run-0/session.jsonl

   Parent action: Read the saved results above and resume the
   already-authorized parent task, or report completion. If approval is
   required, explicitly ask the user. Do not silently yield, rerun
   completed work, or infer new authorization.
   ```

   This notice started a new assistant turn inside the **same** headless
   `pi -p` process, which produced the final report above.
5. Original run's canonical session file
   (`86906f5e-…/run-0/session.jsonl`) contains **both** turns: the first
   task/reply and the revived turn. The revived child's task text begins:
   `You are reviving a previous subagent conversation.\n\nOriginal run:
   86906f5e-…\nOriginal agent: spike3-a\nOriginal session file: …`
6. Revived run's meta
   (`subagent-artifacts/fafa4813-…_spike3-a_meta.json`):
   `parentSessionId` = the main session id, `agent: spike3-a`,
   `model: vllm/nvidia/Qwen3.8-27B-NVFP4`, `exitCode: 0`.

### Observed

- **Done check passes: the revived child remembered the first task**
  (`CODE-ALPHA-7`, "Confirmed from the first turn of this conversation").
- Resume mechanics confirmed as documented: a **new child** seeded from the
  stored session; the revived turn is **appended to the same canonical
  session file**, so context accumulates across repeated resumes — the
  manager-resuming-impl-lead loop the plan risks should carry context.
- The whole headless sequence works in one `pi -p` process: blocking spawn →
  detached resume receipt → turn ends → `subagent-notify` completion notice
  (with the child's final reply inline) starts the next turn; Pi's
  headless `agent_end` auto-drain kept the process alive until it was
  processed (`PS/docs/configuration.md:407`). The teamflow pattern "end
  your turn, continue on the completion notice; never poll" holds headless.
- **Gotcha for Phase 4 prompts:** the id printed as `Mission:` in a
  blocking spawn result is the **mission** id; `resume` needs the **run** id,
  which lives in `~/.pi/agent/missions/projects/<hash>/<mission-id>.json`
  (`runs[].runId`) or in the run receipt/notice.
- Foreground (`async:false`) children are resumable (receipt says "Revived
  foreground subagent").
- Model behaviour, not Pi: spike3-a's first reply added extra text after
  `FIRST-TURN`; the revived reply added the "Confirmed …" sentence after
  `CODE-ALPHA-7`. The protocol markers came through exactly.

**Status: DONE** (run 2026-11-06T20:43Z–20:46Z)

## Spike 4 — Worktree

**Question.** `subagent({…, worktree: true})` — is the child's `pwd` a git
worktree? Where does it live, and what is its branch name? (Matters for
what `tf setup` needs to gitignore.) Mechanism facts re-read on 0.86.0:
default dedicated root is `{dirname(repoRoot)}/worktrees`; leaf is
`{root}/{projectName}/pi-worktree-{runId}-{index}`; branch prefix defaults
to `pi-subagents/`; the source checkout must be clean; cleanly captured
temporary worktrees and branches are removed after the child
(`PS/docs/configuration.md:628-648`, `PS/docs/workflows.md:500`). Worktrunk
is not installed on this machine, so provider `auto` used Pi's native Git
implementation (`configuration.md:644`).

**Done check.** The child's `pwd` is a git worktree; note where it lives and
its branch name.

### Setup

One throwaway agent in user scope (`~/.pi/agent/agents/spike4/`, deleted
after the run): `tools: bash`, body telling it to run `pwd`,
`git rev-parse --abbrev-ref HEAD`, `git worktree list` and report each
output verbatim, then an `IS-WORKTREE:` line. Source checkout was clean
(`git status --porcelain` empty, HEAD at `78ddefb`).

### Command

```sh
cd /Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi
env -u PI_MODEL -u PI_PROVIDER -u PI_REASONING_LEVEL \
    -u PI_SESSION_ID -u PI_SESSION_FILE \
  pi -p "Use the subagent tool to launch the agent spike4-a with worktree set to true and async set to false, with the task: Run these bash commands and report each output verbatim, labelled: 1. pwd  2. git rev-parse --abbrev-ref HEAD  3. git worktree list. Then end with one line starting with IS-WORKTREE: answering yes if you are inside a git worktree that is not the main checkout, no otherwise.
Your final message must quote the child's full report verbatim." \
    --model vllm/nvidia/Qwen3.8-27B-NVFP4 --thinking off
```

### Output

Child's report, verbatim (run `b44ee6c8-4c48-477f-ac91-ea8ba4552cd5`):

```
1. pwd:
/Users/Ashish/SynologyDrive/Projects/Pi/worktrees/teamflow-pi/pi-worktree-b44ee6c8-4c48-477f-ac91-ea8ba4552cd5-0

2. git rev-parse --abbrev-ref HEAD:
pi-subagents/spike4-a-Run-these-bash-commands-and-report-each-output-verbatim-labelled-1.-pwd-2.-git-4393845c-b44ee6c-712f-s0-t0

3. git worktree list:
/Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi  78ddefb [main]
/Users/Ashish/SynologyDrive/Projects/Pi/worktrees/teamflow-pi/pi-worktree-b44ee6c8-4c48-477f-ac91-ea8ba4552cd5-0 78ddefb [pi-subagents/spike4-a-…]

IS-WORKTREE: yes — cwd matches the second entry in `git worktree list`, a
linked worktree, while the main checkout is …/teamflow-pi on `main`.
```

Parent-side verification after the run (ran):

- `git worktree list` → only the main checkout (`78ddefb [main]`).
- `git branch --list 'pi-subagents/*'` → empty.
- `/Users/Ashish/SynologyDrive/Projects/Pi/worktrees/teamflow-pi/` → still
  exists but is empty (dedicated root outlives the leaf).
- Artifacts in the project session dir:
  `subagent-artifacts/b44ee6c8-…_spike4-a_0_{input,output,meta,transcript}`
  (note the `_0_` fan-out index in the names).

### Observed

- **Done check passes:** the child started in a managed linked worktree.
- **Location:** the documented default —
  `{dirname(repoRoot)}/worktrees/{projectName}/pi-worktree-{runId}-{index}`
  = `/Users/Ashish/SynologyDrive/Projects/Pi/worktrees/teamflow-pi/pi-worktree-<runId>-0`.
  A **sibling of the repository checkout, not inside it** — so
  `tf setup` needs no `.gitignore` entry in the repo itself under default
  config (only if a user points `worktreeBaseDir` inside the checkout, which
  pi-subagents rejects anyway: unsafe locations fail setup,
  `configuration.md:636`).
- **Branch name:** `pi-subagents/` prefix + agent name + sanitized task
  text + run/fan-out suffixes, e.g.
  `pi-subagents/spike4-a-Run-these-bash-commands-and-report-each-output-verbatim-labelled-1.-pwd-2.-git-4393845c-b44ee6c-712f-s0-t0`.
  Long; anything that parses branch names should match on the prefix.
- **Auto-cleanup confirmed:** after the child finished, the worktree and
  branch were removed from `git worktree list` and `git branch`; only the
  empty dedicated-root directory remains. Artifacts (output/transcript/meta)
  persist in `subagent-artifacts/`.
- The worktree branched from the clean source HEAD (`78ddefb`) — same
  commit as the main checkout in `git worktree list`.

**Status: DONE** (run 2026-11-06T21:08Z–21:11Z)

## Spike 5 — `tf` on PATH (D4)

**Question.** How do agents find `tf`? The plan's setup (D4): a bash
`spawnHook` extension, verified in the main session and in a foreground and
a background child. Mechanism facts re-read: an extension registers a
replacement `bash` tool built with `createBashTool(cwd, { spawnHook })`;
registering a tool with the same name as a built-in replaces it without a
warning (`PD/docs/extensions.md:2344`, example
`PD/examples/extensions/bash-spawn-hook.ts`); `@earendil-works/pi-coding-agent`
imports map to Pi's own copy, no install needed (`extensions.md:166`).

**Done check.** `command -v tf` succeeds in all three.

### Setup

- Stub `/tmp/spike5-tf/bin/tf`: `#!/bin/sh` + `echo "TF-STUB-OK from $0"`.
  The launcher's shell `PATH` did **not** contain `/tmp/spike5-tf/bin`
  (checked) — the only source of the stub on PATH is the hook.
- Extension `/tmp/spike5/spike5-tf.ts` (user-scope copy later):

  ```typescript
  import { createBashTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
  const TF_DIR = "/tmp/spike5-tf/bin";
  export default function (pi: ExtensionAPI) {
    const cwd = process.cwd();
    const bashTool = createBashTool(cwd, {
      spawnHook: ({ command, cwd: c, env }) => ({
        command, cwd: c, env: { ...env, PATH: `${TF_DIR}:${env.PATH ?? ""}` },
      }),
    });
    pi.registerTool({
      ...bashTool,
      execute: async (id, params, signal, onUpdate, _ctx) =>
        bashTool.execute(id, params, signal, onUpdate),
    });
  }
  ```

- Two throwaway agents in `~/.pi/agent/agents/spike5/` (deleted after):
  `spike5-fg` (`tools: bash` + `extensions: <path to the extension>`) and
  `spike5-bg` (`tools: bash` only, no `extensions` key).
- The main prompt: run `command -v tf && tf` in main bash; spawn fg with
  `async:false`; spawn bg with `async:true`; end the turn; on the completion
  notice emit `MAIN:/FG:/BG:` lines plus a `VERDICT:` line.

### Attempt 1 — extension only via the parent's CLI flag (failed)

Loaded with `pi -p … --extension /tmp/spike5/spike5-tf.ts`:

- **MAIN:** `/tmp/spike5-tf/bin/tf` + `TF-STUB-OK …` (exit 0) — hook active
  via the `-e` load.
- **FG** (run `bfcb181e-…`): same — the frontmatter `extensions:` list
  loaded the file in the in-process child. Its meta:
  `launchResolvedExtensions.configured: [sha256:6818f7a0…]`,
  `disableAmbientExtensions: true`.
- **BG** (run `27dc724e-…`): **failed** — `command -v tf` exit 1, no output.
  The child's own diagnostic dump showed the default system PATH
  (`/Users/Ashish/.pi/agent/bin:/Users/Ashish/.local/bin:/opt/homebrew/bin:…`)
  with no `/tmp/spike5-tf/bin`. Its meta: `configured: []`,
  `effective: [runtime sha only]`, `disableAmbientExtensions: false`.

**Diagnosis (docs, read on 0.86.0):** a background child is a session
inside the *detached runner process*, which loads ambient extensions by its
**own** normal Pi extension discovery; a parent CLI `-e` extension is not
part of that discovery (`PS/docs/agents.md:574`). `launchResolvedExtensions`
is "parent-resolved launch intent only" and does not list ambient
extensions the child's process discovers itself
(`PS/docs/observability.md:252`).

### Attempt 2 — extension in user scope (passed)

Extension copied to `~/.pi/agent/extensions/spike5-tf.ts` (auto-discovery
location, `extensions.md:9`); the fg agent's `extensions:` list updated to
that path; the same main prompt with **no** `-e` flag:

```
MAIN:
/tmp/spike5-tf/bin/tf
TF-STUB-OK from /tmp/spike5-tf/bin/tf

FG:
/tmp/spike5-tf/bin/tf
TF-STUB-OK from /tmp/spike5-tf/bin/tf

BG:
/tmp/spike5-tf/bin/tf
TF-STUB-OK from /tmp/spike5-tf/bin/tf

VERDICT: All three succeeded …
```

The BG child's own report (run `1cbf23a6-…`, exit 0, meta
`launchResolvedExtensions` unchanged in shape — ambient loads are not part
of the parent-resolved intent): "`/tmp/spike5-tf/bin` is the **first entry
of PATH** in this background child's shell environment".

### Observed

- **Done check passes (attempt 2):** `command -v tf` succeeds in the main
  session, the foreground child, and the background child.
- **The spawnHook must be installed where each process can discover it:**
  user scope `~/.pi/agent/extensions/` (or a settings package) reaches the
  main session *and* the detached background runner by auto-discovery. A
  `--extension`/`-e` path reaches only the main session (plus children that
  list it explicitly).
- **Foreground children never load ambient extensions**
  (`agents.md:574`): every teamflow role that needs `tf` in a foreground
  child must list the extension in its frontmatter `extensions:` (or use a
  path-like `tools:` entry, `agents.md:579`). Background children get it
  automatically from discovery.
- The hook is session-scoped PATH injection (`spawnHook` env), so it works
  regardless of the process PATH the runner starts with; no shell-profile
  or launcher changes needed.
- Off-script model behaviour (attempt 1, noted for the record): the main
  model — though never asked to — wrote its own spike record with a wrong
  setup narrative (claiming no extension was loaded and that the stub came
  from the launching shell's PATH), and committed and pushed it (8a4c898).
  This section supersedes that text. Attempt 2's prompt ended with "Do not
  write files or commit anything; just report" and the model complied.

**Status: DONE** (attempt 1 run 2026-11-06T21:21Z–21:32Z;
attempt 2 run 2026-11-06T21:39Z–21:42Z)

## Spike 6 — skill access from a child

**Question.** Can an agent launched by Pi read the `skills/workflow`
skill? Skills are read-only, so the test is purely: the child loads the
skill and quotes it.

**Done check.** The reply quotes a line from
`skills/workflow/SKILL.md`.

### Setup

- Skill installed at the user-scope discovery location
  `~/.pi/agent/skills/workflow/SKILL.md` — a read-only copy of the real
  teamflow skill (reference checkout at `423109c`, 584 lines, frontmatter
  `name: workflow`). Deleted after the run. (This mirrors the Phase 2 packaging: the
teamflow package installs its skills into a Pi-discoverable directory.)
- Throwaway agent `~/.pi/agent/agents/spike6/spike6-a.md` (deleted after):
  `tools: read, bash`, `skills: workflow`.

Mechanism facts re-read in pi-subagents 0.86.0
(`PS/docs/agents.md:620–666`, the Skills section): skills are `SKILL.md`
files; the child prompt gets metadata + absolute location, and the child
reads the file when the task matches (lines 622, 646–659); discovery order
is project config → packages → user `~/.pi/agent/skills/` → user settings
(lines 624–631); frontmatter `skills` selects specific skills "regardless
of `inheritSkills`" (line 648); with an explicit `tools` allowlist plus
resolved skills, `read` is added automatically for that run (line 662);
missing skills warn, they don't fail (line 664).

### What was run (2026-11-06T22:22Z–22:24Z)

Headless main; task to the child: load the workflow skill and report (1)
the exact two-invariants sentence verbatim, (2) the verbatim `## Teams`
table row describing the manager.

Child's reply (verbatim, run `92230935-…`, exit 0, meta
`skills: ["workflow"]`):

```
(1) Two invariants: **`main` is always green**, and **nothing merges on its
author's say-so.**

(2) | manager | the three leads | Routes goals, runs every handoff
(including each PR's rounds between impl-lead and review-lead), counts
each PR's rounds, governs the optional review-implement loop |
```

### Verified against the source

`grep -n` on the reference file: line 16 `Two invariants: **`main` is
always green**, and **nothing merges on its` and line 29 the manager table
row — both match the child's quotes character-for-character (the invariants
sentence wraps across lines 16–17 in the source).

### Observed

- **Done check passes:** the child loaded the user-scope skill and quoted
  the body verbatim; the run's meta records the selection
  (`skills: ["workflow"]`).
- The `skills:` frontmatter selection worked with the ambient user skills
dir containing ~36 other pre-existing skills; the child received exactly
the selected skill.
- No `inheritSkills` setting was needed; the explicit selection is the
durable mechanism (agents.md:648).

**Status: DONE** (run 2026-11-06T22:22Z–22:24Z)

## Spike 7 — manager startup via `pi --teamflow` (D3)

**Question.** Can the manager be started with a dedicated CLI flag that an
extension registers, with the manager system prompt injected in
`before_agent_start`? (Fallback if the flag route is not possible:
`--append-system-prompt`.)

**Done check.** The session reports that it is the manager.

### Setup

Extension installed at user scope
`~/.pi/agent/extensions/spike7-manager.ts` (deleted after the run):

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
export default function (pi: ExtensionAPI) {
  pi.registerFlag("teamflow", {
    description: "Start as the teamflow manager",
    type: "boolean",
    default: false,
  });
  pi.on("before_agent_start", (event) => {
    if (pi.getFlag("teamflow")) {
      event.systemPromptOptions.sections["teamflow_manager"] =
        "You are the teamflow manager: the single session that spawns the " +
        "three leads (research-lead, impl-lead, review-lead), routes goals, " +
        "runs every handoff, and counts each PR's review rounds. You never " +
        "implement, research, or review code yourself.";
    }
  });
}
```

Mechanism facts read (Pi 1.5.0 docs):

- `pi.registerFlag(name, { description, type: "boolean", default })` and
  `pi.getFlag(name)` after load (in the factory `getFlag` returns the
default) — `PD/docs/extensions.md:1862`.
- `before_agent_start` hands a mutable `event.systemPromptOptions` with
  `sections` (custom XML-wrapped sections keyed by tag name) and
  `appendSystemPrompt` — `PD/docs/extensions.md:615–659`. Chose `sections`
  over `appendSystemPrompt` because the docs prefer changing `sections` /
  `selectedTools` / `promptGuidelines` (Pi diffs only the changed section,
  keeping the cached prefix) over replacing the whole prompt.
- `appendSystemPrompt` is a `string`, not an array
  (`PD/dist/core/system-prompt.d.ts:43`) — noted in case the real
  extension appends instead.
- `pi --help` lists extension-registered flags
  (`PD/docs/cli.md:248`).

### What was run (2026-11-06T23:08Z)

Positive — `pi --teamflow -p "State in one line what role you are in this
session. If you are not a teamflow manager, say exactly: NOT-MANAGER. …"`:

> I am the teamflow manager: the single session that spawns the three
> leads, routes goals, runs every handoff, and counts each PR's review
> rounds — never implementing, researching, or reviewing code myself.

Negative control (same command **without** `--teamflow`):

> NOT-MANAGER.

### Transcript evidence

- The positive session file
  (`2026-11-06T23-08-33-…_01a1b31e-….jsonl`) contains the section
  rendered into the system prompt:
  `"teamflow_manager":"<teamflow_manager>\nYou are the teamflow manager: …`.  The model's reply quotes it ("and it says 'You are the
teamflow manager: the single session that spawns the three leads…'").
- The negative session file
  (`2026-11-06T23-08-56-…_01a1b31f-….jsonl`) contains **zero** occurrences
  of `teamflow_manager` — the flag gate works both ways.

### Observed

- **Done check passes:** with `--teamflow` the session reports the manager
  role verbatim from the injected section; without it, `NOT-MANAGER`.
- `pi --help` showed `--teamflow  Start as the teamflow manager` from the
  user-scope extension — flag registration via user-scope discovery works.
- The section approach (vs `appendSystemPrompt` string or full-prompt
  replace) is the D3 mechanism: flag-gated, diffable, cache-friendly.
- The real teamflow extension can combine this with the D4 `spawnHook`
bash override in the same user-scope extension file.

**Status: DONE** (run 2026-11-06T23:08Z)

## Spike 8 — Ponytail

**Question.** Can a child agent run with the ponytail skill and acknowledge
it? (D6: ponytail is installed separately, not part of the teamflow
package.)

**Done check.** The reply acknowledges ponytail mode.

### Setup

- Ponytail already installed at user scope before Phase 0:
  `pi install git:github.com/DietrichGebert/ponytail` (user
  `settings.json` `packages` lists `git:github.com/DietrichGebert/ponytail`).
The package bundles **both** a skill
  (`skills/ponytail/SKILL.md`, `name: ponytail`) and a `pi-extension`
  whose `before_agent_start` injects `sections.ponytail` ("PONYTAIL MODE
ACTIVE — level: full …") — the same section mechanism as spike 7
(`…/ponytail/pi-extension/index.js:242`).
- Throwaway agent `~/.pi/agent/agents/spike8/spike8-a.md` (deleted after):
  `tools: read, bash`, `skills: ponytail`.

### What was run (2026-11-06T23:14Z)

Headless main; child (run `eed9a112-…`, exit 0, meta
`skills: ["ponytail"]`) asked in one sentence what mode it is running in,
based on its configured skills.

Child's reply (verbatim):

> I'm running in **ponytail mode** (lazy senior dev mode, "full" level by
> default) — the smallest change that fully solves the task, with a reply a
> busy human understands in one read.
>
> I skipped anything else — no code was touched for this question — and
> there's no risk to know beyond ponytail being active session-wide until
> told to stop.

### The plan's exact done check (2nd run, 2026-11-06T23:21Z)

The plan names `skills: ponytail-audit` with a verbatim quote as the check.
Second throwaway agent `spike8-b` (`tools: read, bash`,
`skills: ponytail-audit`); child (run `be88ddad-…`, exit 0, meta
`skills: ["ponytail-audit"]`) replied:

> Loaded the ponytail-audit skill from
> `/Users/Ashish/.pi/agent/git/github.com/DietrichGebert/ponytail/skills/ponytail-audit/SKILL.md`.
>
> One line from its body, verbatim:
>
> > One-shot report, changes no code.

Verified: `One-shot report, changes no code.` is line 103 of that
`SKILL.md` — the final line of the body, exactly as the child stated.

### Transcript evidence

- The child's prompt contains the `<available_skills>` catalog entry for
  `ponytail` (name + description), and the child's first tool call was
  `read` of
  `/Users/Ashish/.pi/agent/git/github.com/DietrichGebert/ponytail/skills/ponytail/SKILL.md`;
it answered from that file.
- The child's prompt contains **zero** `PONYTAIL MODE ACTIVE` occurrences:
  the package's section-injecting extension is ambient in the **main**
  session only — foreground children never load ambient extensions
  (spike 5, `agents.md:574`).
- The reply's closing "I skipped … / no risk" line is the skill's own
  required convention — evidence the skill was read and followed, not just
  name-dropped.

### Observed

- **Done check passes** (both runs): the child loaded its `skills:` skill
  from the catalog and acknowledged the mode accurately (including the
default level and stop-switch from the skill body); the plan-exact run
  quoted line 103 of `ponytail-audit/SKILL.md` verbatim.
- For teamflow-pi: the manager (the main session) receives ponytail's
  section ambiently from the installed package; any child role that should
  run ponytail gets it via the `skills:` frontmatter (catalog + read).
  A child would only need the section itself if the frontmatter also
  listed the package's extension — not required here.

**Status: DONE** (runs 2026-11-06T23:14Z and 23:21Z)

## Phase 3, Part 1 — `tf` on PATH via spawnHook (D4)

Build record for [extension-spec.md](extension-spec.md) Part 1. The check
below is the spec's; the lib tests are the spec's rule "write the test
first and see it fail". Versions: Pi 1.5.0, pi-subagents **0.87.0** (up
from 0.86.0 at spike time), model `nvidia/Qwen3.8-27B-NVFP4` (default for
these `pi -p` runs; read from the session files), Node v26.13.0.

### Files

- `extensions/teamflow-lib.test.ts` — 3 tests for `pathWithBin`.
- `extensions/teamflow-lib.ts` — `pathWithBin(path, bin)`: `bin` + `:` +
  old `PATH`, or just `bin` when the old one is empty/undefined.
- `extensions/teamflow.ts` — replaces the `bash` tool:
  `createBashTool(process.cwd(), { spawnHook })` with
  `env: { ...env, PATH: pathWithBin(env.PATH, binDir) }`, where
  `binDir = join(packageRoot, "bin")` and
  `packageRoot = join(dirname(fileURLToPath(import.meta.url)), "..")`.
  Shape copied from `PD/examples/extensions/bash-spawn-hook.ts`; package
  root from `PD/examples/extensions/doom-overlay/wad-finder.ts:7`.

### Test-first

`node --test extensions/teamflow-lib.test.ts` before the lib existed:
`ERR_MODULE_NOT_FOUND` for `extensions/teamflow-lib.ts`, `fail 1`. After
writing the lib: `tests 3, pass 3, fail 0`.

### The spec's check (run 2026-11-10T03:54Z)

```
$ pi -e ./extensions/teamflow.ts -p "Run: command -v tf"
```

Output:

> `tf` resolves to `/Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi/bin/tf` — the project's own script is on your PATH.

A path ending in `bin/tf`. **Pass.**

### Negative control (run 2026-11-10T04:02Z)

Same prompt without `-e`: `command -v tf` → exit 1, no output (`tf` not on
PATH). The hook is the only source of `tf` on PATH.

### Supplementary (run 2026-11-10T04:03Z)

`pi -e ./extensions/teamflow.ts -p "Run exactly: echo \$(command -v tf) &&
head -1 <<< \"\$PATH\" && tf mode"` printed:

```
/Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi/bin/tf
/Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi/bin:/Users/Ashish/.pi/agent/bin:/Users/Ashish/.local/bin:/Users/Ashish/Library/Python/3.12/bin:/opt/homebrew/bin:...
local
```

`bin/` is the first PATH entry, and `tf` executes (`tf mode` → `local`).

### Observed

- Part 1 done check passes in the main session via `pi -e`.
- API confirmed at the cited lines: `createBashTool(cwd, { spawnHook })`
  (`PD/dist/core/sdk.d.ts:80`); `BashSpawnContext.env` is
  `NodeJS.ProcessEnv`, so `env.PATH` may be undefined
  (`PD/dist/core/tools/bash.d.ts:64-70`) — the lib's signature matches.
- `node --test` runs `.ts` test files directly on Node v26.13.0, and the
  lib import must keep its `.ts` extension (spec's Node-docs note, now
  exercised).
- Scope caveat for later parts (spike 5): `-e` reaches only the main
  session; when the package is installed, the spawnHook must be discoverable
  by the detached background runner (user scope or the settings package).

**Status: DONE** (runs 2026-11-10T03:54Z–04:05Z)

## Phase 3, Part 2 — `--teamflow` flag and the manager prompt (D3)

Build record for [extension-spec.md](extension-spec.md) Part 2. Versions:
Pi 1.5.0, pi-subagents 0.87.0, model `nvidia/Qwen3.8-27B-NVFP4` (read from
the session files), Node v26.13.0.

### Files

- `manager.md` — the Phase 3 placeholder line (spec: "a placeholder line
  is enough for Phase 3; Phase 4 writes it"):
  `Your name is teamflow-manager.`
- `extensions/teamflow-lib.ts` — `appendManagerPrompt(systemPrompt,
  manager)`: the system prompt, two newlines, then the manager text.
- `extensions/teamflow-lib.test.ts` — 4th test: the result starts with the
  original, ends with the manager text, and equals
  `original + "\n\n" + manager`.
- `extensions/teamflow.ts` — `pi.registerFlag("teamflow", {
  description: "Start as the teamflow manager", type: "boolean",
  default: false })`; in `before_agent_start`, if
  `pi.getFlag("teamflow")` is on, returns
  `{ systemPrompt: appendManagerPrompt(event.systemPrompt,
  readFileSync(manager.md)) }`. Shape from
  `PD/examples/extensions/preset.ts:388-402` (flag +
  `systemPrompt: event.systemPrompt + "\n\n" + ...`), per the spec.
  `manager.md` is read in the handler when the flag is on, so without the
  flag the extension changes nothing even if the file were missing.

### Test-first

New test run before the lib function existed: `fail 1` (import error).
After: `tests 4, pass 4, fail 0`.

### The spec's check (runs 2026-11-10T04:40Z)

```
$ pi -e ./extensions/teamflow.ts --teamflow -p "What is your name?"
```

> My name is teamflow-manager.

Negative control — same command without `--teamflow`:

> I'm Qwen, an AI assistant developed by Alibaba Group.

**Pass** (with: answers with it; without: does not).

### Regression and observations (2026-11-10T04:41Z)

- Part 1 still works in the same extension file:
  `pi -e ./extensions/teamflow.ts -p "Run: command -v tf"` prints
  `/Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi/bin/tf`.
- `pi -e ./extensions/teamflow.ts --help` lists
  `--teamflow  Start as the teamflow manager`.
- Cited lines re-verified: `getFlag` returns the default in the factory,
  so the flag is read inside the handler
  (`PD/docs/extensions.md:1862-1880`); `before_agent_start`'s
  `event.systemPrompt` is the chained prompt for this handler
  (`PD/docs/extensions.md:615-657`).
- Note for Phase 4/5: returning `systemPrompt` replaces the whole prompt
  for the run (docs: a cache miss when it changes); spike 7 recorded the
  `systemPromptOptions.sections` alternative as cache-friendly. The spec
  chose the replacement shape (matching its cited example); the manager
  prompt is constant per session, so the change happens once.

**Status: DONE** (runs 2026-11-10T04:40Z–04:41Z)

### Model-robustness probe of the Part 2 check (2026-11-10T04:51Z–04:52Z)

Question: does the name check depend on which model answers? Probe with a
second model — local `llama/gemma-4-12b-it` (Gemma 4 12B GGUF Q4_0 on a
llama.cpp OpenAI-compatible endpoint at `localhost:9931`, ctx 131072;
wired as a `llama` provider in `~/.pi/agent/models.json`, same pattern as
the existing `vllm` entry; the alias ID is used because the full ID
contains `:`, which collides with pi's `provider/id:thinking` syntax).
DeepSeek itself was not run: the `huggingface` provider is paywalled
(HTTP 402) and the `openrouter` key is stale (401 "User not found").

- Negative control, `pi -e ./extensions/teamflow.ts --model
  llama/gemma-4-12b-it -p "What is your name?"` →
  "I am a coding assistant running inside pi, a coding agent harness.
  I'm here to help you inspect files, run commands, and modify code."
  Not `teamflow-manager`. The session transcript
  (`2026-11-10T04-51-44-…jsonl`) has **zero** occurrences of the phrase in
  anything sent to the model.
- Positive control, same with `--teamflow` → "I am teamflow-manager."
  The session transcript (`2026-11-10T04-52-41-…jsonl`) contains the
  phrase once, inside the model's own thinking, which quotes the system
  prompt: "The system prompt says 'Your name is teamflow-manager.'"

Observed:

- The check's behaviour varies with the model's identity style (Qwen
  claims its brand; Gemma-4-12B claims no brand and answers from the
  system prompt), but the **mechanism is model-independent**: flag off,
  the handler returns `undefined`, and the transcript shows the prompt
  is unchanged.
- The model-independent arbiter is the transcript (system prompt
  content), the same evidence method spike 7 used — not the model's
  answer.
- Latent risk, not triggered here: the check runs with cwd = the
  teamflow-pi repo, where the phrase literally exists in `manager.md`,
  the lib test, and this file's quoted lines. A model that explores the
  repo before answering could find it and answer with it — a false
  control failure. The transcript check would still grade it correctly.

## Phase 3, Part 3 — spawn limits (D3)

Build record for [extension-spec.md](extension-spec.md) Part 3. Versions:
Pi 1.5.0, pi-subagents 0.87.0, model `nvidia/Qwen3.8-27B-NVFP4` (vllm),
Node v26.13.0. Runs 2026-11-10T17:2xZ–17:4xZ.

### The two unknowns, resolved before writing the part

**Agent names: plain.** Spike 1 already found it: no `package:` field, so
canonical names are plain (this file, Spike 1; the refusal text there names
plain agents). The ten names are teamflow's `agents/` minus `manager` (the
main session): `architect-reviewer`, `docs-reviewer`, `impl-lead`,
`implementer`, `quality-reviewer`, `research-lead`, `researcher`,
`review-lead`, `security-reviewer`, `simplicity-reviewer`.

**Import: npm dependency works; the ceiling takes effect.**

- Cited source verified: `PS/docs/extension-api.md:413-445` —
  `registerSubagentCapabilityCeiling({ sessionId, source, ceiling })`
  returns a handle with `update()` / `dispose()`; register with
  `ctx.sessionManager.getSessionId()` (a ceiling by session file path does
  not apply). `getSessionId(): string` at
  `PD/dist/core/session-manager.d.ts:253`.
- The registry (spec's "inferred, not run"):
  `globalThis[Symbol.for("pi-subagents.capability-ceiling.v1")]`, a Map of
  `sessionId → registrations` (`PS/bundle/chunk-QXASAHIA.js:4-13`); the
  launch path asserts
  `assertAgentAllowedByCapabilityCeiling(agentName, ceiling)` against
  `resolveCurrentSubagentCapabilityCeiling(currentSessionId)` after the
  unknown-agent check (`PS/bundle/chunk-OZCPYJEY.js:3013-3015, 6529-6554`).
- `package.json` now has `dependencies.pi-subagents: 0.87.0` (pinned to the
  installed copy's version) after `npm install`;
  `import … from "pi-subagents/capability-ceiling"` resolves from
  `extensions/`.
- **Cross-copy test, run:** one node process, both module copies — the
  dependency copy and Pi's installed copy
  (`~/.pi/agent/npm/node_modules/pi-subagents/bundle/capability-ceiling.js`).
  Dependency copy registers (source `teamflow`, ten agents) → installed
  copy resolves it (`sources = [teamflow]`, 10 agents, impl-lead allowed);
  installed copy registers → dependency copy resolves it; dependency copy
  `dispose()`s → installed copy resolves `undefined`. Registry key shared.
  The inference is run: in the one pi process that hosts both extension
  copies, our registration is visible to pi-subagents' tool code.
- `PI_SUBAGENT_CHILD` confirmed as `SUBAGENT_CHILD_ENV`
  (`PS/src/runs/shared/child-runtime-config.d.ts:15`).

### Test-first

Nine `spawnDecision` tests added: one per rule (child allowed; each of the
three leads allowed; `action: "resume"` allowed) plus a non-lead `agent`, a
lead inside `tasks`, a missing `agent`, and a lead with a `chain`. First
run: `fail 1` (import error). After implementing
`spawnDecision` in `extensions/teamflow-lib.ts`: **13/13 pass** (4 from
Parts 1–2 + 9 new).

### Files

- `extensions/teamflow-lib.ts` — `spawnDecision(input, isChild)`: child →
  allow; `action: "resume"` → allow; a lead with no `tasks`/`chain` field →
  allow; anything else → refusal naming the three leads (fails closed).
- `extensions/teamflow.ts` — `TEAMFLOW_AGENTS` (the ten plain names);
  `session_start` (flag on): dispose any previous handle, register the
  ceiling with `ctx.sessionManager.getSessionId()`, source `teamflow`;
  `session_shutdown`: `dispose()`; `tool_call` (flag on,
  `event.toolName === "subagent"`):
  `spawnDecision(event.input, process.env.PI_SUBAGENT_CHILD === "1")` →
  `{ block: true, reason }` or `undefined`. Handler shape from
  `PD/examples/extensions/permission-gate.ts:13-33`; `tool_call` block
  semantics from `PD/docs/extensions.md:971-1011`.
- `package.json` — `pi.extensions` now points at
  `./extensions/teamflow.ts`, not the `./extensions` directory: pi loads
  **every** `.ts` file in a declared directory as an extension, so the lib
  and the test file failed to load (the test file even executed its
  `node:test` `test()` calls at import). PD/docs/packages.md: "A file path
  loads one extension. A directory follows normal package discovery
  rules." This only surfaces for an installed package — `-e` always named
  the file.

### The spec's check (2026-11-10T17:23Z–17:25Z, `-e` mode)

Throwaway user-scope agents `implementer`/`impl-lead`
(`~/.pi/agent/agents/tfpart3/`, deleted after the run, Spike 1 pattern).

- `--teamflow`, launch `implementer` → refused, verbatim:
  `The teamflow manager may only launch the leads: research-lead,impl-lead,review-lead.` ✅
- `--teamflow`, launch `impl-lead` → launched; the child ran and replied.
  ✅ (Also live proof the ten-name ceiling does not over-block.)
- Without `--teamflow`, both launch. ✅

**Live ceiling evidence:** the flagged session's transcript records the
resolved ceiling on the `subagent` tool call —
`"capabilityCeiling": {"version":1,"allowedAgents":[…ten…],
"denyExtensions":false,"sources":["teamflow"]}`. The registration from our
dependency copy was consumed by pi-subagents' own tool code in the live
session.

### Phase 3 final gate — installed package (2026-11-10T17:3xZ)

`pi install ./` (personal scope). A local package loads from the resolved
path without copying, and Pi does not install its dependencies
(PD/docs/packages.md) — a fresh clone needs `npm install` before
`pi install ./`; `node_modules/` is git-ignored and the pinned dependency
plus lockfile make that deterministic. From a clean empty directory:

- `pi --teamflow -p "What is your name?"` →
  "My name is teamflow-manager." ✅ — one first attempt answered "Qwen"
  instead (its thinking cites a "system reminder" identity); the re-runs
  all passed (3/3) and a combined session answered the name **and**
  tripped the gate in one turn. Model non-determinism in the identity
  answer, not a mechanism failure — the transcript of every passing run
  shows the injected line, and the failing run's miss was the model
  choosing its built-in identity.
- `pi -p "Run: tf mode"` → `local` ✅
- `pi --teamflow -p "…launch implementer…"` → refused with our reason ✅

Install removed after the gate (`pi remove .`) so the package's `bin/`
does not prefix `PATH` for every session on this machine (it would
shadow `tf` in the source teamflow repo); `pi install ./` re-adds it.

**Status: DONE** (runs 2026-11-10T17:2xZ–17:4xZ)

### Phase 3 re-verification — full check suite re-run (2026-11-10T20:0xZ–20:2xZ)

Complete re-run of every Phase 3 check against the committed tree
(`b68ad98`; that commit adds only `skills/workflow/SKILL.md` and the
Phase 4 record, so no Phase 3 file changed since `2140fee`). Versions:
Pi 1.5.0, pi-subagents 0.87.0 (package dependency and installed copy,
both read from their `package.json`), model local vllm Qwen (the default
for these `pi -p` runs), Node v26.13.0. All `pi` runs stripped inherited
`PI_MODEL`/`PI_PROVIDER`/`PI_REASONING_LEVEL`/`PI_SESSION_ID`/
`PI_SESSION_FILE` and used `--no-session`.

**Fast checks.** `node --test extensions/teamflow-lib.test.ts` →
`tests 13, pass 13, fail 0`. `./scripts/gate.sh` → `Ran 138 tests … OK`,
table `shell scripts parse | pass`, `unit tests | pass`, `gate: green.`

**Part 1** — `pi -e ./extensions/teamflow.ts -p "Run exactly: command -v
tf; then print the output."` printed
`/Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi/bin/tf` ✅.

**Part 2** — with `--teamflow`: "I'm teamflow-manager, the main-session
manager for teamflow-pi." ✅; without the flag: "My name is Qwen." ✅.

**Part 3** (throwaway user-scope agents `implementer`/`impl-lead` in
`~/.pi/agent/agents/tfverify/`, deleted after the runs):

- `--teamflow`, launch `implementer` → refused, verbatim: `The teamflow
  manager may only launch the leads: research-lead,impl-lead,review-lead.`
  ✅
- `--teamflow`, launch `impl-lead` → child ran, final message `LEAD-RAN` ✅
- without `--teamflow`, launch `implementer` → child ran, `IMPL-RAN` ✅
- without `--teamflow`, launch `impl-lead` → child ran, `LEAD-RAN` ✅

**Final gate, installed package** — `pi install ./` from the package
directory; runs from a clean directory; `pi remove .` and the throwaway
agents removed after:

- `pi --teamflow -p "What is your name?…"` → "I'm teamflow-manager." ✅
- `pi -p "Run exactly: tf mode;…"` → first run from a non-git `mktemp` dir
  printed `tf: not inside a git repository` (exit 2); re-run from a clean
git repo (`git init -b main`) → `local` ✅. The "clean empty directory"
in the gate record above must have been a git repo: `tf mode` delegates to
`bin/teamflow-config` main(), which runs `git worktree list --porcelain`
and fails that message when not in one (`bin/teamflow-config:78`); no
`.pi/teamflow.json` falls back to `DEFAULTS` with `forge: "local"`.
- `pi --teamflow`, launch `implementer` → refused with our reason ✅
- `pi --teamflow`, launch `impl-lead` → child ran, `LEAD-RAN` ✅ (live
  ceiling on the installed package: no over-blocking)

**Result: all Phase 3 checks pass on the current tree.** One correction
for future phases: `tf mode` needs to run inside a git repo on the base
branch, not in any empty directory.

**Status: VERIFIED** (runs 2026-11-10T20:0xZ–20:2xZ)

## Phase 4, Task 1 — the workflow skill (2026-11-10T13:01Z)

`skills/workflow/SKILL.md` (698 lines), written new from the Phase 1
transcription `docs/teamflow/workflow-rules.md` (D1: not a file copy) —
rules §1–17 carry over as written, harness wording swapped, the swaps
listed in the skill's own §18 *Deltas*. Frontmatter: `name: workflow`,
`description: >` block saying when to load it.

Verification (all run by me):

- **Rule fidelity:** whitespace-normalized word-level diff of the
  skill's §1–17 against the transcription's §1–17. Every hunk is one of:
  an intended delta (entry point `pi --teamflow`, wait mechanism =
  pi-subagents foreground/async, tool names `edit`/`write`/`bash` +
  allowlists, `.pi/teamflow.json`, `package.json` as the version file,
  shipped paths, `pi update <source>`, `pi-subagents/*` cleanup, the
  port's `tests/test_tf_github.py` test names) or a dropped
  teamflow-internal reference (`#258 Dx`, `#259`, `#226`, the archived
  code-reviewer note, pointers to teamflow docs that do not exist in the
  port). No pipeline rule changed.
- **Facts behind the swapped wording** (read this session, not assumed):
  `pi --teamflow` (Spike 7 above; `pi --help`: "--teamflow Start as the
  teamflow manager"); pi-subagents worktrees auto-remove with
  `pi-subagents/` branch names (Spike 4); `tf setup` installs
  `templates/branch-ruleset.json` in `github` mode (read in `bin/tf`
  `cmd_setup` + `tests/test_tf_github.py`); port test names read in
  `tests/test_tf_github.py`.
- **Structure:** `node` check — frontmatter has `name: workflow` and a
  folded `description`; sections 1–18 present in order.
- **Pi loads it:** Pi 1.5.0, from a clean dir,
  `pi --skill skills/workflow --no-session -p "Reply with the single
  word: ok"` → `ok` (no frontmatter/load errors);
  `pi --skill skills/workflow --no-session -p "Is a skill with the name
  workflow available in this session? …"` → `yes` (registered in the
  session's skill list).

Model: local vllm Qwen (same as the Phase 3 gates).

**Status: DONE**

## Phase 4, Task 2 — the ten subagents + spawn table (2026-11-11T18:22Z)

Built `agents/` — ten subagent files (the manager is the main session, D3,
so it is not an agent). Two human decisions drove the shape:

1. **Canonical names are namespaced `teamflow.<name>`.** Every agent's
   frontmatter sets `package: teamflow`, so `name: researcher` registers
   as `teamflow.researcher` — it does not shadow pi-subagents' builtin
   `researcher`. Confirmed against the documented rule
   (`~/.pi/agent/npm/node_modules/pi-subagents/docs/agents.md:468`:
   "A file with `name: scout` and `package: code-analysis` registers as
   `code-analysis.scout`").
2. **The researcher gets the web tools from `pi-web-access@0.47.0`**
   (installed at user scope): `web_search` + `fetch_content` — the Pi
   equivalents of teamflow's `WebSearch`/`WebFetch`.

**Frontmatter (all ten):** `package: teamflow`; no `model` (D5);
`inheritProjectContext: true`; `skills: workflow`, and every body's first
step reads the workflow skill. The three leads carry `subagent` + the
spawn table as namespaced `allowedAgents`; the seven workers carry no
`subagent` and no `allowedAgents`. Tool allowlists follow teamflow's
per-role lists (Read→read, Grep→grep, Glob→find, Bash→bash, Edit→edit,
Write→write). `simplicity-reviewer` also carries `ponytail,
ponytail-audit, ponytail-debt` (D6; installed at user scope).

**Phase 3 rework to namespaced names** (the ripple of decision 1):
`extensions/teamflow-lib.ts` `LEADS` → the three namespaced leads and the
refusal names them; `extensions/teamflow.ts` `TEAMFLOW_AGENTS` → all ten
namespaced names (the capability ceiling). `extensions/teamflow-lib.test.ts`
spawn tests updated + one new regression: a plain, un-namespaced lead name
is refused.

**New gate test** `tests/test_spawn_table.py` (11 tests): parses every
agent's frontmatter and checks it against the spawn table — exact
`allowedAgents` per lead by set-equality (so widening *or* shrinking
fails), workers have no `subagent`/`allowedAgents`, namespaced canonical
names, no `model`, `inheritProjectContext: true`, the `workflow` skill on
all, researcher web tools, implementer edit/write, the five reviewers
read-only, simplicity-reviewer ponytail skills. Plus a guard self-test
proving a widened lead is detected.

**Verification (all run by me):**

- `node --test extensions/teamflow-lib.test.ts` → 14 pass (was 13; +1
  plain-name regression).
- `python3 -m unittest tests.test_spawn_table -v` → 11 pass.
- **Negative (the plan's required failure):** temporarily widened
  `research-lead` `allowedAgents` to `teamflow.researcher,
  teamflow.implementer` → the test **failed** (`research-lead:
  allowedAgents must be exactly ['researcher'], got ['implementer',
  'researcher'] (widening the spawn table is a decision)`); restored →
  passes.
- `./scripts/gate.sh` → green, **149 tests** (was 138; +11 spawn-table).

**Live (installed the package, then `pi remove .`):** Pi 1.5.0,
pi-subagents 0.87.0, model `vllm/nvidia/Qwen3.8-27B-NVFP4` (local vllm).

- **Registered names:** a fresh session's `subagent` `action:"list"`
  shows all ten as `teamflow.<name>`, and the builtin `researcher` (plain)
  is a separate entry — no shadowing.
- **Depth-1 gate:** `pi --teamflow`, launch `teamflow.implementer` →
  refused verbatim: "The teamflow manager may only launch the leads:
  teamflow.research-lead,teamflow.impl-lead,teamflow.review-lead."
- **Depth-2 ceiling (the plan's top flagged risk):** `pi --teamflow`,
  launch `teamflow.research-lead` whose only job was to spawn
  `teamflow.implementer` → refused verbatim: "Capability ceiling from
  agent:teamflow.research-lead, teamflow does not allow agent
  'teamflow.implementer'. Allowed agents: teamflow.researcher." The lead
  did not retry or reroute (workflow skill: never work around a refusal).
  `allowedAgents` holds at depth 2; the plan's "no fallback yet" risk is
  resolved.

Note: after `pi remove .`, the ten `teamflow.*` names still list when `pi`
is run from the teamflow-pi directory — that is cwd project discovery via
`package.json` `pi.subagents.agents: ["./agents"]`, not a leftover install
(`pi list` shows no teamflow-pi package; no install record under `~/.pi`).

**Status: DONE**
