# `tf setup` — behaviour contract

What `tf setup` does, so a builder can reimplement it from this document
without opening the teamflow repository. Behaviour, not code. Every section
names its teamflow source (file and commit).

**Pinned source:** teamflow @ `423109c`: `bin/tf` (the `setup` function,
lines 711–821, plus the CLI at 858–861 and the `GitHub` preconditions at
420–436) and `templates/` (`gate.sh`, `pull_request_template.md`, `ci.yml`,
`branch-ruleset.json`).
**Verification status:** local mode was run live in a scratch repo
(Appendix A); GitHub mode was run live **read-only** (a dry run against a
real GitHub repo, Appendix A §10) and is pinned by teamflow's `tests/test_setup.py` (15 tests, run OK at this commit) which uses a fake `gh`.

## 1. What it is

Source: `bin/tf:711-717,858-861` @ 423109c; verified in Appendix A.

`tf setup` applies the things a plugin cannot apply: the repository-side
files and (in GitHub mode) the repository settings a teamflow run needs.

```
tf setup [--forge local|github] [--remote R] [--apply]
```

- **`--forge local|github`** (default `local`) — which mode the setup
  prepares.
- **`--remote R`** — the remote for GitHub mode. Default: the `remote` in
  the config file, else `origin` (an explicit `--remote` wins over the
  file — verified, Appendix A §8, §11).
- **`--apply`** — act. Without it: a **dry run** that prints each action
  prefixed `would ` and changes nothing.

Guarantees: **dry run unless `--apply`; never overwrites, never commits**
(the docstring, `bin/tf:712`). It runs in whichever worktree it is started
in — no main-worktree or base-branch requirement — so the setup files can
be prepared on a branch and merged through a PR like any other change
(teamflow test: `test_runs_on_a_branch_in_a_linked_worktree`,
`tests/test_setup.py:72`).

Exit codes: 0 on success (dry run or apply); 2 for setup errors (bad
config JSON, GitHub preconditions); 1 for the ruleset-listing failure
of §4.3. A broken *template* JSON also exits 2, not a traceback (teamflow
test:
`test_a_broken_template_is_a_setup_error_not_a_traceback`,
`tests/test_setup.py:90`).

## 2. The local steps (always, in this order)

Source: `bin/tf:719-774` @ 423109c; verified in Appendix A §1-5.

1. **Read the config of the *current* worktree** — `<worktree>/.claude/
   teamflow.json`. Only JSON syntax and object-ness are checked: invalid
   JSON → exit 2 `<path> is not valid JSON (<parser error>)`; not an
   object → exit 2 `<path> is not a JSON object` (paths shown relative to
   the repo root; verified, Appendix A §7). **Keys are not validated**
   and the main-worktree branch rule does not apply — `tf setup` is the
   one `tf` command that does not go through `teamflow-config`
   ([teamflow-config.md](teamflow-config.md) §4).
2. **Copy the templates**, in order, skipping any target that exists
   (`ok: <target> exists, left alone`); created files are byte-identical to
   the template and `gate.sh` keeps its executable bit (verified,
   Appendix A §2):

   | template | target | when |
   |---|---|---|
   | `gate.sh` | `scripts/gate.sh` | always |
   | `pull_request_template.md` | `.github/pull_request_template.md` | always |
   | `ci.yml` | `.github/workflows/gate.yml` | github mode only |

3. **`.gitignore`:** ensure the three runtime lines
   `.manager-state.json`, `.claude/worktrees/`, `.env` (the `IGNORES`
   list, `bin/tf:708`). Missing lines are appended (a newline is added
   first if the file does not end with one); if all are present:
   `ok: .gitignore covers teamflow's runtime files` (verified,
   Appendix A §1-3).
4. **The config file:** if it exists → `ok: .claude/teamflow.json exists`,
   plus `; note: it says forge <existing>, not <wanted>, left alone` when
   the forge differs (never rewritten — verified, Appendix A §5). If
   missing → create it with 2-space JSON and a trailing newline:
   `{"forge": "local"}` for local mode, `{"forge": "github", "remote":
   <remote>}` for github mode (verified, Appendix A §2, §10-11).
