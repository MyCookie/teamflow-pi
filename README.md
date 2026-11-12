# teamflow-pi

A port of [teamflow](https://github.com/Ribhu-Labs/teamflow), a Claude Code
plugin, to the [Pi](https://pi.dev) coding agent harness.

teamflow runs a three-team agent pipeline in a repository: research turns
goals into Issues, implementation works them in isolated git worktrees, and
a review team reviews every PR before it merges, under a manager that routes
each handoff. Issues and PRs go through one CLI, `tf`, either as local
records or on GitHub.

## Status

**Phase 4 done (2026-11-11).** The workflow skill
([skills/workflow](skills/workflow/SKILL.md)) and the ten subagents
([agents/](agents/)) are built. Each agent sets `package: teamflow`, so
its canonical name is `teamflow.<name>` (no shadowing of the builtin
`researcher`); no `model` (D5); `inheritProjectContext: true`; the
workflow skill as the first step; the spawn table encoded as
`allowedAgents` on the three leads; no `subagent` tool for the seven
workers; `ponytail`, `ponytail-audit`, `ponytail-debt` on
simplicity-reviewer (D6); and `web_search`/`fetch_content` on the
researcher (pi-web-access). [tests/test_spawn_table.py](tests/test_spawn_table.py)
reads the frontmatter and pins the spawn table — the gate stays green
(149 tests) and fails when a lead's `allowedAgents` is widened. The
record, including a live depth-2 check that `allowedAgents` holds, is in
[docs/spikes.md](docs/spikes.md).

**Phase 3 done (2026-11-10).** The extension
([extensions/](extensions/)) is built: `spawnHook` puts the package's
`bin/` on `PATH` so agents find `tf` (D4); `--teamflow` starts the main
session as the teamflow manager (D3, placeholder
[manager.md](manager.md)); and with the flag on the session registers the
ten-agent capability ceiling and the main session may only spawn the three
leads (`spawnDecision`, fails closed). Built test-first against
[docs/extension-spec.md](docs/extension-spec.md) — 14 lib tests pass, and
the spec's checks plus the installed-package gate are recorded in
[docs/spikes.md](docs/spikes.md). `pi install ./` makes the package
active; Phase 5 (the end-to-end run) is next.

**Phase 2 done (2026-11-09).** The package skeleton is in place:
[package.json](package.json), the four forge templates in
[templates/](templates/) (verbatim from teamflow @ `423109c`),
[`tf`](bin/tf) and [`teamflow-config`](bin/teamflow-config) built
against the Phase 1 contracts, and the repo's own
[scripts/gate.sh](scripts/gate.sh) running the unit tests (D7).
138 unit tests in [tests/](tests/) cover both, test-first, with
[fake_gh](tests/fake_gh.py) standing in for `gh` in GitHub-mode tests.

Phase 0's eight spikes ran on Pi 1.5.0 / pi-subagents 0.86.0 and are
recorded in [docs/spikes.md](docs/spikes.md). (Phase 3 built and ran on
pi-subagents 0.87.0.)

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

teamflow is Apache-2.0. This port is also licensed under
[Apache License 2.0](LICENSE), copyright 2026 Ashish Kansara.
