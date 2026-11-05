# teamflow-pi

Porting the teamflow Claude Code plugin to Pi with pi-subagents. The source
is the teamflow repository (local checkout:
`/Users/Ashish/SynologyDrive/Projects/Claude/teamflow`).

## Before you work

- Read [docs/porting-plan.md](docs/porting-plan.md): find the phase you are
  in and its done check, and the decisions (D1 to D7) it builds on. A phase
  starts only when the one before passed.
- For a Claude Code mechanism, look it up in
  [docs/pi-mapping.md](docs/pi-mapping.md); for a teamflow file, in
  [docs/source-inventory.md](docs/source-inventory.md).

## Rules

- **Build from the description, not from teamflow's files** (D1). Code and
  prompts here are written new against `docs/teamflow/`; teamflow is the
  reference you check that description against.
- **Pipeline rules come from teamflow's `skills/workflow/SKILL.md`.** Change
  only the harness wording; a change to a rule itself is a decision for the
  human.
- **Check Pi facts at the source.** Pi's docs ship with the install
  (`PD/docs/`, path in pi-mapping.md) and pi-subagents' in
  `~/.pi/agent/npm/node_modules/pi-subagents/docs/`. Cite file:line. The
  mapping is a reading of versions that move; re-read the line before you
  build on it.
- **Docs state only what was run or read.** Give the command and its result
  for a run, the file:line for a read, and say "not verified" for the rest.
  A spike's result goes in `docs/spikes.md` with Pi and pi-subagents versions.
- **Agent prompts reach Issues and PRs only through `tf`,** so both forge
  modes keep working.
- **A change to `bin/tf` or `bin/teamflow-config` comes with a test in
  `tests/` that fails without it.**
- When a phase lands, update the Status in [README.md](README.md) and the
  phase in the plan.