5. **The tail line:** with `--apply`:
   `next: fill in scripts/gate.sh, then commit these files and merge them
   to the base branch`; dry run: `dry run: nothing changed; run again with
   --apply`.

A second `--apply` prints only `ok:` lines and changes nothing —
customised files survive (teamflow test:
`test_second_apply_changes_nothing_and_never_overwrites`,
`tests/test_setup.py:104`; verified, Appendix A §3-4). Setup never commits
(`test_never_commits`, `tests/test_setup.py:66`) and never touches
`.claude/settings.json` (it does not even create it —
`test_apply_does_not_create_settings_json`, `tests/test_setup.py:62`).

## 3. GitHub-mode preconditions (before any write)

Source: `bin/tf:732,420-436` @ 423109c; verified in Appendix A §8-9.

Checked once, before the copies, when `--forge github`:

1. The configured remote's URL must match `github.com[:/]owner/repo[.git]`
   → else exit 2: `forge is github but remote '<remote>' (<url or
   missing>) is not a GitHub repository` (verified, Appendix A §9-10).
2. `gh` must be installed → else exit 2: `forge is github but gh is not
   installed`.
3. `gh auth status` must exit 0 → else exit 2: `forge is github but gh is
   not authenticated (gh auth login)`.

   Note: this exits non-zero if **any** configured gh account is
   unhealthy, not just the active one. On the verification machine (2026-11-09)
   the `GH_TOKEN` environment account was fine but a stale keyring account
   made the check fail; an isolated `GH_CONFIG_DIR` made it pass
   (Appendix A §9).

On success the slug `owner/repo` is derived from the remote URL; every
later `gh` call runs with `-R <slug>`.

## 4. GitHub-mode repository state (after the local steps)

Source: `bin/tf:776-818` @ 423109c; verified live read-only in Appendix A
§10-11 and pinned by `tests/test_setup.py:120-189`.

Done in this order. The **reads always happen, dry run included**; only
the `do(...)` actions are deferred until `--apply`:

1. **Labels:** list existing (`gh label list --json name --limit 200`);
   for each of the 13 `LABELS` (`bin/tf:705-707`) not present →
   `create label <name>` (action: `gh label create <name>`). The 13:
   `severity:high`, `severity:medium`, `severity:low`, `needs-discussion`,
   `area:architecture`, `area:security`, `area:quality`, `area:docs`,
   `area:simplicity`, `area:research`, `type:feature`, `type:bug`,
   `type:task`. Existing labels are never recreated (teamflow test:
   `test_github_apply_sets_up_labels_settings_ruleset_and_ci`,
   `tests/test_setup.py:164`).
2. **Repository settings:** if both `allow_auto_merge` and
   `delete_branch_on_merge` are true on the repo → `ok: auto-merge and
   branch deletion are on`; otherwise `turn on auto-merge and deletion of
   merged branches` (action: `gh api` `PATCH repos/<slug>` with
   `allow_auto_merge=true`, `delete_branch_on_merge=true`). (API value
   `null` counts as off — verified, Appendix A §10.)
