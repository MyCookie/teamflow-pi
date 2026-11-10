"""teamflow-config: the main-worktree rule, defaults, validation, lookup.

Contract: docs/teamflow/teamflow-config.md (pinned to teamflow @ 423109c).
Exit codes: 0 ok; 2 setup problem (message on stderr, prefixed
"teamflow-config: ").
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from harness import CONFIG, git, make_repo, run_config, write_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name + "/repo")

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, *args):
        return run_config(*args, cwd=self.repo)

    # -- defaults and lookup ---------------------------------------------------

    def test_defaults_printed_in_default_order(self):
        result = self.config()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "forge": "local", "remote": "origin", "base": "main",
            "tdd": "required", "teamflow_auto_approve": "low",
            "loop": {"exit_severity_threshold": "medium",
                     "max_open_issues_to_continue": 0},
        })
        # two-space indent, default key order, no file values to reorder
        self.assertEqual(
            result.stdout,
            '{\n  "forge": "local",\n  "remote": "origin",\n  "base": "main",\n'
            '  "tdd": "required",\n  "teamflow_auto_approve": "low",\n  "loop": {\n'
            '    "exit_severity_threshold": "medium",\n'
            '    "max_open_issues_to_continue": 0\n  }\n}\n')

    def test_single_key_lookup_prints_the_raw_value(self):
        self.assertEqual(self.config("forge").stdout.strip(), "local")
        self.assertEqual(self.config("loop.exit_severity_threshold").stdout.strip(),
                         "medium")
        self.assertEqual(self.config("loop.max_open_issues_to_continue").stdout.strip(),
                         "0")

    def test_dict_value_prints_compact_one_line(self):
        self.assertEqual(self.config("loop").stdout.strip(),
                         '{"exit_severity_threshold": "medium", "max_open_issues_to_continue": 0}')

    def test_file_values_override_defaults_without_reordering(self):
        write_config(self.repo, {"base": "develop", "forge": "github"})
        git("checkout", "-q", "-b", "develop", cwd=self.repo)
        result = self.config()
        self.assertEqual(result.returncode, 0, result.stderr)
        values = json.loads(result.stdout)
        self.assertEqual(values["base"], "develop")
        self.assertEqual(values["forge"], "github")
        self.assertEqual(list(values), ["forge", "remote", "base", "tdd",
                                        "teamflow_auto_approve", "loop"])
        self.assertEqual(self.config("base").stdout.strip(), "develop")

    # -- validation ------------------------------------------------------------

    def assert_setup_error(self, args, fragment, path=".pi/teamflow.json"):
        result = self.config(*args)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("teamflow-config:", result.stderr)
        self.assertIn(fragment, result.stderr)

    def test_unknown_keys_are_setup_problems(self):
        write_config(self.repo, {"nope": 1})
        self.assert_setup_error((), "unknown key 'nope'")
        write_config(self.repo, {"loop": {"nope": 1}})
        self.assert_setup_error((), "unknown key 'loop.nope'")
        self.assert_setup_error(("loop",), "unknown key 'loop.nope'")

    def test_lookup_of_an_unknown_key_is_a_setup_problem(self):
        self.assert_setup_error(("nope",), "unknown key 'nope'")
        self.assert_setup_error(("forge.x",), "unknown key 'forge.x'")
        self.assert_setup_error(("loop.extra",), "unknown key 'loop.extra'")

    def test_type_errors_name_the_key(self):
        write_config(self.repo, {"base": 7})
        self.assert_setup_error((), "'base' must be a string")
        write_config(self.repo, {"loop": {"max_open_issues_to_continue": "0"}})
        self.assert_setup_error((), "'loop.max_open_issues_to_continue' must be an integer")
        write_config(self.repo, {"loop": "fast"})
        self.assert_setup_error((), "'loop' must be an object")
        write_config(self.repo, {"forge": True})  # JSON true is not a string
        self.assert_setup_error((), "'forge' must be a string")

    def test_allowed_values_are_printed_sorted(self):
        write_config(self.repo, {"forge": "nope"})
        self.assert_setup_error((), "one of ['github', 'local']")
        write_config(self.repo, {"tdd": "off"})
        self.assert_setup_error((), "one of ['recommended', 'required']")
        write_config(self.repo, {"teamflow_auto_approve": "always"})
        self.assert_setup_error((), "one of ['low', 'none']")
        write_config(self.repo, {"loop": {"exit_severity_threshold": "critical"}})
        self.assert_setup_error((), "one of ['high', 'low', 'medium', 'none']")

    def test_bad_json_is_a_setup_problem(self):
        write_config(self.repo, "{not json")
        result = self.config()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("teamflow-config: .pi/teamflow.json is not valid JSON",
                      result.stderr)

    def test_non_object_config_is_a_setup_problem(self):
        write_config(self.repo, "[1, 2]")
        self.assert_setup_error((), ".pi/teamflow.json must be a JSON object")

    # -- the main worktree rule --------------------------------------------------

    def test_reads_from_the_main_worktree_not_the_current_one(self):
        other = self.repo.parent / "other"
        git("worktree", "add", "-q", "-b", "feat/1", str(other), cwd=self.repo)
        # main (the trusted checkout) has a valid config; the current worktree
        # has a broken one, which must be ignored
        write_config(self.repo, {"forge": "github"})
        write_config(other, "{broken")
        result = run_config("forge", cwd=other)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "github")
        # and from main itself the same value, from its own file
        self.assertEqual(run_config("forge", cwd=self.repo).stdout.strip(), "github")

    def test_main_worktree_off_the_base_branch_is_a_setup_problem(self):
        git("checkout", "-q", "-b", "feat/x", cwd=self.repo)
        result = self.config()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn(
            f"teamflow-config: the main worktree ({self.repo.resolve()}) must be on main, "
            "not feat/x: its config is trusted only there. Work on other "
            "branches in separate worktrees.",
            result.stderr)

    def test_off_base_uses_the_base_from_the_config_file_itself(self):
        # tf.md Appendix A.12: valid {"forge": "local"} on branch feat/9
        write_config(self.repo, {"forge": "local"})
        git("checkout", "-q", "-b", "feat/9", cwd=self.repo)
        result = self.config()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("must be on main, not feat/9", result.stderr)

    def test_known_hole_a_branch_that_declares_its_own_base_passes(self):
        # Documented hole (teamflow-config.md Section 2): the comparison uses
        # the base from the file this check protects, so a main worktree on
        # branch X whose own config says base X passes. Pin it so the hole
        # stays intentional.
        write_config(self.repo, {"base": "x"})
        git("checkout", "-q", "-b", "x", cwd=self.repo)
        self.assertEqual(self.config().returncode, 0, self.config().stderr)

    def test_detached_main_worktree_is_a_setup_problem(self):
        git("checkout", "-q", "--detach", cwd=self.repo)
        result = self.config()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("must be on main, not a detached HEAD", result.stderr)

    def test_bare_main_checkout_is_a_setup_problem(self):
        bare = Path(self.tmp.name + "/bare.git")
        bare.mkdir(parents=True)
        git("init", "-q", "--bare", "-b", "main", cwd=bare)
        result = run_config(cwd=bare)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn(
            f"teamflow-config: the main checkout ({bare.resolve()}) is a bare repository; "
            "teamflow needs a main worktree on the base branch to read its "
            "config from",
            result.stderr)

    def test_not_inside_git_is_a_setup_problem(self):
        notgit = self.tmp.name + "/notgit"
        os.makedirs(notgit, exist_ok=True)
        result = run_config(cwd=notgit)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(result.stderr.strip(),
                         "teamflow-config: not inside a git repository")


if __name__ == "__main__":
    unittest.main()
