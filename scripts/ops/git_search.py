#!/usr/bin/env python3
"""Search across git repo files using grep."""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "git_search",
    "description": "Search across git repo files using grep",
    "category": "ops",
    "requires_admin": False,
}


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    repo_path = args.get("repo_path", "")
    search_term = args.get("search_term", "")
    file_pattern = args.get("file_pattern", "")
    case_insensitive = args.get("case_insensitive", True)
    max_results = args.get("max_results", 100)

    if not repo_path or not search_term:
        print("ERROR: repo_path and search_term are required")
        print('Usage: SCRIPT_ARGS=\'{"repo_path":"/path/to/repo","search_term":"TODO"}\' python scripts/ops/git_search.py')
        print('  Optional: "file_pattern":"*.py", "case_insensitive":true, "max_results":100')
        sys.exit(1)

    if not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"ERROR: {repo_path} is not a git repository")
        sys.exit(1)

    print(f"=== Git Search ===")
    print(f"  Repo: {repo_path}")
    print(f"  Search: '{search_term}'")
    if file_pattern:
        print(f"  Pattern: {file_pattern}")
    print()

    # Build git grep command
    cmd = ["git", "-C", repo_path, "grep", "-n", "--count"]

    if case_insensitive:
        cmd.append("-i")

    cmd.append(search_term)

    if file_pattern:
        cmd.extend(["--", file_pattern])

    try:
        # First get file-level counts
        count_result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if count_result.returncode == 1:
            print("No matches found.")
            return

        if count_result.returncode not in (0, 1):
            print(f"ERROR: git grep failed (exit {count_result.returncode})")
            print(count_result.stderr.strip())
            sys.exit(1)

        # Parse count results
        file_counts = {}
        total_matches = 0
        if count_result.stdout.strip():
            for line in count_result.stdout.strip().split("\n"):
                parts = line.rsplit(":", 1)
                if len(parts) == 2:
                    fname, count = parts
                    c = int(count)
                    file_counts[fname] = c
                    total_matches += c

        print(f"Found {total_matches} matches in {len(file_counts)} files:")
        print()

        # Show file-level summary
        for fname, count in sorted(file_counts.items(), key=lambda x: -x[1]):
            print(f"  {fname}: {count} matches")

        print()

        # Now get actual matching lines (with context)
        detail_cmd = ["git", "-C", repo_path, "grep", "-n"]
        if case_insensitive:
            detail_cmd.append("-i")
        detail_cmd.append(search_term)
        if file_pattern:
            detail_cmd.extend(["--", file_pattern])

        detail_result = subprocess.run(
            detail_cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if detail_result.stdout.strip():
            lines = detail_result.stdout.strip().split("\n")
            display_lines = lines[:max_results]
            print("--- Matching Lines ---")
            for line in display_lines:
                print(f"  {line}")

            if len(lines) > max_results:
                print(f"\n  ... {len(lines) - max_results} more results truncated (max_results={max_results})")

    except subprocess.TimeoutExpired:
        print("ERROR: search timed out after 30 seconds")
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: git is not installed or not in PATH")
        sys.exit(1)


if __name__ == "__main__":
    main()