3. **The branch ruleset** — named `teamflow: reviewed and gated` from
   `templates/branch-ruleset.json` (the template is JSON-validated: a
   broken one exits 2 `branch-ruleset.json is not valid JSON
   (<parser error>)`, teamflow test above, `tests/test_setup.py:90`):

   - List existing rulesets (`gh api repos/<slug>/rulesets`):
     - non-zero exit **with** `HTTP 403` or `Upgrade to GitHub Pro` in the
       output → non-fatal: `note: rulesets unavailable (<stderr>);
       github mode will run unenforced, with tf checking the gate and
       verdict itself` (teamflow test:
       `test_rulesets_unavailable_is_reported_not_fatal`,
       `tests/test_setup.py:180`).
     - any other non-zero exit → error, exit 1: `listing rulesets failed:
       <output+stderr>` (teamflow test:
       `test_a_rulesets_error_other_than_403_is_an_error`,
       `tests/test_setup.py:157`).
     - ruleset with that name exists → `ok: ruleset 'teamflow: reviewed
       and gated' exists`.
   - No such ruleset: check whether `.github/workflows/gate.yml` is on the
     **default branch** (`gh api repos/<slug>/contents/.github/workflows/
     gate.yml`):
     - not on the default branch → `later: ruleset 'teamflow: reviewed and
       gated' waits until .github/workflows/gate.yml is on the default
       branch; run tf setup --forge github --apply again after the setup
       PR merges` — it is **not created, even with `--apply`** (teamflow
       test: `test_ruleset_waits_until_the_gate_workflow_is_on_the_base_
       branch`, `tests/test_setup.py:151`). Reason (source comment,
       `bin/tf:810-811`): the ruleset requires the `gate` check, so
       creating it before the gate workflow is on the default branch would
       block the very PR that adds the workflow.
     - on the default branch → `create ruleset 'teamflow: reviewed and
       gated'` (action: `gh api` `POST repos/<slug>/rulesets` with
       `--input templates/branch-ruleset.json`).

## 5. The templates

All four files, verbatim, teamflow @ `423109c`. The first three are copied
into the target repository; `branch-ruleset.json` is only sent to the
GitHub API (§4).

### 5.1 `templates/gate.sh` → `scripts/gate.sh`

```bash
#!/usr/bin/env bash
# The merge gate. One script, so what the implementer ran and what the
# review team ran cannot drift (teamflow workflow rules).
#
# Every step runs even after an earlier one fails: a reviewer wants the whole
# picture, not the first thing that broke. Exits non-zero if any step failed.
#
# Add your project's checks in the marked section below, one `step` each.
set -uo pipefail

cd "$(dirname "$0")/.."

results=()
failed=0

step() {
    local name="$1"
    shift
    printf '\n\033[1m── %s ─────────────────────────────\033[0m\n' "$name"
    if "$@"; then
        results+=("$name|pass")
    else
        results+=("$name|FAIL")
        failed=1
    fi
}

# Credentials: load .env ourselves rather than asking the caller to export it.
# No shell state survives between an agent's commands, so "export, then run
# the gate" in two commands leaves the gate with nothing.
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

# The scripts are the runbook, so a broken one is a broken process. Matched by
# shebang, not by *.sh, so extensionless scripts are not silently skipped.
shell_syntax() {
    local rc=0 f
    for f in scripts/*; do
        [ -f "$f" ] || continue
        case "$(head -1 "$f")" in
            '#!'*sh*) bash -n "$f" || { echo "gate: $f does not parse" >&2; rc=1; } ;;
        esac
    done
    return "$rc"
}
step "shell scripts parse" shell_syntax

# -- project checks: add lint, type-check, tests, coverage here ---------------
# step "lint" <command>
# step "tests" <command>

# -- summary: paste this table into the PR body / review ----------------------

printf '\n\033[1m── gate summary ─────────────────────────────\033[0m\n\n'
echo '| check | result |'
echo '| :--- | :--- |'
for row in "${results[@]}"; do
    echo "| ${row%%|*} | ${row#*|} |"
done
echo

if [ "$failed" -ne 0 ]; then
    echo "gate: FAILED — do not open a PR, do not merge." >&2
    exit 1
fi
echo "gate: green."
```

Behaviour notes: one gate script shared by implementer and review team;
every step runs even after a failure (the reviewer wants the whole
picture); it loads `.env` itself (`set -a`); the one built-in step is
`shell scripts parse` (bash `-n` on every file in `scripts/` whose first
line is a shell shebang — extensionless scripts included); projects add
their own `step "name" command` lines in the marked section; it prints a
Markdown summary table meant for the PR body; exit 1 with `gate: FAILED —
do not open a PR, do not merge.` when any step failed, else exit 0 with
`gate: green.`

### 5.2 `templates/pull_request_template.md` → `.github/pull_request_template.md`

