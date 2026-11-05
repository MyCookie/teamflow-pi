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

## Decisions

Decided by the human on 2026-11-05. A change to one is the human's call.

| # | Decision | Answer | What it means here |
|---|---|---|---|
| D1 | How teamflow-pi relates to teamflow | Brownfield, docs only: docs here describe how teamflow works, and teamflow-pi is built from them from the ground up | No file is copied from teamflow. Phase 1 writes the description; later phases build against it. teamflow stays the reference to check the description against |
| D2 | Config path | `.pi/teamflow.json` | `tf` and `teamflow-config` read `.pi/teamflow.json` from the main worktree |
| D3 | How the manager starts | An extension flag, `pi --teamflow`, as recommended in [research/manager-startup.md](research/manager-startup.md) | Phase 0 spike 7 tests it; if it fails, the fallback is `--append-system-prompt` (no main-session spawn limit) |
| D4 | How agents find `tf` | Start with a bash `spawnHook` extension | Phase 0 spike 5; one extension with D3's flag |
| D5 | Models | Pi's defaults, changeable by config | Agents set no `model`. pi-subagents then falls back to `subagents.defaultModel`, then the parent session's model; `subagents.agentOverrides.<name>.model` in `.pi/settings.json` pins one role (`PS/docs/models.md:5-14`). The manager, as the main session, uses Pi's default model or `--model`. No teamflow config key needed |
| D6 | ponytail and mattpocock skills | ponytail is a separate install; mattpocock's skills are dropped | ponytail is a Pi package: `pi install git:github.com/DietrichGebert/ponytail` (its README.md:177; `package.json` `pi.skills: ["./skills"]`, read in the local Claude plugin copy, not installed for Pi). The workflow rules lose the pointer to `domain-modeling`; reading `CONTEXT.md` and `docs/adr/` stays |
| D7 | Gate validation step | None for now | `scripts/gate.sh` runs the unit tests only |

## Phases

Each phase ends on a check you can run. Do them in order; a phase whose
check fails stops the plan.

### Phase 0: spikes (answer the unknowns first)

Small throwaway Pi sessions, one per question, each recorded in
`docs/spikes.md` with the command, the Pi and pi-subagents versions, the
model, and what was observed. Under D5 children run on the parent's model,
so a spike tests the mechanism with the model's behaviour on top: when a
check fails, note whether Pi refused the action or the model did not try it.

1. **Nested spawn with `allowedAgents`.** Main session → agent A
   (`tools: subagent`, `allowedAgents: B`) → agent B. Then A tries to spawn
   C. Done: B runs, C is refused.
2. **Parallel and wait.** A spawns five children at once and reports only
   after all five finish. Done: one report naming all five results.
3. **Resume.** Main spawns A, A returns, main runs `resume` on A with a
   message. Done: A's reply shows it remembers its first task.
4. **Worktree.** `subagent({…, worktree: true})`. Done: the child's
   `pwd` is a git worktree; note where it lives and its branch name.
5. **`tf` on PATH** (D4). A `spawnHook` extension, in the main session and
   in a foreground and a background child. Done: `command -v tf` succeeds in
   all three.
6. **Skill access.** A child with `skills: workflow` reads it when told to.
   Done: the child quotes a line from the skill body.
7. **Manager start** (D3). The four checks under "To verify" in
   [research/manager-startup.md](research/manager-startup.md).
8. **ponytail in a child** (D6). With ponytail installed, a child with
   `skills: ponytail-audit` reads it. Done: the child quotes a line from it.

### Phase 1: describe teamflow (D1)

Docs in `docs/teamflow/` that a builder can work from without opening the
teamflow repository, each checked against teamflow at a named commit:

- **`tf` contract:** every command, flag, output line an agent reads, exit
  code, the local record store, and GitHub mode. The behaviour, not the
  code; teamflow's `tests/test_tf.py` is the list of cases to cover.
- **`teamflow-config`:** keys, defaults, validation, the main-worktree rule.
- **`tf setup`:** what it installs, dry run, `--apply`, the templates' contents.
- **Workflow rules:** the pipeline rules from teamflow's
  `skills/workflow/SKILL.md`, minus the Claude Code wording listed in the
  inventory (Tier 2).
- **Agents:** each role's job, inputs, steps, report format and limits.

Done: every section names its teamflow source (file and commit), and every
`tf` exit code and command in teamflow's `bin/tf` usage text appears.

### Phase 2: package skeleton, `tf` and the gate

- `package.json` with `name`, `version`, a `pi` key for `skills`,
  `extensions` and `subagents.agents`, and the `pi-package` keyword.
- Build `tf` and `teamflow-config` from the Phase 1 contract, test first,
  reading `.pi/teamflow.json` (D2).
- `scripts/gate.sh`: the unit tests (D7).
- Done: `./scripts/gate.sh` passes and `pi -e ./` starts without extension
  errors.

### Phase 3: the extension

Built by Pi, from
[extension-spec.md](extension-spec.md), which breaks it into three parts,
each with an example to copy, a tested pure function and a check.

- `spawnHook` putting the package's `bin/` on `PATH` (D4, from spike 5).
- The manager flag, ceiling and main-session spawn check (D3, from spike 7).
- Done: the spec's Done section, and in an installed package
  `pi --teamflow` gets the manager prompt, `tf mode` prints `local`, and a
  `subagent` call for `implementer` from the main session is refused.

### Phase 4: agents and the workflow skill

- Write the workflow skill from the Phase 1 rules, worded for Pi.
- Write the ten subagents (the manager is the main session, D3) in
  pi-subagents frontmatter: no `model` (D5); the spawn table as
  `allowedAgents` on the three leads; no `subagent` tool for workers;
  `inheritProjectContext: true`; a first step to read the workflow skill;
  `ponytail`, `ponytail-audit`, `ponytail-debt` on simplicity-reviewer (D6).
- A test that reads agent frontmatter and checks it against the spawn table.
  Done: the gate passes with it, and it fails when one agent's
  `allowedAgents` is widened.

### Phase 5: end-to-end run

- In a scratch repository: install, `tf setup --apply`, a small goal.
- Done: the definition of done above, recorded in `docs/running.md` with
  versions, commands and what happened, including what failed.

### Later (not in scope until Phase 5 passes)

`github` forge mode on Pi, post-merge review, restart behaviour, headless
`pi -p` runs, a gate validation step (D7).

## Risks

- **Resume is a new process** (pi-mapping.md, Spawning). The manager resumes
  impl-lead after every review round; if context does not carry, the PR
  loop needs a redesign (for example a state file both read).
- **No caller identity for hooks.** The spawn table depends on
  `allowedAgents` and the D3 main-session check; if spike 1 shows
  `allowedAgents` does not hold at depth 2, there is no fallback yet.
- **Depth.** The chain fits the default depth of 2 only because the manager
  is the main session (D3).
- **Untested upstream.** teamflow's own per-PR round with the five
  specialists has not been run live on Claude Code either
  (`docs/running.md` in teamflow). A failure in Phase 5 may be teamflow's
  design, not Pi's.
