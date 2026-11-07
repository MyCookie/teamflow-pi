# `tf` — behaviour contract

What teamflow's `tf` does, command by command, so a builder can reimplement
it from this document without opening the teamflow repository. Behaviour,
not code. Every section names its teamflow source (file and commit);
output lines are either quoted from a run I made (Appendix A) or from the
source's format strings, and are marked accordingly.

**Pinned source:** teamflow @ `423109c` (clean checkout at
`/Users/Ashish/SynologyDrive/Projects/Claude/teamflow`).
**Verification status:** local mode was exercised end-to-end in a scratch
repo (Appendix A; Pi 1.5.0, pi-subagents 0.86.0, Python 3.15.2, git 2.54.0;
no LLM model involved — pure shell runs). GitHub mode was verified by
running teamflow's own test suite against its `fake_gh` stand-in
(`python3 -m unittest discover -s tests -p "test_tf.py"` → 56 tests, OK)
and by reading `bin/tf`; it was **not** run against a live GitHub.

## 1. What `tf` is

Source: `bin/tf:2-71` @ 423109c

One interface to Issues and PRs, shared by every agent in the team, with
two forge modes selected by the repository's config:

- **`local` (default):** Issues and PRs are JSON records under the git
  common dir, shared by every worktree and never committed. The reviewer
  runs the gate locally; `tf pr merge` merges into the base branch
  locally. Nothing is pushed.
- **`github`:** Issues and PRs live on GitHub. A `teamflow/code-review`
  commit status on the reviewed head is the claim (`pending`) and the
  verdict (`success` or `failure`), replacing review labels; CI checks
  replace the reviewer's own gate run. A branch ruleset can enforce both
  the `gate` check and the verdict, in which case GitHub merges once they
  pass.

`tf` is the *only* path agents have to Issues and PRs. It reads its
configuration through `teamflow-config` (Section 3), so configuration
problems surface as `tf: <message>` on stderr with exit 2.

Errors are printed as `tf: <message>` on stderr; success output goes to
stdout. The usage text (from `tf --help`, which prints the module
docstring) lists every command:

```
tf mode
tf setup [--forge local|github] [--remote R] [--apply]   # dry run without --apply; R defaults to the configured remote
tf issue create --title T (--body B | --body-file F) [--label L ...]   # F may be - for stdin
tf issue list [--label L ...]                # open Issues carrying any label
tf issue view N
tf issue comment N (--body B | --body-file F)   # F may be - for stdin
tf issue edit N [--add-label L ...] [--remove-label L ...]   # at least one flag
# a label is non-empty, printable, with no comma, on create and edit (else exit 2)
tf issue close N
tf pr create --title T (--body B | --body-file F) [--base B]   # F may be - for stdin
tf pr list
tf pr view N
tf pr checkout N                             # review team worktree only
tf pr claim N | tf pr release N
tf pr gate N
tf pr diff N [PATH ...]                      # base...head, after tf pr checkout
tf pr review N --verdict APPROVE|REQUEST_CHANGES --sha SHA (--body B | --body-file F)   # F may be - for stdin
tf pr merge N
```

Source: `bin/tf:4-23` @ 423109c (verified verbatim by running
`tf --help`, Appendix A §15).

## 2. Exit codes

Source: `bin/tf:67-70,92-102,915-933` @ 423109c; verified in Appendix A.

| code | meaning | how it is produced |
|---|---|---|
| 0 | ok | |
| 1 | error — something went wrong | the local gate is red (any non-zero `gate.sh` exit, signal included); a CI check is red in github mode; `tf pr merge`'s git merge failed without conflicts; any failed `gh` call that is not a state refusal; an unexpected `git` failure |
| 2 | setup or usage problem | bad or missing configuration; missing tooling (`gh`, `scripts/gate.sh`); a missing `gate` CI check; invalid `TF_GATE_WAIT`/`TF_GATE_POLL`; argparse usage errors (including a missing required `--body`/`--body-file`) |
| 3 | refused because of PR/Issue state | claimed, head moved, no approval, wrong kind, not publishable, not in the main worktree, not at the PR head, a stacked PR's dependency unmerged, CI still running or unreadable at the deadline. **Exit 3 is a STOP, not a retry signal** (`bin/tf:70`) |
| 4 | the verdict of `tf pr review` is recorded but auto-merge was not armed (github mode) | the reviewer then runs `tf pr merge N` |

Internal mapping (`bin/tf:915-933`): `Refused` → 3, `SetupError` → 2,
`ArmFailed` → 4, `RuntimeError`/`OSError` → 1. `Refused` is deliberately
narrow: "the command is valid but the PR or repository state forbids it"
(`bin/tf:92-94`).

## 3. Mode and configuration

Source: `bin/tf:103-108,849-852` @ 423109c; `bin/teamflow-config:36-99`;
verified in Appendix A §12.

`tf` gets its config by running the sibling `teamflow-config` script; a
non-zero exit becomes `SetupError` (exit 2), with the `teamflow-config: `
prefix stripped. The config is **always read from the main worktree** —
never the current one: a reviewer's worktree holds the PR under review,
which must not choose the rules its own review and merge run under
(teamflow test: `test_config_comes_from_the_main_worktree_not_the_pr_under_review`,
`tests/test_tf.py:263`).

Rules (from `teamflow-config`, which `tf` depends on):

- The main worktree is the first entry of `git worktree list --porcelain`.
  If it is a **bare** repository: exit 2, `the main worktree (<root>) is a
  bare repository; teamflow needs a main worktree on the base branch to
  read its config from`. A bare dir's stray config file is never read
  (teamflow test: `test_bare_main_checkout_is_named_as_such`,
  `tests/test_tf.py:307`).
- The main worktree **must be on the base branch** (default `main`); on
  any other branch (or detached) exit 2: `the main worktree (<root>) must
  be on <base>, not <branch or "a detached HEAD">: its config is trusted
  only there. Work on other branches in separate worktrees.`
- The file is `<main worktree>/.claude/teamflow.json`. Missing file →
  defaults. Invalid JSON → exit 2: `.claude/teamflow.json is not valid
  JSON (<parser error>)`. Not a JSON object → exit 2. Unknown key → exit
  2: `unknown key '<dotted.path>'`. Wrong value type → exit 2: `'<key>'
  must be an integer|string`. Value outside the allowed set → exit 2:
  `'<key>' must be one of [...]`.
- Keys `tf` itself uses: `forge` (`local`|`github`, default `local`),
  `base` (default `main`), `remote` (default `origin`, github mode only).
  The other keys (`tdd`, `teamflow_auto_approve`, `loop.*`) are read by
  agents, not by `tf`; they are documented in `teamflow-config.md`.

`tf mode` prints `local` or `github` and exits 0 after the config and
github-prerequisite checks (a repository that adopted `github` but is
missing `gh` or has a non-GitHub remote exits 2 — never a silent fallback
to local).

## 4. Shared argument conventions

Source: `bin/tf:819-847` @ 423109c; verified in Appendix A.