```markdown
<!-- Everything here is a hint for the review team, never evidence: it
     re-derives all of it independently. State only what you ran. -->

## Issue

Closes #<n>

<one paragraph: what this branch makes true that was not true before>

## Evidence

One row per acceptance criterion of the Issue. If the Issue has none (a
review finding, or one a human filed), one row per stated defect or
stated outcome instead, named in the first column:

| Criterion | How it was verified | Result |
| :--- | :--- | :--- |
| A1 | <test name, command, or what was read> | <observed result> |

## Red/green

For each new or changed test: its name, the command, the failing output
before the change (red), and that it passes after (green). For a change
that cannot be tested, say so and why.

## Gate

Output of `./scripts/gate.sh` at <head SHA>:

| check | result |
| :--- | :--- |
| | |

## Not verified

<Every claim above you did not check yourself, every skipped check, and
anything refused by a permission prompt. "None" only if that is true.>

## Decisions

<Ambiguities in the Issue or docs and how they were resolved, with the doc
change or ADR that records them. "None" if none.>

## Pre-existing tests touched

<Every modified pre-existing test, with its justification, or "none". A test
that looks wrong is a question for the Issue author, not an edit.>
```

### 5.3 `templates/ci.yml` → `.github/workflows/gate.yml` (github mode only)

```yaml
# teamflow gate in CI: copy to .github/workflows/gate.yml when adopting
# forge: github. The job name `gate` is the required check the branch
# ruleset names, so keep it (or update templates/branch-ruleset.json).
#
# One job keeps the required check honest. If you split the gate into several
# jobs, add an aggregate `gate` job with `if: always()` and `needs:` on all of
# them that fails unless every need's result is `success`: a skipped or
# cancelled job must not count as a pass.
name: gate

on:
  pull_request:
  push:
    branches: [main]
  merge_group:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: gate-${{ github.ref }}
  cancel-in-progress: true

jobs:
  gate:
    name: gate
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      # Install the project's toolchain here, pinned like the action above.
      - name: Run the gate
        run: ./scripts/gate.sh
```

Behaviour notes: the job name `gate` **is** the required-check context the
branch ruleset names — renaming it breaks the enforced merge path
(`tf.md` §10); one job keeps the required check honest (a split gate needs
an aggregate `gate` job that fails unless every need succeeded); triggers
on pull_request, push to `main`, merge_group, and manual dispatch;
`contents: read` only; per-ref concurrency with cancel-in-progress; the
checkout action is pinned by full SHA (v7.0.1) with
`persist-credentials: false`; the project toolchain is installed in the
marked step. The `branches: [main]` push trigger must be adjusted to the
configured base branch on adoption (the template hard-codes `main`).

### 5.4 `templates/branch-ruleset.json` (POSTed, not copied)

```json
{
  "name": "teamflow: reviewed and gated",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          {"context": "gate", "integration_id": 15368},
          {"context": "teamflow/code-review"}
        ]
      }
    }
  ]
}
```

