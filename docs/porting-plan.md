# Porting plan

How to get from teamflow (Claude Code) to teamflow-pi. Inputs:
[source-inventory.md](source-inventory.md) (what exists) and
[pi-mapping.md](pi-mapping.md) (what Pi offers). This is a plan: none of it
has been built or run.

## Goal

The same pipeline (manager, three leads, seven workers, `tf`, the two
invariants: `main` always green, nothing merges on its author's say-so)
running on Pi with pi-subagents, installable as one Pi package.

**Done** when a human can `pi install` the package in a fresh repository,
run `tf setup`, state a goal to the manager, and see it reach a merged PR
through one full per-PR round with review-lead and five specialists, in
`local` forge mode, and the run is recorded in the docs as what was run.

## Open decisions

Each needs the human's answer before the phase that depends on it. Record
the answer here (or in `docs/adr/`) when made.

| # | Decision | Options | Blocks |
|---|---|---|---|
| D1 | How teamflow-pi relates to teamflow | (a) hard fork: copy files at commit `423109c` and diverge; (b) shared core: `tf` and the workflow rules in one place, harness layers in each | Phase 1 |
| D2 | Config path | keep `.claude/teamflow.json` (one config for both harnesses) or move to `.pi/teamflow.json` | Phase 1 |
| D3 | How the manager starts | `--append-system-prompt agents/manager.md`; a `/teamflow` prompt template; an extension flag | Phase 3 |
| D4 | How agents find `tf` | bash `spawnHook` extension (recommended to try first); `tf` tool; human adds to `PATH` | Phase 2 |
| D5 | Models | Pi model ids per role (teamflow uses an Opus-class model for manager and leads, a Sonnet-class one for workers) | Phase 3 |
| D6 | ponytail and mattpocock skills | bundle into the package; require separate install; drop ponytail from simplicity-reviewer | Phase 3 |
| D7 | Gate validation step | replace `claude plugin validate` with a script check of `package.json` and agent frontmatter; or none | Phase 1 |

## Phases

Each phase ends on a check you can run. Do them in order; a phase whose
check fails stops the plan.

### Phase 0: spikes (answer the unknowns first)

Small throwaway Pi sessions, one per question, each recorded in
`docs/spikes.md` with the command, the Pi and pi-subagents versions, and
what was observed:

1. **Nested spawn with `allowedAgents`.** Main session → agent A
   (`tools: subagent`, `allowedAgents: B`) → agent B. Then A tries to spawn
   C. Done: B runs, C is refused.
2. **Parallel and wait.** A spawns five children at once and reports only
   after all five finish. Done: one report naming all five results.
3. **Resume.** Main spawns A, A returns, main runs `resume` on A with a
   message. Done: A's reply shows it remembers its first task.
4. **Worktree.** `subagent({…, worktree: true})`. Done: the child's
   `pwd` is a git worktree; note where it lives and its branch name.
5. **`tf` on PATH** (D4). The spawnHook extension, in the main session and in
   a foreground and a background child. Done: `command -v tf` succeeds in all three.
6. **Skill access.** A child with `skills: workflow` reads it when told to.
   Done: the child quotes a line from the skill body.

### Phase 1: package skeleton and harness-agnostic code

- `package.json` with `name`, `version`, a `pi` key for `skills`,
  `extensions` and `subagents.agents`, and the `pi-package` keyword.
- Copy Tier 1 from the inventory (`bin/tf`, `bin/teamflow-config`,
  `templates/`, `tests/test_tf.py`, `tests/fake_gh.py`,
  `tests/test_setup.py`) per D1; apply D2 to the config path.
- `scripts/gate.sh`: the unit tests, plus D7.
- Done: `./scripts/gate.sh` passes and `pi -e ./` starts without extension errors.

### Phase 2: `tf` reachable

- Implement D4 (from spike 5). Done: an agent in the installed package runs
  `tf mode` and gets `local`.

### Phase 3: agents and the workflow skill

- Port `skills/workflow/SKILL.md`: keep every pipeline rule; rewrite Teams,
  Spawn depth, Messaging, Role bounds, Release and Domain language for Pi
  (inventory, Tier 2, lists each).
- Port all 11 agents to pi-subagents frontmatter (mapping table in
  pi-mapping.md). The spawn table becomes `allowedAgents` on manager and the
  three leads; workers get no `subagent` tool. Every agent gets
  `inheritProjectContext: true` and a first step to read the workflow skill.
- Replace in prompt bodies: `Agent(subagent_type: …)` → `subagent({agent, task})`;
  `SendMessage` resume → `subagent({action:"resume", …})`;
  `SubagentHandback` → ends its turn; `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`
  → `PI_SUBAGENT_MAX_DEPTH`; `claude --agent` → D3; `claude plugin update`
  → `pi update`.
- Replace `tests/test_hooks.py` with a test that reads agent frontmatter and
  checks it matches the spawn table, and port `tests/test_agents.py` to the
  Pi fields. Done: gate passes with both, and each fails when one agent's
  `allowedAgents` is widened.

### Phase 4: end-to-end run

- In a scratch repository: install, `tf setup --apply`, a small goal.
- Done: the definition of done above, recorded in `docs/running.md` with
  versions, commands and what happened, including what failed.

### Later (not in scope until Phase 4 passes)

`github` forge mode on Pi, post-merge review, restart behaviour, headless
`pi -p` runs.

## Risks

- **Resume is a new process** (pi-mapping.md, Spawning). The manager resumes
  impl-lead after every review round; if context does not carry, the PR
  loop needs a redesign (for example a state file both read).
- **No caller identity for hooks.** The spawn table depends entirely on
  `allowedAgents`; if spike 1 shows it does not hold at depth 2, there is no
  hook fallback yet.
- **Depth.** The chain fits the default depth of 2 only when the manager is
  the main session (D3).
- **Untested upstream.** teamflow's own per-PR round with the five
  specialists has not been run live on Claude Code either
  (`docs/running.md` in teamflow). A failure in Phase 4 may be teamflow's,
  not Pi's.