- **Body:** every `issue create`, `issue comment`, `pr create`, `pr review`
  takes exactly one of `--body B` or `--body-file F` (mutually exclusive,
  one required — argparse exits 2 otherwise). `F` may be `-`, which reads
  stdin; agents pass text as a **quoted heredoc** (`<<'EOF'`) so the shell
  expands nothing (`bin/tf:819-823`). Stdin bodies are stored verbatim
  (teamflow test: `test_body_from_stdin_is_stored_verbatim`,
  `tests/test_tf.py:120`). The usage text says so for all four commands
  (teamflow test: `Usage.test_every_command_that_takes_a_body_file_says_it_may_be_stdin`,
  `tests/test_tf.py:935`).
- **Labels:** `--label` (create), `--add-label`, `--remove-label` (edit)
  are repeatable. A label must be non-empty, printable (no control
  characters, no unassigned characters, no non-ASCII spaces), and contain
  no comma — else exit 2: `invalid label <label!r>: it must be
  non-empty, with no comma or control character` (`bin/tf:830-837`). The
  comma rule exists because a comma may split in `gh` and fakes a second
  label in `issue list`; a control character fakes a line.
- **`issue edit`** needs at least one of `--add-label`/`--remove-label`
  (else exit 2: `issue edit needs --add-label or --remove-label`), and a
  label may not be on both sides at once (else exit 2: `label on both
  --add-label and --remove-label: <names>`).
- **Numbers:** `N` is always an integer.
- **`--base` on `pr create`** defaults to the configured base.

## 5. `tf mode`

Source: `bin/tf:869` @ 423109c; verified in Appendix A §1.

Prints the effective forge (`local` or `github`), exit 0. Fails with exit
2 for any configuration problem (Section 3) and, in github mode, for
github-prerequisite problems (Section 10.1).

## 6. `tf setup`

Source: `bin/tf:705-821` @ 423109c; verified in Appendix A §1 (local mode
only). Template *contents* and the github-mode setup details belong to
`tf-setup.md`.

Applies what a package cannot: `scripts/gate.sh` and the PR template are
copied into the target repo, `.gitignore` gets teamflow's runtime files,
and `.claude/teamflow.json` is created. Semantics:

- **Dry run unless `--apply`.** Every write prints `would <message>` in a
  dry run and the bare message when applied. A dry run prints
  `dry run: nothing changed; run again with --apply`; an apply prints
  `next: fill in scripts/gate.sh, then commit these files and merge them
  to the base branch`.
- `--forge local|github` (default `local`); `--remote R` (default: the
  configured remote, else `origin`; an explicit flag wins over the file).
- **Never overwrites, never commits.** An existing target prints
  `ok: <target> exists, left alone`; an existing `.claude/teamflow.json`
  prints `ok: .claude/teamflow.json exists` plus, if its `forge` differs,
  `; note: it says forge <existing>, not <forge_name>, left alone`.
- `.gitignore` gets `.manager-state.json`, `.claude/worktrees/`, `.env`
  (the missing ones only): `add <list> to .gitignore`, or `ok:
  .gitignore covers teamflow's runtime files`.
- Local-mode file copies: `scripts/gate.sh` from `templates/gate.sh`
  (kept executable), `.github/pull_request_template.md` from
  `templates/pull_request_template.md` — printed as `create <target> from
  templates/<source>` (or `would create …`).
- GitHub mode additionally: creates missing labels (13 in `LABELS`,
  `bin/tf:705-707`) as `create label <l>`; turns on `allow_auto_merge` and
  `delete_branch_on_merge` (else `turn on auto-merge and deletion of
  merged branches`); creates the branch ruleset named `teamflow: reviewed
  and gated` from `templates/branch-ruleset.json` — or defers with
  `later: ruleset '…' waits until .github/workflows/gate.yml is on the
  default branch; run tf setup --forge github --apply again after the
  setup PR merges` if the gate workflow is not yet on the default branch
  (creating the ruleset first would block the PR that adds the workflow);
  and prints `note: rulesets unavailable (<stderr>); github mode will run
  unenforced, with tf checking the gate and verdict itself` when rulesets
  are 403/Pro-gated.
- In github mode `tf setup` validates `gh` and the remote *before*
  writing anything (exit 2 per Section 10.1).
- Runs in whichever worktree it is started in, so setup files can be
  prepared on a branch and merged through a PR like any other change
  (`bin/tf:711-715`).

## 7. Issues (local mode)

Recorded in the local record store (Section 9). Numbers are shared with
PRs.

### 7.1 `tf issue create --title T (--body B | --body-file F) [--label L …]`

Source: `bin/tf:228-232` @ 423109c; verified in Appendix A §2.

Creates an open Issue. Prints `#N`. Labels validated per Section 4.

### 7.2 `tf issue list [--label L …]`

Source: `bin/tf:233-238` @ 423109c; verified in Appendix A §2.

Prints one line per **open** Issue, ascending number:

```
#N<TAB>title<TAB>label1,label2
```

`--label` filters with **OR** semantics: an Issue is listed if it carries
*any* of the given labels (teamflow test: `test_issue_lifecycle`,
`tests/test_tf.py:63-79`). No matches → no output, exit 0.

### 7.3 `tf issue view N`

Source: `bin/tf:239-244` @ 423109c; verified in Appendix A §2.

```
#N title
state: open|closed
labels: a, b          (or `labels: -` when none)

<body>

--- comment <iso-utc-seconds>
<comment body>
```

(one comment block per comment, appended in order). Refusals: `#N does
not exist` (exit 3); `#N is a PR, not an Issue` (exit 3).

### 7.4 `tf issue comment N (--body B | --body-file F)`

Source: `bin/tf:245-250` @ 423109c; verified in Appendix A §2.

Appends a comment. Prints `#N: commented`. Same refusals as view.

### 7.5 `tf issue edit N [--add-label L …] [--remove-label L …]`

Source: `bin/tf:251-256` @ 423109c; verified in Appendix A §2.

Swaps labels in one call. Prints `#N: labels: a, b` (or `#N: labels: -`).
Semantics: removes happen first, then adds in argument order; a repeated
new label is stored once; removing a label the Issue doesn't have is a
silent no-op. **Closed Issues can be relabelled, not reopened** (teamflow
test: `test_issue_edit_labels`, `tests/test_tf.py:81-99`). Refusals:
missing number (3), wrong kind (3), Section-4 label violations (2).

### 7.6 `tf issue close N`

Source: `bin/tf:257-263` @ 423109c; verified in Appendix A §2.

Sets `state: closed`. Prints `#N: closed`. Closed Issues disappear from
`issue list`; `issue view` still shows them. Refusals: missing number (3),
wrong kind (3).

## 8. Pull requests (local mode)

### 8.1 `tf pr create --title T (--body B | --body-file F) [--base B]`

Source: `bin/tf:265-275,144-159` @ 423109c; verified in Appendix A §3.

Opens a PR record for the current branch. Refusals, all exit 3, checked in
this order (`check_publishable`, `bin/tf:144-155`):

1. `detached HEAD; run this from the feature branch`
2. `refusing to open a PR from <base>` — the current branch *is* the base
3. `working tree is dirty; commit before publishing:` + the
   `git status --porcelain` listing

Then `check_body` (`bin/tf:157-159`): if `.github/pull_request_template.md`
exists in the current worktree and the body equals it (stripped), refuse:
`the PR body is the unmodified .github/pull_request_template.md; fill it
in first` — inline `--body` and `--body-file` are both caught.