Behaviour notes: applies to the default branch only, enforced, no
bypass actors; forbids deletion and non-fast-forward pushes; the
`pull_request` rule needs zero approving reviews (human review is not the
gate — teamflow's own `teamflow/code-review` status is), dismisses stale
reviews on push, requires review-thread resolution; `required_status_checks`
requires both contexts — `gate` (the CI job, pinned to the GitHub App
integration `15368` so other `gate` checks cannot impersonate it) and
`teamflow/code-review` (the status `tf pr review` sets, `tf.md` §10).
This ruleset is what makes `tf pr merge`'s enforced path work: with it,
GitHub itself refuses a merge without both contexts green. The `gate`
context is pinned to `integration_id: 15368` — presumably so that only
checks from that integration count, and a check merely named `gate` from
another integration cannot satisfy it. teamflow documents nothing about
this ID; the purpose is inference, unverified.

## 6. The setup-PR flow

The intended usage (teamflow's `docs/setup.md`, `skills/setup/SKILL.md`):
run `tf setup --forge <mode> --apply` **on a branch** (in a linked
worktree), inspect, commit the created files, open a PR to the base
branch and merge it. In GitHub mode the ruleset deliberately waits for a
second `tf setup --forge github --apply` **after** the setup PR merged
(§4.3), because the CI workflow must be on the default branch first.
`tf setup` never commits itself (§2), so this is always a human-merged PR.

## 7. Deltas in teamflow-pi

This doc describes teamflow. Deltas, from the decisions in
[../porting-plan.md](../porting-plan.md):

- **D2:** the config file is `.pi/teamflow.json`, not `.claude/teamflow.json`
  (Sections 2.4 and 1).
- The `.gitignore` entry `.claude/worktrees/` names where teamflow's worktrees
  live; in Pi, worktrees are created by pi-subagents (`subagent({worktree:
  true})`, porting-plan Phase 0 spike 4) — the entry must name where
  **pi-subagents** puts them, which is not decided yet (open decision for
  Phase 3/5). `.manager-state.json` and `.env` are unchanged.
- The GitHub-mode label/ruleset work (§4) is out of scope until after the
  Phase 5 local-mode run (porting-plan decision).
- The templates themselves (§5) are forge content, not harness content.
  Two of them hard-code teamflow's defaults, which a reimplementation must
  reconcile with the adopted repository: `ci.yml`'s push trigger is
  `branches: [main]` (teamflow's default base) and the ruleset pins
  `integration_id: 15368` — both as-is for the Phase 5 local-mode run,
  how GitHub-mode adoption handles them is an open decision for later.
  (Marked "not decided": the porting plan does not cover it.)

## Appendix A. Verification runs (2026-11-09)

**Suite:** in teamflow @ `423109c`, `python3 -m unittest discover -s tests
-p "test_setup.py"` → `Ran 15 tests … OK`.

**Environment:** Python 3.15.2, git 2.54.0, gh 2.103.3, macOS. Scratch repo
in `/tmp/tf-setup-scratch/repo` (fresh `git init -b main`, one empty
commit); `tf` invoked by absolute path from teamflow @ `423109c`. No LLM
model involved; every line below is a shell run.

### A.1 local dry run, fresh repo (no .gitignore, no config)

```
$ tf setup
would create scripts/gate.sh from templates/gate.sh
would create .github/pull_request_template.md from templates/pull_request_template.md
would add .manager-state.json, .claude/worktrees/, .env to .gitignore
would create .claude/teamflow.json with {"forge": "local"}
dry run: nothing changed; run again with --apply
[exit 0]
$ ls -A
.git                      # nothing was created
```

### A.2 local --apply

```
$ tf setup --apply
create scripts/gate.sh from templates/gate.sh
create .github/pull_request_template.md from templates/pull_request_template.md
add .manager-state.json, .claude/worktrees/, .env to .gitignore
create .claude/teamflow.json with {"forge": "local"}
next: fill in scripts/gate.sh, then commit these files and merge them to the base branch
[exit 0]
$ ls -l scripts/gate.sh .github/pull_request_template.md .claude/teamflow.json
-rw-r--r--@ … .claude/teamflow.json
-rw-r--r--@ … .github/pull_request_template.md
-rwxr-xr-x@ … scripts/gate.sh          # executable bit kept
$ cat .gitignore
.manager-state.json
.claude/worktrees/
.env
$ cat .claude/teamflow.json
{
  "forge": "local"
}
$ git status --porcelain
?? .claude/
?? .github/
?? .gitignore
?? scripts/                   # created, but never committed (1 commit total)
```

### A.3 second --apply

```
$ tf setup --apply
ok: scripts/gate.sh exists, left alone
ok: .github/pull_request_template.md exists, left alone
ok: .gitignore covers teamflow's runtime files
ok: .claude/teamflow.json exists
next: fill in scripts/gate.sh, then commit these files and merge them to the base branch
[exit 0]
```

### A.4 customised gate.sh survives a re-apply

```
$ echo '#!/bin/sh
> # customised' > scripts/gate.sh
$ tf setup --apply | grep -c "create"
0
$ cat scripts/gate.sh
#!/bin/sh
# customised
```

### A.5 existing config with another forge is reported, not changed

```
$ echo '{"forge":"github"}' > .claude/teamflow.json
$ tf setup
…
ok: .claude/teamflow.json exists; note: it says forge github, not local, left alone
dry run: nothing changed; run again with --apply
[exit 0]
```

### A.6 config with a removed key does not stop setup

```
$ echo '{"forge":"local","loop":{"max_iterations":3}}' > .claude/teamflow.json
$ tf setup
[exit 0]        # teamflow-config would exit 2 on this key; tf setup does not
```

### A.7 invalid JSON / non-object config

```
$ echo '{nope' > .claude/teamflow.json
$ tf setup
tf: .claude/teamflow.json is not valid JSON (Expecting property name enclosed in double quotes: line 1 column 2 (char 1))
[exit 2]

$ echo '[]' > .claude/teamflow.json
$ tf setup
tf: .claude/teamflow.json is not a JSON object
[exit 2]
```

### A.8 github mode, remote is not a GitHub repository

```
$ git remote add origin ssh://git@example.com/norepo/repo.git
$ tf setup --forge github
tf: forge is github but remote 'origin' (ssh://git@example.com/norepo/repo.git) is not a GitHub repository
[exit 2]

$ tf setup --forge github --remote otherremote
tf: forge is github but remote 'otherremote' (missing) is not a GitHub repository
[exit 2]
```

(nothing was written before the failure — the hub check precedes the
copies, `bin/tf:732`; teamflow test
`test_github_checks_gh_and_remote_before_writing_anything`,
`tests/test_setup.py:144`)

### A.9 the auth check (environment note)

`gh auth status` on the verification machine printed `✓ Logged in
(GH_TOKEN)` yet exited 1, because a second, stale **keyring** account was
invalid; `tf setup --forge github` therefore reported
`tf: forge is github but gh is not authenticated (gh auth login)` [exit 2]
even though the GH_TOKEN account was healthy. With
`GH_CONFIG_DIR=/tmp/gh-empty` the check passed and the run below
proceeded. Documenting the check itself (not this machine's auth state):
`gh auth status` exit 0 is the contract.

### A.10 real GitHub-mode dry run (read-only) against `MyCookie/teamflow-pi`

Remote `origin` set to `git@github.com:MyCookie/teamflow-pi.git`; config
file present with `{"forge": "github"}`; gate.sh and PR template already
created by A.2; no config change made (dry run):

```
$ tf setup --forge github
ok: scripts/gate.sh exists, left alone
ok: .github/pull_request_template.md exists, left alone
would create .github/workflows/gate.yml from templates/ci.yml
ok: .gitignore covers teamflow's runtime files
ok: .claude/teamflow.json exists
would create label severity:high
would create label severity:medium
would create label severity:low
would create label needs-discussion
would create label area:architecture
would create label area:security
would create label area:quality
would create label area:docs
would create label area:simplicity
would create label area:research
would create label type:feature
would create label type:bug
would create label type:task
would turn on auto-merge and deletion of merged branches
later: ruleset 'teamflow: reviewed and gated' waits until .github/workflows/gate.yml is on the default branch; run tf setup --forge github --apply again after the setup PR merges
dry run: nothing changed; run again with --apply
[exit 0]
```

Cross-checks (same environment): `gh api repos/MyCookie/teamflow-pi --jq
'{allow_auto_merge, delete_branch_on_merge}'` →
`{"allow_auto_merge": null, "delete_branch_on_merge": null}` (null counts
as off → the `would turn on` line, §4.2); `gh api
repos/MyCookie/teamflow-pi/rulesets` → `[]` (no ruleset → the `later:`
line, §4.3; no `HTTP 403` → rulesets API available on this account).

### A.11 remote comes from the config file; config write would include it

```
$ echo '{"forge":"github","remote":"origin"}' > .claude/teamflow.json
$ tf setup --forge github | tail -4     # same run; remote resolved to origin from the file
would create label type:task
would turn on auto-merge and deletion of merged branches
later: ruleset 'teamflow: reviewed and gated' waits until .github/workflows/gate.yml is on the default branch; run tf setup --forge github --apply again after the setup PR merges
dry run: nothing changed; run again with --apply

$ rm .claude/teamflow.json
$ tf setup --forge github --remote origin | grep teamflow.json
would create .claude/teamflow.json with {"forge": "github", "remote": "origin"}
```
