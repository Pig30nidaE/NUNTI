#!/usr/bin/env python3
"""Create or verify isolated role worktrees at an explicitly confirmed base."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
ROLES = ("tts", "avatar", "server")


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True,
                        help="Remote main SHA independently confirmed before running")
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()
    base = git("rev-parse", "origin/main")
    if base != args.expected_sha:
        raise SystemExit("origin/main differs from confirmed remote SHA")
    registered = {}
    for entry in git("worktree", "list", "--porcelain").split("\n\n"):
        fields = dict(line.split(" ", 1) for line in entry.splitlines() if " " in line)
        if "worktree" in fields:
            registered[fields["worktree"]] = fields
    planned = []
    for role in ROLES:
        path = ROOT / ".worktrees" / role
        branch = "codex/" + role + "-next"
        existing = registered.get(str(path))
        if existing:
            if not path.is_dir():
                raise SystemExit("Registered worktree is missing; inspect before recovery: " + str(path))
            if existing.get("branch") != "refs/heads/" + branch:
                raise SystemExit("Unexpected worktree branch: " + str(path))
            if existing.get("HEAD") != base:
                raise SystemExit("Worktree moved from restoration base: " + str(path))
        elif path.exists() or subprocess.run(
            ["git", "-C", str(ROOT), "show-ref", "--verify", "--quiet", "refs/heads/" + branch]
        ).returncode == 0:
            raise SystemExit("Existing path or branch needs manual inspection: " + branch)
        planned.append((role, path, branch, existing))
    for role, path, branch, existing in planned:
        if not existing and args.create:
            subprocess.run(["git", "-C", str(ROOT), "worktree", "add", str(path),
                            "-b", branch, "origin/main"], check=True, stdout=sys.stderr)
    report = {"base": base, "remoteShaConfirmedByCaller": args.expected_sha, "worktrees": []}
    for role, path, branch, existing in planned:
        item = {"role": role, "path": str(path), "branch": branch, "exists": path.exists()}
        if path.exists():
            for name, command in (("head", ["rev-parse", "HEAD"]),
                                  ("gitDir", ["rev-parse", "--absolute-git-dir"]),
                                  ("index", ["rev-parse", "--git-path", "index"]),
                                  ("status", ["status", "--short"])):
                item[name] = subprocess.check_output(["git", "-C", str(path), *command], text=True).strip()
        report["worktrees"].append(item)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(item["exists"] for item in report["worktrees"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