Then the duplicate check (`bin/tf:269-271`): if an open PR already exists
for this branch, refuse `#M is already open for <branch>`.

Prints `#N (<branch> -> <base>)`. `--base` defaults to the configured
base, so stacked PRs are created with `--base <dependency branch>`.

### 8.2 `tf pr list`

Source: `bin/tf:276-281` @ 423109c; verified in Appendix A §4.

One line per open PR, ascending number:

```
#N<TAB>title<TAB>branch -> base
```

### 8.3 `tf pr view N`

Source: `bin/tf:282-297` @ 423109c; verified in Appendix A §4, §9, §10.

```
#N title
state: open|merged
branch: <branch> -> <base>
head: <full sha of the branch tip>   (or `(branch missing)`)
claimed: yes|no
files: f1, f2          (or `files: -`)

<body>

--- review <iso>: VERDICT at <sha>
<review body>
```

(one review block per recorded review, appended in order) `files` is
`git diff --name-only <base>...<tip>` for an open PR (empty when the
branch is missing — verified, Appendix A §11), and for a merged PR
`git diff --name-only merged_sha^1 merged_sha` (the merge commit against
its first parent). Refusals: missing number (3), `#N is an Issue, not a
PR` (3).

### 8.4 `tf pr checkout N`

Source: `bin/tf:298-309,162-170` @ 423109c; verified in Appendix A §5, §13.

For the review team only. Refusals (exit 3):

- `refusing to run in the main worktree (<main>); reviews run in their own`
- `branch <branch> does not exist`

Then detaches the current worktree at the branch tip and prints
`tf: detached at <sha12> (<branch>)`. Finally `.env` handling
(`copy_env`, `bin/tf:162-170`): if the main worktree has an untracked
`.env`, it is copied into the review worktree and `tf: copied .env from
the main worktree (rm -f .env when done)` is printed. If the worktree
being checked out contains a tracked `.env.example` but the main worktree
worktree has no `.env`: **exit 2**, `.env.example exists but <main> has no
.env; stop and report` (on stderr; the detach has already happened — the
true order, per source, is the `tf: detached at …` stdout line first, then
the refusal; when output is redirected the stderr line can appear
earlier; teamflow test: `test_env_example_without_env_stops_checkout`,
`tests/test_tf.py:289`). The `.env` is never invented.

### 8.5 `tf pr claim N`

Source: `bin/tf:314-321` @ 423109c; verified in Appendix A §5.

Creates `claims/<N>/` in the record store. Prints `#N: claimed`. A second
claim is refused: `#N is already claimed by another reviewer` (exit 3).
One reviewer per PR; the claim is the local-mode equivalent of the
`teamflow/code-review` pending status in github mode.

### 8.6 `tf pr release N`

Source: `bin/tf:322-328` @ 423109c; verified in Appendix A §9.

Removes the claim dir. Prints `#N: released`. Releasing a PR that was
never claimed is a silent no-op (still prints the line, exit 0).

### 8.7 `tf pr gate N`

Source: `bin/tf:329-337` @ 423109c; verified in Appendix A §5.

The reviewer's own gate run, local mode only:

- The current worktree must be at the PR's head (as set by `tf pr
  checkout`), else exit 3: `this worktree is not at #N's head; run tf pr
  checkout N first`.
- `scripts/gate.sh` must exist and be executable, else exit 2:
  `scripts/gate.sh is missing or not executable`.
- It runs `./scripts/gate.sh` in the worktree. **Any** non-zero exit — 1,
  2, 3, 127, or a signal — makes `tf pr gate` exit **1**
  (`bin/tf:336-337`): gate's own exit codes must not read as a setup
  problem or a STOP (teamflow test: `test_pr_review_and_merge`,
  `tests/test_tf.py:128-201`). Success prints nothing, exit 0.

### 8.8 `tf pr diff N [PATH …]`

Source: `bin/tf:310-313` @ 423109c; verified in Appendix A §5, §10.

Prints `git diff <base>...<tip> -- [PATH …]` (three-dot: changes on the PR
side of the fork point). After `tf pr checkout`, the worktree is at the
head. A path that changed nothing prints an empty diff, exit 0. If the
branch is missing the diff is empty, exit 0 (no refusal — verified,
Appendix A §11).

### 8.9 `tf pr review N --verdict APPROVE|REQUEST_CHANGES --sha SHA (--body B | --body-file F)`

Source: `bin/tf:338-345` @ 423109c; verified in Appendix A §6, §7.

Records a review on the PR. `SHA` must equal the branch tip now, else
exit 3: `#N's head moved since <sha12>; review the new head`. Prints
`#N: <VERDICT> recorded at <sha12>`. Reviews accumulate in the record
(the merge trailer counts them as rounds).

### 8.10 `tf pr merge N`

Source: `bin/tf:346-400,172-176` @ 423109c; verified in Appendix A
§8-10.

Merges locally into the configured base. Preconditions, all exit 3, in
order:

