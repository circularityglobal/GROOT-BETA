#!/usr/bin/env python3
"""Pull latest changes in a git repository."""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "git_pull",
    "description": "Pull latest changes in a git repo",
    "category": "ops",
    "requires_admin": False,
}


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    repo_path = args.get("repo_path", "")

    if not repo_path:
        print("ERROR: repo_path is required")
        print('Usage: SCRIPT_ARGS=\'{"repo_path":"/path/to/repo"}\' python scripts/ops/git_pull.py')
        sys.exit(1)

    if not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"ERROR: {repo_path} is not a git repository")
        sys.exit(1)

    print(f"=== Git Pull ===")
    print(f"  Repo: {repo_path}")
    print()

    # Show current branch
    try:
        branch_result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        current_branch = branch_result.stdout.strip()
        print(f"  Branch: {current_branch}")
    except Exception:
        current_branch = "unknown"

    # Get current HEAD before pull
    try:
        head_before = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        before_sha = head_before.stdout.strip()
    except Exception:
        before_sha = "unknown"

    # Perform the pull
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "pull", "--ff-only"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"ERROR: git pull failed (exit {result.returncode})")
            print(result.stderr.strip())
            # Try to provide helpful context
            if "diverged" in result.stderr.lower():
                print("\nHint: Local and remote have diverged. Manual merge may be required.")
            sys.exit(1)

        # Get HEAD after pull
        head_after = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        after_sha = head_after.stdout.strip()

        print()
        if before_sha == after_sha:
            print("Already up to date.")
        else:
            print(f"Updated: {before_sha} -> {after_sha}")
            # Show what changed
            log_result = subprocess.run(
                ["git", "-C", repo_path, "log", "--oneline", f"{before_sha}..{after_sha}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if log_result.stdout.strip():
                print("\nNew commits:")
                for line in log_result.stdout.strip().split("\n"):
                    print(f"  {line}")

        print(result.stdout.strip())

    except subprocess.TimeoutExpired:
        print("ERROR: git pull timed out after 60 seconds")
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: git is not installed or not in PATH")
        sys.exit(1)


if __name__ == "__main__":
    main()
