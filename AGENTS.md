# teamflow-pi

You are building teamflow-pi: a port of the teamflow Claude Code plugin to
Pi, using the pi-subagents package. The source is the teamflow repository
(local checkout: `/Users/Ashish/SynologyDrive/Projects/Claude/teamflow`).

## How to work

1. Open [docs/porting-plan.md](docs/porting-plan.md). Find the first phase
   whose done check has not passed. That is your phase. Do not start a later
   one.
2. Do one task of that phase at a time. A task is done when its check
   passes, and you ran the check yourself.
3. Write what you ran and what it printed in `docs/spikes.md` (Phase 0) or
   the doc the phase names. Include the Pi version (`pi --version`), the
   pi-subagents version, and the model you ran on.
4. Stop and report to the human when a check fails twice, when you need an
   API the docs do not show, or when a task needs a decision the plan does
   not hold.

For the extension (Phase 3), follow
[docs/extension-spec.md](docs/extension-spec.md) part by part.

## Where facts live

- A Claude Code mechanism and its Pi equivalent:
  [docs/pi-mapping.md](docs/pi-mapping.md).
- A teamflow file: [docs/source-inventory.md](docs/source-inventory.md).
- Pi's docs and examples:
  `/opt/homebrew/Cellar/pi-coding-agent/1.5.0/libexec/lib/node_modules/@earendil-works/pi-coding-agent/docs/`
  and `…/examples/extensions/`.
- pi-subagents' docs: `~/.pi/agent/npm/node_modules/pi-subagents/docs/`.

## Rules

- **Build from the description, not from teamflow's files** (D1). Code and
  prompts here are written new against `docs/teamflow/`; teamflow is the
  reference you check that description against.
- **Pipeline rules come from teamflow's `skills/workflow/SKILL.md`.** Change
  only the harness wording; a change to a rule itself is a decision for the
  human.
- **Read the cited line before you use a fact.** The docs here cite Pi
  files as file:line. Pi and pi-subagents change between versions, so open
  the line and check it still says that.
- **Write only what you ran or read.** A run gets its command and output; a
  read gets its file:line; anything else is marked "not verified".
- **Agent prompts reach Issues and PRs only through `tf`,** so both forge
  modes keep working.
- **A change to `bin/tf` or `bin/teamflow-config` comes with a test in
  `tests/` that fails without it.**
- When a phase lands, update the Status in [README.md](README.md) and mark
  the phase done in the plan.