1. `#N is <state>` — the PR must be `open`.
2. `#N targets <b>, not <base>: merge its dependency first, then
   retarget` — a stacked PR cannot merge until its dependency is merged
   (the dependency's merge then retargets it: the Success outcome below).
3. `#N has no APPROVE for its current head <sha12>` — the **last**
   recorded review must be `APPROVE` *and* for the current tip. A later
   push invalidates an older approval (verified: rework cycle, Appendix
   A §7).
4. `the <base> checkout at <holder> has uncommitted changes; ask the
   human` — if another worktree has the base branch checked out and its
   tracked tree is dirty, the human's work wins.

The merge itself: `git checkout --detach <old base tip>`, then
`git merge --no-ff` with subject `Merge <branch>: <title>` and a second
message containing one `Closes #<i>` line per issue reference found in
the PR body (a verb — `close`/`closes`/`closed`, `fix`/`fixes`/`fixed`,
`resolve`/`resolves`/`resolved` — followed by whitespace and `#N`,
case-insensitive; `closes()`, `bin/tf:172-176`) plus
`Reviewed-by: teamflow:review-lead (round <n>)` where `<n>` is the total
number of recorded reviews (verified: 2 reviews → `round 2`, Appendix A
§10).

Outcomes:

- **Conflict:** the merge is aborted (`git merge --abort`) and the
  command exits 3: `#N conflicts with <base> in <files>; the
  implementer must rebase`. The worktree is left clean (teamflow test:
  `test_conflict_is_refused_as_a_rebase`, `tests/test_tf.py:246`).
- **Non-conflict failure:** exit 1: `merging #N failed:` + git's output
  (teamflow test:
  `test_a_failed_merge_that_is_not_a_conflict_is_an_error`,
  `tests/test_tf.py:253`).
- **Success:** the base branch is advanced (fast-forward in the holding
  worktree, or `update-ref` if no worktree holds it), the record becomes
  `state: merged` with `merged_sha` and `merged_at`, and:
  - every open PR whose `base` was the merged branch is retargeted to the
    real base, printing `#M: retargeted to <base>` for each (before the
   final line) (teamflow test:
    `test_merging_a_dependency_retargets_its_stacked_pr`,
    `tests/test_tf.py:215`);
  - every issue referenced by `Closes #i` in the body is closed
    (silently) (verified: Appendix A §9);
  - `#N: merged into <base> at <sha12>`.

## 9. Local record store

Source: `bin/tf:179-226,265-274` @ 423109c; layout verified in Appendix A
§11.

```
<git common dir>/teamflow/
  items/<N>.json      # one file per Issue or PR
  claims/<N>/         # an empty directory = the PR is claimed
```

- The common dir comes from `git rev-parse --path-format=absolute
  --git-common-dir`, so **all worktrees of the repository share one store**
  (verified: `pr view` from any worktree sees the same records). The
  store is never committed (`.gitignore` via `tf setup`).
- **Numbering:** Issues and PRs share one sequence. The next number is
  `max(existing) + 1`, taken with `O_EXCL` and bumped on collision
  (`_new`, `bin/tf:211-222`).
- **Writes** are atomic: write to `<N>.json.tmp`, then rename.
- **Reads:** a missing number is a refusal (`#N does not exist`), as is a
  kind mismatch (`#N is a PR, not an Issue` / `#N is an Issue, not a
  PR`).

Record shapes (exactly what is written; verified in Appendix A §12):

```jsonc
// items/N.json — Issue
{ "number": 1, "created_at": "2026-11-06T23:48:46+00:00",
  "kind": "issue", "title": "Ship v2", "body": "…",
  "labels": ["area:docs"], "state": "open",          // or "closed"
  "comments": [ { "at": "…", "body": "…" } ] }

// items/N.json — PR
{ "number": 3, "created_at": "…",
  "kind": "pr", "title": "feat: v2", "body": "…",
  "branch": "feat/1", "base": "main", "state": "open", // or "merged"
  "reviews": [ { "at": "…", "verdict": "APPROVE",
                 "sha": "<full>", "body": "…" } ],
  "merged_sha": "…", "merged_at": "…" }             // added on merge
```

`created_at`/`at`/`merged_at` are UTC ISO-8601 with seconds
(`bin/tf:110-112`).

## 10. GitHub mode

Verified by teamflow's test suite (`tests/test_tf.py:379-932`, run OK)
plus source reads; **not** run live by teamflow-pi.

### 10.1 Preconditions

Source: `bin/tf:420-436` @ 423109c.

Checked once, in the constructor, for **every** command; any failure is
exit 2, and the command stops — never a silent fallback to local
(teamflow test: `test_adopted_github_without_github_remote_stops`,
`tests/test_tf.py:370`):

- the configured remote (`remote`, default `origin`) must resolve to a
  GitHub URL (`github.com[:/]owner/repo[.git]`), else `forge is github
  but remote '<remote>' (<url or 'missing'>) is not a GitHub
  repository`;
- `gh` must be on PATH, else `forge is github but gh is not installed`
  (teamflow test: `test_missing_gh_stops`, `tests/test_tf.py:919`);
- `gh auth status` must pass, else `forge is github but gh is not
  authenticated (gh auth login)` (teamflow test:
  `test_logged_out_gh_stops`, `tests/test_tf.py:928`).

### 10.2 Claim and verdict as commit statuses

Source: `bin/tf:438-451,534-550,626-640` @ 423109c; teamflow test
`test_claim_gate_review_and_unenforced_merge`, `tests/test_tf.py:497-538`.

On the reviewed head, in context `teamflow/code-review`:

| event | status set | description |
|---|---|---|
| `tf pr claim N` | `pending` | `review in progress` |
| `tf pr review … --verdict APPROVE` | `success` | `APPROVE by teamflow:review-lead` |
| `tf pr review … --verdict REQUEST_CHANGES` | `failure` | `REQUEST_CHANGES by teamflow:review-lead` |
| `tf pr release N` while pending | `error` | `review abandoned without a verdict` |

- `pr claim` first reads the head's latest such status; if it is
  `pending`, refuse `#N is already claimed by another reviewer` (exit
  3), else print `#N: claimed at <sha12>`. (Known check-then-set race,
  `bin/tf:534-536`.) `pr release` prints `#N: released` either way.
- "Approved" for merge purposes means: the latest `teamflow/code-review`
  status on the head is `success` — a pending claim or a failure verdict
  is `#N has no APPROVE for its current head <sha12>` (exit 3) (teamflow
  test: `test_merge_refuses_a_rejected_or_merely_claimed_head`,
  `tests/test_tf.py:741`).

### 10.3 Per-command differences from local

Source: `bin/tf:453-543` @ 423109c.

- `issue create` / `issue comment` / `issue close` / `pr create`: print
  the URL `gh` prints. `pr create` first pushes the branch
  (`git push -u <remote> <branch>`) after the same publishable and
  unedited-template refusals as local (exit 3).
- `issue list`: open Issues, limit 200, label filter via `--search
  label:"l1","l2"` (OR), same `#N<TAB>title<TAB>labels` line.
- `issue view`: formatted from `gh issue view --json` — the code comment
  says `gh issue view --comments` prints only the comments when stdout
  is not a terminal, and agents never have one (`bin/tf:464-466`;
  teamflow test: `test_issue_view_prints_without_a_terminal`,
  `tests/test_tf.py:449`). Same block shape as local, with `state`
  lowercased (`open`/`closed`).
- `issue edit`: the REST issues endpoint answers for PRs too, so a PR
  number is refused as `#N is a PR, not an Issue` (exit 3) and a missing
  number as `#N does not exist` (exit 3) — both checked before `gh`
  edits anything. On success prints `#N: labels: a, b` (labels read
  back), matching local mode (teamflow tests: `test_issue_edit_labels`,
  `tests/test_tf.py:459`; `test_issue_edit_matches_local_mode`,
  `tests/test_tf.py:477`).
- `pr list`: same line shape as local.
- `pr view`: same shape as local plus three github-only lines:

  ```
  teamflow/code-review: <state> (<description>)    (or `none`)
  merge state: <mergeStateStatus lowercased, e.g. clean|behind>
  auto-merge: on|off
  ```

  (teamflow tests: `test_pr_view_shows_the_merge_state`,
  `tests/test_tf.py:489`; `test_pr_view_shows_the_auto_merge_state`,
  `tests/test_tf.py:781`)
- `pr checkout`: refuses the main worktree (exit 3, same message), then
  `git fetch <remote> <headRefName>`; if `FETCH_HEAD` no longer equals
  the PR's `headRefOid`, refuse `#N's head moved while fetching; run tf
  pr checkout N again` (exit 3). Detaches at the head: `tf: detached at
  <sha12> (<headRefName>)`; same `.env` copy rules as local.
- `pr diff`: fetches the base branch; if the head OID is not in this
  clone, refuse `#N's head is not in this clone; run tf pr checkout N
  first` (exit 3). Prints `git diff FETCH_HEAD...<head> -- [PATH …]`.
- `pr gate`: CI replaces the reviewer's local run — see 10.4.

### 10.4 `tf pr gate` — CI polling and judging

Source: `bin/tf:402-417,551-624` @ 423109c; teamflow tests
`test_gate_*`, `tests/test_tf.py:540-613,695-707,760-768`.

Timing: `TF_GATE_WAIT` seconds (default 480) and `TF_GATE_POLL` seconds
(default 15). Both must be finite numbers, `wait >= 0`, `poll > 0`, else
exit 2: `TF_GATE_WAIT must be a number of seconds >= 0 and TF_GATE_POLL
one > 0` (`bin/tf:402-417`; also enforced for `tf pr merge`). `wait = 0`
is valid: poll once (teamflow test: `test_gate_rejects_wait_settings_*`,
`tests/test_tf.py:604`).

Polling (`polls`, `bin/tf:570-596`): one deadline for the whole command.
Each poll makes up to two `gh pr checks <N> --json
name,bucket,state,workflow,event,link,startedAt,completedAt,description`-shaped
reads (own `teamflow/code-review` status excluded from both):

1. the **required** checks (`--required`); if that list is non-empty, it
   gates the PR;
2. only when (1) was empty, the full list, filtered to the `gate` check.

On the unenforced merge path (`own` mode) read (1) is never made: the
`gate` check alone gates it (Section 10.6). A failed read is recorded and
**retried** on the next poll — never a fallback to `gate` alone on a
failed `--required` query (teamflow test:
`test_gate_retries_a_failed_or_empty_poll`, `tests/test_tf.py:573`). `gh
pr checks` exits 8 while checks are pending, so a JSON list on stdout is
what counts, not the exit code (`bin/tf:551-569`); `gh`'s "no [required]
checks reported" on stderr means an empty list, while any other
stdout-only failure is treated as unreadable CI → exit 3 (teamflow test:
`test_gate_treats_a_non_list_or_stdout_only_failure_as_unreadable_ci`,
`tests/test_tf.py:695`).

Announcements on stdout:

- `waiting for: <names>` — printed **once**, when pending checks are
  first seen (teamflow test: `test_gate_waits_for_pending_checks`,
  `tests/test_tf.py:540` — asserts exactly one announcement).
- `<name>: <bucket>` — one line per check, from the final judgment.
- If still pending at the deadline, the command prints the PR's head
  SHA (read after the wait — or `head: unreadable (<e>)` if that read
  fails) and, per pending check, the full gh JSON object (`state`,
  `workflow`, `event`, `link`, `startedAt`,
  `completedAt`, `description`), indented, to tell a slow run from a stale
  rollup (teamflow test:
  `test_gate_gives_up_with_the_pending_checks_fields_and_the_head`,
  `tests/test_tf.py:558`).

Judgment (`judge`, `bin/tf:597-617`), in order:

| final state | exit | message |
|---|---|---|
| the read itself still failed at the deadline | 3 | `could not read CI within <wait>s: <error>` |
| no `gate` check at all (empty list at deadline) | 2 | `#N has no `gate` check; add templates/ci.yml as .github/workflows/gate.yml` |
| still pending at the deadline | 3 | `CI did not finish within <wait>s; still running: <names>` |
| any gating check not `pass` | 1 | (after printing each `<name>: <bucket>`) |
| all `pass` | 0 | |

A failed poll at the deadline is a STOP (3), not exit 1 — CI's state is
unknown (teamflow test:
`test_merge_treats_unreadable_ci_as_a_stop_not_an_error`,
`tests/test_tf.py:623`).

### 10.5 `tf pr review` — verdict and auto-merge arming

Source: `bin/tf:631-664` @ 423109c; teamflow tests `test_approve_*`,
`test_request_changes_*`, `test_arming_failure_*`,
`tests/test_tf.py:845-917`.

1. `SHA` must equal the PR's `headRefOid` now, else exit 3 (`#N's head
   moved since <sha12>; review the new head`).
2. The body is posted as a normal PR comment (`gh pr review --comment`).
3. The commit status is set (Section 10.2), and `#N: <VERDICT> recorded
   at <sha12>` is printed.
4. Only for `APPROVE`, `arm()` runs, in order:
   - If the PR targets a branch other than the configured base, print
     `#N targets <b>, not <base>: auto-merge not enabled; merge its
     dependency first` and stop (exit 0) — a stacked PR is never armed
     (teamflow test: `test_approve_on_a_stacked_pr_arms_nothing`,
     `tests/test_tf.py:867`).
   - Read the ruleset for the base (`repos/<slug>/rules/branches/<base>`).
     It must be a `required_status_checks` rule requiring **both** `gate`
     and `teamflow/code-review` (`ruleset_requires_review`,
     `bin/tf:642-647`). Without that, print `#N: no ruleset requires
     `gate` and `teamflow/code-review`: auto-merge not enabled; run tf
     pr merge N` and stop (exit 0). A ruleset that requires *other*
     contexts only is treated the same: tf does not trust it and falls
     back to its own checks at merge time (teamflow test:
     `test_approve_arms_nothing_unless_the_ruleset_requires_both_contexts`,
     `tests/test_tf.py:880`).
   - Otherwise arm: `gh pr merge <N> --auto --merge
     --match-head-commit <headRefOid> --subject "Merge <head>: <title>"
     --body "<Closes lines>Reviewed-by: teamflow:review-lead"` — pinned
     to the reviewed head, so a later push cannot be auto-merged
     (teamflow test: `test_approve_arms_auto_merge_on_a_ruleset_repository`,
     `tests/test_tf.py:845`; the review body is deliberately *not*
     reused as the merge body). If the PR is already clean, armed
     auto-merge merges at once (teamflow test:
     `test_approve_that_makes_the_pr_clean_can_merge_it_at_once`,
     `tests/test_tf.py:857`). Prints `gh`'s output, or `#N:
     auto-merge requested; tf pr view N shows whether GitHub merged it
     or queued it`.
   - If arming fails (including an unreadable ruleset) **after the
     verdict was recorded**: exit 4, `verdict recorded, but auto-merge
     was not enabled (<error>); run tf pr merge N`. The verdict stays;
     `tf pr merge` is the fallback (teamflow test:
     `test_arming_failure_after_the_verdict_exits_4_and_keeps_the_verdict`,
     `tests/test_tf.py:901`). `REQUEST_CHANGES` never arms (teamflow
     test: `test_request_changes_arms_nothing`, `tests/test_tf.py:893`).

### 10.6 `tf pr merge` — enforced vs unenforced

Source: `bin/tf:670-702` @ 423109c; teamflow tests
`test_unenforced_merge_*`, `test_merge_*`, `test_ruleset_merge_*`,
`tests/test_tf.py:615-827`.

Preconditions (exit 3): the PR must be open, must target the configured
base (`#N targets <b>, not <base>: merge its dependency first`, teamflow
test: `test_merge_refuses_a_rejected_or_merely_claimed_head_does_not_target_the_base`,
`tests/test_tf.py:750`), and the head must be approved (Section 10.2).

