# `teamflow-config` — behaviour contract

What teamflow's `teamflow-config` does, so a builder can reimplement it from
this document without opening the teamflow repository. Behaviour, not code.
Every section names its teamflow source (file and commit).

**Pinned source:** teamflow @ `423109c` (clean checkout at
`/Users/Ashish/SynologyDrive/Projects/Claude/teamflow`); the script is
`bin/teamflow-config` (113 lines).
**Verification status:** every behaviour below was either run in a scratch
repo (Appendix A) or is pinned by teamflow's test suite
(`tests/test_tf.py`, 56 tests, run OK at this commit).

## 1. What it is

Source: `bin/teamflow-config:2-15,101-109` @ 423109c; verified in Appendix A.

The single reader of the repository's teamflow configuration. It prints the
**effective** config — the values from the config file with defaults filled
in for anything unset:

```
teamflow-config            # the whole config, as JSON (2-space indented)
teamflow-config <key>      # one value, dotted paths allowed, e.g. loop.exit_severity_threshold
```

Output shapes:

- **No argument:** the whole config, `indent=2` JSON, key order
  `forge, remote, base, tdd, teamflow_auto_approve, loop` (the default
  order; file values do not reorder it — verified, Appendix A §2).
- **One argument:** walk the dotted path in the effective config. A
  scalar is printed raw, unquoted (`main`); a dict is printed as compact
  one-line JSON (`{"exit_severity_threshold": "medium", ...}`) — verified,
  Appendix A §1-2.
- **More than one argument:** only the first is read; extras are ignored
  (verified, Appendix A §2).
- **There is no help flag.** `-h` is treated as a key lookup and fails:
  `teamflow-config: unknown key '-h'`, exit 2 (verified, Appendix A §7).

Exit codes: 0 on success; 2 for every configuration problem, each printed
as `teamflow-config: <message>` on stderr. There is no exit 1 or 3
(`bin/teamflow-config:22-25`).

## 2. Which config it reads — the main-worktree rule

Source: `bin/teamflow-config:7-14,67-99` @ 423109c; verified in Appendix A
§3-5; pinned by `tests/test_tf.py:263-321`.

