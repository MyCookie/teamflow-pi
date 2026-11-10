"""tf, github mode: the gh preconditions, Issues and PRs over gh, the CI
gate, verdict status, auto-merge arming, and merge with or without a
ruleset.

Contract: docs/teamflow/tf.md Section 10 and Appendix A.5 (teamflow @
423109c). `gh` is replaced by tests/fake_gh.py; the remote is a bare
repository under a directory named github.com/me/repo.git, so real git
push/fetch works while the URL passes tf's GitHub check.
"""

import json
import os
import sys
import tempfile
import unittest

from harness import PKG, git, make_repo, run_tf, write_config

STATUS = "teamflow/code-review"
PR_FIELDS = ("title,body,headRefName,headRefOid,baseRefName,state,files,"
             "mergeStateStatus,autoMergeRequest")


class GitHubFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name
        self.main = make_repo(base + "/main")
        self.impl = self.main.parent / "impl"
        self.rev = self.main.parent / "rev"
        self.bare = self.main.parent / "github.com" / "me" / "repo.git"
        self.bare.mkdir(parents=True)
        git("init", "-q", "--bare", "-b", "main", cwd=self.bare)
        (self.main / "app.txt").write_text("v1\n")
        git("add", "-A", cwd=self.main)
        git("commit", "-q", "-m", "init", cwd=self.main)
        write_config(self.main, {"forge": "github"})
        git("remote", "add", "origin", str(self.bare), cwd=self.main)
        git("push", "-q", "origin", "main", cwd=self.main)
        git("worktree", "add", "-q", "-b", "feat/1", str(self.impl), cwd=self.main)
        (self.impl / "app.txt").write_text("v2\n")
        git("add", "-A", cwd=self.impl)
        git("commit", "-q", "-m", "feat 1", cwd=self.impl)
        git("worktree", "add", "--detach", "-q", str(self.rev), cwd=self.main)
        self.state = self.main.parent / "gh-state.json"
        self.write_state({})
        self.fakebin = self.main.parent / "fakebin"
        self.fakebin.mkdir()
        fake_gh = PKG / "tests" / "fake_gh.py"
        (self.fakebin / "gh").write_text(
            f"#!{sys.executable}\nimport runpy, sys\n"
            f"sys.argv = ['gh'] + sys.argv[1:]\n"
            f"runpy.run_path({str(fake_gh)!r}, run_name='__main__')\n")
        (self.fakebin / "gh").chmod(0o755)
        self.env = {"PATH": f"{self.fakebin}{os.pathsep}{os.environ['PATH']}",
                    "FAKE_GH_STATE": str(self.state),
                    "FAKE_GH_BARE": str(self.bare),
                    "TF_GATE_WAIT": "0", "TF_GATE_POLL": "0.01"}

    def tearDown(self):
        self.tmp.cleanup()

    def write_state(self, updates):
        state = json.loads(self.state.read_text()) if self.state.exists() \
            else {}
        state.update(updates)
        self.state.write_text(json.dumps(state, indent=2))

    def read_state(self):
        return json.loads(self.state.read_text())

    def tf(self, *args, cwd=None, env=None, input=None):
        full = dict(self.env)
        if env:
            full.update(env)
        return run_tf(*args, cwd=cwd or self.main, env=full, input=input)

    def ok(self, *args, cwd=None, env=None, input=None):
        result = self.tf(*args, cwd=cwd, env=env, input=input)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def refused(self, code, *args, cwd=None, env=None, input=None):
        result = self.tf(*args, cwd=cwd, env=env, input=input)
        self.assertEqual(result.returncode, code,
                         f"exit {result.returncode}, not {code}: "
                         f"{result.stdout}{result.stderr}")
        self.assertTrue(result.stderr.startswith("tf: "), result.stderr)
        return result.stderr

    def head(self, branch="refs/heads/feat/1"):
        return git("rev-parse", branch, cwd=self.main)

    def pr_number(self, *args, cwd=None):
        out = self.ok("pr", "create", *args, cwd=cwd or self.impl)
        return int(out.rstrip("/").rsplit("/", 1)[1])

    def state_pr(self, n, **updates):
        state = self.read_state()
        state.setdefault("prs", {})[str(n)] = {
            "title": "feat 1", "body": "body", "headRefName": "feat/1",
            "baseRefName": "main", "state": "OPEN", "files": ["app.txt"]}
        state["prs"][str(n)].update(updates)
        self.write_state({"prs": state["prs"]})
        # the PR's head exists on the remote, as GitHub would host it
        git("push", "-q", "origin", "feat/1", cwd=self.main)

    # -- 10.1 preconditions ---------------------------------------------------

    def test_a_non_github_remote_stops_every_command(self):
        git("remote", "set-url", "origin", "/tmp/plain.git", cwd=self.main)
        error = self.refused(2, "mode")
        self.assertIn(
            "forge is github but remote 'origin' (/tmp/plain.git) is not a "
            "GitHub repository", error)
        self.refused(2, "issue", "list")
        self.refused(2, "pr", "list")

    def test_missing_gh_stops_every_command(self):
        import shutil
        empty = self.main.parent / "no-gh"
        empty.mkdir()
        for name in ("python3", "git"):
            os.symlink(shutil.which(name), empty / name)
        error = self.refused(2, "mode", env={"PATH": str(empty)})
        self.assertIn("forge is github but gh is not installed", error)

    def test_unauthenticated_gh_stops_every_command(self):
        error = self.refused(2, "mode", env={"FAKE_GH_LOGGED_OUT": "1"})
        self.assertIn(
            "forge is github but gh is not authenticated (gh auth login)",
            error)

    def test_mode_prints_github(self):
        self.assertEqual(self.ok("mode"), "github\n")

    # -- 10.2 issues ------------------------------------------------------------

    def test_issue_create_prints_url_and_number(self):
        url = self.ok("issue", "create", "--title", "First", "--body", "b")
        self.assertEqual(url, "https://github.com/me/repo/issues/1\n")

    def test_issue_list_shape_and_label_search(self):
        self.ok("issue", "create", "--title", "A", "--body", "b",
                "--label", "area:docs")
        self.ok("issue", "create", "--title", "B", "--body", "b")
        self.assertEqual(self.ok("issue", "list"),
                         "#1\tA\tarea:docs\n#2\tB\t\n")
        self.assertEqual(self.ok("issue", "list", "--label", "area:docs"),
                         "#1\tA\tarea:docs\n")

    def test_issue_list_uses_gh_search_not_a_local_filter(self):
        self.ok("issue", "create", "--title", "A", "--body", "b",
                "--label", "area:docs")
        self.ok("issue", "create", "--title", "B", "--body", "b")
        self.assertEqual(self.ok("issue", "list", "--label", "area:docs"),
                         "#1\tA\tarea:docs\n")
        # the filtering happened in gh, as a search — not in tf
        self.assertEqual(self.read_state()["last_args"],
                         ["issue", "list", "--state", "open",
                          "--json", "number,title,labels", "--limit", "200",
                          "--search", 'label:"area:docs"', "-R", "me/repo"])

    def test_issue_view_shape(self):
        self.ok("issue", "create", "--title", "The title", "--body", "Body text.")
        self.ok("issue", "comment", "1", "--body", "A note")
        self.assertEqual(self.ok("issue", "view", "1"),
                         "#1 The title\nstate: open\nlabels: -\n\nBody text.\n\n"
                         "--- comment 2026-01-01T00:00:00Z\nA note\n")

    def test_issue_comment_prints_url(self):
        self.ok("issue", "create", "--title", "T", "--body", "b")
        self.assertEqual(self.ok("issue", "comment", "1", "--body", "note"),
                         "https://github.com/me/repo/issues/1#issuecomment-1\n")

    def test_issue_edit_labels_prints_the_result(self):
        self.ok("issue", "create", "--title", "T", "--body", "b",
                "--label", "a")
        self.assertEqual(self.ok("issue", "edit", "1",
                                 "--add-label", "b", "--remove-label", "a"),
                         "#1: labels: b\n")

    def test_issue_edit_needs_a_flag_and_rejects_bad_labels(self):
        self.ok("issue", "create", "--title", "T", "--body", "b")
        self.refused(2, "issue", "edit", "1")
        self.refused(2, "issue", "edit", "1", "--add-label", "a,b")

    def test_issue_edit_refuses_a_pr_number(self):
        n = self.pr_number("--title", "T", "--body", "b.")
        error = self.refused(3, "issue", "edit", str(n), "--add-label", "a")
        self.assertIn(f"#{n} is a PR, not an Issue", error)

    def test_issue_edit_refuses_a_missing_number(self):
        error = self.refused(3, "issue", "edit", "99", "--add-label", "a")
        self.assertIn("#99 does not exist", error)

    def test_issue_close_prints_url(self):
        self.ok("issue", "create", "--title", "T", "--body", "b")
        self.assertEqual(self.ok("issue", "close", "1"),
                         "https://github.com/me/repo/issues/1\n")

    # -- 10.3 pr basics -----------------------------------------------------------

    def test_pr_create_pushes_and_prints_url(self):
        self.assertEqual(
            self.ok("pr", "create", "--title", "feat 1", "--body", "Closes #1",
                    cwd=self.impl),
            "https://github.com/me/repo/pull/1\n")
        # the branch is on the bare repository, as GitHub would host it
        self.assertEqual(git("rev-parse", "-q", "--verify", "refs/heads/feat/1",
                             cwd=self.bare, check=False), self.head())

    def test_pr_create_checks_before_pushing(self):
        (self.impl / "loose.txt").write_text("x\n")
        error = self.refused(3, "pr", "create", "--title", "T", "--body", "b.",
                             cwd=self.impl)
        self.assertIn("working tree is dirty", error)
        # nothing reached the bare repository
        self.assertEqual(
            git("branch", "--list", "feat/*", cwd=self.bare, check=False), "")

    def test_pr_list_shape(self):
        self.state_pr(1)
        self.assertEqual(self.ok("pr", "list"),
                         "#1\tfeat 1\tfeat/1 -> main\n")

    def test_pr_view_shape_with_review_status(self):
        self.state_pr(1)
        tip = self.head()
        self.write_state({"statuses": {tip: [{"context": STATUS,
                                              "state": "pending",
                                              "description": "review in progress"}]}})
        out = self.ok("pr", "view", "1")
        self.assertEqual(out,
                         f"#1 feat 1\nstate: open\nbranch: feat/1 -> main\n"
                         f"head: {tip}\n"
                         f"teamflow/code-review: pending (review in progress)\n"
                         f"merge state: clean\nauto-merge: off\n"
                         f"files: app.txt\n\nbody\n")

    def test_pr_view_reports_no_review_status(self):
        self.state_pr(1)
        self.assertIn("teamflow/code-review: none", self.ok("pr", "view", "1"))

    def test_pr_view_reports_auto_merge_on(self):
        self.state_pr(1, auto_merge=True)
        self.assertIn("auto-merge: on", self.ok("pr", "view", "1"))

    def test_pr_checkout_fetches_and_detaches(self):
        self.state_pr(1)
        self.assertEqual(self.ok("pr", "checkout", "1", cwd=self.rev),
                         f"tf: detached at {self.head()[:12]} (feat/1)\n")
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.rev), self.head())

    def test_pr_checkout_refuses_a_head_that_moved_while_fetching(self):
        tip = self.head()
        self.state_pr(1, oid="d" * 40)  # the PR says a head the clone lacks
        error = self.refused(3, "pr", "checkout", "1", cwd=self.rev)
        self.assertIn("#1's head moved while fetching; run tf pr checkout "
                      "1 again", error)

    def test_pr_diff_fetches_the_base_and_prints_the_diff(self):
        self.state_pr(1)
        self.ok("pr", "checkout", "1", cwd=self.rev)  # gets the head in
        out = self.ok("pr", "diff", "1", cwd=self.rev)
        self.assertIn("-v1", out)
        self.assertIn("+v2", out)

    def test_pr_diff_refuses_a_head_not_in_the_clone(self):
        self.state_pr(1, oid="e" * 40)
        error = self.refused(3, "pr", "diff", "1", cwd=self.rev)
        self.assertIn("#1's head is not in this clone; run tf pr checkout 1",
                      error)

    # -- claim / release over statuses -------------------------------------------

    def test_claim_records_a_pending_status(self):
        self.state_pr(1)
        self.ok("pr", "checkout", "1", cwd=self.rev)
        self.assertEqual(self.ok("pr", "claim", "1", cwd=self.rev),
                         f"#1: claimed at {self.head()[:12]}\n")
        statuses = self.read_state()["statuses"][self.head()]
        self.assertEqual(statuses, [{"context": STATUS, "state": "pending",
                                     "description": "review in progress"}])

    def test_claim_refuses_when_a_reviewer_is_already_working(self):
        self.state_pr(1)
        self.write_state({"statuses": {self.head(): [
            {"context": STATUS, "state": "pending",
             "description": "review in progress"}]}})
        error = self.refused(3, "pr", "claim", "1", cwd=self.rev)
        self.assertIn("#1 is already claimed by another reviewer", error)

    def test_release_undoes_a_pending_status(self):
        self.state_pr(1)
        self.ok("pr", "checkout", "1", cwd=self.rev)
        self.ok("pr", "claim", "1", cwd=self.rev)
        self.assertEqual(self.ok("pr", "release", "1", cwd=self.rev),
                         "#1: released\n")
        # the pending status is replaced by an error, as GitHub lists it
        self.assertEqual(self.read_state()["statuses"][self.head()],
                         [{"context": STATUS, "state": "error",
                           "description": "review abandoned without a verdict"},
                          {"context": STATUS, "state": "pending",
                           "description": "review in progress"}])

    def test_release_without_a_pending_status_is_silent(self):
        self.state_pr(1)
        self.assertEqual(self.ok("pr", "release", "1", cwd=self.rev),
                         "#1: released\n")

    # -- 10.4 pr gate ---------------------------------------------------------------

    def gate_env(self, wait="0", poll="0.01"):
        return {"TF_GATE_WAIT": wait, "TF_GATE_POLL": poll}

    def test_gate_passes_when_the_gate_check_passes(self):
        self.state_pr(1)
        out = self.ok("pr", "gate", "1", cwd=self.rev)
        self.assertEqual(out, "gate: pass\n")

    def test_gate_waits_for_a_pending_gate_then_passes(self):
        self.state_pr(1, oid=self.head())
        self.write_state({"check_seq": {self.head(): ["pending", "pass"]}})
        out = self.ok("pr", "gate", "1", cwd=self.rev,
                      env=self.gate_env(wait="1", poll="0.05"))
        self.assertEqual(out, "waiting for: gate\ngate: pass\n")

    def test_gate_fails_on_a_red_check(self):
        self.state_pr(1, oid=self.head())
        self.write_state({"check_seq": {self.head(): ["fail"]}})
        result = self.tf("pr", "gate", "1", cwd=self.rev)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(result.stdout, "gate: fail\n")

    def test_gate_with_no_gate_check_exits_2(self):
        self.state_pr(1)
        self.write_state({"checks": {"1": {"all": [{"name": "lint", "bucket": "pass"}]}}})
        error = self.tf("pr", "gate", "1", cwd=self.rev)
        self.assertEqual(error.returncode, 2, error.stdout)
        self.assertIn(
            "#1 has no `gate` check; add templates/ci.yml as "
            ".github/workflows/gate.yml", error.stderr)

    def test_gate_cannot_read_ci_within_the_wait(self):
        self.state_pr(1)
        self.write_state({"checks_error": True})
        error = self.tf("pr", "gate", "1", cwd=self.rev,
                        env=self.gate_env(wait="0"))
        self.assertEqual(error.returncode, 3, error.stdout)
        self.assertIn("could not read CI within 0s:", error.stderr)

    def test_gate_still_pending_at_the_deadline(self):
        self.state_pr(1, oid=self.head())
        self.write_state({"check_seq": {self.head(): ["pending"]}})
        error = self.tf("pr", "gate", "1", cwd=self.rev,
                        env=self.gate_env(wait="0"))
        self.assertEqual(error.returncode, 3, error.stdout)
        self.assertIn("CI did not finish within 0s; still running: gate",
                      error.stderr)
        self.assertIn('"bucket": "pending"', error.stdout)

    def test_gate_rejects_bad_timing(self):
        self.state_pr(1)
        for bad in ({"TF_GATE_WAIT": "-1"}, {"TF_GATE_POLL": "0"},
                    {"TF_GATE_WAIT": "abc"}):
            error = self.tf("pr", "gate", "1", cwd=self.rev, env=bad)
            self.assertEqual(error.returncode, 2,
                             f"{bad}: {error.stdout}{error.stderr}")
            self.assertIn("TF_GATE_WAIT must be a number of seconds >= 0 "
                           "and TF_GATE_POLL one > 0", error.stderr)

    def test_gate_reads_required_checks_when_the_repo_reports_them(self):
        self.state_pr(1)
        self.write_state({"required": True})
        self.ok("pr", "gate", "1", cwd=self.rev)
        reads = self.read_state()["reads"]
        self.assertEqual(reads, {"required": 1, "all": 0})

    def test_gate_retries_a_failed_required_read(self):
        self.state_pr(1, oid=self.head())
        state = self.read_state()
        state["required"] = True
        state["required_errors_left"] = 1
        state["check_seq"] = {self.head(): ["pending", "pass"]}
        self.state.write_text(json.dumps(state, indent=2))
        out = self.ok("pr", "gate", "1", cwd=self.rev,
                      env=self.gate_env(wait="1", poll="0.05"))
        self.assertEqual(out, "waiting for: gate\ngate: pass\n")
        self.assertEqual(self.read_state()["reads"], {"required": 3, "all": 0})

    # -- 10.5 review and auto-merge arming -------------------------------------------

    def test_review_records_the_verdict_status_and_a_review_comment(self):
        self.state_pr(1)
        self.ok("pr", "checkout", "1", cwd=self.rev)
        tip = self.head()
        out = self.ok("pr", "review", "1", "--verdict", "APPROVE", "--sha", tip,
                      "--body", "lgtm", cwd=self.rev)
        self.assertEqual(out, f"#1: APPROVE recorded at {tip[:12]}\n"
                              "#1: no ruleset requires `gate` and "
                              "`teamflow/code-review`: auto-merge not "
                              "enabled; run tf pr merge 1\n")
        state = self.read_state()
        self.assertEqual(state["statuses"][tip],
                         [{"context": STATUS, "state": "success",
                           "description": "APPROVE by teamflow:review-lead"}])
        self.assertEqual(state["reviews"][0][:2], ["1", "--comment"])
        self.assertIn("--body", state["reviews"][0])
        self.assertIn("lgtm", state["reviews"][0])

    def test_review_request_changes_records_a_failure_status(self):
        self.state_pr(1)
        self.ok("pr", "checkout", "1", cwd=self.rev)
        tip = self.head()
        self.ok("pr", "review", "1", "--verdict", "REQUEST_CHANGES",
                "--sha", tip, "--body", "no", cwd=self.rev)
        self.assertEqual(self.read_state()["statuses"][tip],
                         [{"context": STATUS, "state": "failure",
                           "description":
                               "REQUEST_CHANGES by teamflow:review-lead"}])

    def test_review_refuses_a_stale_sha(self):
        self.state_pr(1)
        self.ok("pr", "checkout", "1", cwd=self.rev)
        error = self.refused(3, "pr", "review", "1", "--verdict", "APPROVE",
                             "--sha", "0" * 40, "--body", "no", cwd=self.rev)
        self.assertIn("#1's head moved since 000000000000", error)

    def test_approve_arms_auto_merge_on_a_ruleset_repo(self):
        self.state_pr(1)
        self.write_state({"required": True})
        self.ok("pr", "checkout", "1", cwd=self.rev)
        tip = self.head()
        out = self.ok("pr", "review", "1", "--verdict", "APPROVE", "--sha", tip,
                      "--body", "lgtm", cwd=self.rev)
        self.assertIn(
            "#1: auto-merge requested; tf pr view 1 shows whether GitHub "
            "merged it or queued it", out)
        argv = self.read_state()["merges"][0]
        self.assertEqual(argv[0], "1")
        self.assertIn("--auto", argv)
        self.assertEqual(argv[argv.index("--match-head-commit") + 1], tip)
        self.assertIn("--subject", argv)
        self.assertIn("Merge feat/1: feat 1", argv)

    def test_approve_arms_nothing_on_an_unenforced_repo(self):
        self.state_pr(1)
        self.ok("pr", "checkout", "1", cwd=self.rev)
        tip = self.head()
        out = self.ok("pr", "review", "1", "--verdict", "APPROVE", "--sha", tip,
                      "--body", "lgtm", cwd=self.rev)
        self.assertIn(
            "#1: no ruleset requires `gate` and `teamflow/code-review`: "
            "auto-merge not enabled; run tf pr merge 1", out)
        self.assertEqual(self.read_state()["merges"], [])

    def test_approve_arms_nothing_on_a_stacked_pr(self):
        self.state_pr(1, baseRefName="feat/0")
        self.write_state({"required": True})
        self.ok("pr", "checkout", "1", cwd=self.rev)
        tip = self.head()
        out = self.ok("pr", "review", "1", "--verdict", "APPROVE", "--sha", tip,
                      "--body", "lgtm", cwd=self.rev)
        self.assertIn("#1 targets feat/0, not main: auto-merge not "
                      "enabled; merge its dependency first", out)
        self.assertEqual(self.read_state()["merges"], [])

    def test_request_changes_arms_nothing(self):
        self.state_pr(1)
        self.write_state({"required": True})
        self.ok("pr", "checkout", "1", cwd=self.rev)
        tip = self.head()
        out = self.ok("pr", "review", "1", "--verdict", "REQUEST_CHANGES",
                      "--sha", tip, "--body", "no", cwd=self.rev)
        self.assertEqual(out, f"#1: REQUEST_CHANGES recorded at {tip[:12]}\n")
        self.assertEqual(self.read_state()["merges"], [])

    def test_arming_failure_exits_4_and_keeps_the_verdict(self):
        self.state_pr(1)
        self.write_state({"required": True, "merge_error": True})
        self.ok("pr", "checkout", "1", cwd=self.rev)
        tip = self.head()
        error = self.tf("pr", "review", "1", "--verdict", "APPROVE",
                        "--sha", tip, "--body", "lgtm", cwd=self.rev)
        self.assertEqual(error.returncode, 4, error.stdout)
        self.assertTrue(error.stderr.startswith(
            "tf: verdict recorded, but auto-merge was not enabled "
            "(gh pr merge 1 --merge --match-head-commit "), error.stderr)
        self.assertIn("failed (1): HTTP 502 Bad Gateway); run tf pr merge "
                      "1", error.stderr)
        # the verdict status survived
        self.assertEqual(self.read_state()["statuses"][tip][0]["state"],
                         "success")

    # -- 10.6 merge --------------------------------------------------------------------

    def approved(self, n=1, rounds=1):
        self.ok("pr", "checkout", str(n), cwd=self.rev)
        tip = self.head()
        for _ in range(rounds):
            self.ok("pr", "review", str(n), "--verdict", "APPROVE",
                    "--sha", tip, "--body", "lgtm", cwd=self.rev)

    def test_merge_refuses_a_head_without_an_approval(self):
        self.state_pr(1)
        error = self.refused(3, "pr", "merge", "1", cwd=self.rev)
        self.assertIn(f"#1 has no APPROVE for its current head "
                      f"{self.head()[:12]}", error)

    def test_merge_refuses_a_wrong_base(self):
        self.state_pr(1, baseRefName="feat/0")
        self.assertIn(
            "#1 targets feat/0, not main: merge its dependency first",
            self.refused(3, "pr", "merge", "1", cwd=self.rev))

    def test_unenforced_merge_waits_for_ci_then_merges_directly(self):
        self.state_pr(1, oid=self.head())
        self.write_state({"check_seq": {self.head(): ["pending", "pass"]}})
        self.approved()
        out = self.ok("pr", "merge", "1", cwd=self.rev,
                      env=self.gate_env(wait="1", poll="0.05"))
        self.assertEqual(out, "waiting for: gate\ngate: pass\n"
                              "#1: merged\n")
        argv = self.read_state()["merges"][0]
        self.assertNotIn("--auto", argv)
        self.assertEqual(argv[argv.index("--match-head-commit") + 1], self.head())
        self.assertEqual(self.read_state()["reads"], {"required": 0, "all": 2})

    def test_unenforced_merge_rereads_the_approval_after_waiting(self):
        self.state_pr(1, oid=self.head())
        state = self.read_state()
        state.update({"check_seq": {self.head(): ["pending", "pass"]},
                      "revoke_on_pending": True})
        self.state.write_text(json.dumps(state, indent=2))
        self.approved()
        error = self.refused(3, "pr", "merge", "1", cwd=self.rev,
                             env=self.gate_env(wait="1", poll="0.05"))
        self.assertIn(f"#1 has no APPROVE for its current head "
                      f"{self.head()[:12]}", error)
        self.assertEqual(self.read_state()["merges"], [])

    def test_unenforced_merge_refuses_a_pr_closed_while_waiting(self):
        self.state_pr(1, oid=self.head())
        state = self.read_state()
        state.update({"check_seq": {self.head(): ["pending", "pass"]},
                      "change_on_pending": {"state": "MERGED"}})
        self.state.write_text(json.dumps(state, indent=2))
        self.approved()
        error = self.tf("pr", "merge", "1", cwd=self.rev,
                        env=self.gate_env(wait="0.2", poll="0.05"))
        self.assertEqual(error.returncode, 3, error.stdout)
        self.assertIn("#1 is not open any more (merged)", error.stderr)
        self.assertEqual(self.read_state()["merges"], [])

    def test_unenforced_merge_rereads_the_base(self):
        self.state_pr(1, oid=self.head())
        state = self.read_state()
        state.update({"check_seq": {self.head(): ["pending", "pass"]},
                      "change_on_pending": {"baseRefName": "feat/0"}})
        self.state.write_text(json.dumps(state, indent=2))
        self.approved()
        error = self.refused(3, "pr", "merge", "1", cwd=self.rev,
                             env=self.gate_env(wait="0.2", poll="0.05"))
        self.assertIn("#1 targets feat/0, not main", error)

    def test_enforced_merge_arms_auto_merge_without_waiting(self):
        self.state_pr(1, oid=self.head())
        self.write_state({"required": True,
                          "check_seq": {self.head(): ["pending"]}})
        self.approved()
        out = self.ok("pr", "merge", "1", cwd=self.rev,
                      env=self.gate_env(wait="1", poll="0.05"))
        self.assertEqual(
            out, "#1: auto-merge enabled; GitHub merges once every "
                 "required check passes\n")
        self.assertNotIn("waiting for:", out)
        argv = self.read_state()["merges"][0]
        self.assertEqual(argv[0], "1")
        self.assertIn("--auto", argv)
        self.assertEqual(self.read_state()["reads"]["all"], 0)

    def test_merge_falls_back_when_the_ruleset_cannot_be_read(self):
        self.state_pr(1, oid=self.head())
        state = self.read_state()
        state.update({"rules_error": True,
                      "check_seq": {self.head(): ["pending", "pass"]}})
        self.state.write_text(json.dumps(state, indent=2))
        # approving still records the verdict, but arming fails (exit 4)
        self.ok("pr", "checkout", "1", cwd=self.rev)
        tip = self.head()
        error = self.tf("pr", "review", "1", "--verdict", "APPROVE",
                        "--sha", tip, "--body", "lgtm", cwd=self.rev)
        self.assertEqual(error.returncode, 4, error.stdout)
        out = self.ok("pr", "merge", "1", cwd=self.rev,
                      env=self.gate_env(wait="1", poll="0.05"))
        self.assertIn(
            "#1: could not read the ruleset "
            "(gh api repos/me/repo/rules/branches/main failed (1): HTTP "
            "500 Server Error): checking `gate` and the verdict myself, "
            "then merging directly", out)
        self.assertIn("gate: pass", out)
        self.assertIn("#1: merged", out)
        self.assertNotIn("--auto", self.read_state()["merges"][0])

    def test_merge_head_moved_during_the_wait(self):
        self.state_pr(1, oid=self.head())
        old = self.head()
        (self.impl / "app.txt").write_text("v3\n")
        git("add", "-A", cwd=self.impl)
        git("commit", "-q", "-m", "more", cwd=self.impl)
        new = self.head()
        state = self.read_state()
        state.update({"check_seq": {old: ["pending", "pass"]},
                      "change_on_pending": {"oid": new}})
        self.state.write_text(json.dumps(state, indent=2))
        # the approval covers the old head, which the PR still reports
        self.ok("pr", "checkout", "1", cwd=self.rev)
        self.ok("pr", "review", "1", "--verdict", "APPROVE", "--sha", old,
                "--body", "lgtm", cwd=self.rev)
        error = self.refused(3, "pr", "merge", "1", cwd=self.rev,
                             env=self.gate_env(wait="0.2", poll="0.05"))
        self.assertIn(f"#1's head moved from {old[:12]} to {new[:12]} "
                      f"during the wait; review the new head", error)
        self.assertEqual(self.read_state()["merges"], [])


if __name__ == "__main__":
    unittest.main()