Then the ruleset is read to decide which path runs. An unreadable
ruleset never arms auto-merge: tf prints `#N: could not read the
ruleset (<e>): checking `gate` and the verdict myself, then merging
directly` and takes the unenforced path (teamflow test:
`test_merge_does_not_arm_auto_merge_on_an_unreadable_ruleset`,
`tests/test_tf.py:829`).

**Enforced path** (ruleset requires both contexts): GitHub enforces the
required checks, so `tf pr merge` does **not** wait for pending checks —
it polls the required-checks read only to tolerate a failed read (one
deadline), then rechecks, all within the single `TF_GATE_WAIT` deadline
(`bin/tf:678-688`; teamflow test:
`test_ruleset_merge_does_not_wait_for_pending_checks_then_arms_auto_merge`,
`tests/test_tf.py:789`):

- the head did not move during the wait, else exit 3: `#N's head moved
  from <a12> to <b12> during the wait; review the new head` (teamflow
  test: `test_merge_refuses_a_head_that_moved_during_the_wait`,
  `tests/test_tf.py:686`);
- the PR is still open, else exit 3: `#N is not open any more
  (<state>)` (teamflow test:
  `test_merge_refuses_a_pr_that_closed_during_the_wait`,
  `tests/test_tf.py:692`);
- the base is still the configured base (teamflow test:
  `test_merge_refuses_a_pr_retargeted_during_the_wait`,
  `tests/test_tf.py:689`).

