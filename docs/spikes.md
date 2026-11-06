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
