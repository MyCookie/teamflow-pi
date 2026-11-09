# teamflow-pi

A port of [teamflow](https://github.com/Ribhu-Labs/teamflow), a Claude Code
plugin, to the [Pi](https://pi.dev) coding agent harness.

teamflow runs a three-team agent pipeline in a repository: research turns
goals into Issues, implementation works them in isolated git worktrees, and
a review team reviews every PR before it merges, under a manager that routes
each handoff. Issues and PRs go through one CLI, `tf`, either as local
records or on GitHub.

## Status

**Phase 1 done (2026-11-09).** The five teamflow description docs are in
[docs/teamflow/](docs/teamflow/): the `tf` contract
([tf.md](docs/teamflow/tf.md)), `teamflow-config`
([teamflow-config.md](docs/teamflow/teamflow-config.md)), `tf setup`
([tf-setup.md](docs/teamflow/tf-setup.md)), the workflow rules
([workflow-rules.md](docs/teamflow/workflow-rules.md)) and the agents
([agents.md](docs/teamflow/agents.md)) — each pinned to teamflow @
`423109c` and checked section by section against it. Nothing has been
built yet; Phase 2 (package skeleton, `tf`, the gate) is next.

Phase 0's eight spikes ran on Pi 1.5.0 / pi-subagents 0.86.0 and are
recorded in [docs/spikes.md](docs/spikes.md).

**Who builds it.** Pi itself builds the extension
(Phase 3), working from [AGENTS.md](AGENTS.md) and
[docs/extension-spec.md](docs/extension-spec.md). Who does the other phases
is not decided yet.

## Read in this order

1. [docs/source-inventory.md](docs/source-inventory.md): what teamflow is
   made of, sorted by how much each part depends on Claude Code.
2. [docs/pi-mapping.md](docs/pi-mapping.md): what Pi and pi-subagents offer
   for each of those parts, with citations, and the gaps.
3. [docs/porting-plan.md](docs/porting-plan.md): the decisions made, phases
   with done checks, and risks.
4. [docs/extension-spec.md](docs/extension-spec.md): the extension, part by
   part, for the agent that builds it.
5. [docs/research/](docs/research/): research behind a decision.

[AGENTS.md](AGENTS.md) holds the rules for agents working in this repository.

## Versions the docs were written against

Read on 2026-11-05: teamflow `0.22.2` at commit `423109c`, Pi `1.5.0`
(Homebrew), pi-subagents `0.84.0`.

## License

teamflow is Apache-2.0, copyright 2026 Ashish Kansara. This port's license
is not yet chosen.