It then enables auto-merge (`gh pr merge … --auto`, same args as
arming) and prints `gh`'s output or `#N: auto-merge enabled; GitHub
merges once every required check passes`. A pending or even a red
required check does not stop it (teamflow test:
`test_enforced_repository_uses_auto_merge`, `tests/test_tf.py:770`).

**Unenforced path** (no such ruleset, or unreadable): tf is the process
control. It polls the `gate` check alone (required checks are not read
on this path at all, teamflow test:
`test_unenforced_merge_has_one_deadline_and_never_reads_required_checks`,
`tests/test_tf.py:658`) until pass, within the one deadline
(teamflow test: `test_unenforced_merge_waits_for_pending_checks`,
`tests/test_tf.py:615`), then judges per 10.4 — an unreadable gate
check at the deadline is a STOP, nothing merged (teamflow test:
`test_unenforced_merge_treats_an_unreadable_gate_check_as_a_stop`,
`tests/test_tf.py:647`), and a red check exits 1. After the wait it
**rereads everything** and refuses (exit 3) if the head moved, the PR
closed, the base changed, or the approval is no longer a `success` on
the head — a review revoked during the wait is caught (teamflow test:
`test_unenforced_merge_rereads_the_approval_after_the_wait`,
`tests/test_tf.py:709`). Finally it merges directly:
`gh pr merge <N> --merge --match-head-commit <headRefOid>` with the
same subject and body as arming; prints `gh`'s output or `#N: merged`.
Whatever else the repo requires, this path judges the `gate` check
alone; if another required check is red, GitHub is *expected* to refuse
that merge (exit 1) — noted in the usage text as "by reading only, not
observed" (`bin/tf:38-40`).

## 11. Deltas in teamflow-pi

This doc describes teamflow. Where teamflow-pi deliberately differs, the
decision and its meaning are in [../porting-plan.md](../porting-plan.md);
for `tf` the known deltas are:

- **D2:** config lives at `.pi/teamflow.json`, not
  `.claude/teamflow.json` (Section 3's file path, and `tf setup`'s
  target, change accordingly).
- **D4:** agents find `tf` on PATH via a Pi `spawnHook` extension, not a
  Claude Code session hook.
- `tf setup`'s github-mode label/ruleset work is out of scope until
  after the Phase 5 local-mode run ("Later" in the plan).

Everything else in this contract is intended to be preserved.

## Appendix A. Verification runs (2026-11-06)

**Suite:** in teamflow @ `423109c`,
`python3 -m unittest discover -s tests -p "test_tf.py"` → `Ran 56 tests
… OK`; `python3 -m unittest discover -s tests -p "test_setup.py"` →
`Ran 15 tests … OK`. (A full `discover -s tests` run additionally has 23
failures, all in `tests/test_agents.py` `QuotingCheck` —
`bash: quoting_is_safe: command not found`: that helper is not on PATH in
this environment. Unrelated to `tf`; noted so a later phase doesn't
chase it.)

**Environment:** Python 3.15.2, git 2.54.0, macOS. Scratch repo in
`/tmp/tf-contract-scratch`: `main` worktree (on `main`) with
`scripts/gate.sh` (exits `${GATE_EXIT:-0}`),
`.github/pull_request_template.md` (content `## Issue`), `app.txt`;
worktree `impl` on branch `feat/1`; a separate detached worktree `rev`
for reviews; more worktrees per scenario. No LLM model was involved;
every line below is a shell run of teamflow's `bin/tf` (absolute path).

### A.1 `mode` and `setup`

```
$ tf mode
local
[exit 0]

$ tf setup                                    # first dry run
ok: scripts/gate.sh exists, left alone
ok: .github/pull_request_template.md exists, left alone
would add .manager-state.json, .claude/worktrees/, .env to .gitignore
would create .claude/teamflow.json with {"forge": "local"}
dry run: nothing changed; run again with --apply
[exit 0]

$ tf setup --apply
ok: scripts/gate.sh exists, left alone
ok: .github/pull_request_template.md exists, left alone
add .manager-state.json, .claude/worktrees/, .env to .gitignore
create .claude/teamflow.json with {"forge": "local"}
next: fill in scripts/gate.sh, then commit these files and merge them to the base branch
[exit 0]

$ tf setup                                   # second dry run, all in place
ok: scripts/gate.sh exists, left alone
ok: .github/pull_request_template.md exists, left alone
ok: .gitignore covers teamflow's runtime files
ok: .claude/teamflow.json exists
dry run: nothing changed; run again with --apply
[exit 0]
```

### A.2 Issues

```
$ tf issue create --title 'Ship v2' --body-file - <<'EOF'    # stdin: 'Adds v2.' / '' / 'Closes #1'
#1
[exit 0]

$ tf issue create --title 'Docs cleanup' --body-file - --label area:docs --label type:task
#2
[exit 0]

$ tf issue list
#1	Ship v2	
#2	Docs cleanup	area:docs,type:task
[exit 0]

$ tf issue list --label area:docs --label type:bug    # OR: #2 matches on area:docs
#2	Docs cleanup	area:docs,type:task
[exit 0]

$ tf issue view 1
#1 Ship v2
state: open
labels: -

Adds v2.

Closes #1
[exit 0]

$ tf issue comment 1 --body 'seen it'
#1: commented
[exit 0]

$ tf issue edit 2 --add-label needs-discussion
#2: labels: area:docs, type:task, needs-discussion
[exit 0]

$ tf issue edit 2                                # no flags
tf: issue edit needs --add-label or --remove-label
[exit 2]

$ tf issue edit 2 --add-label 'bad,label'
tf: invalid label 'bad,label': it must be non-empty, with no comma or control character
[exit 2]

$ tf issue view 99
tf: #99 does not exist
[exit 3]

$ tf issue close 2
#2: closed
[exit 0]

$ tf issue edit 2 --add-label late               # closed issues can be relabelled
#2: labels: area:docs, type:task, needs-discussion, late
[exit 0]

$ tf pr view 1
tf: #1 is an Issue, not a PR
[exit 3]
```

### A.3 `pr create` and its refusals (worktree `impl`, branch `feat/1`)

```
$ tf pr create --title x --body x                # dirty tree
tf: working tree is dirty; commit before publishing:
M app.txt
[exit 3]

$ tf pr create --title x --body-file .github/pull_request_template.md    # unedited template
tf: the PR body is the unmodified .github/pull_request_template.md; fill it in first
[exit 3]

$ tf pr create --title x --body '## Issue'       # same text inline
tf: the PR body is the unmodified .github/pull_request_template.md; fill it in first
[exit 3]

$ tf pr create --title 'feat: v2' --body 'Adds v2. Closes #1'
#3 (feat/1 -> main)
[exit 0]

$ tf pr create --title again --body y            # duplicate branch
tf: #3 is already open for feat/1
[exit 3]

$ tf pr create --title from-main --body y        # from the base branch
tf: refusing to open a PR from main
[exit 3]

$ tf pr create --title 'stacked' --body 'Stacked.' --base feat/1   # untracked file = dirty
tf: working tree is dirty; commit before publishing:
?? top.txt
[exit 3]
```

