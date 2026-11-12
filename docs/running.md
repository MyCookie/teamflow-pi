# Running teamflow-pi: the Phase 5 end-to-end run

Run of 2026-11-11 (local, -0600; 20:44–23:30). This is the Phase 5 done
check from [porting-plan.md](porting-plan.md): a fresh repository,
`pi install` the package, `tf setup --apply`, a stated goal, and a merged
PR through one full per-PR round (review-lead + the five specialists), in
`local` forge mode.

## Versions

| component | version |
| :--- | :--- |
| Pi | 1.5.0 |
| pi-subagents | 0.87.0 |
| Node | v26.13.0 |
| model | `vllm/nvidia/Qwen3.8-27B-NVFP4` (local) |
| Python | 3.15.2 |
| package revision | `59c60d0` + the `manager.md` and `worktree: true` changes committed with this doc |

## The scratch repository

`/Users/Ashish/teamflow-e2e-2026-11-12`, built clean:

```
$ git init -b main
$ # hello/__init__.py  — add(a, b)
$ # tests/test_hello.py — TestAdd (2 tests)
$ git commit -m "chore: initial hello package with add and tests"   # 2d92909
```

Install and setup, from the scratch directory:

```
$ pi install -l /Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi --approve
Installed /Users/Ashish/SynologyDrive/Projects/Pi/teamflow-pi
$ pi list --approve                      # shows the project package
$ tf setup --apply                       # package bin/ on PATH via the extension, or full path
create scripts/gate.sh from templates/gate.sh
create .github/pull_request_template.md from templates/pull_request_template.md
add .manager-state.json, .env to .gitignore
create .pi/teamflow.json with {"forge": "local"}
```

`scripts/gate.sh` then gained its project tests step
(`python3 -m unittest discover -s tests`), the gate ran green, and the
setup was committed (`817e68e`). `.pi/settings.json` records the package
by relative path (`../../SynologyDrive/Projects/Pi/teamflow-pi`) — a local
package loads from the resolved path in place, no copy.

## The headless probe

`pi --teamflow -p --approve "<probe>"` in the scratch repo. Results:

- the `--teamflow` flag is registered (the extension loads from the
  project-local install);
- the manager prompt is appended (the agent cited "You are the teamflow
  manager…" verbatim);
- `command -v tf` → the package `bin/tf` (the extension's spawn hook puts
  it on PATH); `tf mode` → `local`;
- the `workflow` skill is listed among the manager's skills;
- the spawn gate is fail-closed for the main session: even
  `subagent({action:"list"})` is refused with *"The teamflow manager may
  only launch the leads: teamflow.research-lead,teamflow.impl-lead,
  teamflow.review-lead."* (by design — the manager prompt lists the
  canonical names; the gate allows the three lead launches and `resume`
  only).

**Print-mode flag order quirk (Pi 1.5.0).** `pi -p --teamflow "…"` exits 0
in ~0.3s, runs no model, prints nothing, and writes no session file;
`pi --teamflow -p "…"` works. Extension flags must precede `-p` in print
mode. Without `--approve`, project-local files are ignored and
`--teamflow` is an unknown option.

## The run

Goal, verbatim:

> Build teamflow goal: add division to the hello package. Add a divide(a,
> b) helper to the hello package that raises an error (a clear
> exception) when b is zero, and otherwise returns a / b. Keep the
> existing add helper and its tests working. Add unit tests for divide
> (including the division-by-zero case), and finish only when the repo
> gate (./scripts/gate.sh) is green. This run asks for no post-merge
> review.

Command: `pi --teamflow -p --approve "<goal>"` (background, log
`run/e2e-1.log`; started 20:44:28).

### What happened, in order

1. **Startup.** The manager read the workflow skill, read
   `teamflow-config loop` (`exit_severity_threshold=medium`,
   `max_open_issues_to_continue=0`) and
   `teamflow-config teamflow_auto_approve` (`low`), initialised
   `.manager-state.json` (read-then-write), wrote the goal, and routed
   the goal to Research per the routing table.