The config file is **always read from the main worktree** — the first
entry of `git worktree list --porcelain` — never from the current
worktree. The docstring's reason: a reviewer's worktree holds the PR under
review, which must not choose the rules its own review and merge run under
(teamflow test:
`test_config_comes_from_the_main_worktree_not_the_pr_under_review`,
`tests/test_tf.py:263` — a PR that rewrites `base` to its own target
branch does not change what `teamflow-config base` reports from the
reviewer's worktree).

Configuration is per repository, so the file is committed with the project
rather than kept in per-user settings (`bin/teamflow-config:13-14`).

Checks, in order, all exit 2:

1. **Not inside a git repository** (`git worktree list` fails):
   `not inside a git repository` (verified, Appendix A §3).
2. **Bare main worktree:** the first worktree entry is bare →
   `the main checkout (<root>) is a bare repository; teamflow needs a
   main worktree on the base branch to read its config from`. The bare
   dir has no trusted config: a stray file in it (even a malformed one
   with exotic values) is **never read** — the message names no branch and
   no JSON error (teamflow test:
   `test_bare_main_checkout_is_named_as_such`, `tests/test_tf.py:307`;
   verified, Appendix A §5).
3. **Main worktree off its base:** the main worktree's branch must equal
   the *effective* `base` from the config, else
   `the main worktree (<root>) must be on <base>, not <branch>: its
   config is trusted only there. Work on other branches in separate
   worktrees.` — with `a detached HEAD` in place of the branch name when
   the main worktree is detached (verified, Appendix A §4). Reason: the
   working copy is the trusted config only while it is on the base branch;
   on any other branch its copy of the file is unreviewed (teamflow test:
   `test_main_worktree_off_the_base_branch_is_a_setup_problem`,
   `tests/test_tf.py:282`).
   *Known hole:* the comparison uses the base **from the config file
   itself**, so a main worktree on branch X whose own config says
   `base: X` passes. The source comment calls this out: only a human
   breaking the rule gets there, and `tf pr merge` still refuses a PR that
   targets the wrong base (`bin/teamflow-config:93-95`; verified,
   Appendix A §4).

The config file path is `<main worktree>/.claude/teamflow.json`. Missing
file → defaults apply, exit 0. Invalid JSON → exit 2:
`.claude/teamflow.json is not valid JSON (<parser error>)`. Not a JSON
object → exit 2: `.claude/teamflow.json must be a JSON object`
(verified, Appendix A §6).

## 3. Keys, defaults, validation

Source: `bin/teamflow-config:27-64` @ 423109c; verified in Appendix A §1,
§6; pinned by `tests/test_tf.py:302-368`.

Effective config, with defaults:

```json
{ "forge": "local", "remote": "origin", "base": "main", "tdd": "required",
  "teamflow_auto_approve": "low",
  "loop": { "exit_severity_threshold": "medium", "max_open_issues_to_continue": 0 } }
```

| key | default | type | allowed values | read by |
|---|---|---|---|---|
| `forge` | `local` | string | `local`, `github` | `tf` (selects the forge mode, `tf.md` §3) |
| `remote` | `origin` | string | any | `tf` (github mode only) |
| `base` | `main` | string | any | `tf` (merge target, main-worktree rule) |
| `tdd` | `required` | string | `required`, `recommended` | agents — how strictly reviewers grade missing red/green evidence: `major` when `required`, `minor` when `recommended` (`agents/quality-reviewer.md:66`, `agents/implementer.md:45`) |
| `teamflow_auto_approve` | `low` | string | `low`, `none` | the manager — under `low` the manager may skip some human gates for a batch of only `severity:low` Issues; `none` turns that off (`agents/manager.md:29`, `skills/workflow/SKILL.md:66`; teamflow's `docs/setup.md:86-87`) |
| `loop.exit_severity_threshold` | `medium` | string | `high`, `medium`, `low`, `none` | the manager's loop — exit when no open Issues above this severity remain (`agents/manager.md:373`) |
| `loop.max_open_issues_to_continue` | `0` | integer | any integer | the manager's loop — exit when open Issues are at or below this count (`agents/manager.md:381-383`) |

The manager reads `teamflow-config loop` at startup (caching the values in
its `.manager-state.json`) and re-reads `teamflow_auto_approve` on every
start, including resumed runs (`agents/manager.md:28-33`).

Validation rules — applied to the **whole** config even when a single key
is requested, all exit 2 (verified, Appendix A §6):

- `unknown key '<dotted.path>'` — any key not in the default tree, at any
  depth. Includes the **removed** `loop.max_iterations` and
  `loop.human_checkpoint`: a config still setting either fails (teamflow
  test: `test_removed_loop_keys_are_unknown_keys_and_not_printed`,
  `tests/test_tf.py:347`; teamflow's `docs/setup.md:90-94` says: delete
  the key).
- `'<dotted.path>' must be an object` — a value where the default is an
  object (e.g. `loop: []`).
- `'<dotted.path>' must be an integer` / `must be a string` — wrong type.
  The type check is **strict identity**: JSON `true` is rejected for
  `max_open_issues_to_continue` (verified, Appendix A §6).
- `'<dotted.path>' must be one of [...]` — value outside the allowed set;
  the set is printed sorted (teamflow tests:
  `test_tdd_defaults_to_required_and_accepts_only_two_values`,
  `tests/test_tf.py:323`;
  `test_auto_approve_defaults_to_low_and_accepts_only_two_values`,
  `tests/test_tf.py:335`; `test_unknown_forge_is_a_setup_problem`,
  `tests/test_tf.py:302`).

`remote`, `base` and `max_open_issues_to_continue` accept any value of
their type — no set check.

## 4. Relationship to `tf`

Source: `bin/tf:103-108,711-731` @ 423109c; teamflow test
`test_bad_config_is_a_setup_problem`, `tests/test_tf.py:361`.

- Every `tf` command **except `tf setup`** reads its config by shelling
  out to the sibling `teamflow-config`; a non-zero exit becomes a `tf`
  setup error with the `teamflow-config: ` prefix stripped and `tf` exit
  2 (`tf.md` §3). The manager also calls `teamflow-config` directly, so
  its own exit code matters (teamflow test,
  `tests/test_tf.py:365-368`).
- **`tf setup` is the exception.** It does not call `teamflow-config`:
  it reads `.claude/teamflow.json` itself, from the **current** worktree
  (`git rev-parse --show-toplevel`), validates only JSON syntax and
  object-ness (`<path> is not valid JSON (...)` / `is a JSON object`,
  exit 2), takes `forge`/`remote` via `.get()` with defaults, and applies
  none of the key or main-worktree-branch checks — a config with removed
  or unknown keys does not stop it (teamflow's `docs/setup.md:93-94`;
  `bin/tf:722-731`).

## 5. Deltas in teamflow-pi

This doc describes teamflow. The deliberate difference is decision **D2**
in [../porting-plan.md](../porting-plan.md): the file lives at
`.pi/teamflow.json`, not `.claude/teamflow.json` (Section 2's path and
Section 4's `tf setup` behaviour change accordingly; the main-worktree
rule, keys, defaults, validation and output shapes are preserved).

## Appendix A. Verification runs (2026-11-06)

**Suite:** in teamflow @ `423109c`, `python3 -m unittest discover -s tests
-p "test_tf.py"` → `Ran 56 tests … OK`.

**Environment:** Python 3.15.2, git 2.54.0, macOS. Scratch repo in
`/tmp/tf-cfg-scratch` (main worktree on `main`); `teamflow-config`
invoked by absolute path from teamflow @ `423109c`. No LLM model was
involved; every line below is a shell run.

### A.1 whole config and single keys

```
$ teamflow-config                       # .claude/teamflow.json = {"forge": "local"}
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

$ teamflow-config base
main
[exit 0]

$ teamflow-config loop
{"exit_severity_threshold": "medium", "max_open_issues_to_continue": 0}
[exit 0]

$ teamflow-config loop.exit_severity_threshold
medium
[exit 0]

$ teamflow-config forge
local
[exit 0]

$ teamflow-config base extra_arg_ignored
main
[exit 0]
```

### A.2 unknown keys

```
$ teamflow-config no_such_key
teamflow-config: unknown key 'no_such_key'
[exit 2]

$ teamflow-config loop.max_iterations     # removed key
teamflow-config: unknown key 'loop.max_iterations'
[exit 2]

$ teamflow-config forge.x                # path through a scalar
teamflow-config: unknown key 'forge.x'
[exit 2]
```

### A.3 not inside a git repository

```
$ cd /tmp/not-a-repo && teamflow-config
teamflow-config: not inside a git repository
[exit 2]
```

### A.4 main worktree off its base; the config-says-X shortcut

```
$ teamflow-config base                    # main on feat/9, config {"base": "feat/9"}
feat/9
[exit 0]                                  # passes: the hole at bin/teamflow-config:93-95

$ teamflow-config                         # main on feat/10, config {"forge": "local"} (base main)
teamflow-config: the main worktree (/private/tmp/tf-cfg-scratch/main) must be on main, not feat/10: its config is trusted only there. Work on other branches in separate worktrees.
[exit 2]

$ teamflow-config                         # detached main worktree
teamflow-config: the main worktree (/private/tmp/tf-cfg-scratch/main) must be on main, not a detached HEAD: its config is trusted only there. Work on other branches in separate worktrees.
[exit 2]
```

### A.5 bare main worktree (stray malformed config in the bare dir)

```
# bare.git/.claude/teamflow.json = '{"base": "trunk", not json'
$ teamflow-config        (from a worktree of the bare repo, main is bare.git)
teamflow-config: the main checkout (/private/tmp/tf-cfg-scratch/bare.git) is a bare repository; teamflow needs a main worktree on the base branch to read its config from
[exit 2]
```

(no `not valid JSON`, no `trunk`, no branch named — the stray file was
never read; matches `tests/test_tf.py:307`.)

### A.6 validation

```
$ teamflow-config tdd                        # {"tdd": "optional"}
teamflow-config: 'tdd' must be one of ['recommended', 'required']
[exit 2]

$ teamflow-config teamflow_auto_approve      # {"teamflow_auto_approve": "medium"}
teamflow-config: 'teamflow_auto_approve' must be one of ['low', 'none']
[exit 2]

$ teamflow-config loop.exit_severity_threshold  # {"loop": {"exit_severity_threshold": "critical"}}
teamflow-config: 'loop.exit_severity_threshold' must be one of ['high', 'low', 'medium', 'none']
[exit 2]

$ teamflow-config loop.max_open_issues_to_continue  # string value
teamflow-config: 'loop.max_open_issues_to_continue' must be an integer
[exit 2]

$ teamflow-config loop.max_open_issues_to_continue  # true (bool) value
teamflow-config: 'loop.max_open_issues_to_continue' must be an integer
[exit 2]

$ teamflow-config loop                       # {"loop": ["nope"]}
teamflow-config: 'loop' must be an object
[exit 2]

$ teamflow-config                            # config file = [1, 2]
teamflow-config: .claude/teamflow.json must be a JSON object
[exit 2]

$ teamflow-config base                       # {"forge": "local", "extra": 1}
teamflow-config: unknown key 'extra'
[exit 2]

$ teamflow-config                            # every allowed value set
{
  "forge": "local",
  "remote": "origin",
  "base": "main",
  "tdd": "recommended",
  "teamflow_auto_approve": "none",
  "loop": {
    "exit_severity_threshold": "high",
    "max_open_issues_to_continue": 2
  }
}
[exit 0]
```

### A.7 no help flag

```
$ teamflow-config -h
teamflow-config: unknown key '-h'
[exit 2]
```