### A.4 `pr list` / `pr view` (before review)

```
$ tf pr list
#3	feat: v2	feat/1 -> main
[exit 0]

$ tf pr view 3
#3 feat: v2
state: open
branch: feat/1 -> main
head: c56446e65bc4de1d5072304fac2030a9021f360e
claimed: no
files: app.txt

Adds v2. Closes #1
[exit 0]
```

### A.5 claim / checkout / gate / diff

```
$ tf pr claim 3
#3: claimed
[exit 0]

$ tf pr claim 3
tf: #3 is already claimed by another reviewer
[exit 3]

$ tf pr checkout 3                            # from the main worktree
tf: refusing to run in the main worktree (/private/tmp/tf-contract-scratch/main); reviews run in their own
[exit 3]

$ tf pr gate 3                                # in rev worktree, not at head yet
tf: this worktree is not at #3's head; run tf pr checkout 3 first
[exit 3]

$ tf pr checkout 3
tf: detached at c56446e65bc4 (feat/1)
[exit 0]

$ git rev-parse --abbrev-ref HEAD
HEAD                                          # detached, as expected

$ tf pr gate 3
[exit 0]                                      # silent success

$ GATE_EXIT=1 tf pr gate 3
[exit 1]

$ GATE_EXIT=127 tf pr gate 3
[exit 1]                                      # 2/3/127/signal all read as 1

$ tf pr diff 3 app.txt
diff --git a/app.txt b/app.txt
index ce01362..8c1384d 100644
--- a/app.txt
+++ b/app.txt
@@ -1 +1 @@
-hello
+v2
[exit 0]
```

### A.6 review / merge refusals

```
$ tf pr review 3 --verdict APPROVE --sha 0000000000000000000000000000000000000000 --body nope
tf: #3's head moved since 000000000000; review the new head
[exit 3]

$ tf pr review 3 --verdict REQUEST_CHANGES --sha c56446e65bc4de1d5072304fac2030a9021f360e --body 'fix it'
#3: REQUEST_CHANGES recorded at c56446e65bc4
[exit 0]

$ tf pr merge 3                               # last verdict REQUEST_CHANGES
tf: #3 has no APPROVE for its current head c56446e65bc4
[exit 3]
```

### A.7 rework invalidates an old approval

```
# implementer commits a fix; PR head moves
$ tf pr review 3 --verdict APPROVE --sha c56446e65bc4de1d5072304fac2030a9021f360e --body ok
tf: #3's head moved since c56446e65bc4; review the new head
[exit 3]

$ tf pr checkout 3
tf: detached at 9db33f87eb3b (feat/1)
[exit 0]

$ tf pr review 3 --verdict APPROVE --sha 9db33f87eb3b4bb558724d78325449693fdc7e9b --body ok
#3: APPROVE recorded at 9db33f87eb3b
[exit 0]
```

### A.8 dirty main checkout

```
# main worktree has an uncommitted app.txt edit
$ tf pr merge 3
tf: the main checkout at /private/tmp/tf-contract-scratch/main has uncommitted changes; ask the human
[exit 3]
```

### A.9 post-merge state, re-merge, release, trailer

```
$ tf pr merge 3
#3: merged into main at cc93e296212c
[exit 0]

$ tf pr view 3
#3 feat: v2
state: merged
branch: feat/1 -> main
head: 9db33f87eb3b4bb558724d78325449693fdc7e9b
claimed: yes
files: app.txt

Adds v2. Closes #1

--- review 2026-11-06T23:49:25+00:00: REQUEST_CHANGES at c56446e65bc4de1d5072304fac2030a9021f360e
fix it

--- review 2026-11-06T23:50:12+00:00: APPROVE at 9db33f87eb3b4bb558724d78325449693fdc7e9b
ok
[exit 0]

$ tf pr merge 3
tf: #3 is merged
[exit 3]

$ tf pr release 3
#3: released
[exit 0]

$ tf pr release 3                            # never claimed: silent no-op
#3: released
[exit 0]

$ tf issue view 1                            # closed by "Closes #1" in the PR body
#1 Ship v2
state: closed
labels: -

Adds v2.

Closes #1

--- comment 2026-11-06T23:48:45+00:00
seen it
[exit 0]

$ git log -1 --format=%B                     # merge commit: subject + trailer
Merge feat/1: feat: v2

Closes #1
Reviewed-by: teamflow:review-lead (round 2)
```

### A.10 stacked PR retarget

```
# PR #6 on feat/6 -> main (approved at its head); PR #7 on feat/7 -> feat/6
$ tf pr merge 6
#7: retargeted to main
#6: merged into main at 105cb1fe3700
[exit 0]

$ tf pr view 7
#7 stack7
state: open
branch: feat/7 -> main
head: 8617abd8e6312e4d0d859483a84f4f97960378c5
claimed: no
files: top.txt

Top.
[exit 0]

$ tf pr merge 7                              # retargeted but not reviewed
tf: #7 has no APPROVE for its current head 8617abd8e631
[exit 3]

$ tf pr view 7                               # branch deleted: head + files degrade, no refusal
#7 stack7
state: open
branch: feat/7 -> main
head: (branch missing)
claimed: no
files: -

Top.
[exit 0]

$ tf pr diff 7                               # empty diff, no refusal
[exit 0]
```

### A.11 record store layout

```
$ git rev-parse --path-format=absolute --git-common-dir
/private/tmp/tf-contract-scratch/main/.git

$ ls -R /private/tmp/tf-contract-scratch/main/.git/teamflow
claims
items

claims:

items:
1.json 2.json 3.json 4.json 5.json 6.json 7.json

$ cat /private/tmp/tf-contract-scratch/main/.git/teamflow/items/3.json
{
  "number": 3,
  "created_at": "2026-11-06T23:48:46+00:00",
  "kind": "pr",
  "title": "feat: v2",
  "body": "Adds v2. Closes #1",
  "branch": "feat/1",
  "base": "main",
  "state": "merged",
  "reviews": [
    {
      "at": "2026-11-06T23:49:25+00:00",
      "verdict": "REQUEST_CHANGES",
      "sha": "c56446e65bc4de1d5072304fac2030a9021f360e",
      "body": "fix it"
    },
    {
      "at": "2026-11-06T23:50:12+00:00",
      "verdict": "APPROVE",
      "sha": "9db33f87eb3b4bb558724d78325449693fdc7e9b",
      "body": "ok"
    }
  ],
  "merged_sha": "cc93e296212cd1c7bc78fbb014f661e7a8564601",
  "merged_at": "2026-11-06T23:50:12+00:00"
}
```

### A.12 `teamflow-config` and configuration edge cases

