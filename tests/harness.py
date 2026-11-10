"""Shared git + tf helpers for the teamflow-pi unit tests.

Not a test module: unittest discovery matches test*.py only. Every test file
builds its scratch repositories under a fresh tempdir; nothing here touches
the real world. tf and teamflow-config are invoked by absolute path, so the
tests hold against any cwd.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
TF = PKG / "bin" / "tf"
CONFIG = PKG / "bin" / "teamflow-config"
TEMPLATES = PKG / "templates"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def sh(cmd, cwd=None, env=None, input=None):
    full = dict(os.environ, **GIT_ENV)
    if env:
        full.update(env)
    return subprocess.run(cmd, cwd=cwd, env=full, text=True,
                          capture_output=True, input=input)


def git(*args, cwd, check=True):
    result = sh(["git", *args], cwd=cwd)
    if check and result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def make_repo(path, base="main"):
    """A fresh repository with one empty commit on `base`."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    git("init", "-q", "-b", base, cwd=path)
    git("commit", "-q", "--allow-empty", "-m", "init", cwd=path)
    return path


def commit(path, message, files=None):
    """Commit (allowing empty); `files` maps name -> text, written and added."""
    if files:
        for name, text in files.items():
            (path / name).write_text(text)
        git("add", "-A", cwd=path)
    git("commit", "-q", "--allow-empty", "-m", message, cwd=path)
    return git("rev-parse", "HEAD", cwd=path)


def write_config(repo, value, path=None):
    """Write .pi/teamflow.json (value: dict or raw string)."""
    path = Path(path or (repo / ".pi" / "teamflow.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if not isinstance(value, str) else value)
    return path


def run_tf(*args, cwd, env=None, input=None):
    return sh([str(TF), *args], cwd=cwd, env=env, input=input)


def run_config(*args, cwd, env=None):
    return sh([str(CONFIG), *args], cwd=cwd, env=env)


def template(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")