2. **Research.** `teamflow.research-lead` (run `f3fb7499`) answered the
   research questions inline (no researchers spawned — every question was
   answerable from the codebase), filed Issue **#1** ("Add divide helper
   to the hello package with unit tests", `type:feature`,
   `severity:low`, `area:quality`) and tracking Issue **#2**, and
   reported. The manager checked the tracking Issue, recorded
   `research_tracking_issue: 2` and `research_issues: [1]`, and closed
   #2.
3. **Planning.** `teamflow.impl-lead` (run `4e5ab5a8`) got the exact
   plan-only brief and returned a plan table: one unit U1, branch
   `feat/1-divide-hello`, files `hello/__init__.py` +
   `tests/test_hello.py`, agent `teamflow.implementer`, no release unit
   (owned files are not shipped paths).
4. **Auto-approval.** With `teamflow_auto_approve: low` the manager ran
   the plan check itself (Issue #1 has one severity label, `low`; no
   protected files; generic implementer), recorded the `iterations`
   entry `{"iteration": 1, "auto_approved": true, "release": null}`,
   relayed the plan as an auto-approval notice, and spawned the
   executing impl-lead (run `8a62558e`) with the exact execution brief.
5. **Implementation.** The implementer worked in the manual worktree
   `../feat-1-divide-hello`: TDD red/green, commit `d4fb326`
   ("feat(hello): add divide helper with zero-division guard",
   `Refs: #1` trailer), gate green, PR **#3** opened (`Closes #1`,
   base `main`). impl-lead returned its PR-ready report.
6. **PR loop, round 1.** The manager checked `tf pr view 3` (open,
   targets `main`) and spawned a fresh `teamflow.review-lead` (run
   `36015804`) with the exact brief. **Failure #1:** the manager spawned
   review-lead in the main worktree, so `tf pr checkout 3` was refused
   (exit 3, "refusing to run in the main worktree; reviews run in their
   own") — a port gap: the original `review-lead` frontmatter carried
   `isolation: worktree` (a Claude Code harness feature), and the Pi
   mapping (spawn-time `worktree: true`) was missing from `manager.md`.
   The lead stopped at the refusal and asked the manager (supervisor
   channel); the manager authorised the lead to create its own worktree
   (`review-pr3-divide-hello`) and continue the same round. The lead
   pinned head `d4fb326…`, ran the gate (green, 6 tests), claimed #3, and
   spawned the five specialists — first with managed
   `worktree: true` (**Failure #2:** rejected, because the untracked
   `run/` log directory in the main worktree failed the clean-tree
   check), then in five manual worktrees with `cwd`.
   **Failure #3:** all five specialist runs hit the pi-subagents 30-minute
   run timeout (1800000 ms) before finishing on the first pass — the
   local model is slow for a full specialist review. The first
   review-lead run then timed out as well (no verdict recorded).
   The manager checked the PR state, **resumed the original run**
   (run `390a82fc`, same session — no re-claim, no new round), and the
   revived lead re-spawned the five specialists (a fresh batch completed
   in ~16 minutes: security clean, the rest with 2 minor findings and
   duplicate notes on tracked `.pyc` files).
   **Failure #4 (model behaviour):** the revived lead then fell into a
   degenerate loop — ~50 turns of `bash echo N` filler, ending its turn
   each time without retrieving the completed specialist reports.
   **Operator intervention:** the manager `pi` process and its child
   runner were killed (SIGTERM/SIGKILL), and the manager session was
   resumed with a human nudge (`pi --teamflow -p --approve --continue`,
   log `run/e2e-2.log`, 22:36) naming the five completed run records and
   asking for round 1 to be finished from them.
7. **Recovery, round 2.** The resumed manager verified the five
   specialist reports existed and were complete, ran `tf pr release 3`,
   and spawned a fresh review-lead (run `c66374bd`) with the exact brief
   plus operational context. It claimed #3, checked out in the existing
   review worktree (already at the pinned head), re-ran the gate (green),
   read the five reports, recorded the single verdict
   (`tf pr review 3 APPROVE` at `d4fb326…`), released the claim, and ran
   `tf pr merge 3`.
8. **Merge and wind-down.** Merge commit `f6ce7e8` on `main` with
   trailers `Closes #1` and `Reviewed-by: teamflow:review-lead (round
   1)`; Issue #1 auto-closed. The manager resumed impl-lead with the
   verdict; impl-lead confirmed the merge and returned its final report
   with the release line **"No release: no shipped path changed"**
   (checked: the goal touched no shipped path). No post-merge review was
   requested, so the loop check ended the run (rule 1). The manager
   recorded the `impl_prs` entry (iteration 1, PR #3, `closes: [1]`,
   `status: merged`), produced the final report, and reset
   `.manager-state.json` to its initial form as the last write.

### Verdict content (recorded on PR #3)

`APPROVE` at `d4fb326…`, gate green (6 tests). Findings: 0 blocker,
0 major, 2 minor — (1) README documents neither public API nor
onboarding (docs-reviewer); (2) the explicit `if b == 0` guard
duplicates Python's built-in `ZeroDivisionError` (buys only message
wording). One Issue filed outside the PR's diff: **#4** (`.pyc`/
`.gitignore` hygiene, `severity:medium`, `area:docs`) — left open as a
follow-up, per the rules.

