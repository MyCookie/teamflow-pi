# teamflow-pi

A port of [teamflow](https://github.com/Ribhu-Labs/teamflow), a Claude Code
plugin, to the [Pi](https://pi.dev) coding agent harness.

teamflow runs a three-team agent pipeline in a repository: research turns
goals into Issues, implementation works them in isolated git worktrees, and
a review team reviews every PR before it merges, under a manager that routes
each handoff. Issues and PRs go through one CLI, `tf`, either as local
records or on GitHub.

## Status

**Not started.** This repository holds only the planning docs. Nothing has
been built or run on Pi.

## Read in this order

1. [docs/source-inventory.md](docs/source-inventory.md): what teamflow is
   made of, sorted by how much each part depends on Claude Code.
2. [docs/pi-mapping.md](docs/pi-mapping.md): what Pi and pi-subagents offer
   for each of those parts, with citations, and the gaps.
3. [docs/porting-plan.md](docs/porting-plan.md): the decisions made, phases
   with done checks, and risks.
4. [docs/research/](docs/research/): research behind a decision.

[AGENTS.md](AGENTS.md) holds the rules for agents working in this repository.

## Versions the docs were written against

Read on 2026-11-05: teamflow `0.22.2` at commit `423109c`, Pi `1.5.0`
(Homebrew), pi-subagents `0.84.0`.

## License

teamflow is Apache-2.0, copyright 2026 Ashish Kansara. This port's license
is not yet chosen.
