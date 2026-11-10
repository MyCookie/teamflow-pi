"""tf, local mode: Issues, PRs, the record store, merge.

Contract: docs/teamflow/tf.md Sections 7-9 and Appendix A (teamflow @
423109c). Exit codes: 0 ok; 1 error; 2 setup or usage problem; 3 refused
because of PR or Issue state. Every failure message is on stderr, prefixed
"tf: ".
"""

import json
import os
import stat
import tempfile
import unittest

from harness import PKG, git, make_repo, run_tf, template, write_config


class LocalFlow(unittest.TestCase):
    """main on main (with gate.sh and the PR template), impl on feat/1,
    a detached review worktree, forge local."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name
        self.main = make_repo(base + "/main")
        self.impl = self.main.parent / "impl"
        self.rev = self.main.parent / "rev"
        write_config(self.main, {"forge": "local"})
        gate = self.main / "scripts" / "gate.sh"
        gate.parent.mkdir()
        gate.write_text('#!/bin/sh\nexit "${GATE_EXIT:-0}"\n')
        gate.chmod(gate.stat().st_mode | stat.S_IEXEC)
        (self.main / ".github").mkdir()
        (self.main / ".github" / "pull_request_template.md").write_text("## Issue\n")
        (self.main / "app.txt").write_text("v1\n")
        git("add", "-A", cwd=self.main)
        git("commit", "-q", "-m", "init", cwd=self.main)
        git("worktree", "add", "-q", "-b", "feat/1", str(self.impl), cwd=self.main)
        (self.impl / "app.txt").write_text("v2\n")
        git("add", "-A", cwd=self.impl)
        git("commit", "-q", "-m", "feat 1", cwd=self.impl)
        git("worktree", "add", "--detach", "-q", str(self.rev), cwd=self.main)

    def tearDown(self):
        self.tmp.cleanup()

    def tf(self, *args, cwd=None, env=None, input=None):
        return run_tf(*args, cwd=cwd or self.main, env=env, input=input)

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

    def open_pr(self):
        return self.ok("pr", "create", "--title", "feat 1",
                       "--body", "Closes #1\n\nv2.", cwd=self.impl)

    # -- mode ---------------------------------------------------------------

    def test_mode_prints_local(self):
        self.assertEqual(self.ok("mode"), "local\n")

    # -- issues --------------------------------------------------------------

    def test_issue_create_prints_its_number(self):
        self.assertEqual(self.ok("issue", "create", "--title", "First",
                                 "--body", "b"), "#1\n")
        self.assertEqual(self.ok("issue", "create", "--title", "Second",
                                 "--body", "b", "--label", "area:docs"), "#2\n")

    def test_issue_list_lines_and_label_filter(self):
        self.ok("issue", "create", "--title", "A", "--body", "b", "--label", "area:docs")
        self.ok("issue", "create", "--title", "B", "--body", "b")
        self.assertEqual(self.ok("issue", "list"),
                         "#1\tA\tarea:docs\n#2\tB\t\n")
        self.assertEqual(self.ok("issue", "list", "--label", "area:docs"),
                         "#1\tA\tarea:docs\n")
        self.assertEqual(self.ok("issue", "list", "--label", "area:nope"), "")

    def test_issue_view_full_shape(self):
        self.ok("issue", "create", "--title", "The title", "--body", "Body text.")
        self.assertEqual(self.ok("issue", "view", "1"),
                         "#1 The title\nstate: open\nlabels: -\n\nBody text.\n")

    def test_issue_comment_appends(self):
        self.ok("issue", "create", "--title", "T", "--body", "b")
        self.assertEqual(self.ok("issue", "comment", "1", "--body", "A note"),
                         "#1: commented\n")
        self.assertIn("--- comment", self.ok("issue", "view", "1"))
        self.assertIn("A note", self.ok("issue", "view", "1"))

    def test_issue_edit_labels_add_remove_and_dedupe(self):
        self.ok("issue", "create", "--title", "T", "--body", "b", "--label", "a")
        self.assertEqual(self.ok("issue", "edit", "1",
                                 "--add-label", "b", "--add-label", "a",
                                 "--add-label", "c"),
                         "#1: labels: a, b, c\n")
        self.assertEqual(self.ok("issue", "edit", "1", "--remove-label", "a"),
                         "#1: labels: b, c\n")
        self.assertEqual(self.ok("issue", "edit", "1",
                                 "--remove-label", "b", "--remove-label", "c"),
                         "#1: labels: -\n")

    def test_issue_edit_needs_a_flag_and_rejects_bad_labels(self):
        self.ok("issue", "create", "--title", "T", "--body", "b")
        self.assertIn("issue edit needs --add-label or --remove-label",
                      self.refused(2, "issue", "edit", "1"))
        self.assertIn("invalid label 'a,b': it must be non-empty, with no "
                      "comma or control character",
                      self.refused(2, "issue", "edit", "1",
                                   "--add-label", "a,b"))
        self.refused(2, "issue", "create", "--title", "T", "--body", "b",
                     "--label", "")
        self.assertIn("must be non-empty, with no comma or control character",
                      self.refused(2, "issue", "create", "--title", "T",
                                   "--body", "b", "--label", "a\tb"))

    def test_issue_edit_refuses_a_label_on_both_flags(self):
        self.ok("issue", "create", "--title", "T", "--body", "b")
        self.assertIn("label on both --add-label and --remove-label: a",
                      self.refused(2, "issue", "edit", "1",
                                   "--add-label", "a", "--remove-label", "a"))

    def test_issue_close_is_idempotent_and_hides_the_issue_from_list(self):
        self.ok("issue", "create", "--title", "T", "--body", "b")
        self.assertEqual(self.ok("issue", "close", "1"), "#1: closed\n")
        # closing again is not an error; the issue stays hidden from list
        self.assertEqual(self.ok("issue", "close", "1"), "#1: closed\n")
        self.assertEqual(self.ok("issue", "list"), "")
        self.assertIn("state: closed", self.ok("issue", "view", "1"))

    def test_issue_commands_refuse_a_missing_number(self):
        for verb in ("view", "comment", "edit", "close"):
            args = {"view": (), "comment": ("--body", "b"),
                    "edit": ("--add-label", "a"), "close": ()}[verb]
            self.assertIn("#99 does not exist",
                          self.refused(3, "issue", verb, "99", *args))

    def test_issue_commands_refuse_a_pr_number(self):
        pr_number = self.open_pr_number()
        for verb, extra in (("view", ()), ("comment", ("--body", "b")),
                            ("edit", ("--add-label", "a")), ("close", ())):
            self.assertIn(f"#{pr_number} is a PR, not an Issue",
                          self.refused(3, "issue", verb, str(pr_number), *extra))

    def open_pr_number(self):
        out = self.ok("pr", "create", "--title", "T", "--body", "b.",
                      cwd=self.impl)
        return int(out.split()[0][1:])

    # -- pr create -------------------------------------------------------------

    def test_pr_create_refuses_detached_head(self):
        self.assertIn("detached HEAD; run this from the feature branch",
                      self.refused(3, "pr", "create", "--title", "T",
                                   "--body", "b.", cwd=self.rev))

    def test_pr_create_refuses_opening_from_the_base(self):
        self.assertIn("refusing to open a PR from main",
                      self.refused(3, "pr", "create", "--title", "T",
                                   "--body", "b."))

    def test_pr_create_refuses_a_dirty_tree(self):
        (self.impl / "loose.txt").write_text("x\n")
        error = self.refused(3, "pr", "create", "--title", "T", "--body", "b.",
                             cwd=self.impl)
        self.assertIn("working tree is dirty; commit before publishing:", error)
        self.assertIn("loose.txt", error)

    def test_pr_create_refuses_the_unmodified_template_body(self):
        error = self.refused(3, "pr", "create", "--title", "T",
                             "--body", "## Issue", cwd=self.impl)
        self.assertIn(
            "the PR body is the unmodified .github/pull_request_template.md; "
            "fill it in first", error)

    def test_pr_create_prints_number_branch_and_base(self):
        self.assertEqual(self.open_pr(), "#1 (feat/1 -> main)\n")

    def test_pr_create_reads_the_body_from_a_file_or_stdin(self):
        (self.impl / ".gitignore").write_text("body.md\n")
        git("add", "-A", cwd=self.impl)
        git("commit", "-q", "-m", "ignore body.md", cwd=self.impl)
        (self.impl / "body.md").write_text("From a file.")
        self.assertEqual(self.ok("pr", "create", "--title", "A",
                                 "--body-file", "body.md", cwd=self.impl),
                         "#1 (feat/1 -> main)\n")
        # a second PR needs its own branch; the body comes from stdin
        git("checkout", "-q", "-b", "feat/2", cwd=self.impl)
        (self.impl / "top.txt").write_text("top\n")
        git("add", "-A", cwd=self.impl)
        git("commit", "-q", "-m", "feat 2", cwd=self.impl)
        self.assertEqual(self.ok("pr", "create", "--title", "B",
                                 "--body-file", "-", cwd=self.impl,
                                 input="From stdin."),
                         "#2 (feat/2 -> main)\n")

    def test_refuse_duplicate_open_pr(self):
        self.open_pr()
        self.assertIn("#1 is already open for feat/1",
                      self.refused(3, "pr", "create", "--title", "T2",
                                   "--body", "b2.", cwd=self.impl))

    # -- pr list / view ---------------------------------------------------------

    def test_pr_list_line_shape(self):
        self.open_pr()
        self.assertEqual(self.ok("pr", "list"), "#1\tfeat 1\tfeat/1 -> main\n")

    def test_pr_view_open_shape(self):
        self.open_pr()
        tip = git("rev-parse", "refs/heads/feat/1", cwd=self.main)
        self.assertEqual(self.ok("pr", "view", "1"),
                         f"#1 feat 1\nstate: open\nbranch: feat/1 -> main\n"
                         f"head: {tip}\nclaimed: no\nfiles: app.txt\n\nCloses #1\n\nv2.\n")

    def test_pr_view_degrades_when_the_branch_is_missing(self):
        self.open_pr()
        git("branch", "-q", "-m", "feat/1", "feat/1-old", cwd=self.impl)
        self.assertEqual(self.ok("pr", "view", "1"),
                         "#1 feat 1\nstate: open\nbranch: feat/1 -> main\n"
                         "head: (branch missing)\nclaimed: no\nfiles: -\n\n"
                         "Closes #1\n\nv2.\n")

    # -- pr checkout -------------------------------------------------------------

    def test_pr_checkout_refuses_the_main_worktree(self):
        self.open_pr()
        self.assertIn("refusing to run in the main worktree",
                      self.refused(3, "pr", "checkout", "1"))
        self.assertIn("reviews run in their own",
                      self.refused(3, "pr", "checkout", "1"))

    def test_pr_checkout_detaches_at_the_head(self):
        self.open_pr()
        tip = git("rev-parse", "refs/heads/feat/1", cwd=self.main)
        self.assertEqual(self.ok("pr", "checkout", "1", cwd=self.rev),
                         f"tf: detached at {tip[:12]} (feat/1)\n")
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.rev), tip)

    def test_pr_checkout_refuses_a_missing_branch(self):
        self.open_pr()
        git("branch", "-q", "-m", "feat/1", "feat/1-old", cwd=self.impl)
        self.assertIn("branch feat/1 does not exist",
                      self.refused(3, "pr", "checkout", "1", cwd=self.rev))

    def test_pr_checkout_copies_an_untracked_env(self):
        (self.main / ".env").write_text("KEY=secret\n")
        self.open_pr()
        tip = git("rev-parse", "refs/heads/feat/1", cwd=self.main)
        self.assertEqual(self.ok("pr", "checkout", "1", cwd=self.rev),
                         f"tf: detached at {tip[:12]} (feat/1)\n"
                         "tf: copied .env from the main worktree (rm -f .env when done)\n")
        self.assertEqual((self.rev / ".env").read_text(), "KEY=secret\n")

    def test_pr_checkout_refuses_a_missing_main_env_when_the_branch_has_an_example(self):
        # the branch tracks .env.example; main has no .env
        (self.impl / ".env.example").write_text("KEY=\n")
        git("add", "-A", cwd=self.impl)
        git("commit", "-q", "-m", "example", cwd=self.impl)
        self.open_pr()
        error = self.refused(2, "pr", "checkout", "1", cwd=self.rev)
        self.assertIn(".env.example exists but", error)
        self.assertIn("has no .env; stop and report", error)

    # -- claim / release ---------------------------------------------------------

    def test_claim_is_once_and_release_is_idempotent(self):
        self.open_pr()
        self.ok("pr", "checkout", "1", cwd=self.rev)
        self.assertEqual(self.ok("pr", "claim", "1", cwd=self.rev),
                         "#1: claimed\n")
        self.assertIn("#1 is already claimed by another reviewer",
                      self.refused(3, "pr", "claim", "1", cwd=self.rev))
        self.assertEqual(self.ok("pr", "release", "1", cwd=self.rev),
                         "#1: released\n")
        self.assertEqual(self.ok("pr", "release", "1", cwd=self.rev),
                         "#1: released\n")

    def test_view_shows_the_claim(self):
        self.open_pr()
        self.ok("pr", "checkout", "1", cwd=self.rev)
        self.ok("pr", "claim", "1", cwd=self.rev)
        self.assertIn("claimed: yes", self.ok("pr", "view", "1"))

    # -- pr gate -----------------------------------------------------------------

    def test_pr_gate_refuses_a_worktree_not_at_the_head(self):
        self.open_pr()
        self.assertIn(
            "this worktree is not at #1's head; run tf pr checkout 1 first",
            self.refused(3, "pr", "gate", "1", cwd=self.rev))

    def test_pr_gate_refuses_a_missing_gate_script(self):
        os.remove(self.rev / "scripts" / "gate.sh")
        self.open_pr()
        self.ok("pr", "checkout", "1", cwd=self.rev)
        self.assertEqual(
            self.refused(2, "pr", "gate", "1", cwd=self.rev).strip(),
            "tf: scripts/gate.sh is missing or not executable")

    def test_pr_gate_maps_any_failure_to_exit_1(self):
        self.open_pr()
        self.ok("pr", "checkout", "1", cwd=self.rev)
        for exit_code in ("1", "2", "127"):
            result = self.tf("pr", "gate", "1", cwd=self.rev,
                             env={"GATE_EXIT": exit_code})
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_pr_gate_success_is_silent(self):
        self.open_pr()
        self.ok("pr", "checkout", "1", cwd=self.rev)
        self.assertEqual(self.ok("pr", "gate", "1", cwd=self.rev), "")

    # -- pr diff -----------------------------------------------------------------

    def test_pr_diff_prints_the_three_dot_diff(self):
        self.open_pr()
        out = self.ok("pr", "diff", "1", "app.txt", cwd=self.rev)
        self.assertIn("-v1", out)
        self.assertIn("+v2", out)

    def test_pr_diff_of_unchanged_path_is_empty(self):
        self.open_pr()
        out = self.ok("pr", "diff", "1", ".github/pull_request_template.md")
        self.assertEqual(out.strip(), "")

    def test_pr_diff_is_empty_when_the_branch_is_missing(self):
        self.open_pr()
        git("branch", "-q", "-m", "feat/1", "feat/1-old", cwd=self.impl)
        self.assertEqual(self.ok("pr", "diff", "1").strip(), "")

    # -- pr review -----------------------------------------------------------------

    def test_pr_review_refuses_a_stale_sha(self):
        self.open_pr()
        self.ok("pr", "checkout", "1", cwd=self.rev)
        error = self.refused(3, "pr", "review", "1", "--verdict", "APPROVE",
                             "--sha", "0" * 40, "--body", "looks good",
                             cwd=self.rev)
        # the message cites the sha that was passed, not the current tip
        self.assertIn("#1's head moved since 000000000000; review the new head",
                      error)

    def test_pr_review_records_the_verdict(self):
        self.open_pr()
        self.ok("pr", "checkout", "1", cwd=self.rev)
        tip = git("rev-parse", "refs/heads/feat/1", cwd=self.main)
        self.assertEqual(self.ok("pr", "review", "1", "--verdict", "APPROVE",
                                 "--sha", tip, "--body", "lgtm", cwd=self.rev),
                         f"#1: APPROVE recorded at {tip[:12]}\n")
        view = self.ok("pr", "view", "1")
        self.assertIn(f"--- review", view)
        self.assertIn("APPROVE at", view)
        self.assertIn("lgtm", view)

    # -- pr merge -------------------------------------------------------------------

    def approved_pr(self, rounds=1):
        """Open a PR on feat/1, check it out in rev, approve it `rounds`
        times at the current head. Returns the PR number as a string."""
        out = self.open_pr()
        n = out.split()[0][1:]
        self.ok("pr", "checkout", n, cwd=self.rev)
        tip = git("rev-parse", "refs/heads/feat/1", cwd=self.main)
        for _ in range(rounds):
            self.ok("pr", "review", n, "--verdict", "APPROVE", "--sha", tip,
                    "--body", "lgtm", cwd=self.rev)
        return n

    def test_pr_merge_refuses_a_merged_pr(self):
        n = self.approved_pr()
        self.ok("pr", "merge", n)
        # the merge ran in the main worktree and left it detached; tf's
        # config check needs the main worktree back on main
        git("checkout", "-q", "main", cwd=self.main)
        self.assertIn(f"#{n} is merged", self.refused(3, "pr", "merge", n))

    def test_pr_merge_refuses_a_stacked_pr_until_its_dependency_merges(self):
        # feat/2 on feat/1
        git("worktree", "add", "-q", "-b", "feat/2", str(self.main.parent / "impl2"),
            "feat/1", cwd=self.main)
        impl2 = self.main.parent / "impl2"
        (impl2 / "top.txt").write_text("top\n")
        git("add", "-A", cwd=impl2)
        git("commit", "-q", "-m", "feat 2", cwd=impl2)
        self.ok("pr", "create", "--title", "feat 1", "--body", "dep.",
                cwd=self.impl)
        self.ok("pr", "create", "--title", "feat 2", "--body", "top.",
                "--base", "feat/1", cwd=impl2)
        error = self.refused(3, "pr", "merge", "2")
        self.assertIn(
            "#2 targets feat/1, not main: merge its dependency first, then retarget",
            error)

    def test_pr_merge_refuses_without_an_approval(self):
        self.open_pr()
        self.ok("pr", "checkout", "1", cwd=self.rev)
        tip = git("rev-parse", "refs/heads/feat/1", cwd=self.main)
        error = self.refused(3, "pr", "merge", "1", cwd=self.rev)
        self.assertIn(f"#1 has no APPROVE for its current head {tip[:12]}", error)

    def test_pr_merge_refuses_a_stale_approval_after_a_push(self):
        n = self.approved_pr()
        (self.impl / "app.txt").write_text("v3\n")
        git("add", "-A", cwd=self.impl)
        git("commit", "-q", "-m", "rework", cwd=self.impl)
        error = self.refused(3, "pr", "merge", n, cwd=self.rev)
        tip = git("rev-parse", "refs/heads/feat/1", cwd=self.main)
        self.assertIn(f"#1 has no APPROVE for its current head {tip[:12]}", error)

    def test_pr_merge_refuses_a_dirty_base_holder(self):
        n = self.approved_pr()
        (self.main / "app.txt").write_text("human edit\n")
        error = self.refused(3, "pr", "merge", n, cwd=self.rev)
        self.assertIn("has uncommitted changes; ask the human", error)

    def test_pr_merge_allows_an_untracked_only_base_holder(self):
        n = self.approved_pr()
        (self.main / "scratch.txt").write_text("untracked\n")
        out = self.ok("pr", "merge", n, cwd=self.rev).strip()
        self.assertEqual(
            out, f"#1: merged into main at {git('rev-parse', 'HEAD', cwd=self.main)[:12]}")

    def test_pr_merge_success_closes_the_issue_and_records_the_merge(self):
        self.ok("issue", "create", "--title", "The feature", "--body", "b")
        n = self.approved_pr()
        out = self.ok("pr", "merge", n, cwd=self.rev).strip()
        new_main = git("rev-parse", "HEAD", cwd=self.main)
        self.assertEqual(out, f"#{n}: merged into main at {new_main[:12]}")
        self.assertEqual(git("log", "-1", "--format=%s", cwd=self.main),
                         "Merge feat/1: feat 1")
        view = self.ok("pr", "view", n)
        self.assertIn("state: merged", view)
        self.assertIn("state: closed", self.ok("issue", "view", "1"))

    def test_pr_merge_trailer_counts_the_review_rounds(self):
        n = self.approved_pr(rounds=2)
        self.ok("pr", "merge", n, cwd=self.rev)
        log = git("log", "-1", "--format=%B", cwd=self.main)
        self.assertIn("Closes #1", log)
        self.assertIn("Reviewed-by: teamflow:review-lead (round 2)", log)
        subject = git("log", "-1", "--format=%s", cwd=self.main)
        self.assertEqual(subject, "Merge feat/1: feat 1")

    def test_pr_merge_merging_a_dependency_retargets_the_stacked_pr(self):
        # PR #1 feat/1 -> main (approved); PR #2 feat/2 -> feat/1
        git("worktree", "add", "-q", "-b", "feat/2", str(self.main.parent / "impl2"),
            "feat/1", cwd=self.main)
        impl2 = self.main.parent / "impl2"
        (impl2 / "top.txt").write_text("top\n")
        git("add", "-A", cwd=impl2)
        git("commit", "-q", "-m", "feat 2", cwd=impl2)
        self.ok("pr", "create", "--title", "feat 1", "--body", "dep.",
                cwd=self.impl)
        self.ok("pr", "create", "--title", "feat 2", "--body", "top.",
                "--base", "feat/1", cwd=impl2)
        self.ok("pr", "checkout", "1", cwd=self.rev)
        tip = git("rev-parse", "refs/heads/feat/1", cwd=self.main)
        self.ok("pr", "review", "1", "--verdict", "APPROVE", "--sha", tip,
                "--body", "lgtm", cwd=self.rev)
        out = self.ok("pr", "merge", "1", cwd=self.rev)
        self.assertEqual(out, "#2: retargeted to main\n#1: merged into main at "
                              f"{git('rev-parse', 'HEAD', cwd=self.main)[:12]}\n")
        self.assertIn("branch: feat/2 -> main", self.ok("pr", "view", "2"))

    def test_pr_merge_conflict_is_refused_and_the_merge_aborted(self):
        n = self.approved_pr()
        # main moved with a conflicting change to app.txt
        (self.main / "app.txt").write_text("main v2\n")
        git("add", "-A", cwd=self.main)
        git("commit", "-q", "-m", "conflict", cwd=self.main)
        error = self.refused(3, "pr", "merge", n, cwd=self.rev)
        self.assertIn(
            "#1 conflicts with main in app.txt; the implementer must rebase",
            error)
        self.assertEqual(git("rev-parse", "-q", "--verify", "MERGE_HEAD",
                             cwd=self.rev, check=False), "")
        self.assertIn("state: open", self.ok("pr", "view", n))

    # -- record store ------------------------------------------------------------------

    def test_numbers_are_shared_and_stored_in_the_common_dir(self):
        self.ok("issue", "create", "--title", "I", "--body", "b")
        self.open_pr()
        common = git("rev-parse", "--path-format=absolute", "--git-common-dir",
                     cwd=self.main)
        items = os.path.join(common, "teamflow", "items")
        self.assertEqual(sorted(os.listdir(items)), ["1.json", "2.json"])
        record = json.loads(open(os.path.join(items, "2.json")).read())
        self.assertEqual(record["kind"], "pr")
        self.assertEqual(record["branch"], "feat/1")
        self.assertIn("created_at", record)
        self.assertIn("reviews", record)


if __name__ == "__main__":
    unittest.main()