### End state (all verified after the run)

```
$ git log --oneline -3
f6ce7e8 Merge feat/1-divide-hello: feat(hello): add divide helper with zero-division guard
d4fb326 feat(hello): add divide helper with zero-division guard
817e68e chore: teamflow setup (tf setup --apply, gate runs the tests)
$ ./scripts/gate.sh          # in the main worktree
gate: green.                 # 6 tests
$ git worktree list          # only the main worktree remains
$ tf pr view 3               # state: merged
$ tf issue list              # #1 closed, #2 closed, #4 open
```

`.manager-state.json` reset: `goal` cleared, `iteration: 0`, empty
records.

## Definition of done — met

- [x] `pi install` the package in a fresh repository (project-local, in place)
- [x] run `tf setup --apply` (local forge)
- [x] state a goal to the manager (`pi --teamflow -p`)
- [x] a merged PR through one full per-PR round with review-lead and the
      five specialists (`local` forge mode; verdict + merge recorded by
      review-lead; merge on `main`)

## Failures and their dispositions

| # | failure | disposition |
| :--- | :--- | :--- |
| 1 | review-lead spawned in the main worktree → `tf pr checkout` refused | manager authorised its own worktree (supervisor channel); **port fixed mid-run**: `manager.md` now passes `worktree: true` on every review-lead spawn — the Pi mapping of the original `isolation: worktree` frontmatter (the specialist and researcher spawns already carried it) |
| 2 | managed-worktree dispatch refused (untracked `run/` log in the main worktree) | lead fell back to manual worktrees + `cwd`; **operator rule for future runs**: keep the main worktree clean (logs outside the repo) |
| 3 | specialist runs and the first review-lead run hit the 30-min run timeout on the slow local model | manager resumed the run; the fresh specialist batch finished in ~16 min. (Upstream-agnostic; a faster model or a raised `maxRuntimeMs` would avoid it.) |
| 4 | revived review-lead looped on filler `echo` calls, never retrieving the completed reports (model behaviour) | operator killed the run, resumed the manager session with a nudge; the manager verified the reports, released the claim, and a fresh review-lead completed the round from the existing reports |

Nothing in the failures was a pipeline-rule failure: every rule held —
one claim per round, head pinned, gate before specialists, one verdict
per round, verdict before merge, no merge arming outside review-lead,
state read-before-write, reset as the last write. The two port-level
fixes (manager.md worktree flag; clean main worktree) are recorded above
and committed with this doc.
