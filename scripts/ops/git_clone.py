#!/usr/bin/env python3
"""Clone a git repository to a temporary directory for analysis."""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "git_clone",
    "description": "Clone a git repo to a temp directory for analysis",
    "category": "ops",
    "requires_admin": False,
}


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    repo_url = args.get("repo_url", "")

    if not repo_url:
        print("ERROR: repo_url is required")
        print('Usage: SCRIPT_ARGS=\'{"repo_url":"https://github.com/user/repo.git"}\' python scripts/ops/git_clone.py')
        sys.exit(1)

    # Create a temp directory for the clone
    clone_dir = tempfile.mkdtemp(prefix="groot_clone_")
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    target_path = os.path.join(clone_dir, repo_name)

    print(f"=== Git Clone ===")
    print(f"  Repo: {repo_url}")
    print(f"  Target: {target_path}")
    print()

    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "50", repo_url, target_path],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            print(f"ERROR: git clone failed (exit {result.returncode})")
            print(result.stderr.strip())
            sys.exit(1)

        # Show clone summary
        print("Clone successful!")
        print(f"  Path: {target_path}")

        # Count files
        file_count = 0
        for root, dirs, files in os.walk(target_path):
            # Skip .git directory
            if ".git" in root.split(os.sep):
                continue
            file_count += len(files)
        print(f"  Files: {file_count}")

        # Show disk usage
        total_size = 0
        for root, dirs, files in os.walk(target_path):
            for f in files:
                fp = os.path.join(root, f)
                if os.path.isfile(fp):
                    total_size += os.path.getsize(fp)
        size_mb = total_size / (1024 * 1024)
        print(f"  Size: {size_mb:.2f} MB")

        # Output the path for downstream scripts
        print(f"\nCLONE_PATH={target_path}")

    except subprocess.TimeoutExpired:
        print("ERROR: git clone timed out after 120 seconds")
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: git is not installed or not in PATH")
        sys.exit(1)


if __name__ == "__main__":
    main()