```
$ teamflow-config                            # full defaults
{
  "forge": "local",
  "remote": "origin",
  "base": "main",
  "tdd": "required",
  "teamflow_auto_approve": "low",
  "loop": {
    "exit_severity_threshold": "medium",
    "max_open_issues_to_continue": 0
  }
}
[exit 0]

$ teamflow-config loop
{"exit_severity_threshold": "medium", "max_open_issues_to_continue": 0}
[exit 0]

$ teamflow-config loop.no_such_key
teamflow-config: unknown key 'loop.no_such_key'
[exit 2]

$ tf mode                                  # .claude/teamflow.json = "{not json"
tf: .claude/teamflow.json is not valid JSON (Expecting property name enclosed in double quotes: line 1 column 2 (char 1))
[exit 2]

$ teamflow-config                          # same error, direct
teamflow-config: .claude/teamflow.json is not valid JSON (Expecting property name enclosed in double quotes: line 1 column 2 (char 1))
[exit 2]

$ tf mode                                  # {"forge": "GitHub"}
tf: 'forge' must be one of ['github', 'local']
[exit 2]

$ tf mode                                  # main worktree on feat/9, base is main
tf: the main worktree (/private/tmp/tf-contract-scratch/main) must be on main, not feat/9: its config is trusted only there. Work on other branches in separate worktrees.
[exit 2]

$ tf issue list                            # every command takes the config check
tf: the main worktree (/private/tmp/tf-contract-scratch/main) must be on main, not feat/9: its config is trusted only there. Work on other branches in separate worktrees.
[exit 2]
```

### A.13 `.env` copy on checkout

```
# main worktree has an untracked .env (TOKEN=x); PR #7 head has .env.example
$ tf pr checkout 7
tf: detached at 8617abd8e631 (feat/7)
tf: copied .env from the main worktree (rm -f .env when done)
[exit 0]

# remove .env from main; PR #8 head has .env.example
$ tf pr checkout 8
tf: detached at 7b0b41556b21 (feat/8)     # stdout
tf: .env.example exists but /private/tmp/tf-contract-scratch/main has no .env; stop and report   # stderr
[exit 2]
```

### A.14 `tf --help` (usage text, verbatim)

```
usage: tf [-h] {mode,setup,issue,pr} ...

teamflow's one interface to Issues and PRs, local or on GitHub.

    tf mode
    tf setup [--forge local|github] [--remote R] [--apply]   # dry run without --apply; R defaults to the configured remote
    tf issue create --title T (--body B | --body-file F) [--label L ...]   # F may be - for stdin
    tf issue list [--label L ...]                # open Issues carrying any label
    tf issue view N
    tf issue comment N (--body B | --body-file F)   # F may be - for stdin
    tf issue edit N [--add-label L ...] [--remove-label L ...]   # at least one flag
    # a label is non-empty, printable, with no comma, on create and edit (else exit 2)
    tf issue close N
    tf pr create --title T (--body B | --body-file F) [--base B]   # F may be - for stdin
    tf pr list
    tf pr view N
    tf pr checkout N                             # review team worktree only
    tf pr claim N | tf pr release N
    tf pr gate N
    tf pr diff N [PATH ...]                      # base...head, after tf pr checkout
    tf pr review N --verdict APPROVE|REQUEST_CHANGES --sha SHA (--body B | --body-file F)   # F may be - for stdin
    tf pr merge N

The mode comes from `forge` in .claude/teamflow.json (see teamflow-config):

- local (default): Issues and PRs are records under <git common dir>/teamflow,
  shared by every worktree and never committed. The reviewer runs the gate,
  and `tf pr merge` merges into the base branch locally. Nothing is pushed.
- github: Issues and PRs live on GitHub. A `teamflow/code-review` commit status
  on the reviewed head is the claim (pending) and the verdict (success or
  failure), replacing review labels; CI's checks replace the reviewer's own
  gate run. Where a ruleset requires both `gate` and `teamflow/code-review`,
  GitHub enforces them and merges once they pass. Otherwise (no ruleset, one
  that lacks either, or one that cannot be read) tf checks the CI `gate` check
  and the verdict itself before merging, which is a process control only.
  `tf pr review --verdict APPROVE` arms auto-merge (`gh pr merge --auto`,
  pinned to the reviewed head) when the PR targets the configured base and
  `repos/<slug>/rules/branches/<base>` lists a required status check for both
  `gate` and `teamflow/code-review`; GitHub then merges once they pass, or at
  once if the PR is already clean. It prints what it did and arms nothing for
  REQUEST_CHANGES, a stacked PR, or a repository without that ruleset (there,
  and in local mode, the reviewer runs `tf pr merge`). If the verdict is
  recorded but arming fails, including an unreadable ruleset, review exits 4
  and the verdict stays; `tf pr merge N` is then the fallback.
  If the repository adopted github but gh is missing, unauthenticated, or the
  remote is not GitHub, every command stops (exit 2): never a silent fallback.

On GitHub, `tf pr gate` and an unenforced `tf pr merge` (no ruleset requiring
both contexts) wait for pending CI checks, polling every TF_GATE_POLL seconds
(default 15) for up to TF_GATE_WAIT seconds (default 480), then report the
result. An unenforced merge judges the `gate` check alone, whatever else is
required, and merges directly; if another required check is red or pending,
GitHub is expected to refuse that merge (exit 1; by reading only, not
observed). With a ruleset requiring both, `tf pr merge` does not wait for
pending checks: it retries only a failed read of
the required checks, then enables auto-merge. A failed poll or an empty check
list is retried the same way. If a check is still pending at the deadline, tf also
prints the PR's head SHA (read after the wait) and, per pending check, what gh reports (state,
workflow, event, link, startedAt, completedAt, description), to tell a slow run from a stale
rollup. `tf pr merge` has one TF_GATE_WAIT deadline for
all of it, not one per step. tf puts no time limit on the gh calls, so the
real wait is that deadline plus the last poll and the calls after it; how that
compares with the Bash tool's timeout is not verified here. An unenforced merge
reads the verdict again after the wait and refuses (exit 3) unless it is still
an APPROVE for the head. TF_GATE_WAIT must be a finite number >= 0 and
TF_GATE_POLL a finite number > 0, else exit 2 (also for `tf pr merge`).

Exit codes: 0 ok, 1 error, 2 setup or usage problem, 3 refused because of PR
state (claimed, moved head, no approval, or after the wait of tf pr gate or
tf pr merge, CI still running or unreadable), 4 the verdict of tf pr review is
recorded but auto-merge was not armed. Exit 3 is a STOP, not a retry signal.

positional arguments:
  {mode,setup,issue,pr}

options:
  -h, --help            show this help message and exit
```

## Not verified (carried into Phase 2 as open questions)

1. **GitHub mode was not run live** by teamflow-pi. It is verified by
   teamflow's `fake_gh` suite (56 tests OK) and source reads only. The
   "GitHub is expected to refuse that merge (exit 1)" sentence for other
   red required checks on the unenforced path is teamflow's own
   "by reading only, not observed" (`bin/tf:38-40`).
2. **`gh pr checks` exit code 8** while pending is described in
   `tests/fake_gh.py`'s docstring as "from gh's help text; unverified" —
   the behaviour (JSON list on stdout is what counts) is what the suite
   exercises.
3. **Label comma-splitting in `gh`** (why the comma is banned in local
   labels) is likewise "from gh's help text; unverified, #171".
4. `tf pr gate`'s real wall-clock budget vs a Bash tool timeout is "not
   verified here" per the usage text itself (A.14).
