#!/usr/bin/env python3
"""Analyze a git repository: commit count, contributors, language breakdown, recent activity."""

import json
import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "git_analyze",
    "description": "Analyze a git repo: commits, contributors, languages, recent activity",
    "category": "ops",
    "requires_admin": False,
}

# Common file extensions to language mapping
EXT_TO_LANG = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".jsx": "JavaScript", ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".sol": "Solidity", ".rb": "Ruby", ".php": "PHP", ".c": "C", ".cpp": "C++",
    ".h": "C/C++ Header", ".cs": "C#", ".swift": "Swift", ".kt": "Kotlin",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".json": "JSON",
    ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".md": "Markdown",
    ".sh": "Shell", ".bash": "Shell", ".sql": "SQL", ".r": "R",
}


def run_git(repo_path, *args, timeout=30):
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", "-C", repo_path] + list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip(), result.returncode


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    repo_path = args.get("repo_path", "")

    if not repo_path:
        print("ERROR: repo_path is required")
        print('Usage: SCRIPT_ARGS=\'{"repo_path":"/path/to/repo"}\' python scripts/ops/git_analyze.py')
        sys.exit(1)

    if not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"ERROR: {repo_path} is not a git repository")
        sys.exit(1)

    print(f"=== Git Repository Analysis ===")
    print(f"  Path: {repo_path}")
    print()

    # --- Basic Info ---
    print("--- Repository Info ---")
    branch, _ = run_git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    print(f"  Current branch: {branch}")

    remote_url, rc = run_git(repo_path, "remote", "get-url", "origin")
    if rc == 0:
        print(f"  Origin: {remote_url}")

    first_commit_date, _ = run_git(repo_path, "log", "--reverse", "--format=%ai", "--max-count=1")
    if first_commit_date:
        print(f"  First commit: {first_commit_date}")

    latest_commit_date, _ = run_git(repo_path, "log", "--format=%ai", "--max-count=1")
    if latest_commit_date:
        print(f"  Latest commit: {latest_commit_date}")

    # --- Commit Stats ---
    print("\n--- Commit Statistics ---")
    commit_count_str, _ = run_git(repo_path, "rev-list", "--count", "HEAD")
    try:
        commit_count = int(commit_count_str)
    except ValueError:
        commit_count = 0
    print(f"  Total commits: {commit_count}")

    # Commits in last 30 days
    recent_count, _ = run_git(repo_path, "rev-list", "--count", "--since=30.days", "HEAD")
    print(f"  Last 30 days: {recent_count}")

    # Commits in last 7 days
    week_count, _ = run_git(repo_path, "rev-list", "--count", "--since=7.days", "HEAD")
    print(f"  Last 7 days: {week_count}")

    # --- Contributors ---
    print("\n--- Contributors ---")
    contributors_raw, _ = run_git(repo_path, "shortlog", "-sne", "HEAD")
    if contributors_raw:
        lines = contributors_raw.strip().split("\n")
        print(f"  Total contributors: {len(lines)}")
        for line in lines[:10]:
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                count, name = parts
                print(f"    {name.strip()}: {count.strip()} commits")
        if len(lines) > 10:
            print(f"    ... and {len(lines) - 10} more")

    # --- Language Breakdown ---
    print("\n--- Language Breakdown ---")
    lang_counter = Counter()
    lang_bytes = Counter()

    for root, dirs, files in os.walk(repo_path):
        # Skip .git and common vendor directories
        rel = os.path.relpath(root, repo_path)
        skip_dirs = {".git", "node_modules", "venv", ".venv", "__pycache__", ".tox", "dist", "build"}
        if any(part in skip_dirs for part in rel.split(os.sep)):
            continue

        for f in files:
            ext = os.path.splitext(f)[1].lower()
            lang = EXT_TO_LANG.get(ext)
            if lang:
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    lang_counter[lang] += 1
                    lang_bytes[lang] += size
                except OSError:
                    pass

    total_bytes = sum(lang_bytes.values()) or 1
    for lang, byte_count in lang_bytes.most_common(10):
        pct = (byte_count / total_bytes) * 100
        file_count = lang_counter[lang]
        print(f"  {lang:<20} {pct:5.1f}%  ({file_count} files, {byte_count / 1024:.0f} KB)")

    # --- Recent Activity ---
    print("\n--- Recent Commits (last 10) ---")
    recent_log, _ = run_git(repo_path, "log", "--oneline", "--max-count=10", "--format=%h %s (%ar)")
    if recent_log:
        for line in recent_log.split("\n"):
            print(f"  {line}")

    # --- Branch Info ---
    print("\n--- Branches ---")
    branches_raw, _ = run_git(repo_path, "branch", "-a", "--no-color")
    if branches_raw:
        local = []
        remote = []
        for line in branches_raw.split("\n"):
            b = line.strip().lstrip("* ")
            if b.startswith("remotes/"):
                remote.append(b.replace("remotes/origin/", ""))
            else:
                local.append(b)
        print(f"  Local: {len(local)} ({', '.join(local[:5])}{'...' if len(local) > 5 else ''})")
        print(f"  Remote: {len(remote)}")

    print("\n=== Analysis Complete ===")


if __name__ == "__main__":
    main()
