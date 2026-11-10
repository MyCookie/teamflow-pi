"""tf setup: dry run / apply, never overwrites, .gitignore, the config file,
github preconditions, and the deferred github label/ruleset work.

Contract: docs/teamflow/tf-setup.md (teamflow @ 423109c) plus the
teamflow-pi deltas in Section 7 (config at .pi/teamflow.json; no worktrees
.gitignore entry; github label/ruleset work deferred, tf.md Section 11).
"""

import json
import os
import shutil
import stat
import sys
import tempfile
import unittest

from harness import PKG, git, make_repo, run_tf, template, write_config

LATER = ("later: github label and ruleset setup (with auto-merge settings) is "
         "not implemented in teamflow-pi yet; until then github mode runs "
         "unenforced, with tf checking the gate and the verdict itself")


def lines(stdout):
    return [l for l in stdout.splitlines() if l]


class SetupLocal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name + "/repo")

    def tearDown(self):
        self.tmp.cleanup()

    def setup(self, *args):
        return run_tf("setup", *args, cwd=self.repo)

    def fresh_repo_with_setup_files(self):
        """A repository where gate.sh and the PR template already exist
        (as after an earlier setup apply)."""
        gate = self.repo / "scripts" / "gate.sh"
        gate.parent.mkdir()
        gate.write_text("#!/bin/sh\necho old\n")
        gate.chmod(gate.stat().st_mode | stat.S_IEXEC)
        (self.repo / ".github").mkdir()
        (self.repo / ".github" / "pull_request_template.md").write_text("old\n")

    def test_fresh_local_dry_run_changes_nothing(self):
        result = self.setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        out = lines(result.stdout)
        self.assertEqual(out, [
            "would create scripts/gate.sh from templates/gate.sh",
            "would create .github/pull_request_template.md from templates/pull_request_template.md",
            "would add .manager-state.json, .env to .gitignore",
            'would create .pi/teamflow.json with {"forge": "local"}',
            "dry run: nothing changed; run again with --apply",
        ])
        self.assertFalse((self.repo / "scripts").exists())
        self.assertFalse((self.repo / ".pi").exists())
        self.assertFalse((self.repo / ".gitignore").exists())

    def test_apply_creates_the_files(self):
        result = self.setup("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = lines(result.stdout)
        self.assertEqual(out, [
            "create scripts/gate.sh from templates/gate.sh",
            "create .github/pull_request_template.md from templates/pull_request_template.md",
            "add .manager-state.json, .env to .gitignore",
            'create .pi/teamflow.json with {"forge": "local"}',
            "next: fill in scripts/gate.sh, then commit these files and "
            "merge them to the base branch",
        ])
        # gate.sh is verbatim from templates/ and stays executable
        self.assertEqual(
            (self.repo / "scripts" / "gate.sh").read_text(encoding="utf-8"),
            template("gate.sh"))
        self.assertTrue(os.access(self.repo / "scripts" / "gate.sh", os.X_OK))
        self.assertEqual(
            (self.repo / ".github" / "pull_request_template.md")
            .read_text(encoding="utf-8"),
            template("pull_request_template.md"))
        self.assertEqual((self.repo / ".gitignore").read_text(),
                         ".manager-state.json\n.env\n")
        config = (self.repo / ".pi" / "teamflow.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(config), {"forge": "local"})
        self.assertEqual(config, '{\n  "forge": "local"\n}\n')
        self.assertFalse((self.repo / ".github" / "workflows").exists())

    def test_second_run_reports_everything_ok(self):
        self.setup("--apply")
        out = lines(self.setup().stdout)
        self.assertEqual(out, [
            "ok: scripts/gate.sh exists, left alone",
            "ok: .github/pull_request_template.md exists, left alone",
            "ok: .gitignore covers teamflow's runtime files",
            "ok: .pi/teamflow.json exists",
            "dry run: nothing changed; run again with --apply",
        ])

    def test_never_overwrites_existing_files(self):
        self.fresh_repo_with_setup_files()
        self.setup("--apply")
        self.assertEqual((self.repo / "scripts" / "gate.sh").read_text(),
                         "#!/bin/sh\necho old\n")
        self.assertEqual(
            (self.repo / ".github" / "pull_request_template.md").read_text(),
            "old\n")

    def test_gitignore_appends_only_the_missing_entries(self):
        (self.repo / ".gitignore").write_text("node_modules\n")
        (self.repo / ".manager-state.json").write_text("")
        (self.repo / ".gitignore").write_text(
            "node_modules\n.manager-state.json\n")
        self.setup("--apply")
        self.assertEqual((self.repo / ".gitignore").read_text(),
                         "node_modules\n.manager-state.json\n.env\n")

    def test_gitignore_handles_a_missing_trailing_newline(self):
        (self.repo / ".gitignore").write_text("no-newline")
        self.setup("--apply")
        self.assertEqual((self.repo / ".gitignore").read_text(),
                         "no-newline\n.manager-state.json\n.env\n")

    def test_gitignore_without_the_worktrees_entry(self):
        # teamflow-pi delta: no in-repo worktree location to ignore
        self.setup("--apply")
        self.assertNotIn("worktrees", (self.repo / ".gitignore").read_text())

    def test_existing_config_is_left_alone(self):
        write_config(self.repo, {"forge": "github"})
        out = lines(self.setup("--apply").stdout)
        self.assertIn("ok: .pi/teamflow.json exists; note: it says forge "
                      "github, not local, left alone", out)
        self.assertEqual(json.loads(
            (self.repo / ".pi" / "teamflow.json").read_text()),
            {"forge": "github"})

    def test_existing_matching_config_is_ok(self):
        write_config(self.repo, {"forge": "local"})
        out = lines(self.setup().stdout)
        self.assertIn("ok: .pi/teamflow.json exists", out)

    def test_bad_config_json_is_a_setup_problem(self):
        write_config(self.repo, "{not json")
        result = self.setup()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("tf: .pi/teamflow.json is not valid JSON", result.stderr)

    def test_non_object_config_is_a_setup_problem(self):
        write_config(self.repo, "[1]")
        result = self.setup()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("tf: .pi/teamflow.json is not a JSON object",
                      result.stderr)

    def test_setup_runs_in_the_worktree_it_starts_in(self):
        branch_wt = self.repo.parent / "setup-wt"
        git("worktree", "add", "-q", "-b", "setup", str(branch_wt), cwd=self.repo)
        result = run_tf("setup", "--apply", cwd=branch_wt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((branch_wt / ".pi" / "teamflow.json").is_file())
        self.assertFalse((self.repo / ".pi").exists())


class SetupGitHub(unittest.TestCase):
    """github mode, with a fake gh on PATH and a bare repository whose path
    is named github.com/me/repo.git so it satisfies the remote check."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name
        self.repo = make_repo(base + "/main")
        self.bare = self.repo.parent / "github.com" / "me" / "repo.git"
        self.bare.mkdir(parents=True)
        git("init", "-q", "--bare", "-b", "main", cwd=self.bare)
        git("remote", "add", "origin", str(self.bare), cwd=self.repo)
        git("push", "-q", "origin", "main", cwd=self.repo)
        self.fakebin = self.repo.parent / "fakebin"
        self.fakebin.mkdir()
        fake_gh = PKG / "tests" / "fake_gh.py"
        (self.fakebin / "gh").write_text(
            f"#!{sys.executable}\nimport runpy, sys\n"
            f"sys.argv = ['gh'] + sys.argv[1:]\n"
            f"runpy.run_path({str(fake_gh)!r}, run_name='__main__')\n")
        (self.fakebin / "gh").chmod(0o755)
        self.state = self.repo.parent / "gh-state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def setup(self, *args, env=None):
        # tf setup's --forge defaults to local (teamflow); these tests name it
        if "--forge" not in args:
            args = ("--forge", "github", *args)
        full = {"PATH": f"{self.fakebin}{os.pathsep}{os.environ['PATH']}",
                "FAKE_GH_STATE": str(self.state)}
        if env:
            full.update(env)
        return run_tf("setup", *args, cwd=self.repo, env=full)

    def test_local_mode_does_not_need_gh(self):
        # PATH with python3 and git only: no gh anywhere
        only = self.repo.parent / "plain"
        only.mkdir()
        for name in ("python3", "git"):
            os.symlink(shutil.which(name), only / name)
        write_config(self.repo, {"forge": "local"})
        result = run_tf("setup", cwd=self.repo, env={"PATH": str(only)})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_github_dry_run_defers_the_label_and_ruleset_work(self):
        result = self.setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        out = lines(result.stdout)
        self.assertIn("would create .github/workflows/gate.yml from "
                      "templates/ci.yml", out)
        self.assertIn(LATER, out)
        self.assertFalse((self.repo / ".github" / "workflows").exists())

    def test_github_apply_creates_ci_and_config_with_the_remote(self):
        result = self.setup("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.repo / ".github" / "workflows" / "gate.yml")
            .read_text(encoding="utf-8"),
            template("ci.yml"))
        self.assertEqual(json.loads(
            (self.repo / ".pi" / "teamflow.json").read_text()),
            {"forge": "github", "remote": "origin"})
        self.assertIn(LATER, lines(result.stdout))

    def test_remote_flag_selects_the_remote_checked(self):
        # origin is not GitHub; mirror is. Without --remote the setup stops;
        # with it, the preconditions pass and the config records it.
        git("remote", "set-url", "origin", "/tmp/plain.git", cwd=self.repo)
        bare2 = self.repo.parent / "github.com" / "me" / "other.git"
        bare2.mkdir(parents=True)
        git("init", "-q", "--bare", "-b", "main", cwd=bare2)
        git("remote", "add", "mirror", str(bare2), cwd=self.repo)
        bad = self.setup()
        self.assertEqual(bad.returncode, 2, bad.stdout)
        good = self.setup("--remote", "mirror", "--apply")
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(
            (self.repo / ".pi" / "teamflow.json").read_text()),
            {"forge": "github", "remote": "mirror"})

    def test_github_requires_a_github_remote(self):
        git("remote", "set-url", "origin", "/tmp/not-github.git", cwd=self.repo)
        result = self.setup()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn(
            "tf: forge is github but remote 'origin' (/tmp/not-github.git) is "
            "not a GitHub repository", result.stderr)

    def test_github_stops_when_gh_is_missing(self):
        # PATH with python3 and git but no gh
        empty = self.repo.parent / "no-gh"
        empty.mkdir()
        for name in ("python3", "git"):
            os.symlink(shutil.which(name), empty / name)
        result = run_tf("setup", "--forge", "github", cwd=self.repo,
                        env={"PATH": str(empty)})
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("tf: forge is github but gh is not installed",
                      result.stderr)

    def test_github_stops_when_gh_is_unauthenticated(self):
        (self.fakebin / "gh").write_text("#!/bin/sh\nexit 1\n")
        (self.fakebin / "gh").chmod(0o755)
        result = self.setup()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn(
            "tf: forge is github but gh is not authenticated (gh auth login)",
            result.stderr)


if __name__ == "__main__":
    unittest.main()
