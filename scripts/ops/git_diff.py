#!/usr/bin/env python3
"""Show git diff for a repository, optionally comparing branches."""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "git_diff",
    "description": "Show git diff for a repo with optional branch comparison",
    "category": "ops",
    "requires_admin": False,
}


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    repo_path = args.get("repo_path", "")
    base_branch = args.get("base_branch", "")
    compare_branch = args.get("compare_branch", "")
    stat_only = args.get("stat_only", False)

    if not repo_path:
        print("ERROR: repo_path is required")
        print('Usage: SCRIPT_ARGS=\'{"repo_path":"/path/to/repo"}\' python scripts/ops/git_diff.py')
        print('  Optional: "base_branch":"main", "compare_branch":"feature", "stat_only":true')
        sys.exit(1)

    if not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"ERROR: {repo_path} is not a git repository")
        sys.exit(1)

    print(f"=== Git Diff ===")
    print(f"  Repo: {repo_path}")

    # Build the diff command
    cmd = ["git", "-C", repo_path, "diff"]

    if base_branch and compare_branch:
        # Compare two branches
        cmd.append(f"{base_branch}...{compare_branch}")
        print(f"  Comparing: {base_branch} -> {compare_branch}")
    elif base_branch:
        # Diff against a base branch
        cmd.append(base_branch)
        print(f"  Against: {base_branch}")
    else:
        # Working directory diff (unstaged changes)
        print(f"  Mode: working directory changes")

    if stat_only:
        cmd.append("--stat")

    print()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"ERROR: git diff failed (exit {result.returncode})")
            print(result.stderr.strip())
            sys.exit(1)

        diff_output = result.stdout.strip()

        if not diff_output:
            print("No differences found.")

            # Also check for staged changes
            staged_cmd = ["git", "-C", repo_path, "diff", "--cached"]
            if stat_only:
                staged_cmd.append("--stat")
            staged_result = subprocess.run(
                staged_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if staged_result.stdout.strip():
                print("\nStaged changes:")
                print(staged_result.stdout.strip())
        else:
            print(diff_output)

        # Show summary stats
        if not stat_only:
            stat_cmd = ["git", "-C", repo_path, "diff", "--stat"]
            if base_branch and compare_branch:
                stat_cmd.insert(-1, f"{base_branch}...{compare_branch}")
            elif base_branch:
                stat_cmd.insert(-1, base_branch)

            stat_result = subprocess.run(
                stat_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if stat_result.stdout.strip():
                print("\n--- Summary ---")
                # Only print the last line (summary)
                lines = stat_result.stdout.strip().split("\n")
                if lines:
                    print(f"  {lines[-1].strip()}")

    except subprocess.TimeoutExpired:
        print("ERROR: git diff timed out after 30 seconds")
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: git is not installed or not in PATH")
        sys.exit(1)


if __name__ == "__main__":
    main()
